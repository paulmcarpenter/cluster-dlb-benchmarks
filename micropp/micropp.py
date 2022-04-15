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
command_template = ' '.join(['runhybrid.py --hybrid-directory $$hybrid_directory $hybrid_params --debug false --vranks $vranks --$policy --degree $degree --monitor 20',
					         '--config-override dlb.enable_drom=$drom,dlb.enable_lewi=$lewi',
				             'build/mpi-load-balance 10 $ngp 10'])

# For which numbers of nodes is this benchmark valid
def num_nodes():
	return [2,4,8,16,32]

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
	
est_time_secs = 0

# Return the list of all commands to run
def commands(num_nodes, hybrid_params):
	global est_time_secs
	est_time_secs = 0
	t = Template(command_template)
	vranks = num_nodes #* 2 # Start with fixed *2 oversubscription

	# Weak scaling
	ngp = num_nodes * 2400
	for appranks_per_node in (1,2):
		vranks = num_nodes * appranks_per_node
		for degree in list(range(1, min(6,num_nodes+1))):
			if degree == 1:
				policies = ['local']
			else:
				policies = ['local', 'global']
			for policy in policies:
				for drom in ['true']: # ['true','false'] if degree != 1
					for lewi in ['true']: # ['true','false'] if degree != 1
						cmd = t.substitute(vranks=vranks, degree=degree, drom=drom, lewi=lewi, policy=policy, hybrid_params=hybrid_params, ngp=ngp)
						est_time_secs += 12 * 60 # a guess!
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
	results = [ (r,times) for (r,times) in results if r['executable'] == 'build/mpi-load-balance']
	#print(f'results={results}')

	policies = get_values(results, 'policy')
	degrees = get_values(results, 'degree')
	apprankss = get_values(results, 'appranks')
	numnodess = get_values(results, 'numnodes')

	# # Generate time series plots
	# for appranks in apprankss:
	# 	for policy in policies:
	# 		for degree in degrees:
	# 			for lewi in ['true', 'false']:
	# 				for drom in ['true', 'false']: 
	# 					if lewi == 'true':
	# 						if drom == 'true':
	# 							dlb_str = 'dlb'
	# 						else:
	# 							dlb_str = 'lewi'
	# 					else:
	# 						if drom == 'true':	
	# 							dlb_str = 'drom'
	# 						else:
	# 							dlb_str = 'nodlb'
	# 					title = 'micropp-appranks%d-%s-deg%d-%s.pdf' % (appranks, policy, degree, dlb_str)

	# 					res = [ (r,times) for (r,times) in results \
	# 								if r['appranks'] == appranks \
	# 								   and r['degree'] == degree \
	# 								   and r['lewi'] == lewi \
	# 								   and r['drom'] == drom \
	# 								   and (r['policy'] == policy or int(degree) == 1) ]
	# 					if len(res) > 0:
	# 						nsteps = 1+max([int(r['step']) for (r,times) in results])

	# 						with PdfPages('output/%s%s' % (output_prefix_str,title)) as pdf:
	# 							maxy = 0
	# 							for rank in range(0, appranks):
	# 								xx = []
	# 								yy = []
	# 								for step in range(0,nsteps):
	# 									t = [times for r,times in res \
	# 										if int(r['rank']) == rank and int(r['step']) == step]
	# 									#print(f'degree={degree} rank={rank} step={step} t={t}')
	# 									if len(t) == 1:
	# 										xx.append(step)
	# 										yy.append(average(t[0]) / 1000.0)
	# 									else:
	# 										assert len(t) == 0
	# 								plt.plot(xx, yy, label = f'Apprank {rank}')
	# 								maxy = max(maxy,max(yy))
	# 							plt.title('%s degree %d: Execution time per timestep' % (policy, degree))
	# 							plt.xlabel('Iteration number')
	# 							plt.ylabel('Execution time (s)')
	# 							plt.ylim(0,maxy)
	# 							plt.legend()
	# 							pdf.savefig()
	# 							plt.close()
	


	# Generate barcharts
	for policy in ['local', 'global']:
		filename = f'output/{output_prefix_str}micropp-barcharts-{policy}.pdf'
		print(f'Generating {filename}')
		with PdfPages(filename) as pdf:
			lewi = 'true'
			drom = 'true'
			ind = None
			width = 0.1

			fig = plt.figure(figsize=(6.0*0.9,3.2*0.9))
			ax = fig.add_subplot(111)

			# All xticks: x positions
			xticksx = []
			# All xticks: labels
			xtickslabels = []

			for kd, degree in enumerate(range(1,6)):

				xx = []
				avgs = []
				stdevs = []

				for j, appranks_per_node in enumerate([1,2]):
					xcurr = 6.5 * j
					# Centre for each number of nodes
					xnodes = np.arange(len(numnodess)) + xcurr
					xx.extend(xnodes + (kd-1)*width*1.5)
					xticksx.extend(xnodes)
					xtickslabels.extend(numnodess)

					for kn, numnodes in enumerate(numnodess):
						numappranks = appranks_per_node * numnodes
						print(f'{policy} appranks: {numappranks} vranks: {numnodes} {degree}')
						curr1 = [ (r,times) for (r,times) in results \
									if r['appranks'] == numappranks \
									   and r['degree'] == degree \
									   and r['lewi'] == lewi \
									   and r['drom'] == drom \
									   and r['numnodes'] == numnodes \
									   and (r['policy'] == policy or int(degree) == 1) ]

						avg = 0
						stdev = 0
						if len(curr1) > 0:
							nsteps = 1+max([int(r['step']) for (r,times) in curr1])
							curr = [ (r,times) for (r,times) in curr1 \
										   if int(r['step']) >= nsteps*0.67  ] 
							vals = []
							for step in range(0,nsteps):
								curr2 = [average(times) for r,times in curr if int(r['step']) == step]
								if len(curr2) > 0:
									vals.append(max(curr2))

							if len(vals) > 0:
								avg = average(vals)
								stdev = np.std(vals)
						avgs.append(avg / 1000.0)  # Convert ms to seconds
						stdevs.append(stdev / 1000.0)

					if kd == 0:
						xmid = average(xnodes)
						plt.text(xmid, -6, f'MicroPP ({appranks_per_node} appranks per node)', ha ='center')

				print(f'Plot {xx} {avgs} {stdevs}')
				print(len(xx), len(avgs), len(stdevs))
				legend = f'degree {degree}'
				plt.bar(xx, avgs, width, yerr=stdevs, label=legend)

			plt.xticks(xticksx, xtickslabels)
			plt.legend(loc='upper right')
			plt.ylabel('Exec. time per timestep (secs)')
			#ax.xaxis.labelpad = 50
			pdf.savefig()
			plt.close()

	


if __name__ == '__main__':
	sys.exit(main(sys.argv))
	
