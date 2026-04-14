package pricingProblem;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;

import columnGeneration.Duty;
import graph.Connection;
import graph.GraphConstructor;
import graph.PricingGraph;
import graph.ShortestPath;
import instance.Instance;
import instance.Parameters;
import instance.Task;
import util.Pair;

/**
 * Implementation of the O(|N|^3) pricing problem algorithm. The algorithm
 * proceeds by solving a series of SSSPPs and then iterating over all
 * combinations of start and post-break task. For each combination, an optimal
 * pre-break task and end task are found.
 * 
 * @author B.T.C. van Rossum
 */
public class CubicBreak extends PricingProblemSolver
{
	private final PricingGraph graph;

	/**
	 * Initialise the solver for a given instance of the crew scheduling problem.
	 * 
	 * @param instance instance of the crew scheduling problem
	 */
	public CubicBreak(Instance instance)
	{
		this.tasks = instance.getTasks();
		this.depots = instance.getDepots();
		this.graph = createGraph();
	}

	/**
	 * Construct a regular task graph.
	 * 
	 * @return task graph
	 */
	private PricingGraph createGraph()
	{
		PricingGraph graph = new PricingGraph();
		GraphConstructor.addTasks(graph, tasks);
		GraphConstructor.addTaskConnections(graph, tasks);
		return graph;
	}

	@Override
	public String getName()
	{
		return "CubicBreak";
	}

	@Override
	public List<Pair<Duty, Double>> generateDuties()
	{
		// Initialise duties.
		List<Pair<Duty, Double>> duties = new ArrayList<>();

		// Solve SPP for each start task and end task.
		Map<Task, ShortestPath> startTaskMap = new LinkedHashMap<>();
		Map<Task, ShortestPath> endTaskMap = new LinkedHashMap<>();
		for (Task task : tasks)
		{
			if (depots.contains(task.getStartStation()))
			{
				startTaskMap.put(task,
						new ShortestPath(graph, task, true, task.getStartTime() + Parameters.MAX_DUTY_LENGTH));
			}
			if (depots.contains(task.getEndStation()))
			{
				endTaskMap.put(task,
						new ShortestPath(graph, task, false, task.getEndTime() - Parameters.MAX_TIME_WITHOUT_BREAK));
			}
		}

		// Iterate.
		for (Entry<Task, ShortestPath> entry : startTaskMap.entrySet())
		{
			Task startTask = entry.getKey();
			ShortestPath startSPP = entry.getValue();

			for (int j = startTask.getNodeIndex() + 1; j < tasks.size(); j++)
			{
				Task postBreakTask = tasks.get(j);

				Pair<Task, Double> bestPreBreakTask = new Pair<>(null, Double.MAX_VALUE);
				Pair<Task, Double> bestEndTask = new Pair<>(null, Double.MAX_VALUE);

				// Skip if no path exists.
				if (!startSPP.containsPath(postBreakTask))
				{
					continue;
				}

				// Find pre-break task.
				for (Connection arc : graph.getInArcs(postBreakTask))
				{
					Task preBreakTask = arc.getFrom();

					// Skip if no break possible.
					if (postBreakTask.getStartTime() - preBreakTask.getEndTime() < Parameters.MIN_BREAK_LENGTH)
					{
						continue;
					}

					// Skip if break takes place too late.
					if (startTask.getStartTime() + Parameters.MAX_TIME_WITHOUT_BREAK < preBreakTask.getEndTime())
					{
						continue;
					}

					// Update best found.
					double distance = arc.getWeight() + startSPP.getDistance(preBreakTask);
					bestPreBreakTask = (distance < bestPreBreakTask.getValue()) ? new Pair<>(preBreakTask, distance)
							: bestPreBreakTask;
					 //if distance of new candidate is less than distance found before we upload 
				}

				// Skip if no pre-break task is found.
				if (bestPreBreakTask.getKey() == null)
				{
					continue;
				}

				// Find end task.
				int maxEndTime = Math.min(startTask.getStartTime() + Parameters.MAX_DUTY_LENGTH,
						postBreakTask.getStartTime() + Parameters.MAX_TIME_WITHOUT_BREAK);
				for (int k = j; k < tasks.size(); k++)
				{
					// Check whether depots match.
					Task endTask = tasks.get(k);
					/*
					if (endTask.getEndStation() != startTask.getStartStation())
					{
						continue;
					}
					 */
					// Check end time.
					if (endTask.getEndTime() > maxEndTime)
					{
						continue;
					}

					// Update best found.
					double distance = endTaskMap.get(endTask).getDistance(postBreakTask);
					bestEndTask = (distance < bestEndTask.getValue()) ? new Pair<>(endTask, distance) : bestEndTask;
				}

				if (bestEndTask.getKey() == null)
				{
					continue;
				}

				// Compute reduced cost.
				double reducedCost = getReducedCostStart(startTask)
						+ bestPreBreakTask.getValue()
						+ bestEndTask.getValue();

				// Reduced cost criterion.
				if (reducedCost < -Parameters.PRECISION)
				{
					List<Task> tasks = startSPP.getPath(bestPreBreakTask.getKey());
					tasks.addAll(endTaskMap.get(bestEndTask.getKey()).getPath(postBreakTask));

					int cost = computeCost(startTask.getStartTime(), bestEndTask.getKey().getEndTime());
					duties.add(new Pair<>(new Duty(cost, tasks), reducedCost));
				}
			}
		}
		return duties;
	}

	@Override
	public void prepareGraphs()
	{
		resetCosts(graph);
		updateDuals(graph);
	}
}
