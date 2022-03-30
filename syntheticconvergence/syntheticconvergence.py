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


def allowed_policies(degree):
	if degree == 1:
		return ['local', 'global'] # Combine both, if happen to have been run
	else:
		return [policy]


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
				             'build/syntheticconvergence $imbalance'])

# For which numbers of nodes is this benchmark valid
def num_nodes():
	return [2,4,8,16]

# Check whether the binary is missing
def make():
	# Normal make done with cmake
	if not os.path.exists('build/syntheticconvergence'):
		print('Binary build/syntheticconvergence for syntheticconvergence is missing')
		return False
	else:
		return True
	
est_time_secs = 0

def imbalances(vranks):
	if vranks == 2:
		return [1.0, 2.0]
	elif vranks == 4:
		return [1.0, 2.5, 4.0]
	else:
		return [1.0, float(vranks)]


# Return the list of all commands to run
def commands(num_nodes, hybrid_params):
	global est_time_secs
	est_time_secs = 0
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
					for imb in imbalances(vranks):
						cmd = t.substitute(vranks=vranks, degree=degree, drom=drom, lewi=lewi, policy=policy, hybrid_params=hybrid_params, imbalance=imb)
						est_time_secs += imb * 60
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

def read_map_entry(label, line):
	s = line.split()
	if len(s) < 2 or s[0] != label:
		return None
	return int(s[1])

def busy_generator(hybriddir, extrank):
	with open(f'{hybriddir}/utilization{extrank}') as f:
		busy = 0
		curr_time = 0.95
		while True:
			s = f.readline().strip().split()
			if len(s) < 4:
				return
			time = float(s[0])
			#print(f'Wait for time {time}')

			while curr_time < time:
				yield busy
				curr_time += 0.5 # Generate point every half second
			busy = float(s[3]) # busy time
			#print(f'Now busy {busy}')

		#float(s[3]) # busy time



def process(hybriddir):
	print(f'hybriddir {hybriddir}')
	mapfiles = [filename for filename in os.listdir(hybriddir) if filename.startswith('map')]
	print(mapfiles)
	
	extranks = []
	extrank_to_node = {}
	nodes = set([])

	for mapfile in mapfiles:
		with open(f'{hybriddir}/{mapfile}') as f:
			extrank = read_map_entry('externalRank', f.readline())
			apprankNum = read_map_entry('apprankNum', f.readline())
			internalRank = read_map_entry('internalRank', f.readline())
			nodeNum = read_map_entry('nodeNum', f.readline())
			indexThisnode = read_map_entry('indexThisNode', f.readline())
			cpusOnNode = read_map_entry('cpusOnNode', f.readline())
			#print(mapfile, extrank, apprankNum, internalRank, nodeNum, indexThisnode, cpusOnNode)
			extranks.append(extrank)
			extrank_to_node[extrank] = nodeNum
			nodes.add(nodeNum)
	#print(extrank_to_node)
	nodes = list(nodes)
	#print('nodes:', nodes)

	gens = [ busy_generator(hybriddir, extrank) for extrank in extranks ]

	curr_time = 0.0
	xx = []
	yy = []
	while True:
		try:
			busies = [ next(gen) for gen in gens ]
			work_on_node = dict([ (node,0) for node in nodes ])
			for extrank, busy in enumerate(busies):
				work_on_node[ extrank_to_node[extrank] ] += busy
			values = work_on_node.values()
			assert len(values) > 0
			if max(values) > 0:
				imbalance = max(values) / average(values)
				xx.append(curr_time)
				yy.append(imbalance)
				
			#print(work_on_node)
			curr_time += 0.5
		except StopIteration:
			break
	return xx,yy


def fullname_to_hybriddir(txtfilename):
	m = re.match('(.*convergence.*)\.txt', txtfilename)
	if not m:
		print(f'Bad convergence filename {txtfilename}')
		sys.exit(1)
	print(m.group(1))
	return m.group(1) + '.hybrid'


def generate_plots(results, output_prefix_str):

	## Keep only results for correct executable
	results = [ (r,times) for (r,times) in results \
					if r['executable'] == 'build/syntheticconvergence'
					and int(r['iter']) == 0]
	for r,times in results:
		vranks = r['appranks']
		if int(r['degree']) == 1:
			dlb = 'no rebalance '
		elif r['lewi'] == 'true' and r['drom'] == 'true':
			dlb = ''
		elif r['lewi'] == 'true' :
			dlb = 'lewi-only '
		else:
			assert r['drom'] == 'true'
			dlb = 'drom-only '
		policy = r['policy'] if int(r['degree']) > 1 else ''
		label = f'vranks: {vranks} {dlb}{policy}'

		print(r['fullname'], label)
		hybriddir = fullname_to_hybriddir(r['fullname'])
		xx, yy = process(hybriddir)
		print('xx: ', xx)
		print('yy: ', yy)

	#policies = get_values(results, 'policy')
	#degrees = get_values(results, 'degree')
	#apprankss = get_values(results, 'appranks')
	#print(f'policies {policies}')
	#print(f'degrees {degrees}')
	#print(f'apprankss {apprankss}')

	#all_iters = [int(x) for x in get_values(results, 'iter')]
	#if len(all_iters) == 0:
	#	# No synthetic results collected
	#	return
	#niters = 1 + max(all_iters)

	#baseline_time = 5

	## Generate plot as function of memory
	#maxyy = 1
	#for appranks in apprankss:
	#	for policy in policies:
	#	
	#		with PdfPages('output/%ssynthetic-scatter-%d-%s.pdf' % (output_prefix_str,appranks,policy)) as pdf:

	#			# Draw perfect balance line
	#			min_imb = min([float(r['imb']) for (r,times) in results if r['appranks'] == appranks])
	#			max_imb = max([float(r['imb']) for (r,times) in results if r['appranks'] == appranks])
	#			print(min_imb, max_imb, baseline_time)
	#			plt.plot([min_imb, max_imb], [baseline_time, baseline_time], color='silver', label='Perfect balance') #, marker='o')

	#			for degree in degrees:
	#				lewi = 'true'
	#				drom = 'true'
	#				if degree == 1:
	#					lcl_policies = ['local', 'global'] # Combine both, if happen to have been run
	#				else:
	#					lcl_policies = [policy]
	#				curr = [ (r,times) for (r,times) in results \
	#							if r['appranks'] == appranks \
	#							   and r['degree'] == degree \
	#							   and r['lewi'] == lewi \
	#							   and r['drom'] == drom \
	#							   and r['policy'] in lcl_policies \
	#							   and int(r['iter']) == niters-1]
	#				xx = [float(r['imb']) for (r,times) in curr] # x is imbalance
	#				yy = [times for (r,times) in curr]
	#				xx,yy = split_by_times(xx, yy)
	#				if len(xx) > 0:
	#					maxyy = max(maxyy, max(yy))

	#					print(f'appranks {appranks} policy {policy} degree {degree}')
	#					print('xx =', xx)
	#					print('yy =', yy)
	#					plt.plot(xx, yy, label = f'degree {degree}', marker='o')

	#			plt.title(f'Appranks {appranks} policy {policy}')
	#			plt.xlabel('Imbalance')
	#			plt.ylabel('Execution time (s)')
	#			plt.xlim(min_imb, max_imb)
	#			plt.ylim(0,maxyy)

	#			# Order legend to put the perfect balance (which was plotted first, so has index 0) last
	#			handles, labels = plt.gca().get_legend_handles_labels()
	#			n = len(handles)
	#			order = list(range(1,n)) + [0] # List of indices according to original order
	#			plt.legend([handles[idx] for idx in order], [labels[idx] for idx in order], loc='best')

	#			pdf.savefig()
	#			plt.close()

#	# Generate convergence plot
#	lewi = 'true'
#	drom = 'true'
#	for policy in policies:
#		print('syntheticscatter convergence for ', policy)
#		with PdfPages('output/%synthetic-scatter-convergence-%s.pdf' % (output_prefix_str, policy)) as pdf:
#
#			#            appranks    degree    imb
#			toplot = [   (2,         1,        1.0 ),
#			             (2,         1,        2.0 ),
#						 (2,         2,        1.0 ),
#						 (2,         2,        2.0 ) ]
#
##				syntheticscatter convergence for  global
##				[(2, 2, '1.000'), (2, 2, '1.042'), (2, 2, '1.083'), (2, 2, '1.125'), (2, 2, '1.167'), (2, 2, '1.208'), (2, 2, '1.250'), (2, 2, '1.292'), (2, 2, '1.333'), (2, 2, '1.375'), (2, 2, '1.417'), (2, 2, '1.458'), (2, 2, '1.500'), (2, 2, '1.542'), (2, 2, '1.583'), (2, 2, '1.625'), (2, 2, '1.667'), (2, 2, '1.708'), (2, 2, '1.750'), (2, 2, '1.792'), (2, 2, '1.833'), (2, 2, '1.875'), (2, 2, '1.917'), (2, 2, '1.958')]
##				syntheticscatter convergence for  local
##				[(2, 1, '1.000'), (2, 1, '1.042'), (2, 1, '1.083'), (2, 1, '1.125'), (2, 1, '1.167'), (2, 1, '1.208'), (2, 1, '1.250'), (2, 1, '1.292'), (2, 1, '1.333'), (2, 1, '1.375'), (2, 1, '1.417'), (2, 1, '1.458'), (2, 1, '1.500'), (2, 1, '1.542'), (2, 1, '1.583'), (2, 1, '1.625'), (2, 1, '1.667'), (2, 1, '1.708'), (2, 1, '1.750'), (2, 1, '1.792'), (2, 1, '1.833'), (2, 1, '1.875'), (2, 1, '1.917'), (2, 1, '1.958'), (2, 2, '1.000'), (2, 2, '1.042'), (2, 2, '1.083'), (2, 2, '1.125'), (2, 2, '1.167'), (2, 2, '1.208'), (2, 2, '1.250'), (2, 2, '1.292'), (2, 2, '1.333'), (2, 2, '1.375'), (2, 2, '1.417'), (2, 2, '1.458'), (2, 2, '1.500'), (2, 2, '1.542'), (2, 2, '1.583'), (2, 2, '1.625'), (2, 2, '1.667'), (2, 2, '1.708'), (2, 2, '1.750'), (2, 2, '1.792'), (2, 2, '1.833'), (2, 2, '1.875'), (2, 2, '1.917'), (2, 2, '1.958')]
##	
#			curr = [ (r,times) for (r,times) in results \
#						if r['lewi'] == lewi \
#						and r['drom'] == drom \
#						and r['policy'] in allowed_policies(r['degree']) ]
#			
#			for (appranks, degree, imb) in toplot:
#				curr2 = [ (r,times) for (r,times) in curr \
#							if int(r['appranks']) == appranks \
#							and int(r['degree']) == degree \
#							and int(r['imb']) == imb ]
#				max_iter = max([ int(r['iter']) for (r,times) in curr2])
#				xx = []
#				yy = []
#				for it in range(0,
#
#			allcharts = set([ (r['appranks'], r['degree'], r['imb']) for (r,times) in curr])
#			print(sorted(allcharts))

	
