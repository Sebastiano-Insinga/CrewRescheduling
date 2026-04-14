package instance;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;



/**
 * Class that generates an instance of specified size by generating tasks with
 * random start and end stations and start and end times. Note that it can occur
 * that the tasks generated in this way cannot be covered by any feasible
 * duties, e.g. when the earliest task does not start at a depot.
 * 
 * @author B.T.C. van Rossum
 */
public class InstanceGenerator
{
	/**
	 * Generate a random instance with a specified number of tasks, depots, and
	 * stations.
	 * 
	 * @param random      random generator
	 * @param numTasks    number of tasks
	 * @param numDepots   number of depots
	 * @param numStations number of stations
	 * @return randomly generated instance of specified size
	 */
	public static Instance generateInstance(Random random,int numTasks, int numDepots, int numStations)
	{
		
		Map<Integer,Map<Integer,Double>> stationDistances= new LinkedHashMap<>();
		 final double MAX_CROSS_STATION_COST = 500.0;
	 	 final double MIN_CROSS_STATION_COST = 100.0;
		
	 	 // 1. Inizializza tutte le righe della matrice.
	 	 for(int i=0; i<numStations; i++) {
	 	 	 stationDistances.put(i,new LinkedHashMap<>());
	 	 }
	 	 
	 	 // 2. Popolamento completo e simmetrico della matrice
	 	 for(int i=0; i<numStations; i++) {
	 	 	 for(int j=0; j< numStations; j++) {
	 	 		 if(i==j) {
	 	 			 // La diagonale è sempre 0.0
	 	 			 stationDistances.get(i).put(j,0.0);	
	 	 		 } else if(i < j) {
	 	 			 // Genera un costo casuale solo per la metà superiore
	 	 			// double distance = MIN_CROSS_STATION_COST +	
	 	 			//		 (MAX_CROSS_STATION_COST - MIN_CROSS_STATION_COST) * random.nextDouble();	
	 	 			//Random random1 = new Random(11235);
	 	 			 double distance= random.nextDouble(500);
	 	 			//double distance=365;
	 	 			System.out.println(distance);
	 	 			 // distance = Math.round(distance * 100.0) / 100.0;	
	 	 				 
	 	 			 // Salvataggio in (i, j)
	 	 			 stationDistances.get(i).put(j, distance);
	 	 				 
	 	 			 // Salvataggio simmetrico in (j, i)
	 	 			 stationDistances.get(j).put(i, distance);
	 	 		 } else { // if (i > j)
                   //rimposto il costo per sicurezza
                   stationDistances.get(i).put(j, stationDistances.get(j).get(i));
                }
	 	 	 }
	 	 	
	 	 }
     
	// Generate depots.
		List<Integer> depots = new ArrayList<>();
		for (int i = 0; i < numDepots; i++)
		{
			depots.add(i);
		}
		System.out.println(depots);
		
		
		
	// Generate tasks.
		List<Task> tasks = new ArrayList<>();
		for (int i = 0; i < numTasks; i++)
		{
			int startTime = random.nextInt(Parameters.MAX_START_TIME);
			int endTime = startTime + Parameters.MIN_TASK_LENGTH
					+ random.nextInt(Parameters.MAX_TASK_LENGTH - Parameters.MIN_TASK_LENGTH);
			int startStation = random.nextInt(numStations);
			int endStation = random.nextInt(numStations);
			tasks.add(new Task(i, startTime, endTime, startStation, endStation));

		}

		// Return instance.
		return new Instance(depots, tasks,stationDistances);
	}
}
