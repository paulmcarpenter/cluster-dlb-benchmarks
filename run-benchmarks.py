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

verbose = True

job_output_dir = 'jobs/'
output_dir = 'output/'
archive_output_dir = 'archive/'

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

def run_single_command(cmd, keep_output=True):
	global verbose
	if keep_output:
		job_output_file = unique_output_name(job_output_dir, 'interactive_', '.txt')
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
	

	

def Usage():
	print('./monitor.py <options> command')
	print('where:')
	print(' -h                      Show this help')
	print('Commands:')
	print('make                     Show make instructions')
	print('interactive              Run interactively')
	print('submit                   Submit jobs')
	print('genplots                 Generate plots')
	print('archive                  Archive data')
	return 1

def main(argv):

	try:
		opts, args = getopt.getopt( argv[1:],
									'hf', ['help'])

	except getopt.error as msg:
		print(msg)
		print("for help use --help")
		sys.exit(2)
	for o, a in opts:
		if o in ('-h', '--help'):
			return Usage()
	
	if len(args) < 1:
		return Usage()

	command = args[0]
	if command == 'make':
		print('To make, run make')
		return 0
	elif command == 'interactive':
		if not os.path.exists(job_output_dir):
			os.mkdir(job_output_dir)
		print('Interactive command not implemented')
		if not check_num_nodes.get_on_compute_node():
			print('run-experiment.py interactive must be run on a compute node')
			return 2
		num_nodes = check_num_nodes.get_num_nodes()
		try:
			for cmd in unbalanced_sweep.commands(num_nodes):
				run_single_command(cmd)
		except KeyboardInterrupt:
			print('Interrupted')
		return 1
	elif command == 'submit':
		print('Submit command not implemented')
		return 1
	elif command == 'genplots':
		print('Genplots command not implemented')
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
