#! /usr/bin/env python
import sys
import os
from string import Template
import re

# Workaround for python/3.6.6_gdb doesn't support numpy
# See run-benchmarks.py
try:
	import numpy as np
	from matplotlib.backends.backend_pdf import PdfPages
	import matplotlib.pyplot as plt
except ImportError:
	pass


# Template to create the command to run the benchmark
# NOTE: --debug false does not work on Nord3!
# command_template = ' '.join(['runhybrid.py --hybrid-directory $$hybrid_directory $hybrid_params --debug false --vranks $vranks --$policy --degree $degree --local-period 10 --monitor 20',
# 					         '--config-override dlb.enable_drom=$drom,dlb.enable_lewi=$lewi',
# 				             'build/localbad'])

# For which numbers of nodes is this benchmark valid
#def num_nodes():
#	return [2,4,8,16]

# Check whether the binary is missing
def make():
	# Normal make done with cmake
	if not os.path.exists('build/localbad'):
		print('Binary build/localbad for localbad is missing')
		return False
	else:
		return True

est_time_secs = 0

# Return the list of all commands to run
def commands(num_nodes, hybrid_params):
	# Run manually to get traces
	# runhybrid.py --debug false --vranks 2 --local --degree 2 --local-period 5 --monitor 10 --config-override dlb.enable_drom=true,dlb.enable_lewi=true ./localbad
	return []

def get_est_time_secs():
	global est_time_secs
	return est_time_secs

# Get all values of a field 
def get_values(results, field):
	values = set([])
	for r, times in results:
		values.add(r[field])
	return sorted(values)

def average(l):
	return 1.0 * sum(l) / len(l)

def generate_plots(results, output_prefix_str):
	# Run manually to get traces
	return

if __name__ == '__main__':
	sys.exit(main(sys.argv))
	
