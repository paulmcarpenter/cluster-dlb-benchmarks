#! /usr/bin/env python
import sys
import os

# runhybrid.py --debug false --vranks 4 --local --degree 2 --local-period 120 --monitor 200  2 ./synthetic_unbalanced 10 480 20M 0 48.6 16.0 2.5 2.0

def main(argv):
	cmd_prefix = argv[1]
	cmd_suffix = argv[2]
	for mem in ['1', '1k', '10k', '100k', '1M', '10M', '20M', '40M']:
		for drom in [0,1]:
			for lewi in [0,1]:
				if drom == 1 or lewi == 1:
					os.environ['NANOS6_ENABLE_DROM'] = str(drom)
					os.environ['NANOS6_ENABLE_LEWI'] = str(lewi)
					print 'NANOS6_ENABLE_DROM =', drom, 'NANOS6_ENABLE_LEWI =', lewi
					cmd = cmd_prefix + ' ' + mem + ' ' + cmd_suffix
					print cmd
					sys.stdout.flush()
					os.system(cmd)

if __name__ == '__main__':
	sys.exit(main(sys.argv))
