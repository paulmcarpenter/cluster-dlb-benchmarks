#include <assert.h>
#include <string.h>
#include "mpi.h"
#include "common.h"

#define MAX_RANKS 100

// #pragma oss task inout(a[0;1000])
void wait(int *a, int t)
{
    int j,k;

    for(j=0; j<t; j++)
    {
        for(k=0; k<10000000;k++)
            *a = (*a >>1) * 17;
    }
}

int main( int argc, char *argv[] )
{
    int i, id, nproc, id_from;
    int comm;
    int mywork;
    int iter, task;
    int ntasks = 48*3;
    int rank, max_rank;
    int *a = nanos6_dmalloc(ntasks * 1000 * sizeof(int), nanos6_equpart_distribution, 0, NULL);

    MPI_Status status;
    // Initialize MPI:
    // MPI_Init(&argc, &argv);

    comm = nanos6_app_communicator();

    // Get my rank:
    MPI_Comm_rank(comm, &id);
    // Get the total number of processors:
    MPI_Comm_size(comm, &nproc);
  
    // How much work do I have?
    srand(id);
    mywork = (1+rand() % 10) * (1+rand() % 10);
    printf("Application rank %d of %d\n", id, nproc);

    int *all_ranks = (int *)nanos6_lmalloc(nproc * ntasks * sizeof(int));
    int *ranks = (int *)nanos6_lmalloc(ntasks * sizeof(int));

	int it = 0;
    while (1)
    {
        memset(ranks, 0, ntasks * sizeof(int));
        for(task=0; task<ntasks; task++)
        {
            int *aa = a + 1000 * task;
            #pragma oss task inout(aa[0;1000]) out(ranks[task;1]) 
            {
                int rank = nanos6_get_cluster_node_id();
				wait(&ranks[task], 3);
                ranks[task] = rank;

                // printf("task %d-%d on %d\n", id, task, rank);
            }
        }
        #pragma oss taskwait
        MPI_Gather(ranks, ntasks, MPI_INT, all_ranks, ntasks, MPI_INT, 0, comm);
        if (id == 0)
        {
            int p, t;
            for (p = 0; p < nproc; p++)
            {
				if (p==0)
					printf("%3d: ", it);
				else
					printf("%3s  ", "");
                printf("Rank %2d: ", p);
                for (t = 0; t < ntasks; t++)
                {
                    printf("%d", all_ranks[p*ntasks + t]);
                }
				printf("\n");
            }
        }
        // sleep(2);
        MPI_Barrier(comm);
		it++;
    }

    // Terminate MPI:
    // MPI_Finalize();
}
