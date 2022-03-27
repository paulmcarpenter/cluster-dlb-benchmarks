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
# NOTE: --debug false does not work on Nord!
command_template = ' '.join(['runhybrid.py --hybrid-directory $$hybrid_directory $hybrid_params --debug true --vranks $vranks --$policy --degree $degree --local-period 10 --monitor 20',
					         '--config-override dlb.enable_drom=$drom,dlb.enable_lewi=$lewi',
				             'build/syntheticslow'])

# For which numbers of nodes is this benchmark valid
def num_nodes():
	return [2,4,8,16]

# Check whether the binary is missing
def make():
	# Normal make done with cmake
	if not os.path.exists('build/syntheticslow'):
		print('Binary build/syntheticslow for syntheticslow is missing')
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
		if degree == 1:
			policies = ['local']
		else:
			policies = ['local', 'global']
		for policy in policies:
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
	results = [ (r,times) for (r,times) in results if r['executable'] == 'build/syntheticslow']
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

	baseline_time = 5

	# Generate plot as function of memory
	maxyy = 1
	for appranks in apprankss:
		for policy in policies:
			lewi = 'true'
			drom = 'true'

			# Get scale
			curr2 = [ (r,times) for (r,times) in results \
						if r['appranks'] == appranks \
						   and r['lewi'] == lewi \
						   and r['drom'] == drom \
						   and int(r['iter']) == niters-1 ]
			# ymax = max([times for (r,times) in curr])
			# xmax = max([float(r['imb']) for (r,times) in curr])

			maxyy = max([max(times) for (r,times) in curr2])

			for slow_worst in [0,1]:
		
				if slow_worst == 0:
					whichslow = 'slowleast'
				else:
					whichslow = 'slowmost'

				with PdfPages('output/%ssynthetic-slow-%d-%s-%s.pdf' % (output_prefix_str,appranks,whichslow, policy)) as pdf:

					# Draw perfect balance line
					min_imb = min([float(r['imb']) for (r,times) in results if r['appranks'] == appranks])
					max_imb = max([float(r['imb']) for (r,times) in results if r['appranks'] == appranks])
					print(min_imb, max_imb, baseline_time)
					plt.figure(figsize=(4,6))
					plt.plot([min_imb, max_imb], [baseline_time, baseline_time], color='silver', label='Perfect balance') #, marker='o')

					for degree in degrees:
						if degree == 1:
							lcl_policies = ['local', 'global'] # Combine both, if happen to have been run
						else:
							lcl_policies = [policy]
						curr = [ (r,times) for (r,times) in curr2 \
								   if r['degree'] == degree \
								   and r['policy'] in lcl_policies \
								   and int(r['slow_worst']) == slow_worst]

						xx = [float(r['imb']) for (r,times) in curr] # x is imbalance
						yy = [times for (r,times) in curr]
							
						xx,yy = split_by_times(xx, yy)
						if len(xx) > 0:

							print(f'appranks {appranks} policy {policy} degree {degree}')
							print('xx =', xx)
							print('yy =', yy)
							plt.plot(xx, yy, label = f'degree {degree}', marker='o')

					plt.title(f'Appranks {appranks} policy {policy}')
					if slow_worst == 0:
						plt.xlabel('Imbalance (slow node has least work)')
						plt.xlim(max_imb, 1.0)
						plt.ylabel('Execution time (s)')
					else:
						plt.xlabel('Imbalance (slow node has most work)')
						plt.xlim(1.0, max_imb)
					plt.ylim(0,maxyy)

					# Order legend to put the perfect balance (which was plotted first, so has index 0) last
					handles, labels = plt.gca().get_legend_handles_labels()
					n = len(handles)
					order = list(range(1,n)) + [0] # List of indices according to original order
					plt.legend([handles[idx] for idx in order], [labels[idx] for idx in order], loc='best')

					pdf.savefig()



if __name__ == '__main__':
	sys.exit(main(sys.argv))
	
