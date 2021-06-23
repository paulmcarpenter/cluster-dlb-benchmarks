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
command_template = ' '.join(['runhybrid.py --hybrid-directory $$hybrid_directory $hybrid_params --debug false --vranks $vranks --local --degree $degree --monitor 20',
					         '--config-override dlb.enable_drom=$drom,dlb.enable_lewi=$lewi',
				             'build/mpi-load-balance 10 2400 10'])

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
def commands(num_nodes, hybrid_params):
	t = Template(command_template)
	vranks = num_nodes * 2 # Start with fixed *2 oversubscription

	for degree in list(range(1, num_nodes+1)):
		for drom in ['true']: # ['true','false'] if degree != 1
			for lewi in ['true']: # ['true','false'] if degree != 1
				cmd = t.substitute(vranks=vranks, degree=degree, drom=drom, lewi=lewi, hybrid_params=hybrid_params)
				yield cmd

# Get all values of a field 
def get_values(results, field):
	values = set([])
	for r, times in results:
		values.add(r[field])
		if field =='appranks' and r[field] == '':
			print(r)
	#print(f'values for {field} is {values}')
	return sorted(values)

def average(l):
	return 1.0 * sum(l) / len(l)

def generate_plots(results):
	# Keep only results for correct executable
	results = [ (r,times) for (r,times) in results if r['executable'] == 'build/mpi-load-balance']
	#print(f'results={results}')

	policies = get_values(results, 'policy')
	degrees = get_values(results, 'degree')
	apprankss = get_values(results, 'appranks')

	for appranks in apprankss:
		for policy in policies:
			for degree in degrees:
				for lewi in ['true', 'false']:
					for drom in ['true', 'false']: 
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
						title = 'micropp-appranks%d-%s-deg%d-%s.pdf' % (appranks, policy, degree, dlb_str)

						res = [ (r,times) for (r,times) in results \
									if r['appranks'] == appranks \
									   and r['degree'] == degree \
									   and r['lewi'] == lewi \
									   and r['drom'] == drom \
									   and r['policy'] == policy]
						if len(res) > 0:
							nsteps = 1+max([int(r['step']) for (r,times) in results])

							with PdfPages('output/%s' % title) as pdf:
								maxy = 0
								for rank in range(0, appranks):
									xx = []
									yy = []
									for step in range(0,nsteps):
										t = [times for r,times in res \
											if int(r['rank']) == rank and int(r['step']) == step]
										#print(f'degree={degree} rank={rank} step={step} t={t}')
										if len(t) == 1:
											xx.append(step)
											yy.append(average(t[0]) / 1000.0)
										else:
											assert len(t) == 0
									plt.plot(xx, yy, label = f'Apprank {rank}')
									maxy = max(maxy,max(yy))
								plt.title('%s degree %d: Execution time per timestep' % (policy, degree))
								plt.xlabel('Iteration number')
								plt.ylabel('Execution time (s)')
								plt.ylim(0,maxy)
								plt.legend()
								pdf.savefig()
								plt.close()


if __name__ == '__main__':
	sys.exit(main(sys.argv))
	
