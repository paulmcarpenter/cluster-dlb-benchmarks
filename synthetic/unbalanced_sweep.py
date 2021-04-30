#! /usr/bin/env python
import sys
import os
from string import Template
import re

try:
	import numpy as np
	from matplotlib.backends.backend_pdf import PdfPages
	import matplotlib.pyplot as plt
except ImportError:
	pass

command_template = ' '.join(['runhybrid.py --debug false --vranks $vranks --local --degree $degree --local-period 120 --monitor 200',
					         '--config-override dlb.enable_drom=$drom,dlb.enable_lewi=$lewi',
				             'build/synthetic_unbalanced 10 480 $memsize $noflush $costs'])
# runhybrid.py --debug false --vranks 4 --local --degree 2 --local-period 120 --monitor 200  ./synthetic_unbalanced 10 480 20M 0 48.6 16.0 2.5 2.0


def num_nodes():
	return [2,4]

def commands(num_nodes):
	
	t = Template(command_template)
	vranks = num_nodes * 2 # Start with fixed *2 oversubscription
	if vranks == 4:
		costs = '48.6 16.0 2.5 2.0'
	else:
		costs = '48.6 16.0 2.5 2.0 2.0 2.0 2.0 2.0'

	for noflush in [0,1]:
		for degree in [1,2]:
			for drom in ['true']: # ['true','false'] if degree != 1
				for lewi in ['true']: # ['true','false'] if degree != 1
					for memsize in ['1', '1k', '10k', '100k', '1M', '10M', '20M', '40M']:
						cmd = t.substitute(vranks=vranks, degree=degree, drom=drom, lewi=lewi, memsize=memsize, noflush=noflush, costs=costs)
						yield cmd


def from_mem(s):
	assert len(s) > 0
	suffixes = {'k': 1000, 'M' : 1000000, 'G' : 1000000000 }
	if s[-1] in suffixes:
		return int(s[:-1]) * suffixes[s[-1]]
	else:
		return int(s)

def format_mem(x):
    num = 0
    while x >= 1000 and (x % 1000) == 0:
        num += 1
        x /= 1000
    if num == 0:
        return '%d' % x
    else:
        return ('%d' % x) + 'kMGTPE'[num-1]

def get_values(results, field):
	values = set([])
	for r, times in results:
		values.add(r[field])
	return sorted(values)

def average(l):
	return 1.0 * sum(l) / len(l)

def generate_plots(results):
	print('generate_plots')

	# Keep only results for correct executable
	results = [ (r,times) for (r,times) in results if r['executable'] == 'build/synthetic_unbalanced']

	policies = get_values(results, 'policy')
	degrees = get_values(results, 'degree')
	apprankss = get_values(results, 'appranks')
	print('policies', policies)
	print('degrees', degrees)

	for r, times in results:
		print(r, times)
	
	for appranks in apprankss:
		for policy in policies:
			for degree in degrees:
				for noflush in [0,1]:
					for lewi in ['true', 'false']:
						for drom in ['true', 'false']: 
							noflush_str = 'noflush' if noflush==1 else 'flush'
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
							title = 'unbalanced-sweep-appranks%d-%s-deg%d-%s-%s.pdf' % (appranks, policy, degree, noflush_str, dlb_str)

							res = [ (r,times) for (r,times) in results \
										if r['appranks'] == appranks \
										   and r['degree'] == degree \
										   and int(r['params'][3]) == noflush \
										   and r['lewi'] == lewi \
										   and r['drom'] == drom \
										   and r['policy'] == policy]
							print(title)
							mems = sorted(set([from_mem(r['params'][2]) for r,times in res]))
							iters = sorted(set([int(r['params'][9][5:]) for r,times in res]))
							print('mems', mems)
							print('iters', iters)
							if len(mems) > 0:
															
								with PdfPages('output/%s' % title) as pdf:
									maxy = 0
									for mem in mems:
										xx = []
										yy = []
										for iter_num in iters:
											t = [times for r,times in res \
												if from_mem(r['params'][2]) == mem \
													and int(r['params'][9][5:]) == iter_num]
											print(t)
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


if __name__ == '__main__':
	sys.exit(main(sys.argv))
	
