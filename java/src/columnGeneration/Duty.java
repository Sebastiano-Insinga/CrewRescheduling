package columnGeneration;

import java.util.List;
import java.util.Random;

import instance.Task;

/**
 * Simple class to model a duty. Each duty is defined by a cost and a list of
 * tasks.
 * 
 * @author B.T.C. van Rossum
 */
public class Duty
{
	private final double cost;
	private final List<Task> tasks;
	private static int counter=0;
	private final int id;
	/**
	 * Initialise a duty with specified cost and list of tasks.
	 * 
	 * @param cost  cost of the duty
	 * @param tasks list of tasks in the duty
	 */
	public Duty(double cost, List<Task> tasks)
	{
		this.cost = cost;
		this.tasks = tasks;
		this.id=counter++;
	}

	/**
	 * Returns cost of the duty.
	 * 
	 * @return cost of the duty.
	 */
	public double getCost()
	{
		return cost;
	}

	/**
	 * Returns the list of tasks in the duty.
	 * 
	 * @return list of tasks in the duty
	 */
	public List<Task> getTasks()
	{
		return tasks;
	}

	public int getID() {
		return id;
	}
	
	}





