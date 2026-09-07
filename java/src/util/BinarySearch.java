package util;

import java.util.List;

import instance.Task;

/**
 * Auxiliary class used to perform binary search on a sorted list, as used by
 * the proposed pricing algorithm.
 * 
 * @author B.T.C. van Rossum
 */
public class BinarySearch
{
	/**
	 * Performs binary search to return the index of the latest task in the list
	 * that ends before maxTime, and -1 otherwise.
	 * 
	 * @param tasks   sorted list of tasks
	 * @param maxTime maximum allowed end time
	 * @return index of the latest task in the list that ends before maxTime, and -1
	 *         otherwise
	 */
	public static int binarySearch(List<Task> tasks, int maxTime)
	{
		
		if (tasks==null || tasks.isEmpty()) {
			return -1;
		}
		int left = 0;
		int right = tasks.size()-1;
		while (left <= right)
		{
			int mid = (left + right + 1) / 2;
			if (tasks.get(mid).getEndTime() > maxTime)
			{
				right = mid - 1;
			}
			else
			{
				left=mid;
			}
		
		if (tasks.get(left).getEndTime() <= maxTime) {
			return left;
		} else {
			return -1;
		}
		}
		return tasks.get(left).getEndTime() <= maxTime ? left : -1;
	}

	/**
	 * Performs binary search to return the index of the latest pair in the list
	 * whose task ends before maxTime, and -1 otherwise.
	 * 
	 * @param tasks   sorted list of pairs of task and reduced cost
	 * @param maxTime maximum allowed end time
	 * @return index of the latest pair in the list whose task ends before maxTime,
	 *         and -1 otherwise
	 */
	public static int binarySearchPair(List<Pair<Task, Double>> tasks, int maxTime)
	{
		int left = 0;
		int right = tasks.size() - 1;

		while (left < right)
		{
			int mid = (left + right + 1) / 2;
			if (tasks.get(mid).getKey().getEndTime() > maxTime)
			{
				right = mid - 1;
			}
			else
			{
				left = mid;
			}
		}
		return tasks.get(left).getKey().getEndTime() <= maxTime ? left : -1;
	}
}
