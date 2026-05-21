package instance;

import java.util.List;
import java.util.Map;

import util.TaskComparator;

/**
 * Simple class to model an instance of the crew scheduling problem, defined by
 * a list of depots and a list of timetabled tasks.
 * 
 * @author B.T.C. van Rossum
 */
public class Instance
{
	private final List<Integer> depots;
	private final List<Task> tasks;
	private final Map<Integer, Map<Integer, Double>> stationDistances;
	/**
	 * Initialises an instance with specified list of depots and tasks.
	 * 
	 * @param depots list of depots
	 * @param tasks  list of tasks
	 * @param stationDistances 
	 */
	public Instance(List<Integer> depots, List<Task> tasks, Map<Integer, Map<Integer, Double>> stationDistances)
	{
		this.depots = depots;
		this.tasks = tasks;
		this.stationDistances = stationDistances;
		sortTasks();
	}

	/**
	 * Returns list of depots.
	 * 
	 * @return list of depots
	 */
	public List<Integer> getDepots()
	{
		return depots;
	}

	/**
	 * Returns list of tasks.
	 * 
	 * @return list of tasks
	 */
	public List<Task> getTasks()
	{
		return tasks;
	}

	/**
	 * Topologically sort the list of tasks.
	 */
	public void sortTasks()
	{
		tasks.sort(new TaskComparator());
	}
	
	public Map<Integer,Map<Integer,Double>>getStationDistances()
	{
		return stationDistances;
	}





}
