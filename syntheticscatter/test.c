#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include <assert.h>
// #include <limits.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <sys/time.h>

int cmpfunc(const void *a, const void *b)
{
	return ( *(int*)a - *(int *)b);
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

	// Set up initial allocation with worst_work on one node and rest at zero
	int worst_rank = rand() % num_appranks;
	memset(work_per_rank, 0, num_appranks * sizeof(int));
	work_per_rank[worst_rank] = worst_work;
	int num_live_appranks = num_appranks-1;

	// How much work is left to allocate to get the right average work
	int rest_work = worst_work * (num_appranks / target_imbalance - 1);
	// printf("rest_work = %d\n", rest_work);

	while (rest_work > 0) {
		// The remaining m=n-1 entries should be "uniform" but must sum to rest_work.
		// A simple way is to choose m-1 places on the interval [0,rest_work], then sort
		// and use the sizes of these pieces. They must also be no larger than worst_work,
		// so we may need to drop any excess and try again.
		int m = num_live_appranks;
		int tmp[m+1];
		tmp[0] = 0;
		for(int i=1; i < m; i++) {
			tmp[i] = rand() % rest_work;
			printf("Y_%d = %d\n", i, tmp[i]);
		}
		tmp[m] = rest_work;
		qsort(tmp, m+1, sizeof(int), cmpfunc);

		// for(int i=0; i < m+1; i++) {
		// 	printf("Now Y_%d = %d\n", i, tmp[i]);
		// }
	
		double multiplier = 1.0;
		// Check whether any exceed worst_work
		int i = 1;
		for(int j=0; j<num_appranks; j++) {
			if (work_per_rank[j] < worst_work) {
				int extra_work = tmp[i] - tmp[i-1];
				int slack = worst_work - work_per_rank[j];
				// printf("Proposed extra work for %d is %d\n", j, extra_work);
				if (extra_work >= slack) {
					double my_multiplier = (double)slack / extra_work;
					if (my_multiplier < multiplier) {
						multiplier = my_multiplier;
					}
				}
				i++;
			}
		}
		// printf("multiplier = %f\n", multiplier);

		i = 1;
		for(int j=0; j<num_appranks; j++) {
			if (work_per_rank[j] < worst_work) {
				int extra_work = multiplier * (tmp[i] - tmp[i-1]);
				// printf("Proposed extra work for %d is %d\n", j, extra_work);
				work_per_rank[j] += extra_work;
				assert (work_per_rank[j] <= worst_work);
				if (work_per_rank[j] == worst_work) {
					num_live_appranks --;
				}
				rest_work -= extra_work;
				// printf("Actual extra work for %d is %d\n", j, extra_work);
				i++;
			}
			// printf("work_per_rank[%d] = %d\n", j, work_per_rank[j]);
		}
		printf("rest_work = %d\n", rest_work);
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
		assert (imbalance >= target_imbalance - 0.1);
		assert (imbalance <= target_imbalance + 0.1);
	}

}
