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
command_template = ' '.join(['runhybrid.py --hybrid-directory $$hybrid_directory $hybrid_params --debug false --vranks $vranks --$policy --degree $degree --local-period 120 --monitor 200',
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

	for degree in [1,2]: #,3,4,5,6]:
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
	results = [ (r,times) for (r,times) in results if r['executable'] == 'build/synthetic_unbalanced']

	policies = get_values(results, 'policy')
	degrees = get_values(results, 'degree')
	apprankss = get_values(results, 'appranks')

	all_iters = [int(x) for x in get_values(results, 'iter')]
	if len(all_iters) == 0:
		# No synthetic results collected
		return
	niters = 1 + max(all_iters)

	# Generate time series plots
	for appranks in apprankss:
		for policy in policies:
			for degree in degrees:
				for noflush in [0,1]:
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
							title = 'unbalanced-sweep-appranks%d-%s-deg%d-%s-%s.pdf' % (appranks, policy, degree, noflush_str[noflush], dlb_str)

							res = [ (r,times) for (r,times) in results \
										if r['appranks'] == appranks \
										   and r['degree'] == degree \
										   and int(r['params'][3]) == noflush \
										   and r['lewi'] == lewi \
										   and r['drom'] == drom \
										   and r['policy'] == policy]

							# Index in the output for the time value
							idx_iter = 5 + appranks
							for r,times in res:
								assert r['params'][idx_iter-1] == ':'
								assert r['params'][idx_iter][0:5] == 'iter='
								assert len(r['params']) == idx_iter+1

							mems = sorted(set([from_mem(r['params'][2]) for r,times in res]))
							if len(mems) > 0:
								iters = sorted(set([int(r['params'][idx_iter][5:]) for r,times in res]))
															
								with PdfPages('output/%s%s' % (output_prefix_str,title)) as pdf:
									maxy = 0
									for mem in mems:
										xx = []
										yy = []
										for iter_num in iters:
											t = [times for r,times in res \
												if from_mem(r['params'][2]) == mem \
													and int(r['params'][idx_iter][5:]) == iter_num]
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

	# Generate barcharts
	mems = sorted(set([from_mem(r['params'][2]) for r,times in results]))
	for mem in mems:
		with PdfPages('output/%sunbalanced-%s-barcharts.pdf' % (output_prefix_str, format_mem(mem))) as pdf:
			lewi = 'true'
			drom = 'true'
			groups = [ (nf,a,p) for nf in [0,1] for a in [4,8] for p in ['local','global']]
			for k,degree in enumerate(degrees):
				avgs = []
				stdevs = []
				for (noflush, appranks, policy) in groups:
					curr = [ (r,times) for (r,times) in results \
								if r['appranks'] == appranks \
								   and r['degree'] == degree \
								   and int(r['params'][3]) == noflush \
								   and r['lewi'] == lewi \
								   and r['drom'] == drom \
								   and r['policy'] == policy \
								   and from_mem(r['params'][2]) == mem \
								   and int(r['iter']) >= niters * 0.67 ]
					#print(f'mem={mem} curr={curr}')
					vals = []
					for i in range(0,niters):
						curr2 = [average(times) for r,times in curr if int(r['iter']) == i]
						if len(curr2) > 0:
							vals.append(average(curr2))

					if len(vals) > 0:
						avg = average(vals)
						stdev = np.std(vals)
					else:
						avg = 0
						stdev = 0
					avgs.append(avg)
					stdevs.append(stdev)
				ind = np.arange(len(avgs))
				width = 0.2
				plt.bar(ind + k * width, avgs, width, yerr=stdev, label='degree %d' % degree)
			plt.xticks(ind + 2*width, ['%s %d %s' % (noflush_str[nf],a,p) for (nf,a,p) in groups], rotation=20, wrap=True)
			plt.legend(loc='best')
			pdf.savefig()
			plt.close()

	# Generate plot as function of memory
	mems = sorted(set([from_mem(r['params'][2]) for r,times in results]))
	for appranks in [4,8]:
		groups = [ (nf,p) for nf in [0,1] for p in ['local','global']]
		with PdfPages('output/%sunbalanced-sweep-appranks-%d.pdf' % (output_prefix_str,appranks)) as pdf:
			for (noflush, policy) in groups:
				for degree in degrees:
					lewi = 'true'
					drom = 'true'
					curr = [ (r,times) for (r,times) in results \
								if r['appranks'] == appranks \
								   and r['degree'] == degree \
								   and int(r['params'][3]) == noflush \
								   and r['lewi'] == lewi \
								   and r['drom'] == drom \
								   and r['policy'] == policy \
								   and int(r['iter']) >= niters * 0.67 ]
					#print(f'mem={mem} curr={curr}')
					xx = [] # memory
					yy = [] # time
					for mem in mems:
						vals = [] # All iterations for this amount of memory
						for i in range(0,niters):
							curr2 = [average(times) for r,times in curr if int(r['iter']) == i and from_mem(r['params'][2]) == mem]
							if len(curr2) > 0:
								vals.append(max(curr2))
						#print(f'nf={noflush} a={appranks} p={policy} deg={degree} mem={mem} vals={vals}')
						if len(vals) > 0:
							yy.append(average(vals))
							xx.append(mem)
					plt.plot(xx, yy, label = '%s appranks=%d %s deg=%d' % (noflush_str[noflush], appranks, policy, degree))

			plt.xlabel('Memory footprint')
			plt.ylabel('Execution time (s)')
			plt.ylim(0,1)
			plt.legend(loc='best')
			pdf.savefig()
			plt.close()



if __name__ == '__main__':
	sys.exit(main(sys.argv))
	
