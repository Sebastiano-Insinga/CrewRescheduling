package pricingProblem;

import java.util.List;

import columnGeneration.Duty;
import graph.Connection;
import graph.Connection.ConnectionType;
import graph.PricingGraph;
import ilog.concert.IloException;
import instance.Parameters;
import instance.Task;
import util.Pair;

/**
 * Abstract class to model a framework for any pricing problem solver. Each
 * solver should place duals on appropriate pricing graphs, and generate zero or
 * more duties. The class also contains some auxiliary functions, e.g. to
 * compute (reduced) costs.
 * 
 * @authors B.T.C. van Rossum
 */
public abstract class PricingProblemSolver
{
	protected List<Task> tasks;
	protected List<Integer> depots;

	/**
	 * Generates a, possibly empty, list of pairs of duties and their reduced cost.
	 * The reduced cost of each duty in the list should be negative.
	 * 
	 * @return a, possibly empty, list of pairs of duties and their reduced cost
	 */
	public abstract List<Pair<Duty, Double>> generateDuties();

	/**
	 * Returns the name of the pricing problem solver.
	 * 
	 * @return name of the pricing problem solver
	 */
	public abstract String getName();

	/**
	 * Ensures that the costs and duals are properly set on all pricing graphs used
	 * by the solver.
	 */
	public abstract void prepareGraphs() throws IloException;

	/**
	 * Place the duals, obtained from the restricted master problem, of the coverage
	 * constraint of each task on all incoming arcs of that task.
	 * 
	 * @param graph pricing graph
	 */
	protected void updateDuals(PricingGraph graph)
	{
		for (Task task : tasks)
		{
			for (Connection arc : graph.getInArcs(task))
			{
				if (!arc.getConnectionType().equals(ConnectionType.WAIT))
				{
					//System.out.println("T"+task.getID());
					arc.addWeight(task.getDual());
				}
			}
		}
	}

	/**
	 * Reset the weight of each connection to the cost of that connection, i.e.,
	 * remove all dual information.
	 * 
	 * @param graph pricing graph
	 */
	protected void resetCosts(PricingGraph graph)
	{
		for (Connection arc : graph.getArcs())
		{
			arc.setWeight(arc.getCost());
		}
	}

	/**
	 * Computes the reduced cost contribution of the start task, consisting of a
	 * fixed cost, variable cost, and the dual of this task.
	 * 
	 * @param startTask start task
	 * @return reduced cost contribution of the start task
	 */
	protected double getReducedCostStart(Task startTask)
	{
		double reducedCost = Parameters.FIXED_DUTY_COST + Parameters.VARIABLE_DUTY_COST * startTask.getDuration() + startTask.getDual();
		return reducedCost;
	}

	/**
	 * Computes the cost of a duty, consisting of a fixed cost and variable cost.
	 * 
	 * @param startTime start time of the duty
	 * @param endTime   end time of the duty
	 * @return cost of the duty
	 */
	protected int computeCost(int startTime, int endTime)
	{
		return Parameters.FIXED_DUTY_COST + Parameters.VARIABLE_DUTY_COST * (endTime - startTime);
	}

	/**
	 * Computes the end time of the duty by finding the maximum end time of all
	 * non-sink tasks in the duty.
	 * 
	 * @param tasks list of tasks in the duty
	 * @return end time of the duty
	 */
	protected int computeEndTime(List<Task> tasks)
	{
		int endTime = 0;
		for (Task task : tasks)
		{
			// The source and sink have negative ID.
			if (task.getID() >= 0 && task.getEndTime() > endTime)
			{
				endTime = task.getEndTime();
			}
		}
		return endTime;
	}
}
