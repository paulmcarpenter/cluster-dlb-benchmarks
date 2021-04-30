#! /usr/bin/env python
import sys
import os
from string import Template

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

	for noflush in [0]:#[0,1]:
		for degree in [1,2]:
			for drom in ['true']: # ['true','false'] if degree != 1
				for lewi in ['true']: # ['true','false'] if degree != 1
					for memsize in ['20M']: #['1', '1k', '10k', '100k', '1M', '10M', '20M', '40M']:
						cmd = t.substitute(vranks=vranks, degree=degree, drom=drom, lewi=lewi, memsize=memsize, noflush=noflush, costs=costs)
						yield cmd
	

def main(argv):
	for cmd in commands:
		print(cmd)
		#sys.stdout.flush()
		#os.system(cmd)

if __name__ == '__main__':
	sys.exit(main(sys.argv))
