#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include <assert.h>
// #include <limits.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <sys/time.h>

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

int calculate_work(int num_appranks, double target_imbalance, int *work_per_rank)
{
	int worst_work = 500;
	if (target_imbalance > num_appranks) {
		printf("Imbalance of %f not possible on %d nodes (max imbalance is %d)\n",
				target_imbalance, num_appranks, num_appranks);
		return 0;
	}
	printf("target_imbalance = %f\n", target_imbalance);

	// Which rank will get the worst amount of work?
	int worst_rank = rand() % num_appranks;

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

int main( int argc, char *argv[] )
{

	int num_appranks = 4;
	int work_per_rank[num_appranks]; // in ms

	srand(100);
	double imbalance_step = 0.1;
	int max_i = (num_appranks-1) / imbalance_step;
	for(int i=0; i<max_i; i++) {
		double target_imbalance = 1.0 + i * imbalance_step;

		calculate_work(num_appranks, target_imbalance, work_per_rank);
		long long tot = 0;
		int max = 0;
		printf("Work per rank: \n");
		for(int i=0; i < num_appranks; i++) {
			printf("%d ", work_per_rank[i]);
			tot += work_per_rank[i];
			if (work_per_rank[i] > max) {
				max = work_per_rank[i];
			}
		}
		printf("\n");
		double avg = (double)tot/num_appranks;
		// printf("Average: %.3f\n", avg);
		// printf("Max: %d\n", max);
		double imbalance = max / avg;
		printf("Imbalance: %.3f\n", imbalance);
		assert (imbalance >= target_imbalance - 0.05);
		assert (imbalance <= target_imbalance + 0.05);
	}

}
