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


def split_by_times(xx, yy):
	out_xx = []
	out_yy = []
	n = len(xx)
	assert n == len(yy)
	for j in range(0,n):
		for y in yy[j]:
			out_xx.append(xx[j])
			out_yy.append(y)
	return out_xx, out_yy

# Template to create the command to run the benchmark
command_template = ' '.join(['runhybrid.py --hybrid-directory $$hybrid_directory $hybrid_params --debug false --vranks $vranks --$policy --degree $degree --local-period 10 --monitor 200',
					         '--config-override dlb.enable_drom=$drom,dlb.enable_lewi=$lewi',
				             'build/syntheticscatter'])

# For which numbers of nodes is this benchmark valid
def num_nodes():
	return [2,4]

# Check whether the binary is missing
def make():
	# Normal make done with cmake
	if not os.path.exists('build/syntheticscatter'):
		print('Binary build/syntheticscatter for syntheticscatter is missing')
		return False
	else:
		return True
	
# Return the list of all commands to run
def commands(num_nodes, hybrid_params):
	if num_nodes == 1:
		# No commands if running on single node
		return
	t = Template(command_template)
	vranks = num_nodes # Start with fixed *2 oversubscription

	max_degree = min(4, num_nodes)
	for degree in range(1, max_degree+1):
		for policy in ['local']: #('local', 'global'):
			for drom in ['true']: # ['true','false'] if degree != 1
				for lewi in ['true']: # ['true','false'] if degree != 1
					cmd = t.substitute(vranks=vranks, degree=degree, drom=drom, lewi=lewi, policy=policy, hybrid_params=hybrid_params)
					yield cmd

# Get all values of a field 
def get_values(results, field):
	values = set([])
	for r, times in results:
		values.add(r[field])
	return sorted(values)

def average(l):
	return 1.0 * sum(l) / len(l)

noflush_str = ['flush', 'noflush']


def generate_plots(results, output_prefix_str):

	# Keep only results for correct executable
	results = [ (r,times) for (r,times) in results if r['executable'] == 'build/syntheticscatter']
	# print(results)

	policies = get_values(results, 'policy')
	degrees = get_values(results, 'degree')
	apprankss = get_values(results, 'appranks')
	print(f'policies {policies}')
	print(f'degrees {degrees}')
	print(f'apprankss {apprankss}')

	all_iters = [int(x) for x in get_values(results, 'iter')]
	if len(all_iters) == 0:
		# No synthetic results collected
		return
	niters = 1 + max(all_iters)

	# Generate plot as function of memory
	maxyy = 1
	for appranks in apprankss:
		for policy in policies:
		
			with PdfPages('output/%ssynthetic-scatter-%d-%s.pdf' % (output_prefix_str,appranks,policy)) as pdf:

				for degree in degrees:
					lewi = 'true'
					drom = 'true'
					curr = [ (r,times) for (r,times) in results \
								if r['appranks'] == appranks \
								   and r['degree'] == degree \
								   and r['lewi'] == lewi \
								   and r['drom'] == drom \
								   and r['policy'] == policy \
								   and int(r['iter']) == niters-1]
					xx = [r['imb'] for (r,times) in curr] # x is imbalance
					yy = [times for (r,times) in curr]
					xx,yy = split_by_times(xx, yy)
					if len(xx) > 0:
						maxyy = max(maxyy, max(yy))

						print('xx =', xx)
						print('yy =', yy)
						plt.scatter(xx, yy, label = f'degree {degree}')

				plt.title(f'Appranks {appranks} policy {policy}')
				plt.xlabel('Imbalance')
				plt.ylabel('Execution time (s)')
				plt.ylim(0,maxyy)
				plt.legend(loc='best')
				pdf.savefig()
				plt.close()



if __name__ == '__main__':
	sys.exit(main(sys.argv))
	
