#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <assert.h>
#include <limits.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>
#include <unistd.h>
#include <nanos6.h>
#include "mpi.h"

// Simple function to wait for t units of 10 ms
void wait(unsigned int t_1ms)
{
	struct timespec ts;
	ts.tv_sec = 0;
	ts.tv_nsec = t_1ms * 1000000;
	nanosleep(&ts, NULL);
}

int main( int argc, char *argv[] )
{
    int comm;                             // Application's communicator
    int id, nproc;                        // Application (virtual) rank and number of ranks
    int iter, task;                       // Counters
    int ntasks = 48 * 5;                  // Number of tasks per application rank
    int niter = 6;                        // Number of iterations

    MPI_Status status;
    // Initialize MPI:
    // MPI_Init(&argc, &argv);

    comm = nanos6_app_communicator();

    // Get my rank:
    MPI_Comm_rank(comm, &id);
    // Get the total number of appranks
    MPI_Comm_size(comm, &nproc);
  
	/* Get physical nodes for this process */
	int master_node = nanos6_get_cluster_physical_node_id();
	int num_nodes = nanos6_get_num_cluster_physical_nodes();
	for (int i=0; i<nproc; i++) {
		if (i == id) {
			printf("Application rank %d of %d: master on node %d\n", id, nproc, master_node);
			MPI_Barrier(comm);
		}
	}

    int *ranks = (int *)nanos6_lmalloc(ntasks * sizeof(int));

    for(iter=0; iter < niter; iter++) {

		if (id == 0) {
			printf("Iteration %d\n", iter);
			memset(ranks, -1, ntasks * sizeof(int));
			for(task=0; task<ntasks; task++) {
				#pragma oss task out(ranks[task;1])  node(1)
				{
					int rank = nanos6_get_cluster_physical_node_id();  // physical node not irank
					wait(400);
					ranks[task] = rank;
				}
			}
			#pragma oss taskwait
		}
        MPI_Barrier(comm);
    }

    // Terminate MPI:
    // MPI_Finalize();
}
