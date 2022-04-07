#! /usr/bin/env python

import os
import os.path
import sys
import time
import getopt
import re
import time
import subprocess
import copy
from synthetic import unbalanced_sweep
from syntheticscatter import syntheticscatter
from syntheticslow import syntheticslow
from syntheticconvergence import syntheticconvergence
from micropp import micropp
from nbody import nbody
import check_num_nodes
from string import Template
import copy

try:
	import numpy as np
	canImportNumpy = True
except ImportError:
	canImportNumpy = False

# Default parameters
apps = ['synthetic', 'micropp', 'scatter', 'slow', 'nbody', 'convergence']
needs_cmake = {'synthetic' : True, 'micropp' : False, 'scatter' : True, 'slow' : True, 'nbody' : False, 'convergence' : True}
include_apps = {'synthetic' : True, 'micropp' : True, 'scatter' : True, 'slow' : True, 'nbody' : True, 'convergence' : True}
apps_desc = {'synthetic' : 'synthetic benchmarks',
			'micropp' : 'micropp benchmarks',
			'scatter' : 'synthetic scatter benchmark',
			'slow' : 'test with slow node',
			'nbody' : 'n-body benchmark',
			'convergence' : 'convergence benchmark'}

verbose = True
dry_run = False
qos = 'bsc_cs'
req_nodes = None
req_degree = None
req_policies = None
extrae = False
output_prefix = None
archived_subfolder = None

# Fixed working/output directories
job_output_dir = 'jobs/'
output_dir = 'output/'
archive_output_dir = 'archive/'

def Usage():
	print('./run-benchmarks.py <options> command')
	print('where:')
	print(' -h                      Show this help')
	for a,d in apps_desc.items():
		print(' --no-%-10s         Do not include %s' % (a,d))
	for a,d in apps_desc.items():
		print(' --%-10s            Include %s' % (a,d))
	print(' --quiet                 Less verbose output')
	print(' --dry-run               Show commands to run but do not run them')
	print(' --qos queue             Choose queue')
	print(' --nodes n               Number of nodes')
	print(' --degree d              Degree')
	print(' --extrae                Generate extrae trace')
	print(' --local, --global       Specify allocation policy')
	print(' --output-prefix         Prefix for filenames in output plots')
	print(' --archived <folder_name> Subfolder of archive/ with results')
	print('Commands:')
	print('make                     Run make')
	print('interactive              Run interactively')
	print('submit                   Submit jobs')
	print('process                  Generate plots')
	print('archive <folder_name>    Archive data')
	return 1

def print_time(desc):
	now = time.strftime('%d/%m/%Y %H:%M:%S')
	print(f'{desc} {now}')

def print_jobid():
	jobid = os.environ.get('SLURM_JOBID', '<none>')
	print(f'SLURM_JOBID: {jobid}')

# Template for job script
job_script_template = """#! /bin/bash
#SBATCH --nodes=$num_nodes
#SBATCH --cpus-per-task=48
#SBATCH --time=$hours:$mins:00
#SBATCH --qos=$qos
#SBATCH --output=$job_name.out
#SBATCH --error=$job_name.err

#ulimit -s 524288 # for AddressSanitizer

./run-benchmarks.py $args batch
"""

def unique_output_name(subdir, prefix="", suffix=""):
	basename = time.strftime('%Y%m%d_%H-%M')
	counter = ''
	k = 1
	while k<100:

		fullname = os.path.join(subdir, prefix+basename+counter+suffix)
		if not os.path.exists(fullname):
			return fullname
		counter = '_%d' % k
		k = k + 1
	print('Something went wrong')
	sys.exit(1)

def filter_command(cmd):
	global req_degree
	global req_policies
	filters = [(r'--degree ([1-9][0-9]*)', 'degree', [str(s) for s in req_degree] if not req_degree is None else None),
			   (r'--(local|global)', 'policy', req_policies)]
	for (regex, param_str, values) in filters:
		if not values is None:
			m = re.search(regex, cmd)
			if m:
				if not m.group(1) in values:
					# Does not match
					g = m.group(1)
					return False
			else:
				print('Command "%s" does not specify ', param_str)
				sys.exit(1)
	# All match
	return True
			

def run_single_command(cmd, benchmark=None, command=None, keep_output=True, num_nodes=None):
	global verbose
	if keep_output:
		if benchmark is None:
			benchmark_str=''
		else:
			benchmark_str = '_' + benchmark + '_'
		job_output_file = unique_output_name(job_output_dir, f'{command}{benchmark_str}{num_nodes}_', '.txt')
		hybrid_directory = job_output_file[:-4] + '.hybrid'
		cmd = Template(cmd).substitute(hybrid_directory = hybrid_directory)
		if not dry_run:
			with open(job_output_file, 'w') as fp:
				print(cmd, file=fp)
		if verbose:
			full_cmd = cmd + ' | tee -a ' + job_output_file
		else:
			full_cmd = cmd + ' >> ' + job_output_file
	else:
		full_cmd = cmd
	print(full_cmd)
	if not dry_run:
		s = subprocess.run(full_cmd, shell=True)
	
def create_job_script(num_nodes, hours, mins, benchmark):
	if qos == 'debug' and num_nodes > 4:
		print('Cannot run >4 nodes on debug queue')
		return None
	job_script_name = unique_output_name(job_output_dir, 'batch%d_' % num_nodes, '.job')
	t = Template(job_script_template)
	job_name = job_script_name[:-4]
	#print(job_name, job_script_name)
	args_list = []
	if not verbose:
		args_list.append('quiet')
	args_list.append('--' + benchmark)
	if dry_run:
		args_list.append('--dry-run')
	if extrae:
		args_list.append('--extrae')
	args = ' '.join(args_list)
	with open(job_script_name, 'w') as fp:
		print( t.substitute(num_nodes=num_nodes, job_name=job_name, args=args, qos=qos, hours=hours, mins=mins), file = fp)
	return job_script_name

def submit_job_script(job_script_name):
	run_single_command(f'sbatch {job_script_name}', benchmark=None, command=None, keep_output=False)

def get_from_command(regex, desc, command, fullname):
	m = re.search(regex, command)
	if not m:
		print('%s not defined in the command for %s' % (desc, fullname))
		print(f'Command is {command}')
		sys.exit(1)
	return m.group(1)



def get_file_results(fullname, results):
	re_result = re.compile('# ([-a-zA-Z0-9./_]*) appranks=([1-9][0-9]*) deg=([1-9][0-9]*) (.*) time=([0-9.]*) (sec|ms)')
	re_trace = re.compile('mv TRACE.mpits (.*)')
	re_experiment = re.compile('Experiment vranks: ([1-9][0-9]*) nodes: ([1-9][0-9]*) deg: ([1-9][0-9]*)')
	with open(fullname) as fp:
		keys = set()
		command = fp.readline()
		drom = get_from_command('dlb.enable_drom=(true|false)', 'dlb.enable_drom', command, fullname)
		lewi = get_from_command('dlb.enable_lewi=(true|false)', 'dlb.enable_lewi', command, fullname)
		policy = get_from_command(' --(local|global)', 'policy', command, fullname)
		numnodes = None

		for line in fp.readlines():
			m = re_experiment.match(line)
			if m:
				numnodes = int(m.group(1))
			m = re_result.match(line)
			if m:
				r = {}
				r['executable'] = m.group(1)
				r['appranks'] = int(m.group(2))
				r['degree'] = int(m.group(3))
				params = tuple(m.group(4).split())
				for p in params:
					if '=' in p:
						p2 = p.split('=')
						r[p2[0]] = p2[1]
				r['params'] = params
				r['lewi'] = lewi
				r['drom'] = drom
				r['policy'] = policy
				r['fullname'] = fullname
				assert(not numnodes is None)
				r['numnodes'] = numnodes
				time = float(m.group(5))
				results.append((r,time))
				key = f"executable: {r['executable']} numnodes: {r['numnodes']} appranks: {r['appranks']} degree: {r['degree']} policy: {r['policy']} lewi: {r['lewi']} drom: {r['drom']}"
				#print(key)
				if not key in keys:
					print(fullname + ':', key)
				keys.add(key)
			m = re_trace.match(line)
			if m:
				print(' --> trace: ', m.group(1))


def get_all_results():
	output_dir = job_output_dir
	if not archived_subfolder is None:
		output_dir = os.path.join(archive_output_dir, archived_subfolder)
	filenames = os.listdir(output_dir)
	re_filename = re.compile('(interactive|batch)([a-z_]*)[1-9][0-9]*_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9]*-[0-9]*.*\.txt$')
	# build/synthetic_unbalanced appranks=4 deg=1 10 480 1k 0 48.6 16.0 2.5 2.0 : iter=0 time=0.54 sec
	results = []
	for filename in filenames:
		if re_filename.match(filename):
			get_file_results(os.path.join(output_dir, filename), results)
	return results
	
def averaged_results(results):
	times = {}
	seen_excl_fullname = {}
	for r,time in results:

		# Check if already seen with perhaps different fullname (for averaging of results)
		r2 = copy.deepcopy(r)
		del r2['fullname']
		key_seen = tuple(sorted(r2.items()))
		if key_seen in seen_excl_fullname:
			r2['fullname'] = seen_excl_fullname[key_seen]
		else:
			r2['fullname'] = r['fullname']
			seen_excl_fullname[key_seen] = r['fullname']

		key = tuple(sorted(r2.items()))
		if not key in times:
			times[key] = []
		times[key].append(time)
	avg = []
	for key,timelist in times.items():
		avg.append( (dict(key), timelist) )
	return avg

def cmake_make():
	owd = os.getcwd()
	if not os.path.exists('build/Makefile'):
		print('build/Makefile does not exist')
		return False
	os.chdir('build')
	ret = os.system('make')
	os.chdir(owd)
	return ret == 0
		
def decode_time_secs(secs):
	mins = int(secs / 60)
	return mins // 60, mins % 60

def make():
	if not os.path.exists('build'):
		print('Please create build/ directory first')
		print('  mkdir build/')
		print('  cd build/')
		print('  cmake ..')
		print('  cd ..')
		return False
	ok = True
	do_cmake = False
	for a,d in include_apps.items():
		if d:
			if needs_cmake[a]:
				do_cmake = True
	if do_cmake:
		# Benchmarks using cmake
		ok = ok and cmake_make()
	if ok and include_apps['synthetic']:
		ok = ok and unbalanced_sweep.make()
	if ok and include_apps['scatter']:
		ok = ok and syntheticscatter.make()
	if ok and include_apps['slow']:
		ok = ok and syntheticslow.make()
	if ok and include_apps['convergence']:
		ok = ok and syntheticconvergence.make()
	if ok and include_apps['micropp']:
		ok = ok and micropp.make()
	if ok and include_apps['nbody']:
		ok = ok and nbody.make()
	return ok

def all_commands(num_nodes, hybrid_params, benchmark):
	if benchmark == 'synthetic':
		for cmd in unbalanced_sweep.commands(num_nodes, hybrid_params):
			yield cmd
	if benchmark == 'scatter':
		for cmd in syntheticscatter.commands(num_nodes, hybrid_params):
			yield cmd
	if benchmark == 'slow':
		for cmd in syntheticslow.commands(num_nodes, hybrid_params):
			yield cmd
	if benchmark == 'convergence':
		for cmd in syntheticconvergence.commands(num_nodes, hybrid_params):
			yield cmd
	if benchmark == 'micropp':
		for cmd in micropp.commands(num_nodes, hybrid_params):
			yield cmd
	if benchmark == 'nbody':
		for cmd in nbody.commands(num_nodes, hybrid_params):
			yield cmd

def get_est_time_secs(benchmark):
	my_est_time_secs = 60 * 60 # start with one hour slack
	if benchmark == 'synthetic':
		my_est_time_secs += unbalanced_sweep.get_est_time_secs()
	if benchmark == 'scatter':
		my_est_time_secs += syntheticscatter.get_est_time_secs()
	if benchmark == 'slow':
		my_est_time_secs += syntheticslow.get_est_time_secs()
	if benchmark == 'convergence':
		my_est_time_secs += syntheticconvergence.get_est_time_secs()
	if benchmark == 'micropp':
		my_est_time_secs += micropp.get_est_time_secs()
	if benchmark == 'nbody':
		my_est_time_secs += nbody.get_est_time_secs()
	return my_est_time_secs



def all_num_nodes():
	num_nodes = set([])
	if include_apps['synthetic']:
		num_nodes.update(unbalanced_sweep.num_nodes())
	if include_apps['scatter']:
		num_nodes.update(syntheticscatter.num_nodes())
	if include_apps['slow']:
		num_nodes.update(syntheticslow.num_nodes())
	if include_apps['convergence']:
		num_nodes.update(syntheticconvergence.num_nodes())
	if include_apps['micropp']:
		num_nodes.update(micropp.num_nodes())
	if include_apps['nbody']:
		num_nodes.update(nbody.num_nodes())
	return sorted(num_nodes)

def generate_plots(results):
	global output_prefix
	output_prefix_str = output_prefix if not output_prefix is None else ''
	if include_apps['synthetic']:
		unbalanced_sweep.generate_plots(results, output_prefix_str)
	if include_apps['scatter']:
		syntheticscatter.generate_plots(results, output_prefix_str)
	if include_apps['slow']:
		syntheticslow.generate_plots(results, output_prefix_str)
	if include_apps['convergence']:
		syntheticconvergence.generate_plots(results, output_prefix_str)
	if include_apps['micropp']:
		micropp.generate_plots(results, output_prefix_str)
	if include_apps['nbody']:
		nbody.generate_plots(results, output_prefix_str)
		

def main(argv):
	global include_apps
	global verbose
	global dry_run
	global qos
	global req_nodes
	global req_degree
	global req_policies
	global extrae
	global output_prefix
	global archived_subfolder
	seen_app = None
	seen_noapp = None

	if not canImportNumpy:
		if len(argv) >= 2 and argv[1] == '--recurse':
			print('Error with recursive invocation')
			return 1
		ret = os.system('module load python/3.6.1; python ' + argv[0] + ' --recurse ' + ' '.join(argv[1:]))
		return ret

	try:
		app_opts = [app for app in apps] + ['no-' + app for app in apps]
		opts, args = getopt.getopt( argv[1:],
									'hf', ['help', 'recurse', 'no-synthetic', 'no-micropp', 'quiet',
											'dry-run', 'qos=', 'nodes=', 'degree=', 'extrae',
											'local', 'global', 'output-prefix=', 'archived='] + app_opts)

	except getopt.error as msg:
		print(msg)
		print("for help use --help")
		sys.exit(2)
	for o, a in opts:
		if o in ('-h', '--help'):
			return Usage()
		elif o == '--recurse':
			# Ignore
			pass
		elif o == '--quiet':
			verbose = False
		elif o == '--dry-run':
			dry_run = True
		elif o == '--qos':
			qos = a
		elif o == '--nodes':
			req_nodes = [int(n) for n in a.split(',')]
		elif o == '--degree':
			req_degree = [int(n) for n in a.split(',')]
		elif o == '--extrae':
			extrae = True
		elif o == '--local':
			req_policies = ['local']
		elif o == '--global':
			req_policies = ['global']
		elif o == '--output-prefix':
			output_prefix = a
		elif o == '--archived':
			archived_subfolder = a
		else:
			assert o.startswith('--')
			if o[2:] in apps:
				if not seen_noapp is None:
					print(f'Cannot combine --{o[2:]} with {seen_noapp}')
					sys.exit(1)
				if seen_app is None:
					include_apps = dict([(app, False) for app in apps])
				include_apps[o[2:]] = True
				seen_app = o
			elif o.startswith('--no-') and o[5:] in apps:
				if not seen_app is None:
					print(f'Cannot combine --{o[2:]} with {seen_app}')
					sys.exit(1)
				include_apps[o[5:]] = False
				seen_noapp = o
			else:
				assert(False)
	
	if len(args) < 1:
		return Usage()

	command = args[0]
	if not req_nodes is None:
		if not (command == 'submit' or dry_run) :
			print('--nodes n only valid for submit command or with --dry-run')
			return 1
	if not req_degree is None:
		if command != 'submit' and command != 'interactive' and command != 'batch':
			print('--degree d only valid for submit, interactive or batch command')
			return 1
	if not output_prefix is None:
		if command != 'process':
			print('--output-prefix only valid for process command')
			return 1
	if not archived_subfolder is None:
		if command != 'process':
			printf('--archived only valid for process command')
			return 1
	
	hybrid_params_list = []
	if extrae:
		hybrid_params_list.append('--extrae')
	hybrid_params = ' '.join(hybrid_params_list)

	cwd = os.getcwd()

	expected_curdir = 'cluster-dlb-benchmarks'
	if (os.path.basename(cwd) != expected_curdir):
		if f'/{expected_curdir}/' in cwd:
			subdir = os.path.basename(cwd)
			print(f'Run from {expected_curdir} directory, not subdirectory {subdir}')
		else:
			print(f'Run from {expected_curdir} directory')
		return 1

	if command in ['make', 'interactive', 'batch', 'submit']:
		# Run make
		if not make():
			print('Error: one or more binary missing; use make')
			return 1

	if command == 'make':
		# Already ran 'make' above
		return 0
	elif command == 'interactive' or command == 'batch':

		if check_num_nodes.get_on_compute_node():
			nums_nodes = [check_num_nodes.get_num_nodes()]
		else:
			if not dry_run:
				print('run-benchmarks.py interactive must be run on a compute node')
				return 2
			if req_nodes is None:
				nums_nodes = [2,4,8]
			else:
				nums_nodes = req_nodes

		print_time('Started at')
		print_jobid()
		os.makedirs(job_output_dir, exist_ok=True)
		try:
			for num_nodes in nums_nodes:
				for benchmark in apps:
					if include_apps[benchmark]:
						for cmd in all_commands(num_nodes, hybrid_params, benchmark):
							if filter_command(cmd):
								#print(cmd, benchmark, command)
								if not dry_run:
									print_time('Current time')
								run_single_command(cmd, benchmark, command, keep_output=True, num_nodes=num_nodes)
		except KeyboardInterrupt:
			print('Interrupted')
		print_time('Finished at')
		return 1
	elif command == 'submit':
		os.makedirs(job_output_dir, exist_ok=True)
		num_nodes = all_num_nodes()
		fail = False
		if not req_nodes is None:
			num_nodes = [n for n in num_nodes if n in req_nodes]
			for r in req_nodes:
				if not r in num_nodes:
					print(f'No experiment with {r} nodes')
					fail = True
		if fail:
			return 1
		for n in num_nodes:
			if dry_run:
				for benchmark in apps:
					if include_apps[benchmark]:
						print(f'=== {benchmark} on {n} nodes ===')
						for cmd in all_commands(n, hybrid_params, benchmark):
							if filter_command(cmd):
								print(cmd)
						hours, mins = decode_time_secs(get_est_time_secs(benchmark))
						print(f'Estimated time {hours} hours and {mins} mins')
			else:
				# Go through all commands to get estimated time only
				for benchmark in apps:
					if include_apps[benchmark]:
						for cmd in all_commands(n, hybrid_params, benchmark):
							pass
						hours, mins = decode_time_secs(get_est_time_secs(benchmark))
						print(f'{benchmark} on {n} nodes: Estimated time {hours} hours and {mins} mins')
						job_script_name = create_job_script(n, hours, mins, benchmark)
						print(job_script_name)
						if not job_script_name is None:
							submit_job_script(job_script_name)
		return 1
	elif command == 'process':
		os.makedirs(output_dir, exist_ok=True)
		results = get_all_results()
		results = averaged_results(results)
		generate_plots(results)
		return 1

	elif command == 'archive':
		os.makedirs(archive_output_dir, exist_ok=True)
		if len(args) >= 2:
			archive_folder = archive_output_dir + '/' + args[1]
			if os.path.exists(archive_folder):
				print(f'archive output folder {archive_folder} already exists')
				return 1
		else:
			archive_folder = unique_output_name(archive_output_dir, 'jobs_')
		os.mkdir(archive_folder)
		run_single_command('mv ' + job_output_dir + '/* ' + archive_folder, command=None, keep_output=False)
	else:
		print('Unrecognized command %s\n' % command)
		return Usage()

	return 0

if __name__ == '__main__':
	sys.exit(main(sys.argv))
