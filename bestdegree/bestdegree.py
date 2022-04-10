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
	import matplotlib.colors
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
command_template = ' '.join(['runhybrid.py --hybrid-directory $$hybrid_directory $hybrid_params --debug false --vranks $vranks --$policy --degree $degree --local-period 10 --monitor 20',
					         '--config-override dlb.enable_drom=$drom,dlb.enable_lewi=$lewi',
				             'build/bestdegree'])

# For which numbers of nodes is this benchmark valid
def num_nodes():
	return list(range(2,33))

# Check whether the binary is missing
def make():
	# Normal make done with cmake
	if not os.path.exists('build/bestdegree'):
		print('Binary build/bestdegree for bestdegree is missing')
		return False
	else:
		return True
	
est_time_secs = 0

# Return the list of all commands to run
def commands(num_nodes, hybrid_params):
	global est_time_secs
	est_time_secs = 0
	if num_nodes == 1:
		# No commands if running on single node
		return
	t = Template(command_template)
	vranks = num_nodes # Start with fixed *2 oversubscription

	max_degree = min(6, num_nodes)
	for degree in range(1, max_degree+1):
		policies = ['global']
		for policy in policies:
			for drom in ['true']: # ['true','false'] if degree != 1
				for lewi in ['true']: # ['true','false'] if degree != 1
					cmd = t.substitute(vranks=vranks, degree=degree, drom=drom, lewi=lewi, policy=policy, hybrid_params=hybrid_params)
					est_time_secs += 4 * 60 * 60 # 4 hours each
					yield cmd

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

noflush_str = ['flush', 'noflush']


def generate_plots(results, output_prefix_str):

	# Keep only results for correct executable
	results = [ (r,times) for (r,times) in results if r['executable'] == 'build/bestdegree']
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

	imb_max = 4
	imb_delta = 0.1
	apprank_max = 32

	y, x = np.mgrid[slice(0.5, 32.5,1), slice(1-imb_delta/2,imb_max-imb_delta/2,imb_delta)]
	z = 0*x + np.NaN

	max_bestdeg = 0
	with PdfPages('output/%sbestdegree.pdf' % (output_prefix_str)) as pdf:
		for appranks in apprankss:
			lewi = 'true'
			drom = 'true'
			
			curr = [(r,times) for (r,times) in results \
						if r['appranks'] == appranks \
						and r['lewi'] == lewi \
						and r['drom'] == drom \
						and int(r['iter']) == niters-1]
			imbs = get_values(curr, 'imb')
			print(f'appranks {appranks} imbs {imbs}')
			for imb in imbs:
				curr2 = [(r,times) for (r,times) in curr if r['imb'] == imb]
				degrees = get_values(curr2, 'degree')
				print(f'imb: {imb} degs: {degrees}')
				bestdeg = None
				bestval = None
				for degree in degrees:
					curr3 = [(r,times) for (r,times) in curr2 if r['degree'] == degree]
					ys = [times for (r,times) in curr3]
					yval = average(ys[0])
					if bestval is None or yval < bestval:
						bestval = yval
						bestdeg = degree
				print(f'appranks {appranks} imb {imb} bestdeg {bestdeg}')
				max_bestdeg = max(max_bestdeg, bestdeg)

				colnum = int(0.5+(float(imb)-1)/imb_delta)
				z[appranks-1][colnum] = bestdeg - 0.5
				#xx.append(appranks)
				#yy.append(imb)
				#zz.append(bestdeg)

		cmap = plt.cm.get_cmap("rainbow", max_bestdeg)
		im = plt.pcolormesh(x, y, z, cmap=cmap)

		norm= matplotlib.colors.BoundaryNorm(np.arange(0,max_bestdeg+1)+0.5, max_bestdeg)
		sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
		sm.set_array([])
		plt.colorbar(sm, ticks=np.arange(1,max_bestdeg+1))

		plt.xlabel('Imbalance')
		plt.ylabel('Number of appranks')
		pdf.savefig()
		plt.close()




if __name__ == '__main__':
	sys.exit(main(sys.argv))
	
