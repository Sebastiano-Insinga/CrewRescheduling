package graph;

import instance.Task;

/**
 * Simple class to model a connection between tasks.
 * 
 * @author B.T.C. van Rossum
 */
public class Connection
{
	/**
	 * Type of the connection. A connection is either a source arc, sink arc,
	 * connection arc between tasks, or waiting arc. Each connection has a cost, and
	 * a weight that is used to store dual information in the pricing problems.
	 * 
	 * @author B.T.C. van Rossum
	 */
	public enum ConnectionType
	{
		SOURCE("SOURCE"), SINK("SINK"), CONNECTION("CONNECTION"), WAIT("WAIT");

		public String name;

		private ConnectionType(String name)
		{
			this.name = name;
		}
	}

	private final ConnectionType connectionType;
	private final Task from;
	private final Task to;
	private final int cost;
	private double weight;

	/**
	 * Initialise a connection.
	 * 
	 * @param connectionType type of the connection
	 * @param from           start task of the connection
	 * @param to             end task of the connection
	 * @param cost           cost of the connection
	 * @param weight         weight of the connection
	 */
	public Connection(ConnectionType connectionType, Task from, Task to, int cost, double weight)
	{
		this.connectionType = connectionType;
		this.from = from;
		this.to = to;
		this.cost = cost;
		this.weight = weight;
	}

	/**
	 * Returns connection type.
	 * 
	 * @return connection type
	 */
	public ConnectionType getConnectionType()
	{
		return connectionType;
	}

	/**
	 * Returns start task of the connection.
	 * 
	 * @return start task of the connection
	 */
	public Task getFrom()
	{
		return from;
	}

	/**
	 * Returns end task of the connection.
	 * 
	 * @return end task of the connection
	 */
	public Task getTo()
	{
		return to;
	}

	/**
	 * Returns cost of the connection.
	 * 
	 * @return cost of the connection
	 */
	public int getCost()
	{
		return cost;
	}

	/**
	 * Returns start time of the connection. For source arcs, this equals the start
	 * time of the end task. For all other arcs, this equals the end time of the
	 * start task.
	 * 
	 * @return start time of the connection
	 */
	public int getStartTime()
	{
		if (connectionType.equals(ConnectionType.SOURCE))
		{
			return to.getStartTime();
		}
		return from.getEndTime();
	}

	/**
	 * Returns end time of the connection. For sink arcs, this equals the end time
	 * of the start task. For all other arcs, this equals the end time of the end
	 * task.
	 * 
	 * @return end time of the connection
	 */
	public int getEndTime()
	{
		if (connectionType.equals(ConnectionType.SINK))
		{
			return from.getEndTime();
		}
		return to.getEndTime();
	}

	/**
	 * Returns duration of the connection, defined as the difference in end and
	 * start time.
	 * 
	 * @return duration of the connection
	 */
	public int getDuration()
	{
		return getEndTime() - getStartTime();
	}

	/**
	 * Returns weight of the connection.
	 * 
	 * @return weight of the connection
	 */
	public double getWeight()
	{
		return weight;
	}

	/**
	 * Sets weight of the connection to specified value.
	 * 
	 * @param weight weight of the connection
	 */
	public void setWeight(double weight)
	{
		this.weight = weight;
	}

	/**
	 * Adds specified value to weight of the connection.
	 * 
	 * @param add value to be added to weight
	 */
	public void addWeight(double add)
	{
		this.weight += add;
	}

	@Override
	public int hashCode()
	{
		final int prime = 31;
		int result = 17;
		result = prime * result + ((from == null) ? 0 : from.hashCode());
		result = prime * result + ((to == null) ? 0 : to.hashCode());
		long bits = Double.doubleToLongBits(weight);
		result = prime * result + (int) (bits ^ (bits >>> 32));
		return result;
	}

	@Override
	public boolean equals(Object obj)
	{
		if (this == obj)
			return true;
		if (obj == null)
			return false;
		if (getClass() != obj.getClass())
			return false;
		Connection other = (Connection) obj;
		if (from == null)
		{
			if (other.from != null)
				return false;
		}
		else if (!from.equals(other.from))
			return false;
		if (to == null)
		{
			if (other.to != null)
				return false;
		}
		else if (!to.equals(other.to))
			return false;
		else if (weight != other.weight)
		{
			return false;
		}
		return true;
	}
}