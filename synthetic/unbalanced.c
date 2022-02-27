#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
// #include <limits.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>
#include "mpi.h"

// Simple function to wait for a fixed time
void wait(const struct timespec ts)
{
	struct timespec rem;
	int retval = nanosleep(&ts, &rem);

	while (retval == -1) {
		struct timespec ts2 = rem;
		retval = nanosleep(&ts2, &rem);
	}
}

int main( int argc, char *argv[] )
{
	int comm;							  // Application's communicator
	int id, num_appranks;				  // Application (virtual) rank and number of ranks
	int task;							  // Counters
	struct timeval time_start, time_end;  // For timing each iteration

	// Initialize MPI:
	// MPI_Init(&argc, &argv);	 // Cluster+DLB: do not call MPI_Init

	comm = nanos6_app_communicator();  // Cluster+DLB: use application communicator

	// Get my (virtual) rank
	MPI_Comm_rank(comm, &id);
	// Get the total number of appranks
	MPI_Comm_size(comm, &num_appranks);

	// Check number of arguments
	if (argc < 5 + num_appranks) {
		if (id == 0) {
			fprintf(stderr, "Usage: %s <num iterations> <tasks/rank> <bytes/task> <noflush> <ms_per_task_rank1> ...\n", argv[0]);
		}
		return 1;
	}
	
	// Get number of iterations and number of tasks
	char *endPtr;
	int niter = atoi(argv[1]);
	int ntasks = atoi(argv[2]);
	size_t bytes_per_task = strtoll(argv[3], &endPtr, 10);
	int noflush = atoi(argv[4]);

	switch (*endPtr) {
		case '\0': break;
		case 'k':  bytes_per_task *= 1000; break;
		case 'M':  bytes_per_task *= 1000000; break;
		case 'G':  bytes_per_task *= 1000000000; break;
		default:
			if (id == 0) {
				fprintf(stderr, "Bad suffix on bytes/task\n");
			}
			return 1;
	}

	if (bytes_per_task == 0) {
		if (id == 0) {
			fprintf(stderr, "Bytes/task must be at least 1\n");
		}
		return 1;
	}

	// Get work per task for my rank
	double mywork_ms = atof(argv[5+id]);
	long long mywork_us = (int)(mywork_ms * 1000);

	// Time per task as struct timespec
	struct timespec ts;
	ts.tv_sec = mywork_us / 1000000;
	ts.tv_nsec = (mywork_us % 1000000) * 1000;

	// Allocate memory for all tasks
	char *mem = (char *)nanos6_lmalloc(ntasks * bytes_per_task);
	for (int i=0;i<ntasks;i++) {
		mem[i*bytes_per_task] = i+10;
	}

	// Run iterations
	MPI_Barrier(comm);
	for(int iter=0; iter < niter; iter++)
	{
		gettimeofday(&time_start, NULL);

		// Create independent tasks
		for(int task=0; task<ntasks; task++)
		{
			char *c = &mem[task * bytes_per_task];
			#pragma oss task inout(c[0;bytes_per_task]) 
			{
				// Very simple correctness check on the first byte
				assert(c[0] == (char)(task + iter + 10));
				c[0] ++;
				wait(ts);
			}
		}

		if (noflush) {
			#pragma oss taskwait noflush
		} else {
			#pragma oss taskwait
		}

		// Barrier
		MPI_Barrier(comm);

		// Print execution time
		if (id == 0)
		{
			int p, t;
			gettimeofday(&time_end, NULL);
			double secs = (time_end.tv_sec - time_start.tv_sec) + (time_end.tv_usec - time_start.tv_usec) / 1000000.0;
			printf("# %s appranks=%d deg=%d ", argv[0], num_appranks, nanos6_get_num_cluster_iranks());
			for (int i=1; i<argc; i++) {
				printf("%s ", argv[i]);
			}
			printf(": iter=%d time=%3.2f sec\n", iter, secs);
		}
	}

	// Terminate MPI:
	// MPI_Finalize();	 // Cluster+DLB: do not call MPI_Finalize
}
