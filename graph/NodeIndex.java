package graph;

/**
 * Auxiliary class used to store the index of a node in the topological ordering
 * of a graph. This allows efficient array-based shortest path algorithms.
 * 
 * @author B.T.C. van Rossum
 */
public class NodeIndex
{
	private int index;

	/**
	 * Returns index of the node.
	 * 
	 * @return index
	 */
	public int getNodeIndex()
	{
		return index;
	}

	/**
	 * Sets index of the node.
	 * 
	 * @param index index of the node
	 */
	public void setIndex(int index)
	{
		this.index = index;
	}
}
