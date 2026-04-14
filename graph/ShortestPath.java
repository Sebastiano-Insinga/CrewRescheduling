package graph;

import java.util.ArrayList;
import java.util.List;

import graph.Connection.ConnectionType;
import instance.Task;

/**
 * Implementation of a dynamic programming algorithm to compute single-source
 * shortest paths in a directed acyclic graph, potentially incorporating a
 * minimum or maximum allowed time.
 * 
 * @author B.T.C. van Rossum
 */
public class ShortestPath
{
	private Task origin;

	private final int numNodes;
	private final int timeLimit;

	private double[] distances;
	private Connection[] predecessors;
	private final boolean forwardDirection;

	/**
	 * Initialise distance and predecessor maps, and then compute the shortest path
	 * from origin to destination, only using arcs whose start and end time fall
	 * within the determined time limit.
	 * 
	 * @param graph            directed acyclic graph which we assume to be
	 *                         topologically sorted
	 * @param origin           origin node
	 * @param forwardDirection whether we move in forward direction or not
	 * @param timeLimit        maximum or minimum allowed time
	 */
	public ShortestPath(PricingGraph graph, Task origin, boolean forwardDirection, int timeLimit)
	{
		this.origin = origin;
		this.forwardDirection = forwardDirection;

		this.timeLimit = timeLimit;
		this.numNodes = graph.getNumberOfNodes();

		graph.setNodeIndices();
		initialiseArrays(graph);
		updateDistances(graph);
		
	}

	/**
	 * Returns distance from origin to target node.
	 * 
	 * @param target target node
	 * @return distance from origin to target
	 */
	public double getDistance(Task target)
	{
		return distances[target.getNodeIndex()];
	}

	/**
	 * Returns true when a path from origin to target exists.
	 * 
	 * @param target target node
	 * @return true when a path from origin to target exists
	 */
	public boolean containsPath(Task target)  //controllo dell'esistenza di un cammino
	{
		return distances[target.getNodeIndex()] < Double.MAX_VALUE;
	}

	/**
	 * Returns the path, defined as list of tasks, from target to origin. The path
	 * is obtained by backtracking.
	 * 
	 * @param target target node
	 * @return path from target to origin
	 */
	public List<Task> getPath(Task target)   //restituisce la lista di nodi che compongono il cammino minimo
	{
		List<Task> path = new ArrayList<>();

		// When target equals origin, the path consists of a single task.
		if (target.equals(origin))
		{
			path.add(target);
			return path;
		}

		// Retrieve the first connection used in the path.
		Connection connection = predecessors[target.getNodeIndex()];

		// Ensure that the target node is added.
		if (!forwardDirection)
		{
			path.add(target);
		}

		while (true)
		{
			// Process connection. We do not add tasks of waiting connections, since these
			// tasks are not actually performed.
			if (!connection.getConnectionType().equals(ConnectionType.WAIT))
			{
				path.add(connection.getTo());
			}

			// Stopping criterion.
			Task next = forwardDirection ? connection.getFrom() : connection.getTo();
			boolean stop = next.equals(origin);
			if (stop)
			{
				// Ensure that the origin node is added.
				if (forwardDirection)
				{
					path.add(origin);
				}
				break;
			}

			// Update connection.
			connection = predecessors[next.getNodeIndex()];
		}
		return path;
	}
	/**
	 * Returns the path, defined as list of tasks, from target to origin.
	 * MODIFIED: Adds ALL tasks, including those reached via WAIT arcs.
	 * * @param target target node
	 * @return path from target to origin
	 */
	/*public List<Task> getPath(Task target)
	{
		List<Task> path = new ArrayList<>();

		// When target equals origin, the path consists of a single task.
		if (target.equals(origin))
		{
			path.add(target);
			return path;
		}

		// Retrieve the first connection used in the path.
		Connection connection = predecessors[target.getNodeIndex()];

		// Ensure that the target node is added.
		if (!forwardDirection)
		{
			path.add(target);
		}
		while (true)
		{
			// MODIFICA CRUCIALE: Rimosso il controllo if (!WAIT).
			// Aggiungiamo SEMPRE il task, perché in questo grafo i nodi sono Task reali.
			path.add(connection.getTo());

			// Stopping criterion.
			Task next = forwardDirection ? connection.getFrom() : connection.getTo();
			boolean stop = next.equals(origin);
			if (stop)
			{
				// Ensure that the origin node is added.
				if (forwardDirection)
				{
					path.add(origin);
				}
				break;
			}

			// Update connection.
			connection = predecessors[next.getNodeIndex()];
		}
		return path;
	}
	/**
	 * Initialise a distance array and predecessor array for all tasks in the graph.
	 * The distance is initialised to zero for the origin and to plus inifinity for
	 * all other tasks.
	 * 
	 * @param graph pricing graph
	 */
	private void initialiseArrays(PricingGraph graph)
	{
		this.predecessors = new Connection[numNodes];
		this.distances = new double[numNodes];

		for (int i = 0; i < numNodes; i++)
		{
			predecessors[i] = null;
			distances[i] = Double.MAX_VALUE;
		}

		distances[origin.getNodeIndex()] = 0;
	}

	/**
	 * Perform the dynamic programming algorithm by iteratively processing all arcs
	 * in the pricing graph, until the time limit is reached.
	 * 
	 * @param graph pricing graph
	 */
	private void updateDistances(PricingGraph graph)  //gestione delle distanze tra i vari nodi
	{
		if (forwardDirection)
		{
			for (int i = origin.getNodeIndex(); i < numNodes; i++)
			{
				Task node = graph.getNodes().get(i);

				// Check whether time limit is exceeded by all remaining nodes.
				if (node.getEndTime() > timeLimit)
				{
					break;
				}

				for (Connection arc : graph.getOutArcs(node))
				{
					/*
					 * Check whether time limit is exceeded by arc.
					 *  Time limit è un parametro che viene passato al costruttore di SSP, nel caso di InitaliseBreakTaskMap
					 *  timeLimit = duty without break
					 */
					if (arc.getEndTime() > timeLimit)
					{
						continue;
					}
					processArc(node, arc.getTo(), arc);
					/*
					 * confronta la distanza dal node che stiamo considerando con la distanza da un nodo from e vede la migliore
					 */
				}
			}
		}
		else
		{
			for (int i = origin.getNodeIndex(); i >= 0; i--)
			{
				Task node = graph.getNodes().get(i);

				// Check whether time limit is exceeded by all remaining nodes.
				if (node.getEndTime() < timeLimit)
				{
					break;
				}

				for (Connection arc : graph.getInArcs(node))
				{
					// Check whether time limit is exceeded by arc.
					if (arc.getStartTime() < timeLimit)
					{
						continue;
					}
					processArc(node, arc.getFrom(), arc);
				}
			}
		}
	}

	/**
	 * Process a connection between task from and task to.
	 * 
	 * @param from task from
	 * @param to   task to
	 * @param arc  connection between from and to
	 */
	private void processArc(Task from, Task to, Connection arc) //tiene conto dei percorsi migliori per andare da un nodo all'altro
	{
		/*
		 * Se il costo per arrivare al nodo to passando dal nodo from è inferiore al costo del percorso più breve 
		 * trovato fino a quel momento per raggiungere to, 
		 * allora l'algoritmo aggiorna il costo [distances] e memorizza il nuovo percorso [arc]
		 */
		double distance = arc.getWeight();
		if (distances[from.getNodeIndex()] + distance < distances[to.getNodeIndex()])
		{
			distances[to.getNodeIndex()] = distances[from.getNodeIndex()] + distance;
			predecessors[to.getNodeIndex()] = arc;
		}
	}

	public List<Task> getFullPathWithWait(Task target)
	{
		List<Task> path = new ArrayList<>();

		// When target equals origin, the path consists of a single task.
		if (target.equals(origin))
		{
			path.add(target);
			return path;
		}

		// Retrieve the first connection used in the path.
		Connection connection = predecessors[target.getNodeIndex()];

		// Ensure that the target node is added.
		if (!forwardDirection)
		{
			path.add(target);
		}

		while (true)
		{
			// THIS IS THE MODIFIED PART:
			// We add the task REGARDLESS of the connection type.
			path.add(connection.getTo());

			// Stopping criterion.
			Task next = forwardDirection ? connection.getFrom() : connection.getTo();
			boolean stop = next.equals(origin);
			if (stop)
			{
				// Ensure that the origin node is added.
				if (forwardDirection)
				{
					path.add(origin);
				}
				break;
			}

			// Update connection.
			connection = predecessors[next.getNodeIndex()];
		}
		return path;
	}

	public boolean pathContainsWaitConnection(Task target)
	{
		// If target is unreachable or is the origin, there's no WAIT arc.
		if (target.equals(origin) || predecessors[target.getNodeIndex()] == null)
		{
			return false;
		}

		// Start backtracking from the target
		Connection connection = predecessors[target.getNodeIndex()];

		while (true)
		{
			// Check the current connection
			if (connection.getConnectionType().equals(ConnectionType.WAIT))
			{
				return true;
			}

			// Find the next task in the path
			Task next = forwardDirection ? connection.getFrom() : connection.getTo();
			
			// Stop if we reached the origin
			if (next.equals(origin))
			{
				break;
			}

			// Update connection to the next one
			connection = predecessors[next.getNodeIndex()];
		}
		
		// No WAIT arcs were found on the entire path
		return false;
	}





}
