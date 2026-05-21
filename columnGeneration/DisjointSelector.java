package columnGeneration;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

import instance.Task;
import util.Pair;

/**
 * This class selects a subset of duties that are
 * sufficiently task-disjoint.
 * 
 * @author B.T.C. van Rossum
 */
public class DisjointSelector
{
	private final double threshold;

	/**
	 * @param threshold the maximum allowed task-similarity between duties
	 */
	public DisjointSelector(double threshold)
	{
		this.threshold = threshold;
	}

	/**
	 * Iteratively select the duty with lowest reduced cost that is sufficiently
	 * disjoint from all previously selected duties, until no more such duties
	 * exist.
	 * 
	 * @param generatedColumns list of generated pairs of duty and reduced cost
	 * @return subset of the generated duties
	 */
	public List<Duty> selectColumns(List<Pair<Duty, Double>> generatedColumns)
	{
		// Initialise list of duties.
		List<Duty> duties = new ArrayList<>();
		Duty latestAdded = null;

		// Sort columns.
		generatedColumns.sort(new ReducedCostComparator());  // mette prima quelli nella lista che hanno un double relativo alla duty 

		int index = 0;
		latestAdded = null;
		for (int i = index; i < generatedColumns.size(); i++)
		{
			// Similarity criterion.
			Duty duty = generatedColumns.get(i).getKey();
			if (latestAdded != null)
			{
				double similarity = computeSimilarity(duty, latestAdded);
				if (similarity >= threshold)
				{
					continue;
				}
			}

			// Add column.
			duties.add(duty);
			latestAdded = duty;
			index = i;
		}
		return duties;
	}

	
	
	
	//new method to select columns
	public List<Duty> selectColumns1(List<Pair<Duty, Double>> generatedColumns)
	{
		// Inizializza la lista di duty selezionate.
		List<Duty> duties = new ArrayList<>();
		
		// Ordina le duty per costo ridotto crescente (la più negativa è la prima).
		generatedColumns.sort(new ReducedCostComparator());
		
		// Se la lista non è vuota, aggiungi solo la prima duty.
		if (!generatedColumns.isEmpty()) {
			duties.add(generatedColumns.get(0).getKey());
		}
		
		return duties;
	}
	
	/**
	 * Compute the similarity between the first and second duty, defined as the
	 * number of tasks occurring in both duties divided by the number of tasks in
	 * the first duty.
	 * 
	 * @param firstDuty  first duty
	 * @param secondDuty second duty
	 * @return similarity between duties
	 */
	private static double computeSimilarity(Duty firstDuty, Duty secondDuty)
	{
		//System.out.println("Controllo di similarità tra le duty");
		int numTasks = firstDuty.getTasks().size();
		int numTasksShared = 0;
		for (Task task : firstDuty.getTasks())
		{
			if (secondDuty.getTasks().contains(task))
			{
				numTasksShared++;
			}
		}
		double similarity = (double) numTasksShared / numTasks;
		return similarity;
	}

	/**
	 * Comparator to sort pairs of duties and reduced cost based on increasing
	 * reduced cost.
	 * 
	 * @author B.T.C. van Rossum
	 */
	private class ReducedCostComparator implements Comparator<Pair<Duty, Double>>
	{
		@Override
		public int compare(Pair<Duty, Double> o1, Pair<Duty, Double> o2)
		{
			return Double.compare(o1.getValue(), o2.getValue());
		}
	}
}
