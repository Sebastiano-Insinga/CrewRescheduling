package graph;

import java.util.List;

import graph.Connection.ConnectionType;
import instance.Parameters;
import instance.Task;

/**
 * Class that contains method to initialise pricing graphs.
 * 
 * @author B.T.C. van Rossum
 */
public class GraphConstructor
{
	/**
	 * Adds connection between all pairs of tasks in the graph that can be performed
	 * consecutively.
	 * 
	 * @param graph pricing graph
	 * @param tasks list of tasks in the graph
	 */
	public static void addTaskConnections(PricingGraph graph, List<Task> tasks)
	{
		// Add connections between tasks.
		for (Task from : tasks)
		{
			for (Task to : tasks)
			{
				/* Check :se la stazione di fine di un task è uguale alla stazione di inizio 
				 * del task successivo
				 * and times match = start time del task è maggiore dell'end time 
				 * del successivo
				 */
				if (stationsMatch(from, to) && timesMatch(from, to))
				{
					/*Add a connection.
					 *  Parameters.VARIABLE_DUTY_COST è un costo predefinito (tipo costo orario)
					 *  definito nella classe Parameter.java
					 */
					int variableCost = (to.getEndTime() - from.getEndTime()) * Parameters.VARIABLE_DUTY_COST;
					graph.addArc(ConnectionType.CONNECTION, from, to, variableCost, variableCost);
				}
			}
		}
	}

	/**
	 * Adds a virtual source task to the graph, representing a specified depot.
	 * 
	 * @param graph pricing graph
	 * @param depot depot
	 */
	public static void addSource(PricingGraph graph, int depot)
	{
		// Add a source che ha come startStation e come endStation lo stesso depot
		Task source = new Task(-1, 0, 0, depot, depot);
		graph.addNode(source);
	}

	/**
	 * Adds a virtual sink task to the graph, representing a specified depot.
	 * 
	 * @param graph pricing graph 
	 * 
	 * @param depot depot
	 */
	public static void addSink(PricingGraph graph, int depot)
	{
		// Add sink.
		int latestEndTime = Parameters.MAX_START_TIME + Parameters.MAX_TASK_LENGTH + Parameters.MIN_TRANSITION_TIME;
		Task sink = new Task(-2, latestEndTime, latestEndTime, depot, depot);
		graph.addNode(sink);
	}

	/**
	 * Adds tasks to the pricing graph.
	 * 
	 * @param graph pricing graph
	 * @param tasks list of tasks
	 */
	public static void addTasks(PricingGraph graph, List<Task> tasks)
	{
		for (Task task : tasks)
		{
			graph.addNode(task);
		}
	}

	/**
	 * Adds source and sink connections to all tasks in the graph that start or end
	 * at one of the specified depots.
	 * 
	 * @param graph  pricing graph
	 * @param depots list of depots
	 */
	public static void addSourceSinkConnections(PricingGraph graph, List<Integer> depots)
	{
		/* Add source and sink connections.
		 * Implicitamente sa che nella prima e nell'ultima posizione della lista dei nodi che appartengono
		 * ad un grafo trova il node SOURCE e il node SINK
		 */
		Task source = graph.getNodes().get(0);
		Task sink = graph.getNodes().get(graph.getNumberOfNodes() - 1);
		
		/*
		 * 
		 */
		
		for (int i = 1; i < graph.getNumberOfNodes() - 1; i++)
		{
			Task task = graph.getNodes().get(i);

			/*
			 *  verifica se il numero che identifica la stazione di inizio del Task è presente nella lista dei numeri che 
			 *  identificano i depot.
				Se i numeri corrispondono, significa che il Task in questione inizia in una stazione che è anche un depot, 
				e quindi può essere il primo Task di una Duty che parte da quella specifica base.
			 */
			if (depots.contains(task.getStartStation()))
			{
				int cost = Parameters.VARIABLE_DUTY_COST * task.getDuration();
				graph.addArc(ConnectionType.SOURCE, source, task, cost, cost);
			}

			// From task to sink.
			if (depots.contains(task.getEndStation()))
			{
				graph.addArc(ConnectionType.SINK, task, sink, 0, 0);
			}
		}
	}

	/**
	 * Adds source and sink connections to all tasks in the graph that start or end
	 * at the depot specified by the source and sink node.
	 * 
	 * @param graph pricing graph
	 */
	public static void addSourceSinkConnections(PricingGraph graph)
	{
		// Add source and sink connections.
		Task source = graph.getNodes().get(0);
		Task sink = graph.getNodes().get(graph.getNumberOfNodes() - 1);
		for (int i = 1; i < graph.getNumberOfNodes() - 1; i++)
		{
			Task task = graph.getNodes().get(i);

			// From source to task.
			if (task.getStartStation() == source.getEndStation())
			{
				int cost = Parameters.VARIABLE_DUTY_COST * task.getDuration();
				graph.addArc(ConnectionType.SOURCE, source, task, cost, cost);
			}

			// From task to sink.
			if (task.getEndStation() == sink.getStartStation())
			{
				graph.addArc(ConnectionType.SINK, task, sink, 0, 0);
			}
		}
	}

	/**
	 * Adds a waiting arc from each task to the first next task that ends at the
	 * same station, if any.
	 * 
	 * @param graph pricing graph
	 * @param tasks list of tasks
	 */
	public static void addWaitingArcs(PricingGraph graph, List<Task> tasks)
	{
		for (Task task : tasks)
		{
			task.getID();
			// Add connections representing waiting at stations. This is a connection to the
			// first other task arriving at the same station, with maximal start time.
			Task minWaitTask = null;
			for (Task wait : tasks)
			{
				if (wait.equals(task))
				{
					//se sono lo stesso task non viene creata
					continue;
				}
				if (task.getEndStation() != wait.getEndStation())
				{
					//se hanno stazioni diverse si continua
					continue;
				}
				if (task.getEndTime() > wait.getEndTime())
				{
					//endTime del task di riferimento è maggiore del task che stiamo considerando si continua
					continue;
				}
				if (task.getEndTime() == wait.getEndTime() && task.getID() > wait.getID())
				//if (task.getEndTime() == wait.getEndTime())
				{
					continue;
				}
				if (minWaitTask == null)
				{
					minWaitTask = wait;
				}
				/*
				 * cerca il task con un startTime quanto più vicino possibile all'endTime  
				 */
				
				if (dominatesWaitingTask(wait, minWaitTask))
				{
					minWaitTask = wait;
				}
			
			}

			if (minWaitTask != null)
			{
				int variableCost = (minWaitTask.getEndTime() - task.getEndTime()) * Parameters.VARIABLE_DUTY_COST;
				graph.addArc(ConnectionType.WAIT, task, minWaitTask, variableCost, variableCost);
				//System.out.println("Generazione del WaitingArc tra : "+ "T"+task.getID()+"T"+minWaitTask.getID());
			}
		}
	}

	/**
	 * Adds an incoming performing arc to each task, from the latest other task
	 * ending at the start station of the task, if any such task exists.
	 * 
	 * @param graph pricing graph
	 * @param tasks list of tasks
	 */
	public static void addPerformingArcs(PricingGraph graph, List<Task> tasks)
	{
		for (Task task : tasks)
		{
			// Add connections representing a task being performed. This is a connection to
			// latest task at the start station before departure.
			Task maxStartTask = null;
			for (Task start : tasks)
			{
				if (stationsMatch(start, task) && timesMatch(start, task))
				{
					if (maxStartTask == null)
					{
						maxStartTask = start;
					}
					/*
					 * crea un collegamento con il nodo con l'endTime() più alto possibile rispetto a quel task
					 * per ogni task abbiamo questo collegamento 
					 */
					else if (dominatesConnectionTask(start, maxStartTask))
					{
						maxStartTask = start;
					}
				}
			}

			if (maxStartTask != null)
			{
				int variableCost = (task.getEndTime() - maxStartTask.getEndTime()) * Parameters.VARIABLE_DUTY_COST;
				graph.addArc(ConnectionType.CONNECTION, maxStartTask, task, variableCost, variableCost);
				System.out.println("Creation Performing_Arc from "+ "T"+maxStartTask.getID()+",T"+task.getID());
			}
			
		}
	}

	/*
	 * Override addPerfomingArcs 
	 */
	public static void addPerformingArcs1(PricingGraph graph, List<Task> tasks)
	{
		for (Task to : tasks)
		{
			for (Task from : tasks)
			{
				// 1. Stessa Stazione (Come confermato dal validatore, niente deadheading)
				if (stationsMatch(from, to)) 
				{
					// 2. Controllo Temporale (Usa <= per accettare gap 0)
					if (timesMatch(from, to))
					{
						// ELIMINATA LA LOGICA DI DOMINANZA (maxStartTask)
						// Creiamo l'arco per OGNI coppia valida.
						
						int variableCost = (to.getEndTime() - from.getEndTime()) * Parameters.VARIABLE_DUTY_COST;
						graph.addArc(ConnectionType.CONNECTION, from, to, variableCost, variableCost);
					}
				}
			}
		}
	}
	/**
	 * Returns true when task a precedes task b in the topological sorting, and is
	 * therefore a more appropriate candidate for a waiting arc.
	 * 
	 * @param a task a
	 * @param b task b
	 * @return true when task a precedes task b in the topological sorting
	 */
	private static boolean dominatesWaitingTask(Task a, Task b)
	{
		if (a.getEndTime() < b.getEndTime())
		{
			return true;
		}
		else if (a.getEndTime() == b.getEndTime())
		{
			if (a.getID() < b.getID())
			{
				return true;
			}
		}
		return false;
	}

	/**
	 * Returns true when task a succeeds task b in the topological sorting, and is
	 * therefore a more appropriate candidate for a task performing arc.
	 * 
	 * @param a task a
	 * @param b task b
	 * @return true when task a succeeds task b in the topological sorting
	 */
	private static boolean dominatesConnectionTask(Task a, Task b)
	{
		if (a.getEndTime() > b.getEndTime())
		{
			return true;
		}
		else if (a.getEndTime() == b.getEndTime())
		{
			if (a.getID() > b.getID())
			{
				return true;
			}
		}
		return false;
	}

	/**
	 * Returns true when task from ends at the start station of task to.
	 * 
	 * @param from task from
	 * @param to   task to
	 * @return true when task from ends at the start station of task to
	 */
	private static boolean stationsMatch(Task from, Task to)
	{
		return from.getEndStation() == to.getStartStation();
	}

	/**
	 * Returns true when task to does not start before the end time of from plus the
	 * minimum transition time between tasks.
	 * 
	 * @param from task form
	 * @param to   task to
	 * @return true when task to does not start before the end time of from plus the
	 *         minimum transition time between tasks
	 */
	private static boolean timesMatch(Task from, Task to)
	{
		return from.getEndTime() + Parameters.MIN_TRANSITION_TIME <= to.getStartTime();
	}

	public static PricingGraph createPricingGraph(List<Task> tasks, int minTransitionTime) {
		// TODO Auto-generated method stub
		return null;
	}
}
