#! /usr/bin/env python
import os
import sys
import getopt

varname = 'SLURM_JOB_NUM_NODES'

def Usage():
	print('check_num_nodes.py <options>')
	print('where:')
	print(' -h                      Show this help')
	print(' --expect n              Expect n nodes')
	return 1

def get_on_compute_node():
	on_compute_node = varname in os.environ
	return on_compute_node

def get_num_nodes():
	assert get_on_compute_node()
	return int(os.environ[varname])

def main(argv):
	expected_num_nodes = None
	try:
		opts, args = getopt.getopt( argv[1:],
									'h', ['help', 'expect='])

	except getopt.error as msg:
		print(msg)
		print("for help use --help")
		sys.exit(2)
	for o, a in opts:
		if o in ('-h', '--help'):
			return Usage()
		elif o == '--expect':
			expected_num_nodes = int(a)
	
	if not get_on_compute_node():
		print('Error: Not running on a compute node', file=sys.stderr)
		return 2
	
	actual_num_nodes = get_num_nodes()
	if expected_num_nodes is None:
		print('Reserved %d nodes' % actual_num_nodes)
		return 0
	elif actual_num_nodes == expected_num_nodes:
		return 0
	else:
		print('Error: Reserved %d nodes != Expected %d nodes' % (actual_num_nodes, expected_num_nodes), file=sys.stderr)
		return 2


if __name__ == '__main__':
	sys.exit(main(sys.argv))
