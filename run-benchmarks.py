#! /usr/bin/env python

import os
import os.path
import sys
import time
import getopt
import re
import time
import subprocess
from synthetic import unbalanced_sweep
from micropp import micropp
import check_num_nodes
from string import Template
import copy

try:
	import numpy as np
	canImportNumpy = True
except ImportError:
	canImportNumpy = False

# Default parameters
include_synthetic = True
include_micropp = True
verbose = True
dry_run = False

# Fixed working/output directories
job_output_dir = 'jobs/'
output_dir = 'output/'
archive_output_dir = 'archive/'

# Template for job script
job_script_template = """#! /bin/bash
#SBATCH --nodes=$num_nodes
#SBATCH --cpus-per-task=48
#SBATCH --time=02:00:00
#SBATCH --qos=bsc_cs
#SBATCH --output=$job_name.out
#SBATCH --error=$job_name.err

#ulimit -s 524288 # for AddressSanitizer

./run-benchmarks.py $args batch
"""

def unique_output_name(subdir, prefix="", suffix=""):
	basename = time.strftime('%Y%m%d_%H-%M')
	counter = ''
	k = 1
	while k<100:
		fullname = os.path.join(subdir, prefix+basename+counter+suffix)
		if not os.path.exists(fullname):
			return fullname
		counter = '_%d' % k
		k = k + 1
	print('Something went wrong')
	sys.exit(1)

def run_single_command(cmd, command=None, keep_output=True):
	global verbose
	if keep_output:
		job_output_file = unique_output_name(job_output_dir, command + '_', '.txt')
		if not dry_run:
			with open(job_output_file, 'w') as fp:
				print(cmd, file=fp)
		if verbose:
			full_cmd = cmd + ' | tee -a ' + job_output_file
		else:
			full_cmd = cmd + ' >> ' + job_output_file
	else:
		full_cmd = cmd
	print(full_cmd)
	if not dry_run:
		s = subprocess.run(full_cmd, shell=True)
	
def create_job_script(num_nodes):
	job_name = unique_output_name(job_output_dir, 'batch%d_' % num_nodes)
	t = Template(job_script_template)
	job_script_name = job_name + '.job'
	print(job_script_name)
	args_list = []
	if dry_run:
		args_list.append('--dry-run')
	args = ' '.join(args_list)
	with open(job_script_name, 'w') as fp:
		print( t.substitute(num_nodes=num_nodes, job_name=job_name, args=args), file = fp)
	return job_script_name

def submit_job_script(job_script_name):
	run_single_command(f'sbatch {job_script_name}', None, False)

def get_from_command(regex, desc, command, filename):
	m = re.search(regex, command)
	if not m:
		print('%s not defined in the command for %s', desc, filename)
		sys.exit(1)
	return m.group(1)

def get_file_results(filename, results):
	re_result = re.compile('# ([-a-zA-Z0-9./_]*) appranks=([1-9][0-9]*) deg=([1-9][0-9]*) (.*) time=([0-9.]*) (sec|ms)')
	with open(os.path.join(job_output_dir, filename)) as fp:
		command = fp.readline()
		drom = get_from_command('dlb.enable_drom=(true|false)', 'dlb.enable_drom', command, filename)
		lewi = get_from_command('dlb.enable_lewi=(true|false)', 'dlb.enable_lewi', command, filename)
		policy = get_from_command(' --(local|global)', 'policy', command, filename)

		for line in fp.readlines():
			m = re_result.match(line)
			if m:
				r = {}
				r['executable'] = m.group(1)
				r['appranks'] = int(m.group(2))
				r['degree'] = int(m.group(3))
				params = tuple(m.group(4).split())
				for p in params:
					if '=' in p:
						p2 = p.split('=')
						r[p2[0]] = p2[1]
				r['params'] = params
				r['lewi'] = lewi
				r['drom'] = drom
				r['policy'] = policy
				time = float(m.group(5))
				results.append((r,time))


def get_all_results():
	filenames = os.listdir(job_output_dir)
	re_filename = re.compile('(interactive|batch)_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9]*-[0-9]*.*\.txt$')
	# build/synthetic_unbalanced appranks=4 deg=1 10 480 1k 0 48.6 16.0 2.5 2.0 : iter=0 time=0.54 sec
	results = []
	for filename in filenames:
		if re_filename.match(filename):
			get_file_results(filename, results)
	return results
	
def averaged_results(results):
	times = {}
	for r,time in results:
		key = tuple(sorted(r.items()))
		if not key in times:
			times[key] = []
		times[key].append(time)
	avg = []
	for key,timelist in sorted(times.items()):
		avg.append( (dict(key), timelist) )
	return avg

def cmake_make():
	owd = os.getcwd()
	if not os.path.exists('build/Makefile'):
		print('build/Makefile does not exist')
		return False
	os.chdir('build')
	ret = os.system('make')
	os.chdir(owd)
	return ret == 0
		
def make():
	if not os.path.exists('build'):
		print('Please create build/ directory first')
		print('  mkdir build/')
		print('  cd build/')
		print('  cmake ..')
		print('  cd ..')
		return False
	ok = True
	if include_synthetic:
		# Benchmarks using cmake
		ok = ok and cmake_make()
	if ok and include_synthetic:
		ok = ok and unbalanced_sweep.make()
	if ok and include_micropp:
		ok = ok and micropp.make()
	return ok

def all_commands(num_nodes):
	if include_synthetic:
		for cmd in unbalanced_sweep.commands(num_nodes):
			yield cmd
	if include_micropp:
		for cmd in micropp.commands(num_nodes):
			yield cmd

def all_num_nodes():
	num_nodes = set([])
	if include_synthetic:
		num_nodes.update(unbalanced_sweep.num_nodes())
	if include_micropp:
		num_nodes.update(micropp.num_nodes())
	return sorted(num_nodes)

def generate_plots(results):
	if include_synthetic:
		unbalanced_sweep.generate_plots(results)
	if include_micropp:
		micropp.generate_plots(results)
		

def Usage():
	print('./monitor.py <options> command')
	print('where:')
	print(' -h                      Show this help')
	print(' --no-synthetic          Do not include synthetic benchmarks')
	print(' --no-micropp            Do not include micropp benchmarks')
	print(' --quiet                 Less verbose output')
	print(' --dry-run               Show commands to run but do not run them')
	print('Commands:')
	print('make                     Run make')
	print('interactive              Run interactively')
	print('submit                   Submit jobs')
	print('process                  Generate plots')
	print('archive                  Archive data')
	return 1

def main(argv):
	global include_synthetic
	global include_micropp
	global verbose
	global dry_run

	if not canImportNumpy:
		if len(argv) >= 2 and argv[1] == '--recurse':
			print('Error with recursive invocation')
			return 1
		ret = os.system('module load python/3.6.1; python ' + argv[0] + ' --recurse ' + ' '.join(argv[1:]))
		return ret

	try:
		opts, args = getopt.getopt( argv[1:],
									'hf', ['help', 'recurse', 'no-synthetic', 'no-micropp', 'quiet', 'dry-run'])

	except getopt.error as msg:
		print(msg)
		print("for help use --help")
		sys.exit(2)
	for o, a in opts:
		if o in ('-h', '--help'):
			return Usage()
		elif o == '--recurse':
			# Ignore
			pass
		elif o == '--quiet':
			verbose = False
		elif o == '--no-synthetic':
			include_synthetic = False
		elif o == '--no-micropp':
			include_micropp = False
		elif o == '--dry-run':
			dry_run = True
		else:
			assert False
	
	if len(args) < 1:
		return Usage()

	command = args[0]

	cwd = os.getcwd()

	expected_curdir = 'cluster-dlb-benchmarks'
	if (os.path.basename(cwd) != expected_curdir):
		if f'/{expected_curdir}/' in cwd:
			subdir = os.path.basename(cwd)
			print(f'Run from {expected_curdir} directory, not subdirectory {subdir}')
		else:
			print(f'Run from {expected_curdir} directory')
		return 1

	if command in ['make', 'interactive', 'batch', 'submit']:
		# Run make
		if not make():
			print('Error: one or more binary missing; use make')
			return 1

	if command == 'make':
		# Already ran 'make' above
		return 0
	elif command == 'interactive' or command == 'batch':
		os.makedirs(job_output_dir, exist_ok=True)
		if not check_num_nodes.get_on_compute_node():
			print('run-benchmarks.py interactive must be run on a compute node')
			return 2
		num_nodes = check_num_nodes.get_num_nodes()
		try:
			for cmd in all_commands(num_nodes):
				run_single_command(cmd, command)
		except KeyboardInterrupt:
			print('Interrupted')
		return 1
	elif command == 'submit':
		os.makedirs(job_output_dir, exist_ok=True)
		num_nodes = all_num_nodes()
		for n in num_nodes:
			job_script_name = create_job_script(n)
			if not dry_run:
				submit_job_script(job_script_name)
		return 1
	elif command == 'process':
		os.makedirs(output_dir, exist_ok=True)
		results = get_all_results()
		results = averaged_results(results)
		generate_plots(results)
		return 1

	elif command == 'archive':
		os.makedirs(archive_output_dir, exist_ok=True)
		archive_folder = unique_output_name(archive_output_dir, 'jobs_')
		os.mkdir(archive_folder)
		run_single_command('mv ' + job_output_dir + '/* ' + archive_folder, command=None, keep_output=False)
	else:
		print('Unrecognized command %s\n' % command)
		return Usage()

	return 0

if __name__ == '__main__':
	sys.exit(main(sys.argv))
