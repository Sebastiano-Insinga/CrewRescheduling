package util;

import java.util.Comparator;

import instance.Task;

/**
 * Comparator used to topologically sort tasks.
 * 
 * @author B.T.C. van Rossum
 */
public class TaskComparator implements Comparator<Task>
{
	@Override
	public int compare(Task o1, Task o2)
	{
		int compare = Integer.compare(o1.getEndTime(), o2.getEndTime());
		if (compare == 0)
		{
			return Integer.compare(o1.getID(), o2.getID());
		}
		return compare;
	}
}


