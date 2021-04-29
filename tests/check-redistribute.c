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

#define NUM_APPRANKS 4
#define BASELINE_IMBALANCE ( (486.0+160.0) / ((486.0+160.0+25.0+20.0)/2.0) )
int work[NUM_APPRANKS] = {486, 160, 25, 20};

int main( int argc, char *argv[] )
{
    int comm;                             // Application's communicator
    int id, nproc;                        // Application (virtual) rank and number of ranks
    int mywork;                           // Amount of work per task (unbalanced among ranks)
    int iter, task;                       // Counters
    int ntasks = 48 * 5;                  // Number of tasks per application rank
    struct timeval time_start, time_end;  // For timing each iteration
    int niter = 3;                        // Number of iterations
	double imbalance = 0.0;
	double seconds_per_iter;

    MPI_Status status;
    // Initialize MPI:
    // MPI_Init(&argc, &argv);

    comm = nanos6_app_communicator();

    // Get my rank:
    MPI_Comm_rank(comm, &id);
    // Get the total number of appranks
    MPI_Comm_size(comm, &nproc);
	assert(nproc == NUM_APPRANKS);
  
    // How much work do I have?
    srand(id+10);
    mywork = work[id];

	/* Get physical nodes for this process */
	int master_node = nanos6_get_cluster_node_id();
	int num_nodes = nanos6_get_num_cluster_nodes();
	for (int i=0; i<nproc; i++) {
		if (i == id) {
			printf("Application rank %d of %d: master on node %d\n", id, nproc, master_node);
			MPI_Barrier(comm);
		}
	}

    int *all_nodes = (int *)nanos6_lmalloc(nproc * ntasks * sizeof(int));
    int *ranks = (int *)nanos6_lmalloc(ntasks * sizeof(int));
	int *work_on = (int *)malloc(num_nodes * sizeof(int));

    for(iter=0; iter < niter; iter++) {
        gettimeofday(&time_start, NULL);
        memset(ranks, -1, ntasks * sizeof(int));
        for(task=0; task<ntasks; task++) {
            #pragma oss task out(ranks[task;1]) 
            {
                int rank = nanos6_get_cluster_node_id();  // physical node not irank
				wait(mywork);
                ranks[task] = rank;

                // printf("task %d-%d on %d\n", id, task, rank);
            }
        }
        #pragma oss taskwait

		// Collect and print information
        MPI_Gather(ranks, ntasks, MPI_INT, all_nodes, ntasks, MPI_INT, 0, comm);
        if (id == 0) {
            int p, t;
            gettimeofday(&time_end, NULL);
            double seconds_per_iter = (time_end.tv_sec - time_start.tv_sec) + (time_end.tv_usec - time_start.tv_usec) / 1000000.0;
            printf("%3.2f sec ", seconds_per_iter);
			printf("%3d: ", iter);
			memset(work_on, 0, num_nodes * sizeof(int));
            for (p = 0; p < nproc; p++) {
                printf("Rank %2d: ", p);
				for (int curr_node = 0; curr_node < num_nodes; curr_node++) {
					int count_tasks = 0;
					for (int t = 0; t < ntasks; t++) {
						int node = all_nodes[p*ntasks + t];
						assert(node >= 0 && node < num_nodes);
						if (node == curr_node) {
							count_tasks ++;
							work_on[curr_node] += work[p];
						}
					}
					printf("%3d ", count_tasks);
				}
				printf("  |  ");
            }
			printf("\n");
			printf("Work on: ");
			int max_work_on_node = 0;
			int total_work_on_node = 0;
			for (int node = 0; node < num_nodes; node++) {
				printf("node %d: %d  ", node, work_on[node]);
				total_work_on_node += work_on[node];
				if (work_on[node] > max_work_on_node) {
					max_work_on_node = work_on[node];
				}
			}
			imbalance = (double)max_work_on_node / ((double)total_work_on_node / num_nodes);
			printf("\n");
			printf("Imbalance: %.5f\n", imbalance);

        }
        MPI_Barrier(comm);
    }

    // Terminate MPI:
    // MPI_Finalize();

	if (id == 0) {
		int fail = 0;
		int degree = nanos6_get_num_cluster_iranks(); /* #ranks = degree */
		double target_min_imbalance, target_max_imbalance;

		if (degree == 1) {
			target_min_imbalance = BASELINE_IMBALANCE - 0.1;
			target_max_imbalance = BASELINE_IMBALANCE + 0.1;
		} else {
			target_min_imbalance = 1.0;
			target_max_imbalance = 1.17;
		}
		if (imbalance >= target_min_imbalance && imbalance <= target_max_imbalance) {
			printf("Imbalance %.5f OK (min=%.3f, max=%.3f)\n", imbalance, target_min_imbalance, target_max_imbalance);
		} else {
			printf("Imbalance %.5f FAIL (min=%.3f, max=%.3f)\n", imbalance, target_min_imbalance, target_max_imbalance);
			fail = 1;
		}
		if (!fail) {
			printf("Test PASSED\n");
		} else {
			printf("Test FAILED\n");
		}
		return fail;
	} else {
		return 0;
	}
}
