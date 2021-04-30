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
import check_num_nodes
from string import Template
import copy

try:
	import numpy as np
	canImportNumpy = True
except ImportError:
	canImportNumpy = False

verbose = True

job_output_dir = 'jobs/'
output_dir = 'output/'
archive_output_dir = 'archive/'

job_script_template = """#! /bin/bash
#SBATCH --nodes=$num_nodes
#SBATCH --cpus-per-task=48
#SBATCH --time=02:00:00
#SBATCH --qos=bsc_cs
#SBATCH --output=$job_name.out
#SBATCH --error=$job_name.err

#ulimit -s 524288 # for AddressSanitizer

./run-experiment.py batch
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

def run_single_command(command, cmd, keep_output=True):
	global verbose
	if keep_output:
		job_output_file = unique_output_name(job_output_dir, command + '_', '.txt')
		with open(job_output_file, 'w') as fp:
			print(cmd, file=fp)
		if verbose:
			full_cmd = cmd + ' | tee -a ' + job_output_file
		else:
			full_cmd = cmd + ' >> ' + job_output_file
	else:
		full_cmd = cmd
	print(full_cmd)
	s = subprocess.run(full_cmd, shell=True)
	
def create_job_script(num_nodes):
	job_name = unique_output_name(job_output_dir, 'batch%d_' % num_nodes)
	t = Template(job_script_template)
	job_script_name = job_name + '.job'
	print(job_script_name)
	with open(job_script_name, 'w') as fp:
		print( t.substitute(num_nodes=num_nodes, job_name=job_name), file = fp)
	return job_script_name
	
def get_from_command(regex, desc, command, filename):
	m = re.search(regex, command)
	if not m:
		print('%s not defined in the command for %s', desc, filename)
		sys.exit(1)
	return m.group(1)

def get_file_results(filename, results):
	re_result = re.compile('# ([a-zA-Z0-9/_]*) appranks=([1-9][0-9]*) deg=([1-9][0-9]*) (.*) time=([0-9.]*) sec')
	#runhybrid.py --debug false --vranks 4 --local --degree 1 --local-period 120 --monitor 200 --config-override dlb.enable_drom=true,dlb.enable_lewi=true build/synthetic_unbalanced 10 480 1 0 48.6 16.0 2.5 2.0
	with open(os.path.join(job_output_dir, filename)) as fp:
		command = fp.readline()
		drom = get_from_command('dlb.enable_drom=(true|false)', 'dlb.enable_drom', command, filename)
		lewi = get_from_command('dlb.enable_lewi=(true|false)', 'dlb.enable_drom', command, filename)

		for line in fp.readlines():
			m = re_result.match(line)
			if m:
				r = {}
				r['executable'] = m.group(1)
				r['appranks'] = int(m.group(2))
				r['deg'] = int(m.group(3))
				r['params'] = tuple(m.group(4).split())
				r['lewi'] = lewi
				r['drom'] = drom
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
		

def Usage():
	print('./monitor.py <options> command')
	print('where:')
	print(' -h                      Show this help')
	print('Commands:')
	print('make                     Show make instructions')
	print('interactive              Run interactively')
	print('submit                   Submit jobs')
	print('process                  Generate plots')
	print('archive                  Archive data')
	return 1

def main(argv):
	if not canImportNumpy:
		if len(argv) >= 2 and argv[1] == '--recurse':
			print('Error with recursive invocation')
			return 1
		ret = os.system('module load python/3.6.1; python ' + argv[0] + ' --recurse ' + ' '.join(argv[1:]))
		return ret

	try:
		opts, args = getopt.getopt( argv[1:],
									'hf', ['help', 'recurse'])

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
	
	if len(args) < 1:
		return Usage()

	command = args[0]
	if command == 'make':
		print('To make, run make')
		return 0
	elif command == 'interactive' or command == 'batch':
		if not os.path.exists(job_output_dir):
			os.mkdir(job_output_dir)
		if not check_num_nodes.get_on_compute_node():
			print('run-experiment.py interactive must be run on a compute node')
			return 2
		num_nodes = check_num_nodes.get_num_nodes()
		try:
			for cmd in unbalanced_sweep.commands(num_nodes):
				run_single_command(command, cmd)
		except KeyboardInterrupt:
			print('Interrupted')
		return 1
	elif command == 'submit':
		if not os.path.exists(job_output_dir):
			os.mkdir(job_output_dir)
		num_nodes = set([])
		for n in [unbalanced_sweep.num_nodes()]:
			num_nodes.update(n)
		for n in sorted(n):
			job_script_name = create_job_script(n)
		return 1
	elif command == 'process':
		print('Genplots command not implemented')
		results = get_all_results()
		results = averaged_results(results)
		unbalanced_sweep.generate_plots(results)
		return 1

	elif command == 'archive':
		if not os.path.exists(archive_output_dir):
			os.mkdir(archive_output_dir)
		archive_folder = unique_output_name(archive_output_dir, 'jobs_')
		os.mkdir(archive_folder)
		run_single_command('mv ' + job_output_dir + '/* ' + archive_folder, keep_output=False)
	else:
		print('Unrecognized command %s\n' % command)
		return Usage()

	return 0

if __name__ == '__main__':
	sys.exit(main(sys.argv))
