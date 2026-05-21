package graph;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import graph.Connection.ConnectionType;
import instance.Task;

/**
 * Simple class to model a pricing graph by storing a list of nodes, arcs, and
 * for each node a list of in- and out-arcs.
 * 
 * @author B.T.C. van Rossum
 */
public class PricingGraph
{
	protected final List<Task> nodes;
	protected final List<Connection> arcs;
	private final Map<Task, List<Connection>> outArcs;
	private final Map<Task, List<Connection>> inArcs;

	/**
	 * Creates an empty graph with no nodes or arcs.
	 */
	public PricingGraph()
	{
		this.nodes = new ArrayList<>();
		this.arcs = new ArrayList<>();
		this.outArcs = new LinkedHashMap<>();
		this.inArcs = new LinkedHashMap<>();
	}

	/**
	 * Adds a task node to the graph
	 * 
	 * @param node node to be added to the graph
	 * @throws IllegalArgumentException if the node is null or already contained in
	 *                                  the graph
	 */
	public void addNode(Task node) throws IllegalArgumentException
	{
		if (node == null)
		{
			throw new IllegalArgumentException("Unable to add null to the graph");
		}
		else if (inArcs.containsKey(node))
		{
			throw new IllegalArgumentException("Unable to add the same node twice to the same graph");
		}
		else
		{
			nodes.add(node);
			inArcs.put(node, new ArrayList<>());
			outArcs.put(node, new ArrayList<>());
		}
	}

	/**
	 * Adds a connection between two tasks in the graph.
	 * 
	 * @param connectionType type of the connection
	 * @param from           start task of the connection
	 * @param to             end task of the connection
	 * @param cost           cost of the connection
	 * @param weight         weight of the connection
	 * @throws IllegalArgumentException if either node is not contained in the graph
	 */
	public void addArc(ConnectionType connectionType, Task from, Task to, int cost, double weight)
			throws IllegalArgumentException
	{
		if (!inArcs.containsKey(from) || !outArcs.containsKey(to))
		{
			throw new IllegalArgumentException("Unable to add arcs between nodes not in the graph");
		}
		Connection a = new Connection(connectionType, from, to, cost, weight);
		outArcs.get(from).add(a);
		inArcs.get(to).add(a);
		arcs.add(a);
	}

	/**
	 * Removes a node, and all its in- and out-arcs, from the graph.
	 * 
	 * @param node node to be removed from the graph
	 * @throws IllegalArgumentException if the node is not contained in the graph
	 */
	public void removeNode(Task node) throws IllegalArgumentException
	{
		if (node == null)
		{
			throw new IllegalArgumentException("Unable to remove null from the graph");
		}
		else if (!nodes.contains(node))
		{
			throw new IllegalArgumentException("Unable to remove node that is not in the graph");
		}
		else
		{
			nodes.remove(node);
			for (Connection arc : inArcs.get(node))
			{
				arcs.remove(arc);
				outArcs.get(arc.getFrom()).remove(arc);
			}
			inArcs.remove(node);
			for (Connection arc : outArcs.get(node))
			{
				arcs.remove(arc);
				inArcs.get(arc.getTo()).remove(arc);
			}
			outArcs.remove(node);
		}
	}

	/**
	 * Removes an arc from the graph.
	 * 
	 * @param arc arc to be removed
	 * @throws IllegalArgumentException if the arc is not contained in the graph
	 */
	public void removeArc(Connection arc) throws IllegalArgumentException
	{
		if (arc == null)
		{
			throw new IllegalArgumentException("Unable to remove null from the graph");
		}
		else if (!arcs.contains(arc))
		{
			throw new IllegalArgumentException("Unable to remove arc that is not in the graph");
		}
		else
		{
			arcs.remove(arc);
			outArcs.get(arc.getFrom()).remove(arc);
			inArcs.get(arc.getTo()).remove(arc);
		}
	}

	/**
	 * Returns a list of all nodes currently in the graph.
	 * 
	 * @return nodes in the graph
	 */
	public List<Task> getNodes()
	{
		return Collections.unmodifiableList(nodes);
	}

	/**
	 * Returns a list of all arcs currently in the graph.
	 * 
	 * @return arcs in the graph
	 */
	public List<Connection> getArcs()
	{
		return Collections.unmodifiableList(arcs);
	}

	/**
	 * Returns all the arcs that leave a particular node in the graph. Note that
	 * this list may be empty if no arcs leave this node.
	 * 
	 * @param node the node for which we want the leaving arcs
	 * @return list of arcs leaving the node
	 * @throws IllegalArgumentException if the node is not in the graph
	 */
	public List<Connection> getOutArcs(Task node) throws IllegalArgumentException
	{
		if (!outArcs.containsKey(node))
		{
			throw new IllegalArgumentException("Unable to provide out-arcs for a node that is not in the graph");
		}
		return Collections.unmodifiableList(outArcs.get(node));
	}

	/**
	 * Gives all the arcs that enter a particular node in the graph. Note that this
	 * list may be empty if no arcs enter this node.
	 * 
	 * @param node the node for which we want the entering arcs
	 * @return a list of arcs entering the node
	 * @throws IllegalArgumentException if the node is not in the graph
	 */
	public List<Connection> getInArcs(Task node) throws IllegalArgumentException
	{
		if (!inArcs.containsKey(node))
		{
			throw new IllegalArgumentException("Unable to provide in-arcs for a node that is not in the graph");
		}
		return Collections.unmodifiableList(inArcs.get(node));
	}

	/**
	 * The total number of nodes in this graph.
	 * 
	 * @return the number of nodes in the graph
	 */
	public int getNumberOfNodes()
	{
		return nodes.size();
	}

	/**
	 * The total number of arcs in this graph.
	 * 
	 * @return the number of arcs in the graph
	 */
	public int getNumberOfArcs()
	{
		return arcs.size();
	}

	/**
	 * Returns the in-degree of a node in the graph.
	 * 
	 * @param node the node for which we want the in-degree
	 * @return in-degree of the node
	 * @throws IllegalArgumentException if the node is not in the graph
	 */
	public int getInDegree(Task node) throws IllegalArgumentException
	{
		return getInArcs(node).size();
	}

	/**
	 * Iterate over all nodes to set the index. This is an auxiliary function used
	 * in the shortest path algorithms.
	 */
	public void setNodeIndices()
	{
		for (int i = 0; i < nodes.size(); i++)
		{
			nodes.get(i).setIndex(i);
		}
	}

	/**
	 * Returns the out-degree of a node in the graph.
	 * 
	 * @param node the node for which we want the out-degree
	 * @return out-degree of the node
	 * @throws IllegalArgumentException if the node is not in the graph
	 */
	public int getOutDegree(Task node) throws IllegalArgumentException
	{
		return getOutArcs(node).size();
	}

	@Override
	public int hashCode()
	{
		final int prime = 31;
		int result = 17;
		result = prime * result + ((arcs == null) ? 0 : arcs.hashCode());
		result = prime * result + ((nodes == null) ? 0 : nodes.hashCode());
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
		PricingGraph other = (PricingGraph) obj;
		if (arcs == null)
		{
			if (other.arcs != null)
				return false;
		}
		else if (!arcs.equals(other.arcs))
			return false;
		if (nodes == null)
		{
			if (other.nodes != null)
				return false;
		}
		else if (!nodes.equals(other.nodes))
			return false;
		return true;
	}
}
