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
int ntasks = (16 * NTASKS_PER_CORE) - 8;

const char *get_hostname(void)
{
  FILE *fp;
  int size = 1000;
  char *hostname = malloc(size);

  /* Open the command to get hostname. */
  fp = popen("hostname", "r");
  if (fp == NULL) {
    printf("Failed to run command\n" );
    exit(1);
  }
  fgets(hostname, size, fp);

  /* close */
  pclose(fp);

  return hostname;
}


float get_cpu_freq_mhz(void)
{
  FILE *fp;
  char line[1035];

  /* Open the command for reading. */
  fp = popen("lscpu", "r");
  if (fp == NULL) {
    printf("Failed to run command\n" );
    exit(1);
  }

  /* Read the output a line at a time - output it. */
  const char *prefix = "CPU MHz: ";
  size_t len_prefix = strlen(prefix);
  float freq = 0;

  while (fgets(line, sizeof(line), fp) != NULL) {
  	if (strlen(line) >= len_prefix && memcmp(line, prefix, len_prefix) == 0) {
		freq = atof(line + len_prefix);
		break;
	}
  }

  /* close */
  pclose(fp);

  return freq;
}




// Comparison function for qsort of ints
int cmpfunc(const void *a, const void *b)
{
	return ( *(int*)a - *(int *)b);
}

// Generate array of m numbers, each of value from 0 to max, with given total
int gen(int m, int total, int max, int *pieces) {

	int fail;
	do {
		fail = 0;
		// A simple way is to choose m-1 random places on the interval [0,total],
		// then sort these places and use the sizes of these pieces between them.
		int tmp[m+1];
		tmp[0] = 0;
		for(int i=1; i < m; i++) {
			tmp[i] = (total>0) ? (rand() % total) : 0;
		}
		tmp[m] = total;
		qsort(tmp, m+1, sizeof(int), cmpfunc);

		// Check whether any piece exceeds max; if so, need to try again
		for(int i=0; i<m; i++) {
			pieces[i] = tmp[i+1] - tmp[i];
			if (pieces[i] > max) {
				fail = 1;
				break;
			}
		}
	} while (fail);
}

int avg_time_per_task = 50000; // in ms

// Calculate work on each rank with a given target imbalance
int calculate_work(int num_appranks, double target_imbalance, int *work_per_rank)
{
	int worst_work = avg_time_per_task * target_imbalance;
	if (target_imbalance > num_appranks) {
		printf("Imbalance of %f not possible on %d nodes (max imbalance is %d)\n",
				target_imbalance, num_appranks, num_appranks);
		return 0;
	}
	printf("target_imbalance = %f\n", target_imbalance);

	// Last (slow) rank always gets the worst amount of work
	int worst_rank = num_appranks-1;

	// How much work is left to allocate to get the right average work
	int rest_work = worst_work * (num_appranks / target_imbalance - 1);
	int slack_work = worst_work * (num_appranks-1) - rest_work;

	int tmp[num_appranks-1];
	if (rest_work < slack_work) {
		// Distribute rest_work across the remaining appranks
		gen(num_appranks-1, rest_work, worst_work, tmp);
	} else {
		// Better to start with full allocation to all nodes, then reduce it
		// by distributing the slack. Since the total slack is smaller than
		// rest_work, it is less likely that any particular value will exceed
		// worst_work, and require re-sampling.
		gen(num_appranks-1, slack_work, worst_work, tmp);
		for(int i=0; i<num_appranks-1; i++) {
			tmp[i] = worst_work - tmp[i];
		}
	}

	// Set up work_per_rank array
	int i = 0;
	for(int j=0; j<num_appranks; j++) {
		if (j != worst_rank) {
			work_per_rank[j] = tmp[i];
			i++;
		} else {
			work_per_rank[j] = worst_work;
		}
	}
}

static int val = 1;

// Simple function to wait for a roughly time
void wait(int mywork_us)
{
	// 30 iterations of this loop takes about 1 ms on Nord3
	int w, j;
	int a = 1;
	for(w = 0; w < mywork_us; w++) {
		// Each iteration is about 1 us on Nord3
		for(j = 0; j < 300; j++) {
			a = (a*3) + 56 + (a>>5);
		}
	}
	val += a;
}

void run_with_imbalance(const char *appname, int id, int num_appranks, double target_imbalance, int runs_per_imbalance)
{
	int task;							  // Counters
	int comm = nanos6_app_communicator();  // Cluster+DLB: use application communicator
	struct timeval time_start, time_end;  // For timing each iteration
	int work_per_rank[num_appranks]; // in us
	double imbalance = 0.0;
	for(int run=0; run < runs_per_imbalance; run++) {

		// Rank 0 calculates work for each rank
		if (id == 0) {
			calculate_work(num_appranks, target_imbalance, work_per_rank);

			long long tot = 0;
			int max = 0;
			printf("Work per rank (ms): \n");
			for(int i=0; i < num_appranks; i++) {
				printf("%.3f ", 1.0 * work_per_rank[i] / 1000);
				tot += work_per_rank[i];
				if (work_per_rank[i] > max) {
					max = work_per_rank[i];
				}
			}
			printf("\n");
			double avg = (double)tot/num_appranks;
			// printf("Average: %.3f\n", avg);
			// printf("Max: %d\n", max);
			imbalance = max / avg;
			printf("Imbalance: %.3f\n", imbalance);
		}

		// Get work per task for my rank
		int mywork_us;
		MPI_Scatter(work_per_rank, 1, MPI_INT, &mywork_us, 1, MPI_INT, 0, comm);
		MPI_Bcast(&imbalance, 1, MPI_DOUBLE, 0, comm);
		printf("Rank %d gets %d (imb=%f)\n", id, mywork_us, imbalance);

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
					wait(mywork_us);
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
				printf(": iter=%d imb=%.3f time=%3.2f sec\n", iter, imbalance, secs);
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

	if (argc > 3) {
		printf("Usage: %s <imbalance> <niter>\n");
		printf("  imbalance and niter are optional\n");
		return -1;
	}
	double imbalance;
	if (argc >= 2) {
		sweep_imbalance = 0;
		target_imbalance = atof(argv[1]);
	}
	if (argc == 3) {
		niter = atoi(argv[2]);
	}

	// Initialize MPI:
	// MPI_Init(&argc, &argv);	 // Cluster+DLB: do not call MPI_Init

	comm = nanos6_app_communicator();  // Cluster+DLB: use application communicator

	// Get my (virtual) rank
	MPI_Comm_rank(comm, &id);
	// Get the total number of appranks
	MPI_Comm_size(comm, &num_appranks);

	int degree = nanos6_get_num_cluster_nodes();
	for (int i = 0; i < num_appranks; i++) {
		if (i == id) {
			int seq = 0;
			for (int j = 0; j < degree; j++) {
				#pragma oss task inout(seq) node(j)
				{
					const char *hostname = get_hostname();
					float freq_ghz = get_cpu_freq_mhz() / 1000.0;
					printf("Apprank %d internalRank %d: %s freq = %f GHz\n", i, j, hostname, freq_ghz);
				}
			}
		}
	}
	MPI_Barrier(comm);

	srand(100);

	if (sweep_imbalance) {
		int estimated_time_secs = 30 * 60;  // for the baseline
		double avg_imbalance = (1.0 + num_appranks) / 2.0;
		double est_time_per_run = niter * ntasks_per_core * avg_time_per_task * avg_imbalance/ 1000000.0;
		int nruns = estimated_time_secs / est_time_per_run;
		printf("est_time_per_run = %.3f\n", est_time_per_run);
		printf("nruns: %d\n", nruns);
		float imbalance_step = 1.0 * (num_appranks - 1.0) / nruns;

		int max_i = (num_appranks-1) / imbalance_step;
		for(int i=0; i<max_i; i++) {
			double target_imbalance = 1.0 + i * imbalance_step;
			run_with_imbalance(argv[0], id, num_appranks, target_imbalance, runs_per_imbalance);
		}
	} else {
		run_with_imbalance(argv[0], id, num_appranks, target_imbalance, runs_per_imbalance);
	}

	// Terminate MPI:
	// MPI_Finalize();	 // Cluster+DLB: do not call MPI_Finalize
}
