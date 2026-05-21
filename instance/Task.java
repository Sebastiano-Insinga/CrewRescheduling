package instance;

import graph.NodeIndex;
import java.util.Locale;
/**
 * Models a task in a crew scheduling problem.
 * 
 * @author B.T.C. van Rossum
 */
public class Task extends NodeIndex
{
	private final int id;
	private final int startTime;
	private final int endTime;
	private final int startStation;
	private final int endStation;
	private double dual = 0;

	/**
	 * Creates a task with given id, start time, end time, start station, and end
	 * station.
	 * 
	 * @param id           id
	 * @param startTime    start time
	 * @param endTime      end time
	 * @param startStation start station
	 * @param endStation   end station
	 */
	public Task(int id, int startTime, int endTime, int startStation, int endStation)
	{
		this.id = id;
		this.startTime = startTime;
		this.endTime = endTime;
		this.startStation = startStation;
		this.endStation = endStation;
	}

	/**
	 * Returns id of the task.
	 * 
	 * @return id
	 */
	public int getID()
	{
		return id;
	}

	/**
	 * Returns start time of the task.
	 * 
	 * @return start time
	 */
	public int getStartTime()
	{
		return startTime;
	}

	/**
	 * Returns end time of the task.
	 * 
	 * @return end time
	 */
	public int getEndTime()
	{
		return endTime;
	}

	/**
	 * Returns duration of the task, defined as the difference in end and start
	 * time.
	 * 
	 * @return duration
	 */
	public int getDuration()
	{
		return endTime - startTime;
	}

	/**
	 * Returns start station of the task.
	 * 
	 * @return start station
	 */
	public int getStartStation()
	{
		return startStation;
	}

	/**
	 * Returns end station of the task.
	 * 
	 * @return end station
	 */
	public int getEndStation()
	{
		return endStation;
	}

	/**
	 * Returns dual value of task.
	 * 
	 * @return dual value of task
	 */
	public double getDual()
	{
		return dual;
	}

	/**
	 * Set dual value of task.
	 * 
	 * @param dual dual value of task
	 */
	public void setDual(double dual)
	{
		this.dual = dual;
	
	}
	// in cima al file:
	

	    private static String fmt(int minutes) {
	        int h = minutes / 60;
	        int m = minutes % 60;
	        return String.format(Locale.US, "%02d:%02d", h, m);
	    }


	    @Override
	    public String toString() {
	        return String.format(Locale.US,
	            "Task{id=%d, start=%s(%d), end=%s(%d), dur=%d, s%d->s%d}",
	            id, fmt(startTime), startTime, fmt(endTime), endTime,
	            getDuration(), startStation, endStation);
	    }
	}

	
	
	
