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
command_template = ' '.join(['runhybrid.py --hybrid-directory $$hybrid_directory $hybrid_params --debug false --vranks $vranks --$policy --degree $degree --monitor 10 --local-period 10 --config-override dlb.enable_drom=$drom,dlb.enable_lewi=$lewi',
				             'build/n_body -N 1000000 -s 10 -v'])

# For which numbers of nodes is this benchmark valid
def num_nodes():
	return [2,4,8]

# Check whether the binary is missing
def make():
	nbody_location = os.environ['NBODY']
	owd = os.getcwd()
	os.chdir(f'{nbody_location}/build')
	ret = os.system('make')
	os.chdir(owd)
	if ret != 0:
		return False
	nbody_binary = f'{nbody_location}/build/n_body'
	if not os.path.exists(nbody_binary):
		print('Binary {nbody_binary} for nbody is missing')
		return False
	os.system(f'cp {nbody_binary} build/n_body')
	return True
	
est_time_secs = 0

# Return the list of all commands to run
def commands(num_nodes, hybrid_params):
	global est_time_secs
	est_time_secs = 0
	t = Template(command_template)
	vranks = num_nodes #* 2 # Start with fixed *2 oversubscription

	for degree in [1,2]:
		if degree == 1:
			policies = ['local']
		else:
			policies = ['local', 'global']
		for policy in policies:
			for drom in ['true']: # ['true','false'] if degree != 1
				for lewi in ['true']: # ['true','false'] if degree != 1
					cmd = t.substitute(vranks=vranks, degree=degree, drom=drom, lewi=lewi, policy=policy, hybrid_params=hybrid_params)
					est_time_secs += 60 # Approx. 6 seconds per iteration
					yield cmd

def get_est_time_secs():
	global est_time_secs
	return est_time_secs


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

def generate_plots(results, output_prefix_str):
	# Keep only results for correct executable
	results = [ (r,times) for (r,times) in results if r['executable'] == 'build/n_body']
	#print(f'results={results}')

	policies = get_values(results, 'policy')
	degrees = get_values(results, 'degree')
	apprankss = get_values(results, 'appranks')

	# Generate time series plots
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
						title = 'nbody-appranks%d-%s-deg%d-%s.pdf' % (appranks, policy, degree, dlb_str)

						res = [ (r,times) for (r,times) in results \
									if r['appranks'] == appranks \
									   and r['degree'] == degree \
									   and r['lewi'] == lewi \
									   and r['drom'] == drom \
									   and r['policy'] == policy]
						if len(res) > 0:
							nsteps = 1+max([int(r['step']) for (r,times) in results])

							with PdfPages('output/%s%s' % (output_prefix_str,title)) as pdf:
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
	
	# Generate barcharts
	with PdfPages('output/%snbody-barcharts.pdf' % output_prefix_str) as pdf:
		lewi = 'true'
		drom = 'true'
		groups = [(4, 'local'), (4, 'global'), (8, 'local'), (8, 'global'), (16, 'local'), (16, 'global')]
		for k,degree in enumerate(degrees):
			avgs = []
			stdevs = []
			for (appranks, policy) in groups:
				curr = [ (r,times) for (r,times) in results \
							if r['appranks'] == appranks \
							   and r['degree'] == degree \
							   and r['lewi'] == lewi \
							   and r['drom'] == drom \
							   and r['policy'] == policy \
							   and int(r['step']) >= nsteps*0.67  ] 
				vals = []
				for step in range(0,nsteps):
					curr2 = [average(times) for r,times in curr if int(r['step']) == step]
					if len(curr2) > 0:
						vals.append(max(curr2))

				if len(vals) > 0:
					avg = average(vals)
					stdev = np.std(vals)
				else:
					avg = 0
					stdev = 0
				avgs.append(avg)
				stdevs.append(stdev)
			ind = np.arange(len(avgs))
			width = 0.1
			plt.bar(ind + k * width, avgs, width, yerr=stdev, label='degree %d' % degree)
		plt.xticks(ind + 2*width, ['%d %s' % g for g in groups])
		plt.legend(loc='best')
		pdf.savefig()
		plt.close()
	sys.exit(1)


	


if __name__ == '__main__':
	sys.exit(main(sys.argv))
	
