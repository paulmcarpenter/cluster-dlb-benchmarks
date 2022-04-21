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
command_template = ' '.join(['runhybrid.py --nodes $nodes --oneslow --hybrid-directory $$hybrid_directory $hybrid_params --debug false --vranks $vranks --$policy --degree $degree --monitor 30 --local-period 30 --config-override dlb.enable_drom=$drom,dlb.enable_lewi=$lewi',
				             'build/n_body -N $nbodies -s 10 -v -A'])

# For which numbers of nodes is this benchmark valid
def num_nodes():
	return [2,4,8,16,32]

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

	for appranks_per_node in [2]: #[1,2]:
		degrees = [deg for deg in (1,2,3,4,6) if deg <= num_nodes]
		if appranks_per_node > 1:
			degrees = [0] + degrees
		vranks = num_nodes * appranks_per_node #* 2 # Start with fixed *2 oversubscription

		for degreecode in degrees:
			degree = degreecode if degreecode != 0 else 1
			if degree == 1:
				policies = ['local']
			else:
				policies = ['global']
			for policy in policies:
				drom = 'true' if degreecode != 0 else 'false'
				lewi = 'true' if degreecode != 0 else 'false'
				nbodies = num_nodes * 20000
				cmd = t.substitute(nodes=num_nodes, vranks=vranks, degree=degree, drom=drom, lewi=lewi, policy=policy, hybrid_params=hybrid_params, nbodies=nbodies)
				est_time_secs += 600 # Approx. 60 seconds per iteration
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
	numnodess = get_values(results, 'numnodes')
	numnodess = [num_nodes for num_nodes in numnodess if num_nodes <= 16]

	# Generate barcharts
	for policy in ['local', 'global']:
		filename = f'output/{output_prefix_str}nbodyslownord-barcharts-{policy}.pdf'
		with PdfPages(filename) as pdf:
			ind = None
			width = 0.1
			fig = plt.figure(figsize=(4.7,2.7))
			ax = fig.add_subplot(111)

			# All xticks: x positions
			xticksx = []
			# All xticks: labels
			xtickslabels = []

			for kd, degreecode in enumerate([0,1,2,3,6]):

				xx = []
				avgs = []
				stdevs = []
				degree = degreecode if degreecode != 0 else 1
				drom = 'true' if degreecode != 0 else 'false'
				lewi = 'true' if degreecode != 0 else 'false'


				for j, appranks_per_node in enumerate([2]): #,2]):
					xcurr = 6.5 * j
					# Centre for each number of nodes
					xnodes = np.arange(len(numnodess)) + xcurr
					xx.extend(xnodes + (kd-1)*width*1.5)
					xticksx.extend(xnodes)
					xtickslabels.extend(numnodess)

					for kn, numnodes in enumerate(numnodess):
						numappranks = appranks_per_node * numnodes
						print(f'{policy} appranks: {numappranks} vranks: {numnodes} {degreecode}')
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
										   if int(r['step']) >= nsteps*0.25  ] 
							vals = []
							for step in range(0,nsteps):
								curr2 = [max(times) for r,times in curr if int(r['step']) == step]
								if len(curr2) > 0:
									vals.append(max(curr2))

							if len(vals) > 0:
								avg = average(vals)
								stdev = np.std(vals)
						avgs.append(avg / 1000.0)  # Convert ms to seconds
						stdevs.append(stdev / 1000.0)

					if kd == 0:
						xmid = average(xnodes)
						ypos = -25
						plt.text(xmid, ypos, f'n-body ({appranks_per_node} appranks per node)', ha ='center')

				print(f'Plot {xx} {avgs} {stdevs}')
				print(len(xx), len(avgs), len(stdevs))
				legend = f'degree {degree}' if degreecode > 0 else 'No DLB'
				plt.bar(xx, avgs, width, yerr=stdevs, label=legend)

			plt.xticks(xticksx, xtickslabels)
			plt.legend(loc='upper left', ncol=2)
			plt.ylabel('Exec. time per timestep (secs)')
			#ax.xaxis.labelpad = 50
			pdf.savefig()
			plt.close()

	


if __name__ == '__main__':
	sys.exit(main(sys.argv))
	


















