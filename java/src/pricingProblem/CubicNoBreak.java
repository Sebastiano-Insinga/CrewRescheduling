package pricingProblem;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

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
 * Implementation of the O(|N|^3) pricing problem algorithm for the pricing
 * problem without breaks. The algorithm proceeds by solving SSSPP for each
 * start task.
 * 
 * @author B.T.C. van Rossum
 */
public class CubicNoBreak extends PricingProblemSolver
{
	private final Map<Integer, PricingGraph> depotGraphMap;

	/**
	 * Initialise the solver for a given instance of the crew scheduling problem.
	 * 
	 * @param instance instance of the crew scheduling problem
	 */
	public CubicNoBreak(Instance instance)
	{
		this.tasks = instance.getTasks();
		this.depots = instance.getDepots();
		this.depotGraphMap = new LinkedHashMap<>();
		for (int depot : depots)
		{
			depotGraphMap.put(depot, createGraph(depot));
		}
	}

	/**
	 * Create a regular task graph with source and sink nodes for a specific depot.
	 * 
	 * @param depot depot
	 * @return task graph with source and sink nodes for the specific depot
	 */
	private PricingGraph createGraph(int depot)
	{
		PricingGraph graph = new PricingGraph();
		GraphConstructor.addSource(graph, depot);
		GraphConstructor.addTasks(graph, tasks);
		GraphConstructor.addSink(graph, depot);
		GraphConstructor.addSourceSinkConnections(graph);
		GraphConstructor.addTaskConnections(graph, tasks);
		return graph;
	}

	@Override
	public String getName()
	{
		return "CubicNoBreak";
	}

	@Override
	public List<Pair<Duty, Double>> generateDuties()
	{
		// Initialise duties.
		List<Pair<Duty, Double>> duties = new ArrayList<>();

		// Iterate over depots.
		for (int depot : depots)
		{
			PricingGraph graph = depotGraphMap.get(depot);
			Task source = graph.getNodes().get(0);
			Task sink = graph.getNodes().get(graph.getNumberOfNodes() - 1);

			for (Connection sourceArc : graph.getOutArcs(source))
			{
				Task startTask = sourceArc.getTo();
				ShortestPath shortestPath = new ShortestPath(graph, startTask, true,
						startTask.getStartTime() + Parameters.MAX_DUTY_LENGTH);

				// Compute reduced cost.
				double reducedCost = getReducedCostStart(startTask) + shortestPath.getDistance(sink);

				// Reduced cost criterion.
				if (reducedCost < -Parameters.PRECISION)
				{
					List<Task> tasks = shortestPath.getPath(sink);
					int cost = computeCost(startTask.getEndTime(), computeEndTime(tasks));
					duties.add(new Pair<>(new Duty(cost, tasks), reducedCost));
				}
			}
		}
		return duties;
	}

	@Override
	public void prepareGraphs()
	{
		for (int depot : depots)
		{
			resetCosts(depotGraphMap.get(depot));
			updateDuals(depotGraphMap.get(depot));
		}
	}
}
