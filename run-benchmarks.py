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
qos = 'bsc_cs'
req_nodes = None
req_degree = None
req_policies = None
extrae = False
output_prefix = None
archived_subfolder = None

# Fixed working/output directories
job_output_dir = 'jobs/'
output_dir = 'output/'
archive_output_dir = 'archive/'

def Usage():
	print('./run-benchmarks.py <options> command')
	print('where:')
	print(' -h                      Show this help')
	print(' --no-synthetic          Do not include synthetic benchmarks')
	print(' --no-micropp            Do not include micropp benchmarks')
	print(' --quiet                 Less verbose output')
	print(' --dry-run               Show commands to run but do not run them')
	print(' --qos queue             Choose queue')
	print(' --nodes n               Number of nodes')
	print(' --degree d              Degree')
	print(' --extrae                Generate extrae trace')
	print(' --local, --global       Specify allocation policy')
	print(' --output-prefix         Prefix for filenames in output plots')
	print(' --archived              Subfolder of archive/ with results')
	print('Commands:')
	print('make                     Run make')
	print('interactive              Run interactively')
	print('submit                   Submit jobs')
	print('process                  Generate plots')
	print('archive                  Archive data')
	return 1

# Template for job script
job_script_template = """#! /bin/bash
#SBATCH --nodes=$num_nodes
#SBATCH --cpus-per-task=48
#SBATCH --time=02:00:00
#SBATCH --qos=$qos
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

def filter_command(cmd):
	global req_degree
	global req_policies
	filters = [(r'--degree ([1-9][0-9]*)', 'degree', [str(s) for s in req_degree] if not req_degree is None else None),
			   (r'--(local|global)', 'policy', req_policies)]
	for (regex, param_str, values) in filters:
		if not values is None:
			m = re.search(regex, cmd)
			if m:
				if not m.group(1) in values:
					# Does not match
					g = m.group(1)
					return False
			else:
				print('Command "%s" does not specify ', param_str)
				sys.exit(1)
	# All match
	return True
			

def run_single_command(cmd, command=None, keep_output=True):
	global verbose
	if keep_output:
		job_output_file = unique_output_name(job_output_dir, command + '_', '.txt')
		hybrid_directory = job_output_file[:-4] + '.hybrid'
		cmd = Template(cmd).substitute(hybrid_directory = hybrid_directory)
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
	if qos == 'debug' and num_nodes > 4:
		print('Cannot run >4 nodes on debug queue')
		return None
	job_name = unique_output_name(job_output_dir, 'batch%d_' % num_nodes)
	t = Template(job_script_template)
	job_script_name = job_name + '.job'
	print(job_script_name)
	args_list = []
	if not verbose:
		args_list.append('quiet')
	if not include_synthetic:
		args_list.append('--no-synthetic')
	if not include_micropp:
		args_list.append('--no-micropp')
	if dry_run:
		args_list.append('--dry-run')
	if extrae:
		args_list.append('--extrae')
	args = ' '.join(args_list)
	with open(job_script_name, 'w') as fp:
		print( t.substitute(num_nodes=num_nodes, job_name=job_name, args=args, qos=qos), file = fp)
	return job_script_name

def submit_job_script(job_script_name):
	run_single_command(f'sbatch {job_script_name}', None, False)

def get_from_command(regex, desc, command, fullname):
	m = re.search(regex, command)
	if not m:
		print('%s not defined in the command for %s', desc, fullname)
		sys.exit(1)
	return m.group(1)



def get_file_results(fullname, results):
	re_result = re.compile('# ([-a-zA-Z0-9./_]*) appranks=([1-9][0-9]*) deg=([1-9][0-9]*) (.*) time=([0-9.]*) (sec|ms)')
	re_trace = re.compile('mv TRACE.mpits (.*)')
	with open(fullname) as fp:
		keys = set()
		command = fp.readline()
		drom = get_from_command('dlb.enable_drom=(true|false)', 'dlb.enable_drom', command, fullname)
		lewi = get_from_command('dlb.enable_lewi=(true|false)', 'dlb.enable_lewi', command, fullname)
		policy = get_from_command(' --(local|global)', 'policy', command, fullname)

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
				key = f"executable: {r['executable']} appranks: {r['appranks']} degree: {r['degree']} policy: {r['policy']} lewi: {r['lewi']} drom: {r['drom']}"
				if not key in keys:
					print(fullname + ':', key)
				keys.add(key)
			m = re_trace.match(line)
			if m:
				print(' --> trace: ', m.group(1))


def get_all_results():
	output_dir = job_output_dir
	if not archived_subfolder is None:
		output_dir = os.path.join(archive_output_dir, archived_subfolder)
	filenames = os.listdir(output_dir)
	re_filename = re.compile('(interactive|batch)_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9]*-[0-9]*.*\.txt$')
	# build/synthetic_unbalanced appranks=4 deg=1 10 480 1k 0 48.6 16.0 2.5 2.0 : iter=0 time=0.54 sec
	results = []
	for filename in filenames:
		if re_filename.match(filename):
			get_file_results(os.path.join(output_dir, filename), results)
	return results
	
def averaged_results(results):
	times = {}
	for r,time in results:
		key = tuple(sorted(r.items()))
		if not key in times:
			times[key] = []
		times[key].append(time)
	avg = []
	for key,timelist in times.items():
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

def all_commands(num_nodes, hybrid_params):
	if include_synthetic:
		for cmd in unbalanced_sweep.commands(num_nodes, hybrid_params):
			yield cmd
	if include_micropp:
		for cmd in micropp.commands(num_nodes, hybrid_params):
			yield cmd

def all_num_nodes():
	num_nodes = set([])
	if include_synthetic:
		num_nodes.update(unbalanced_sweep.num_nodes())
	if include_micropp:
		num_nodes.update(micropp.num_nodes())
	return sorted(num_nodes)

def generate_plots(results):
	global output_prefix
	output_prefix_str = output_prefix if not output_prefix is None else ''
	if include_synthetic:
		unbalanced_sweep.generate_plots(results, output_prefix_str)
	if include_micropp:
		micropp.generate_plots(results, output_prefix_str)
		

def main(argv):
	global include_synthetic
	global include_micropp
	global verbose
	global dry_run
	global qos
	global req_nodes
	global req_degree
	global req_policies
	global extrae
	global output_prefix
	global archived_subfolder

	if not canImportNumpy:
		if len(argv) >= 2 and argv[1] == '--recurse':
			print('Error with recursive invocation')
			return 1
		ret = os.system('module load python/3.6.1; python ' + argv[0] + ' --recurse ' + ' '.join(argv[1:]))
		return ret

	try:
		opts, args = getopt.getopt( argv[1:],
									'hf', ['help', 'recurse', 'no-synthetic', 'no-micropp', 'quiet',
											'dry-run', 'qos=', 'nodes=', 'degree=', 'extrae',
											'local', 'global', 'output-prefix=', 'archived='])

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
		elif o == '--qos':
			qos = a
		elif o == '--nodes':
			req_nodes = [int(n) for n in a.split(',')]
		elif o == '--degree':
			req_degree = [int(n) for n in a.split(',')]
		elif o == '--extrae':
			extrae = True
		elif o == '--local':
			req_policies = ['local']
		elif o == '--global':
			req_policies = ['global']
		elif o == '--output-prefix':
			output_prefix = a
		elif o == '--archived':
			archived_subfolder = a
		else:
			assert False
	
	if len(args) < 1:
		return Usage()

	command = args[0]
	if not req_nodes is None:
		if not (command == 'submit' or dry_run) :
			print('--nodes n only valid for submit command or with --dry-run')
			return 1
	if not req_degree is None:
		if command != 'submit' and command != 'interactive' and command != 'batch':
			print('--degree d only valid for submit, interactive or batch command')
			return 1
	if not output_prefix is None:
		if command != 'process':
			print('--output-prefix only valid for process command')
			return 1
	if not archived_subfolder is None:
		if command != 'process':
			printf('--archived only valid for process command')
			return 1
	
	hybrid_params_list = []
	if extrae:
		hybrid_params_list.append('--extrae')
	hybrid_params = ' '.join(hybrid_params_list)

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

		if check_num_nodes.get_on_compute_node():
			nums_nodes = [check_num_nodes.get_num_nodes()]
		else:
			if not dry_run:
				print('run-benchmarks.py interactive must be run on a compute node')
				return 2
			if req_nodes is None:
				nums_nodes = [2,4,8]
			else:
				nums_nodes = req_nodes

		try:
			for num_nodes in nums_nodes:
				for cmd in all_commands(num_nodes, hybrid_params):
					if filter_command(cmd):
						run_single_command(cmd, command)
		except KeyboardInterrupt:
			print('Interrupted')
		return 1
	elif command == 'submit':
		os.makedirs(job_output_dir, exist_ok=True)
		num_nodes = all_num_nodes()
		fail = False
		if not req_nodes is None:
			num_nodes = [n for n in num_nodes if n in req_nodes]
			for r in req_nodes:
				if not r in num_nodes:
					print(f'No experiment with {r} nodes')
					fail = True
		if fail:
			return 1
		for n in num_nodes:
			job_script_name = create_job_script(n)
			if not job_script_name is None:
				if dry_run:
					for cmd in all_commands(n, hybrid_params):
						if filter_command(cmd):
							print(cmd)
				else:
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
