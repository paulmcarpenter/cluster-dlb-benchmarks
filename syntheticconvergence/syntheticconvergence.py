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
			drom_lewis = [('true', 'true')]
		else:
			policies = ['local', 'global']
			drom_lewis = [('true','true'), ('true', 'false'), ('false', 'true')]
		for policy in policies:
			for drom,lewi in drom_lewis:
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

	imbalances = get_values(results, 'imb')
	apprankss = get_values(results, 'appranks')
	print(f'imbalances {imbalances}')
	print(f'appranks {apprankss}')

	for appranks in apprankss:
		for imbalance in imbalances:
			curr = [(r,times) for r,times in results \
						if r['appranks'] == appranks \
						and r['imb'] == imbalance ]
			lcurr = len(curr)

			print(f'appranks {appranks} imb {imbalance}: len {lcurr}')
			if float(imbalance) > 1.0 and len(curr) > 0:
				with PdfPages('output/%ssynthetic-convergence-%s-%s.pdf' % (output_prefix_str,appranks, imbalance)) as pdf:
					plt.figure(figsize=(8,6))
					for r,times in results:
						if r['appranks'] == appranks and r['imb'] == imbalance:
							vranks = int(appranks)
							if int(r['degree']) == 1:
								dlb = 'no rebalance '
								linestyle = '-'
								linewidth = 1.5
							elif r['lewi'] == 'true' and r['drom'] == 'true':
								dlb = ''
								linestyle = '-'
								linewidth = 2.0
							elif r['lewi'] == 'true' :
								dlb = 'lewi-only '
								linestyle = '--'
								linewidth = 0.7
							else:
								assert r['drom'] == 'true'
								dlb = 'drom-only '
								linestyle = '-.'
								linewidth = 1.0
							imb = r['imb']
							policy = r['policy'] if int(r['degree']) > 1 else ''
							if int(r['degree']) == 1:
								color = '#1f77b4'
							elif policy == 'local':
								color = '#ff7f0e'
							else:
								assert policy == 'global'
								color = '#2ca02c'
							label = f'vranks: {dlb}{policy}'

							print(r['fullname'], label)
							hybriddir = fullname_to_hybriddir(r['fullname'])
							xx, yy = process(hybriddir)
							#print('xx: ', xx)
							print('label', label)
							print('yy: ', yy)
							plt.plot(xx, yy, label = label, linestyle = linestyle, linewidth = linewidth, color=color)

					if int(appranks) == 2:
						plt.xlim(0,20)


					plt.xlabel('Time (secs)')
					plt.ylabel('Imbalance')
					plt.legend(loc='best')
					pdf.savefig()
					plt.close()

