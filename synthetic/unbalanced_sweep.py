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
							for s in res:
								print(' ', s)
															

#                        with PdfPages('sweep-%s-%s-%s.pdf' % (program, policy, degree)) as pdf:
#                            for mem in mems:
#                                xx = []
#                                yy = []
#                                for iter_num in range(0,max_iter):
#                                    key = (program, policy, degree, mem, iter_num)
#                                    if key in mean_results:
#                                        xx.append(iter_num)
#                                        yy.append(mean_results[key])
#                                plt.plot(xx, yy, label = format_mem(mem))
#                            plt.title('%s degree %d: Execution time per iteration' % (policy, degree))
#                            plt.xlabel('Iteration number')
#                            plt.ylabel('Execution time (s)')
#                            plt.legend()
#                            pdf.savefig()
#                            plt.close()

#	dromlewi_re = re.compile(r'NANOS6_ENABLE_DROM = ([01]) NANOS6_ENABLE_LEWI = ([01])')
#
#	cmd_re = re.compile(r"\.\.\/all.py.* --(local|global) --degree ([1-9][0-9]*) .*\.\./([^ ]*) ([0-9]*) ([0-9]*)  *([0-9]*[kMG]?)")
#
#	result_re = re.compile(r"([0-9]*\.[0-9]*) sec")
#	
#	results = {}
#	mems = set([])
#
#	drom = None
#	lewi = None
#	degrees = set([])
#   	programs = set([])
#	max_iter = 0
#	for filename in argv[1:]:
#		mem = None
#		iters = None
#		iter_num = None
#		with open(filename, 'r') as fp:
#			for line in fp.readlines():
#				m = dromlewi_re.match(line)
#				if m:
#					drom = int(m.group(1))
#					lewi = int(m.group(2))
#				m = cmd_re.match(line)
#				if m:
#					policy = m.group(1)
#					degree = int(m.group(2))
#					assert not drom is None
#					assert not lewi is None
#					program = m.group(3) + ('-drom=%d-lewi=%d' % (drom,lewi))
#					iters = int(m.group(4))
#					tasks = int(m.group(5))
#					mem = from_mem(m.group(6))
#					iter_num = 0
#				m = result_re.match(line)
#				if m:
#					assert not mem is None
#					assert not iter_num is None
#					time = float(m.group(1))
#					#print policy, degree, mem, iter_num, time
#					max_iter = max(iter_num, max_iter)
#					mems.add(mem)
#                                        programs.add(program)
#					degrees.add(degree)
#					key = (program, policy, degree, mem, iter_num)
#					if not key in results:
#						results[key] = []
#					results[key].append(time)
#					iter_num += 1
#
#        for program in sorted(programs):
#            print
#            print 'drom=', drom, 'lewi=', lewi, 'program=',program
#            print 'policy degree         memory   iteration   avg-time (s)   time (s)'
#            for policy in ['local', 'global']:
#                    for degree in sorted(degrees):
#                            for mem in sorted(mems):
#                                    for iter_num in range(0,max_iter):
#                                            key = (program, policy, degree, mem, iter_num)
#                                            
#                                            if key in results:
#                                                    mean = sum(results[key]) / len(results[key])
#                                                    print '%-6s     %2d   %12d  %10d          %5.2f  ' % (policy, degree, mem, iter_num, mean),
#
#                                                    for t in results[key]:
#                                                            print '%5.2f' % t,
#                                                    print
#
#        mean_results = dict([ (key, sum(l) / len(l)) for (key,l) in results.items()])
#
#        for program in sorted(programs):
#            for policy in ['local', 'global']:
#                for degree in sorted(degrees):
#
#                    # Any data for this combination?
#                    m = sorted(mems)
#                    haveData = False
#                    for mem in m:
#                        if haveData:
#                            break
#                        key = (program, policy, degree, mem, 0)
#                        if key in results:
#                            haveData = True
#                            break
#
#                    if haveData:


if __name__ == '__main__':
	sys.exit(main(sys.argv))
	
