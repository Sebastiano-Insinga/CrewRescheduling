package pricingProblem;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedList;
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
import util.BinarySearch;
import util.Pair;
import util.TaskComparator;

/**
 * Implementation of the O(|D| |N|^2 log |N|) pricing problem algorithm.
 * 
 * @author B.T.C. van Rossum
 */
public class QuadraticLogBreak extends PricingProblemSolver
{
	private final PricingGraph graph;
	private final Map<Task, Map<Task, Task>> breakTaskMap;
	private final List<Task> postBreakTasks;

	/**
	 * Initialise the solver for a given instance of the crew scheduling problem.
	 * 
	 * @param instance instance of the crew scheduling problem
	 */
	public QuadraticLogBreak(Instance instance)
	{
		this.tasks = instance.getTasks();
		this.depots = instance.getDepots();
		this.graph = createGraph();

		this.breakTaskMap = new LinkedHashMap<>();
		this.postBreakTasks = new ArrayList<>();

		initialiseBreakTaskMap(instance.getTasks());
	}

	/**
	 * Construct a linearly sized time-space network.
	 * 
	 * @param instance instance of the crew scheduling problem
	 */
	private PricingGraph createGraph()
	{
		PricingGraph graph = new PricingGraph();
		GraphConstructor.addSource(graph, -1);
		GraphConstructor.addTasks(graph, tasks);
		GraphConstructor.addSink(graph, -1);
		GraphConstructor.addSourceSinkConnections(graph, depots);
		GraphConstructor.addWaitingArcs(graph, tasks);
		GraphConstructor.addPerformingArcs(graph, tasks);
		return graph;
	}
	
	public PricingGraph getGraph()
	{
		return graph;
	}

	@Override
	public String getName()
	{
		return "QuadraticLogBreakTwo";
	}

	/**
	 * For each start task, compute the list of sufficient combinations of pre- and
	 * post-break task.
	 * 
	 * @param tasks list of tasks
	 */
	private void initialiseBreakTaskMap(List<Task> tasks)
	{
		// Sort tasks by end station.
		Map<Integer, List<Task>> tasksByEndStation = new LinkedHashMap<>();
		for (Task task : tasks)
		{
			if (!tasksByEndStation.containsKey(task.getEndStation()))
			{
				tasksByEndStation.put(task.getEndStation(), new ArrayList<>());
			}
			tasksByEndStation.get(task.getEndStation()).add(task);
		}

		// Sort all lists by end time.
		for (List<Task> taskList : tasksByEndStation.values())
		{
			taskList.sort(new TaskComparator());
		}

		// Find optimal pre-break tasks.
		for (Connection sourceArc : graph.getOutArcs(graph.getNodes().get(0)))
		{
			Task startTask = sourceArc.getTo();
			breakTaskMap.put(startTask, new LinkedHashMap<>());

			// Solve a SPP to obtain reachability.
			ShortestPath shortestPath = new ShortestPath(graph, startTask, true,
					startTask.getEndTime() + Parameters.MAX_TIME_WITHOUT_BREAK);

			// Iterate over potential post-break tasks.
			for (Task postBreakTask : tasks)
			{
				// Duty length criterion.
				if (postBreakTask.getEndTime() > startTask.getStartTime() + Parameters.MAX_DUTY_LENGTH)
				{
					continue;
				}

				// Find optimal pre-break task.
				List<Task> preBreakTasks = tasksByEndStation.get(postBreakTask.getStartStation());
				int maxTime = Math.min(startTask.getStartTime() + Parameters.MAX_TIME_WITHOUT_BREAK,
						postBreakTask.getStartTime() - Parameters.MIN_BREAK_LENGTH);
				int optimalPreBreakIndex = BinarySearch.binarySearch(preBreakTasks,
						maxTime);

				// No such pre-break task exists.
				if (optimalPreBreakIndex == -1)
				{
					continue;
				}

				// The pre-break task is not reachable from the start task.
				if (!shortestPath.containsPath(preBreakTasks.get(optimalPreBreakIndex)))
				{
					continue;
				}

				breakTaskMap.get(startTask).put(postBreakTask, preBreakTasks.get(optimalPreBreakIndex));
				if (!postBreakTasks.contains(postBreakTask))
				{
					postBreakTasks.add(postBreakTask);
				}
			}
		}
	}

	@Override
	public List<Pair<Duty, Double>> generateDuties()
	{
		// Initialise duties.
		List<Pair<Duty, Double>> duties = new ArrayList<>();

		// Solve SPP for each start and post break task.
		Map<Task, ShortestPath> shortestPathMap = createShortestPathMap(graph);

		// Construct function mapping for each post-break task and depot.
		Map<Task, Map<Integer, List<Pair<Task, Double>>>> postBreakFunctionMap = createFunctionMap(graph,
				shortestPathMap);

		// Loop to construct duties.
		for (Pair<Duty, Double> duty : createDuties(graph, shortestPathMap, postBreakFunctionMap))
		{
			duties.add(duty);
		}
		return duties;
	}

	/**
	 * Solve a SSSPPs for each start task and each post-break task.
	 * 
	 * @param graph pricing graph
	 * @return map containing the solution to a SSSPP for each start task and each
	 *         post-break task
	 */
	private Map<Task, ShortestPath> createShortestPathMap(PricingGraph graph)
	{
		// Solve SPP for each start and post break task.
		Map<Task, ShortestPath> shortestPathMap = new LinkedHashMap<>();
		for (Connection sourceArc : graph.getOutArcs(graph.getNodes().get(0)))
		{
			Task startTask = sourceArc.getTo();
			shortestPathMap.put(startTask,
					new ShortestPath(graph, startTask, true,
							startTask.getStartTime() + Parameters.MAX_TIME_WITHOUT_BREAK));
		}
		for (Task postBreakTask : postBreakTasks)
		{
			if (!shortestPathMap.containsKey(postBreakTask))
			{
				shortestPathMap.put(postBreakTask, new ShortestPath(graph, postBreakTask, true,
						postBreakTask.getStartTime() + Parameters.MAX_TIME_WITHOUT_BREAK));
			}
		}
		return shortestPathMap;
	}

	/**
	 * Construct a mapping function for each combination of post-break task and
	 * depot.
	 * 
	 * @param graph           pricing graph
	 * @param shortestPathMap map containing the solutions to SSSPPs from each
	 *                        post-break task
	 * @return map containing, for each combination of post-break task and depot, a
	 *         mapping function
	 */
	private Map<Task, Map<Integer, List<Pair<Task, Double>>>> createFunctionMap(PricingGraph graph,
			Map<Task, ShortestPath> shortestPathMap)
	{
		Map<Task, Map<Integer, List<Pair<Task, Double>>>> postBreakFunctionMap = new LinkedHashMap<>();
		for (Task postBreakTask : postBreakTasks)
		{
			// Add mapping entry.
			postBreakFunctionMap.put(postBreakTask, new LinkedHashMap<>());

			// Initialise depot mapping.
			Map<Integer, List<Pair<Task, Double>>> endTasksPerDepot = new LinkedHashMap<>();
			for (int depot : depots)
			{
				endTasksPerDepot.put(depot, new ArrayList<>());
			}

			// Construct sorted list of end tasks.
			for (Connection sinkArc : graph.getInArcs(graph.getNodes().get(graph.getNumberOfNodes() - 1)))
			{
				Task endTask = sinkArc.getFrom();
				if (shortestPathMap.get(postBreakTask).containsPath(endTask))
				{
					endTasksPerDepot.get(endTask.getEndStation())
									.add(new Pair<>(endTask, shortestPathMap.get(postBreakTask).getDistance(endTask)));
				}
			}

			// Construct function for each depot.
			for (int depot : depots)
			{
				// Sort endtasks.
				List<Pair<Task, Double>> endTasks = endTasksPerDepot.get(depot);
				endTasks.sort(
						(Pair<Task, Double> a, Pair<Task, Double> b) -> Double.compare(a.getValue(), b.getValue()));

				// Construct mapping function.
				LinkedList<Pair<Task, Double>> linkedFunction = new LinkedList<>();
				int lastTime = Integer.MAX_VALUE;
				for (int i = 0; i < endTasks.size(); i++)
				{
					Pair<Task, Double> pair = endTasks.get(i);
					if (pair.getKey().getEndTime() < lastTime)
					{
						linkedFunction.addFirst(pair);
						lastTime = pair.getKey().getEndTime();
					}
				}
				List<Pair<Task, Double>> function = new ArrayList<>(linkedFunction);
				postBreakFunctionMap.get(postBreakTask).put(depot, function);
			}
		}
		return postBreakFunctionMap;
	}

	/**
	 * Create duties by iterating over all combinations of start and post-break
	 * task, and finding the optimal end task through the mapping function.
	 * 
	 * @param graph                pricing graph
	 * @param shortestPathMap      map containing the solutions to SSSPPs from each
	 *                             start task
	 * @param postBreakFunctionMap map containing, for each combination of
	 *                             post-break task and depot, a mapping function
	 * @return list of pairs of duty and reduced cost
	 */
	private List<Pair<Duty, Double>> createDuties(PricingGraph graph, Map<Task, ShortestPath> shortestPathMap,
			Map<Task, Map<Integer, List<Pair<Task, Double>>>> postBreakFunctionMap)
	{
		LinkedList<Pair<Duty, Double>> duties = new LinkedList<>();
		for (Connection sourceArc : graph.getOutArcs(graph.getNodes().get(0)))
		{
			Task startTask = sourceArc.getTo();
			for (Entry<Task, Task> breakEntry : breakTaskMap.get(startTask).entrySet())
			{
				Task preBreakTask = breakEntry.getValue();
				Task postBreakTask = breakEntry.getKey();

				int maxEndTime = Math.min(startTask.getStartTime() + Parameters.MAX_DUTY_LENGTH,
						postBreakTask.getStartTime() + Parameters.MAX_TIME_WITHOUT_BREAK);
				List<Pair<Task, Double>> function = postBreakFunctionMap.get(postBreakTask)
																		.get(startTask.getStartStation());
				if (function.size() == 0)
				{
					continue;
				}

				int optimalEndTaskIndex = BinarySearch.binarySearchPair(function,
						maxEndTime);
				if (optimalEndTaskIndex == -1)
				{
					continue;
				}

				// Compute reduced cost.
				Pair<Task, Double> endTaskPair = function.get(optimalEndTaskIndex);
				double reducedCost = getReducedCostStart(startTask)
						+ shortestPathMap.get(startTask).getDistance(preBreakTask)
						+ Parameters.VARIABLE_DUTY_COST
								* (postBreakTask.getEndTime() - preBreakTask.getEndTime())
						+ postBreakTask.getDual()
						+ endTaskPair.getValue();

				// Reduced cost criterion.
				if (reducedCost < -Parameters.PRECISION)
				{
					List<Task> tasks = shortestPathMap.get(startTask).getPath(preBreakTask);
					tasks.addAll(shortestPathMap.get(postBreakTask).getPath(endTaskPair.getKey()));

					int cost = computeCost(startTask.getStartTime(), endTaskPair.getKey().getEndTime());
					duties.addFirst(new Pair<>(new Duty(cost, tasks), reducedCost));
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
