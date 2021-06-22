# cluster-dlb-benchmarks

Simple benchmarks for OmpSs2@Cluster + DLB.

# How to run correctness tests

Get exactly two nodes and run:

	salloc -q debug -c 48 -n 2 -t 02:00:00
	cd cluster-dlb-benchmarks/build
	make ..
	make
	make test

# How to run performance tests

	cd cluster-dlb-benchmarks
	./run-benchmarks.py --dry-run interactive  # To see what will run
	./run-benchmarks.py interactive            # To run them interactively
	./run-benchmarks.py submit                 # To run them as batch jobs

# How to generate the plots

	./run-benchmarks.py process

# How to remove current results

	./run-benchmarks archive
