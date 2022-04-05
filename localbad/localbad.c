#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include <assert.h>
// #include <limits.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <sys/time.h>
#include "mpi.h"

// Parameters
int niter = 10;
#define NTASKS_PER_CORE 100
int ntasks_per_core = NTASKS_PER_CORE;
int ntasks = (48 * NTASKS_PER_CORE) - 24;


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

void run_with_work(const char *appname, int id, int num_appranks, int *work_per_rank, int part, int runs_per_imbalance)
{
	int task;							  // Counters
	int comm = nanos6_app_communicator();  // Cluster+DLB: use application communicator
	struct timeval time_start, time_end;  // For timing each iteration
	for(int run=0; run < runs_per_imbalance; run++) {

		// Get work per task for my rank
		int mywork_us = work_per_rank[id];
		printf("Rank %d gets %d)\n", id, mywork_us);

		// Time per task as struct timespec
		struct timespec ts;
		ts.tv_sec = mywork_us / 1000000;
		ts.tv_nsec = (mywork_us % 1000000) * 1000;

		// Allocate memory for all tasks
		int bytes_per_task = 1;
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

			#pragma oss taskwait noflush

			// Barrier
			MPI_Barrier(comm);

			// Print execution time
			if (id == 0)
			{
				int p, t;
				gettimeofday(&time_end, NULL);
				double secs = (time_end.tv_sec - time_start.tv_sec) + (time_end.tv_usec - time_start.tv_usec) / 1000000.0;
				printf("# %s appranks=%d deg=%d ", appname, num_appranks, nanos6_get_num_cluster_iranks());
				printf(": part=%d iter=%d time=%3.2f sec\n", part, iter, secs);
			}
		}
	}
}


int main( int argc, char *argv[] )
{
	int comm;							  // Application's communicator
	int id, num_appranks;				  // Application (virtual) rank and number of ranks
	int runs_per_imbalance = 1;
	int sweep_imbalance = 1;
	double target_imbalance;

	if (argc != 1) {
		printf("Usage: %s\n", argv[0]);
		return -1;
	}

	// Initialize MPI:
	// MPI_Init(&argc, &argv);	 // Cluster+DLB: do not call MPI_Init

	comm = nanos6_app_communicator();  // Cluster+DLB: use application communicator

	// Get my (virtual) rank
	MPI_Comm_rank(comm, &id);
	// Get the total number of appranks
	MPI_Comm_size(comm, &num_appranks);

	int work_per_rank[num_appranks]; // in us
	memset(work_per_rank, 0, num_appranks * sizeof(int));
	work_per_rank[0] = 50000;
	run_with_work(argv[0], id, num_appranks, work_per_rank, 1, 1);
	work_per_rank[0] = 50000;;
	work_per_rank[1] = 50000;
	run_with_work(argv[0], id, num_appranks, work_per_rank, 2, 1);

	// Terminate MPI:
	// MPI_Finalize();	 // Cluster+DLB: do not call MPI_Finalize
}
