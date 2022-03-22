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
	int niter = 10;
	int ntasks = 480;

	// Initialize MPI:
	// MPI_Init(&argc, &argv);	 // Cluster+DLB: do not call MPI_Init

	comm = nanos6_app_communicator();  // Cluster+DLB: use application communicator

	// Get my (virtual) rank
	MPI_Comm_rank(comm, &id);
	// Get the total number of appranks
	MPI_Comm_size(comm, &num_appranks);

	int work_per_rank[num_appranks]; // in ms

	srand(100);

	float target_imbalance = 2.0; // target value of max / average
	double imbalance;

	if (target_imbalance > num_appranks) {
		printf("Imbalance of %f not possible on %d nodes (max imbalance is %d)\n",
				target_imbalance, num_appranks, num_appranks);
		return 0;
	}


	// Rank 0 calculates work for each rank
	if (id == 0) {
		int worst_work = 500;
		int worst_rank = rand() % num_appranks;
		work_per_rank[worst_rank] = worst_work;
		int rest_work = worst_work * (num_appranks / target_imbalance - 1);

		// Uniformly random on remaining nodes (unnormalized)
		long long total = 0;
		int tmp[num_appranks];
		for(int i=0; i < num_appranks; i++) {
			if (i != worst_rank) {
				tmp[i] = rand();
				total += tmp[i];
			}
		}

		// Now normalize uniformly random on remaining nodes
		for(int i=0; i < num_appranks; i++) {
			if (i != worst_rank) {
				work_per_rank[i] = (int)( (double)tmp[i] / total * rest_work );
			}
		}

		long long tot = 0;
		int max = 0;
		for(int i=0; i < num_appranks; i++) {
			printf("%d ", work_per_rank[i]);
			tot += work_per_rank[i];
			if (work_per_rank[i] > max) {
				max = work_per_rank[i];
			}
		}
		double avg = (double)tot/num_appranks;
		printf("\nAverage: %.3f\n", avg);
		printf("Max: %d\n", max);
		imbalance = max / avg;
		printf("Imbalance: %.3f\n", imbalance);
	}

	// Get work per task for my rank
	int mywork_ms;
	MPI_Scatter(work_per_rank, 1, MPI_INT, &mywork_ms, 1, MPI_INT, 0, comm);
	MPI_Bcast(&imbalance, 1, MPI_DOUBLE, 0, comm);
	printf("Rank %d gets %d (imb=%f)\n", id, mywork_ms, imbalance);

	long long mywork_us = (int)(mywork_ms * 1000);

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
			printf("# %s appranks=%d deg=%d ", argv[0], num_appranks, nanos6_get_num_cluster_iranks());
			for (int i=1; i<argc; i++) {
				printf("%s ", argv[i]);
			}
			printf(": iter=%d imb=%.3f time=%3.2f sec\n", iter, imbalance, secs);
		}
	}

	// Terminate MPI:
	// MPI_Finalize();	 // Cluster+DLB: do not call MPI_Finalize
}
