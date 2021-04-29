#! /usr/bin/env python

import os
import sys
import time
import getopt
import re

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
		print('Interactive command not implemented')
		return 1
	elif command == 'submit':
		print('Submit command not implemented')
		return 1
	elif command == 'genplots':
		print('Genplots command not implemented')
		return 1
	else:
		print('Unrecognized command %s\n' % command)
		return Usage()

	return 0

if __name__ == '__main__':
	sys.exit(main(sys.argv))
