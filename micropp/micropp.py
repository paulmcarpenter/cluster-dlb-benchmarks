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
command_template = ' '.join(['runhybrid.py --debug false --vranks $vranks --local --degree $degree --monitor 20',
					         '--config-override dlb.enable_drom=$drom,dlb.enable_lewi=$lewi',
				             '../Micropp/test/mpi-load-balance 10 2400 10'])

# For which numbers of nodes is this benchmark valid
def num_nodes():
	return [2,4,8]

# Check whether the binary is missing
def make():
	if not 'MICROPP' in os.environ:
		print('Environment variable MICROPP not set')
		return False
	micropp_location = os.environ['MICROPP']
	owd = os.getcwd()
	os.chdir(f'{micropp_location}/test')
	ret = os.system('make')
	os.chdir(owd)
	if ret != 0:
		return False
	micropp_binary = f'{micropp_location}/test/mpi-load-balance'
	if not os.path.exists(micropp_binary):
		print('Binary {micropp_binary} for MicroPP is missing')
		return False
	os.system(f'cp {micropp_binary} build/mpi-load-balance')
	return True
	
# Return the list of all commands to run
def commands(num_nodes):
	t = Template(command_template)
	vranks = num_nodes * 2 # Start with fixed *2 oversubscription

	for degree in list(range(1, num_nodes+1)):
		for drom in ['true']: # ['true','false'] if degree != 1
			for lewi in ['true']: # ['true','false'] if degree != 1
				cmd = t.substitute(vranks=vranks, degree=degree, drom=drom, lewi=lewi)
				yield cmd

# Convert memory size descriptor to number of bytes
def from_mem(s):
	assert len(s) > 0
	suffixes = {'k': 1000, 'M' : 1000000, 'G' : 1000000000 }
	if s[-1] in suffixes:
		return int(s[:-1]) * suffixes[s[-1]]
	else:
		return int(s)

# Convert number of bytes to memory size descriptor
def format_mem(x):
    num = 0
    while x >= 1000 and (x % 1000) == 0:
        num += 1
        x /= 1000
    if num == 0:
        return '%d' % x
    else:
        return ('%d' % x) + 'kMGTPE'[num-1]

# Get all values of a field 
def get_values(results, field):
	values = set([])
	for r, times in results:
		values.add(r[field])
	return sorted(values)

def average(l):
	return 1.0 * sum(l) / len(l)

def generate_plots(results):

	# Keep only results for correct executable
	results = [ (r,times) for (r,times) in results if r['executable'] == 'build/synthetic_unbalanced']

	policies = get_values(results, 'policy')
	degrees = get_values(results, 'degree')
	apprankss = get_values(results, 'appranks')

	for appranks in apprankss:
		for policy in policies:
			for degree in degrees:
				for noflush in [0,1]:
					for lewi in ['true', 'false']:
						for drom in ['true', 'false']: 
							noflush_str = 'noflush' if noflush==1 else 'flush'
							if lewi == 'true':
								if drom == 'true':
									dlb_str = 'dlb'
								else:
									dlb_str = 'lewi'
							else:
								if drom == 'true':	
									dlb_str = 'drom'
								else:
									dlb_str = 'nodlb'
							title = 'unbalanced-sweep-appranks%d-%s-deg%d-%s-%s.pdf' % (appranks, policy, degree, noflush_str, dlb_str)

							res = [ (r,times) for (r,times) in results \
										if r['appranks'] == appranks \
										   and r['degree'] == degree \
										   and int(r['params'][3]) == noflush \
										   and r['lewi'] == lewi \
										   and r['drom'] == drom \
										   and r['policy'] == policy]
							mems = sorted(set([from_mem(r['params'][2]) for r,times in res]))
							iters = sorted(set([int(r['params'][9][5:]) for r,times in res]))
							if len(mems) > 0:
															
								with PdfPages('output/%s' % title) as pdf:
									maxy = 0
									for mem in mems:
										xx = []
										yy = []
										for iter_num in iters:
											t = [times for r,times in res \
												if from_mem(r['params'][2]) == mem \
													and int(r['params'][9][5:]) == iter_num]
											if len(t) == 1:
												xx.append(iter_num)
												yy.append(average(t[0]))
											else:
												assert len(t) == 0
										plt.plot(xx, yy, label = format_mem(mem))
										maxy = max(maxy,max(yy))
									plt.title('%s degree %d: Execution time per iteration' % (policy, degree))
									plt.xlabel('Iteration number')
									plt.ylabel('Execution time (s)')
									plt.ylim(0,maxy)
									plt.legend()
									pdf.savefig()
									plt.close()


if __name__ == '__main__':
	sys.exit(main(sys.argv))
	
