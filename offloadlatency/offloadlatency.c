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

float calc_avg(float *vals, int ntasks, float start)
{
	float tot = 0;
	int count = 0;
	for(int task=(int)(ntasks*start); task<ntasks; task++)
	{
		tot += vals[task];
		count ++;
	}
	return tot / count;
}

float calc_max(float *vals, int ntasks, float start)
{
	float maxval = 0;
	for(int task=(int)(ntasks*start); task<ntasks; task++)
	{
		if (vals[task] > maxval) {
			maxval = vals[task];
		}
	}
	return maxval;
}


int main( int argc, char *argv[] )
{
	int id, num_appranks;				  // Application (virtual) rank and number of ranks

	if (argc > 1) {
		printf("Usage: %s\n");
		printf("  imbalance and niter are optional\n");
		return -1;
	}


	int task;							  // Counters
	int max_ntasks = 16384;
	struct timeval time_start[max_ntasks];
	float latency_time[max_ntasks];

	int bytes_per_task = 1;
	char *mem = (char *)nanos6_lmalloc(max_ntasks * bytes_per_task);

	int runs = 1;
	int niter = 1;

	int offload;
	for(offload = 0; offload <= 1; offload++) {
		printf("Offload: %s\n", offload ? "yes" : "no");
		int full_speed = 1;
		float tasks_per_sec = 100000.0;
		while (tasks_per_sec >= 50.0) {
			double period = 1.0 / tasks_per_sec;
			int ntasks = (int)(tasks_per_sec * 2);
			if (ntasks > max_ntasks) {
				ntasks = max_ntasks;
			}

			if (full_speed) {
				ntasks = max_ntasks;
			}

			// printf("ntasks: %d\n", ntasks);

			// Time per task as struct timespec
			// struct timespec ts;
			// ts.tv_sec = mywork_us / 1000000;
			// ts.tv_nsec = (mywork_us % 1000000) * 1000;

			// // Time per task as struct timespec (slow node)
			// struct timespec ts_slow;
			// int mywork_us_slow = mywork_us * slowdown_last_node;
			// ts_slow.tv_sec = (mywork_us_slow / 1000000);
			// ts_slow.tv_nsec = (mywork_us_slow % 1000000) * 1000;


			for(int iter=0; iter < niter; iter++)
			{
				printf("Iter %d\n", iter);
				// Create independent tasks
				struct timeval time_very_start;
				gettimeofday(&time_very_start, NULL);
				int node = offload;
				for(int task=0; task<ntasks; task++)
				{
					gettimeofday(&time_start[task], NULL);
					char *c = &mem[task * bytes_per_task];
					#pragma oss task inout(c[0;bytes_per_task])  node(node)
					{
						assert(nanos6_get_cluster_node_id() == node);
					}
					#pragma oss task in(c[0;bytes_per_task]) out(latency_time[task]) node(nanos6_cluster_no_offload)
					{
						struct timeval time_end;
						gettimeofday(&time_end, NULL);
						double secs = (time_end.tv_sec - time_start[task].tv_sec) + (time_end.tv_usec - time_start[task].tv_usec) / 1000000.0;
						latency_time[task] = secs;
						// printf("Latency %d = %f [%ld; %ld]\n", task, secs, (long long)time_start[task].tv_sec, (long long)time_end.tv_sec);
					}

					if (!full_speed) {
						double secs = 0;
						while (secs < period) {
							struct timeval time_now;
							gettimeofday(&time_now, NULL);
							secs = (time_now.tv_sec - time_start[task].tv_sec) + (time_now.tv_usec - time_start[task].tv_usec) / 1000000.0;
						}
					}
				}
				struct timeval time_very_end;
				gettimeofday(&time_very_end,NULL);

				#pragma oss taskwait

				float secs_all = (time_very_end.tv_sec - time_very_start.tv_sec) + (time_very_end.tv_usec - time_very_start.tv_usec) / 1000000.0;
				float actual_tasks_per_sec = ntasks / secs_all;

				float avg_latency_75 = calc_avg(latency_time, ntasks, 0.75);
				float avg_latency_95 = calc_avg(latency_time, ntasks, 0.95);
				float max_latency = calc_max(latency_time, ntasks, 0.5);
				printf("Tasks/sec: %f (target %f) Average (75%%): %f ms Average(95%%): %f ms  Max: %f ms\n", actual_tasks_per_sec, tasks_per_sec, 1000.0 * avg_latency_75, 1000.0 * avg_latency_95, 1000.0 * max_latency);
			}
			tasks_per_sec /= 2.0;
			full_speed = 0;
		}
	}

	// Terminate MPI:
	// MPI_Finalize();	 // Cluster+DLB: do not call MPI_Finalize
}
