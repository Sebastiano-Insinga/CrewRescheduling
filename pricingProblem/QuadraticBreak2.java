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
 * Implementation of the O(|N|^2) pricing problem algorithm.
 * 
 * @author B.T.C. van Rossum
 */
public class QuadraticBreak2 extends PricingProblemSolver
{
	private final PricingGraph graph;
	private final Map<Task, Map<Task, List<Task>>> breakTaskMap;
	private final Map<Task,List<Integer>> endTaskMap;
	//private final Map<Task, Integer> endTaskMap;
	private final List<Task> postBreakTasks;

	 // NUOVO
    private final Map<Integer, Map<Integer, Double>> stationDistances;
	
	
	
	/**
	 * Initialise the solver for a given instance of the crew scheduling problem.
	 * 
	 * @param instance instance of the crew scheduling problem
	 */
	public QuadraticBreak2(Instance instance)
	{
		this.tasks = instance.getTasks();
		this.depots = instance.getDepots();
		this.graph = createGraph();

		this.breakTaskMap = new LinkedHashMap<>();
		this.endTaskMap = new LinkedHashMap<>();
		this.postBreakTasks = new ArrayList<>();

		initialiseBreakTaskMap(instance.getTasks());
		initialiseEndTaskMap(instance.getTasks());
		//NUOVO
		this.stationDistances = instance.getStationDistances();
		debugDuty455(this.graph, this.tasks);
	
	}

	/**
	 * Construct a linearly-sized time-space network.
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
	 * post-break tasks.
	 * 
	 * @param tasks list of tasks
	 */
	private void initialiseBreakTaskMap(List<Task> tasks)
	{
	    Map<Integer, List<Task>> tasksByEndStation = new LinkedHashMap<>();
	    for (Task task : tasks)
	    {
	        if (!tasksByEndStation.containsKey(task.getEndStation()))
	        {
	            tasksByEndStation.put(task.getEndStation(), new ArrayList<>());
	        }
	        tasksByEndStation.get(task.getEndStation()).add(task);
	    }

	    for (List<Task> taskList : tasksByEndStation.values())
	    {
	        taskList.sort(new TaskComparator());
	    }

	    // Find valid pre-break tasks.
	    for (Connection sourceArc : graph.getOutArcs(graph.getNodes().get(0)))
	    {
	        Task startTask = sourceArc.getTo();
	        breakTaskMap.put(startTask, new LinkedHashMap<>());

	        // Solve a SPP to obtain reachability from startTask
	        ShortestPath shortestPath = new ShortestPath(graph, startTask, true,
	                startTask.getEndTime() + Parameters.MAX_TIME_WITHOUT_BREAK);

	        // Iterate over potential post-break tasks.
	        for (Task postBreakTask : tasks)
	        {
	            // Duty length criterion (check grezzo sulla durata massima totale)
	            if (postBreakTask.getEndTime() > startTask.getStartTime() + Parameters.MAX_DUTY_LENGTH)
	            {
	                continue;
	            }

	            // Otteniamo i candidati che finiscono nella stazione dove inizia il postBreakTask
	            List<Task> potentialPreBreaks = tasksByEndStation.get(postBreakTask.getStartStation());
	            
	            // Se non ci sono candidati o la lista è vuota, salta
	            if (potentialPreBreaks == null || potentialPreBreaks.isEmpty()) {
	                continue;
	            }

	            // Lista per accumulare tutti i preBreak validi per questa coppia (start, post)
	            List<Task> validPreBreaks = new ArrayList<>();

	            // Iteriamo su tutti i possibili preBreakTask
	            for (Task preBreakCandidate : potentialPreBreaks) {
	                
	                // 1. Controllo validità Pausa:
	                // Il preBreak deve finire abbastanza presto da permettere la pausa minima prima del postBreak
	                if (preBreakCandidate.getEndTime() + Parameters.MIN_BREAK_LENGTH > postBreakTask.getStartTime()) {
	                    // Poiché la lista è ordinata per endTime crescente, se questo fallisce, 
	                    // anche i successivi falliranno (finiscono ancora più tardi).
	                    // Possiamo interrompere il ciclo interno.
	                    break; 
	                }

	                // 2. Controllo tempo massimo senza pausa (rispetto allo startTask)
	                // Il preBreak non deve finire troppo tardi rispetto all'inizio del turno
	                if (preBreakCandidate.getEndTime() > startTask.getStartTime() + Parameters.MAX_TIME_WITHOUT_BREAK) {
	                    break;
	                }

	                // 3. Controllo Raggiungibilità:
	                // Deve esistere un percorso dallo startTask al preBreakCandidate
	                if (shortestPath.containsPath(preBreakCandidate)) {
	                    validPreBreaks.add(preBreakCandidate);
	                }
	            }

	            // Se abbiamo trovato almeno un preBreak valido, salviamo la lista nella mappa
	            if (!validPreBreaks.isEmpty()) {
	                breakTaskMap.get(startTask).put(postBreakTask, validPreBreaks);
	                
	                if (!postBreakTasks.contains(postBreakTask))
	                {
	                    postBreakTasks.add(postBreakTask);
	                }
	            }
	        }
	    }
	}
	/**
	 * For each start task, compute index of latest allowed end task.
	 * 
	 * @param tasks list of tasks
	 */
	private void initialiseEndTaskMap(List<Task> tasks)
	{
		
		endTaskMap.clear();
		// Iterate over start tasks.
		for (int i = 0; i < tasks.size(); i++)
		{
			Task startTask = tasks.get(i);
			// Iterate over possible end tasks.
			
			List<Integer> compatibleEndIndices = new ArrayList<>();
			for (int j = i; j < tasks.size(); j++)
			{
				Task endTask = tasks.get(j);			
				if (endTask.getEndTime() < startTask.getStartTime() + Parameters.MAX_DUTY_LENGTH)
				{
					compatibleEndIndices.add(j);
				}
							
			}
			
				
			endTaskMap.put(startTask, compatibleEndIndices);
			// Store latest allowed ID in map.			
		}
	}
	
	@Override
	public List<Pair<Duty, Double>> generateDuties()
	{
		// Initialise duties.
		List<Pair<Duty, Double>> duties = new ArrayList<>();

		// Solve SPP for each start and post break task.
		Map<Task, ShortestPath> shortestPathMap = createShortestPathMap(graph);

		Map<Task, Pair<List<Task>, double[]>> postBreakArrayMap1 = createArrayMap1(graph,
				shortestPathMap);
		
		// Loop to construct duties.
		//for (Pair<Duty,Double> duty: createDuties_New(graph,shortestPathMap,postBreakArrayMap))
		
		for (Pair<Duty, Double> duty : createDuties2(graph, shortestPathMap,postBreakArrayMap1))
		{
			duties.add(duty);
		//	System.out.println("Duty creata"+duty.getKey().getTasks()+duty);
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
			/*
			 * Partendo da ogni nodo che è collegato direttamente a SOURCE, che sono per noi gli startTask,
			 * viene effettuata una ShortestPath in avanti che si blocca quando il tempo limite di attraversamento 
			 * supera il timeLimit = startTask.getStartTime()+ Parameters.MAX_TIME_WITHOUT_BREAK quindi praticamente stiamo
			 * aggiornando tutte le distanze dei nodi che possono essere visitati entro un turno senza pausa. Le stiamo aggiornando
			 * perchè dentro ogni volta che chiamiamo ShortestPath viene anche chiamato updateDistance(). Le distanze non sono altro
			 * che i pesi degli archi e il costo. Il costo dipende dalla tipologia di arco.
			 */

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
	 * Construct distance matrix E and auxiliary matrix of end task indices.
	 * 
	 * @param graph           pricing graph
	 * @param shortestPathMap map containing the solutions to SSSPPs from each
	 *                        post-break task
	 * @return distance matrix E and auxiliary matrix of end task indices, returned
	 *         in the form of a pair of arrays for each post-break task
	 */
	/* private Map<Task, Pair<int[], double[]>> createArrayMap(PricingGraph graph,
			Map<Task, ShortestPath> shortestPathMap)
	{
		Map<Task, Pair<int[], double[]>> postBreakArrayMap = new LinkedHashMap<>();
		for (Task postBreakTask : postBreakTasks)
		{
			// Use auxiliary array such that we can do all depots simultaneously.
			int[] indexPerDepot = new int[depots.size()];
			double[] distancePerDepot = new double[depots.size()];
			for (int depot : depots)
			{
				indexPerDepot[depot] = 0;
				distancePerDepot[depot] = Double.MAX_VALUE;
			}

			// Initialise arrays.
			int[] indexArray = new int[graph.getNumberOfNodes()];
			double[] distanceArray = new double[graph.getNumberOfNodes()];

			// Iterate over tasks.
			for (int i = 0; i < tasks.size(); i++)
			{
				// Task should end at depot.
				Task task = tasks.get(i);
				int depot = task.getEndStation();
				if (shortestPathMap.get(postBreakTask).containsPath(task))
				{
					// Update distance if it is shorter.
					double distance = shortestPathMap.get(postBreakTask).getDistance(task);
					/*
					 * controlla in quale task potrebbe finire la duty tra quelli che sono più vicini al postBreak che già
					 * rispettano il criterio di lunghezza della duty senza pause per cui siamo ancora nel limite di tempo
					 * della duty, controlla solo il task più vicino 	
					 */			
		/*			if (distance < distancePerDepot[depot])
					{
						indexPerDepot[depot] = i;
						distancePerDepot[depot] = distance;
					}
				}

				// Store in array.
				indexArray[i] = indexPerDepot[depot];
				distanceArray[i] = distancePerDepot[depot];
			}

			Pair<int[], double[]> pair = new Pair<int[], double[]>(indexArray, distanceArray);
			postBreakArrayMap.put(postBreakTask, pair);
		}
		return postBreakArrayMap;
	}

	/**
	 * Create duties by iterating over all combinations of start and post-break
	 * task, and finding the optimal end task through the array.
	 * 
	 * @param graph             pricing graph
	 * @param shortestPathMap   map containing the solutions to SSSPPs from each
	 *                          start task
	 * @param postBreakArraymap map containing, for each post-break task, a pair of
	 *                          distance and index arrays
	 * @return list of pairs of duty and reduced cost
	 */
	/*private List<Pair<Duty, Double>> createDuties(PricingGraph graph, Map<Task, ShortestPath> shortestPathMap)
	{

		int n=0;
		LinkedList<Pair<Duty, Double>> duties = new LinkedList<>();
	
		for (Connection sourceArc : graph.getOutArcs(graph.getNodes().get(0)))
		{
			
			Task startTask = sourceArc.getTo();
			System.out.println("startT"+startTask.getID());
			//ShortestPath spFromStart = shortestPathMap.get(startTask);
			for (Entry<Task, Task> breakEntry : breakTaskMap.get(startTask).entrySet())
			{
				Task preBreakTask = breakEntry.getValue();
				Task postBreakTask = breakEntry.getKey();
				//ShortestPath spFromPostBreak=shortestPathMap.get(postBreakTask);
				for (Task endTaskCandidate: tasks) {
				// 1. Vincolo di raggiungibilità: deve esistere un percorso dopo la pausa
					//System.out.println("endT"+endTaskCandidate.getID());
				if(!shortestPathMap.get(postBreakTask).containsPath(endTaskCandidate)) {
					continue;
				}
				 List<Task> tasks2= shortestPathMap.get(startTask).getFullPathWithWait(preBreakTask);
				System.out.println("Task reachable by from" + postBreakTask.getID()+tasks2);
				 //2. Vincolo di durata massima della duty
				if((endTaskCandidate.getEndTime()-startTask.getStartTime())>Parameters.MAX_DUTY_LENGTH){
					continue;
				}
				//Costo di rientro della stazione finale 
				double returnTravelCost= getTravelCost(endTaskCandidate.getEndStation(),startTask.getStartStation());
				
				// Costo operativo standard del duty
                int operationalCost = computeCost(startTask.getStartTime(), endTaskCandidate.getEndTime());

                // Costo totale che verrà assegnato all'oggetto Duty
                int totalDutyCost = operationalCost + (int) Math.round(returnTravelCost);				
				// Compute reduced cost.
				double reducedCost = getReducedCostStart(startTask)
						+ shortestPathMap.get(startTask).getDistance(preBreakTask)
						+ Parameters.VARIABLE_DUTY_COST
								* (postBreakTask.getEndTime() - preBreakTask.getEndTime())
						+ postBreakTask.getDual() 
						+ shortestPathMap.get(postBreakTask).getDistance(endTaskCandidate)
						+ returnTravelCost;
				n++;
				//stampe per controllare i valori 
				
				
			//	System.out.println("\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\");
				
			//	System.out.println("Number of iteration"+" "+n);
				
			//	System.out.println("Reduced cost startTask\n"+startTask.getID()+":"+ " "+getReducedCostStart(startTask));
				//System.out.println(shortestPathMap.get(startTask).getDistance(preBreakTask));
			//	System.out.println("postBreakTask dual\n" +postBreakTask.getID()+":"+  " "+postBreakTask.getDual());
				
			//	System.out.println("endTask choosed:"+" "+endTaskCandidate.getID());
				
			//	System.out.println("Return travel cost: "+" "+returnTravelCost);
				
			//	System.out.println("Computation of the cost of the duty "+" "+ reducedCost);
				
			//	System.out.println("\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\");
				
				
				if (reducedCost < -Parameters.PRECISION) {
	                    List<Task> tasks= shortestPathMap.get(startTask).getFullPathWithWait(preBreakTask);
	          //          System.out.println("List of preBreakTask");
	          //          System.out.println("   Tasks in pre-break path: " + tasks);
	          //          System.out.println("//////////////////////////////////");	                  
	                    List<Task> postBreakPath = shortestPathMap.get(postBreakTask).getFullPathWithWait(endTaskCandidate);
	                    tasks.addAll(shortestPathMap.get(postBreakTask).getPath(endTaskCandidate));
	          //          System.out.println("   Tasks in post-break path: " + postBreakPath);
	                   
	           //         System.out.println("//////////////////////////////////");	
	           //         System.out.println("List of all task");
	                    for(Task task:tasks) {
	                    	System.out.println(task.getID());
	                    }
	                    	
	                    duties.addFirst(new Pair<>(new Duty(totalDutyCost, tasks), reducedCost));
	                    // Uniamo i percorsi per formare il duty completo
					} 
				}
			}
		
		}	
		return duties;
	}
*/
	private List<Pair<Duty, Double>> createDuties2(PricingGraph graph, Map<Task, ShortestPath> shortestPathMap, Map<Task, Pair<List<Task>, double[]>> postBreakArrayMap1)
	{
	    LinkedList<Pair<Duty, Double>> duties = new LinkedList<>();

	    for (Connection sourceArc : graph.getOutArcs(graph.getNodes().get(0)))
	    {
	        Task startTask = sourceArc.getTo();

	        for (Entry<Task, List<Task>> breakEntry : breakTaskMap.get(startTask).entrySet())
	        {
	            Task postBreakTask = breakEntry.getKey();
	            List<Task> preBreakTasksList = breakEntry.getValue();
	     
	            for (Task preBreakTask : preBreakTasksList) 
	            {
	                Pair<List<Task>, double[]> pair = postBreakArrayMap1.get(postBreakTask);
	                List<Task> endTaskCandidates = pair.getKey();

	                for (Task endTaskCandidate : endTaskCandidates) {
	                    

	                    if ((endTaskCandidate.getEndTime() - startTask.getStartTime()) > Parameters.MAX_DUTY_LENGTH) {
	                        continue;
	                    }


	                    double returnTravelCost = getTravelCost(endTaskCandidate.getEndStation(), startTask.getStartStation());

	                    int operationalCost = computeCost(startTask.getStartTime(), endTaskCandidate.getEndTime());

	    
	                    int actualBreakDuration = postBreakTask.getStartTime() - preBreakTask.getEndTime();
	                    int totalDutyDuration = endTaskCandidate.getEndTime() - startTask.getStartTime();

	 
	                    if (actualBreakDuration < 30 && totalDutyDuration > 6 * 60) {
	                        continue; 
	                    }
						
	                    // Compute reduced cost
	                    double reducedCost = getReducedCostStart(startTask)
	                            + shortestPathMap.get(startTask).getDistance(preBreakTask)
	                            + Parameters.VARIABLE_DUTY_COST * (postBreakTask.getEndTime() - preBreakTask.getEndTime())
	                            + postBreakTask.getDual()
	                            + shortestPathMap.get(postBreakTask).getDistance(endTaskCandidate)
	                            + returnTravelCost;

	                 

	                    if (reducedCost < -0.0001) { 
	                        List<Task> tasks = shortestPathMap.get(startTask).getPath(preBreakTask);
	                        
	                       
	                        tasks.addAll(shortestPathMap.get(postBreakTask).getPath(endTaskCandidate));
	                        
	                        
	                        int totalCost = operationalCost + (int) Math.round(returnTravelCost); 

	                        duties.addFirst(new Pair<>(new Duty(totalCost, tasks), reducedCost));
	                    }
	                }
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

	private Map<Task, Pair<int[], double[]>> createArrayMap(PricingGraph graph,
			Map<Task, ShortestPath> shortestPathMap)
	{
		Map<Task, Pair<int[], double[]>> postBreakArrayMap = new LinkedHashMap<>();
		
        // 1. CALCOLO DELLA DIMENSIONE MASSIMA NECESSARIA
        // Trova l'ID di deposito massimo per assicurare che l'array sia abbastanza grande.
        // Se 'depots' è vuoto, usa 0 come dimensione minima.
        int maxDepotId = 0;
        for (int depotId : depots) {
            if (depotId > maxDepotId) {
                maxDepotId = depotId;
            }
        }
        int arraySize = maxDepotId + 1; // E.g., se ID max è 5, la dimensione deve essere 6 (indici 0-5)
        
		for (Task postBreakTask : postBreakTasks)
		{
			// Use auxiliary array such that we can do all depots simultaneously.
			// 2. DIMENSIONAMENTO DEGLI ARRAY CORRETTO
			int[] indexPerDepot = new int[arraySize];
			double[] distancePerDepot = new double[arraySize];
            
			// 3. INIZIALIZZAZIONE DEGLI ARRAY
			for (int i = 0; i < arraySize; i++)
			{
				indexPerDepot[i] = 0;
				distancePerDepot[i] = Double.MAX_VALUE;
			}
            
            
			// Initialise arrays for tasks (la dimensione qui è corretta, dipende dai nodi del grafo)
			int[] indexArray = new int[graph.getNumberOfNodes()];
			double[] distanceArray = new double[graph.getNumberOfNodes()];

			// Iterate over tasks.
			for (int i = 0; i < tasks.size(); i++)
			{
				// Task should end at depot.
				Task task = tasks.get(i);
				int depot = task.getEndStation(); // Depot ID
                
                // 4. VERIFICA DELL'INDICE PRIMA DI ACCEDERE A indexPerDepot/distancePerDepot
                // Se l'istanza è mal formata (depot ID negativo o fuori da maxDepotId)
                if (depot < 0 || depot >= arraySize) {
                    // Ignora o gestisci l'errore del depot non valido per questa task.
                    // Dato che non è il focus, la ignoriamo (o l'errore è implicito nel bug originale).
                    continue; 
                }
                
				if (shortestPathMap.get(postBreakTask).containsPath(task))
				{
					// Update distance if it is shorter.
					double distance = shortestPathMap.get(postBreakTask).getDistance(task);
					
                    // L'indice 'depot' è ora valido rispetto a 'arraySize'
                    if (distance < distancePerDepot[depot])
                    {
                        indexPerDepot[depot] = i;
                        distancePerDepot[depot] = distance;
                    }
				}
				

                // Questa parte usa 'i' (indice della task) e non 'depot' (ID del deposito)
				indexArray[i] = indexPerDepot[depot];
				distanceArray[i] = distancePerDepot[depot];
			}

			Pair<int[], double[]> pair = new Pair<int[], double[]>(indexArray, distanceArray);
			postBreakArrayMap.put(postBreakTask, pair);
		}
		return postBreakArrayMap;
	}

	//NUOVO
	
	private double getTravelCost(int startStation, int endStation) {
	        if (startStation == endStation) {
	            return 0.0;
	        }
	        
	        // Recupera la mappa per la stazione di partenza (riga)
	        Map<Integer, Double> row = stationDistances.get(startStation);
	        if (row != null) {
	            // Recupera il costo per la stazione di arrivo (colonna)
	            Double cost = row.get(endStation);
	            if (cost != null) {
	                return cost;
	            }
	        }
	        
	        // Questo non dovrebbe accadere se InstanceGenerator è corretto.
	        System.err.println("ATTENZIONE: Costo di viaggio non trovato tra stazione " + startStation + " e " + endStation);
	        return 0.0; 
	    }

/*	private List<Pair<Duty, Double>> createDuties_New(PricingGraph graph, Map<Task, ShortestPath> shortestPathMap,Map<Task, Pair<int[], double[]>> postBreakArrayMap)
	{

		int n=0;
		LinkedList<Pair<Duty, Double>> duties = new LinkedList<>();
	
		for (Connection sourceArc : graph.getOutArcs(graph.getNodes().get(0)))
		{
			Task startTask = sourceArc.getTo();
			System.out.println("T"+startTask.getID());
			//ShortestPath spFromStart = shortestPathMap.get(startTask);
			for (Entry<Task, Task> breakEntry : breakTaskMap.get(startTask).entrySet())
			{
				System.out.println("start:T"+startTask.getID());
				Task preBreakTask = breakEntry.getValue();
				Task postBreakTask = breakEntry.getKey();
				
				Pair<int[], double[]> pair = postBreakArrayMap.get(postBreakTask);
				List<Integer> compatibleIndices = endTaskMap.get(startTask);
				/*
				 * restituisce l'indice del task finale valido più tardivo per lo startTask che rispetti i 
				 * vincoli di raggiungibilità
				 * per lo startTask e in questa espressione viene utilizzato come indice per andare a pescare nell'array 
				 * l'endTask più vicino possibile al postBreak ( più vicino --> distanza + bassa -> costi più bassi )
				        
				for (int compatibleIndex : compatibleIndices)
	            {
					
					int optimalIndex = pair.getKey()[compatibleIndex];
	                double distance = pair.getValue()[compatibleIndex];
	                Task endTask = tasks.get(optimalIndex);
	                if(!shortestPathMap.get(postBreakTask).containsPath(endTask)) {
						continue;
					}
							
				//ShortestPath spFromPostBreak=shortestPathMap.get(postBreakTask);
				//Costo di rientro della stazione finale 
				double returnTravelCost= getTravelCost(endTask.getEndStation(),startTask.getStartStation());
				
				// Costo operativo standard del duty
                int operationalCost = computeCost(startTask.getStartTime(), endTask.getEndTime());

                // Costo totale che verrà assegnato all'oggetto Duty
                int totalDutyCost = operationalCost + (int) Math.round(returnTravelCost);				
				// Compute reduced cost.
				double reducedCost = getReducedCostStart(startTask)
						+ shortestPathMap.get(startTask).getDistance(preBreakTask)
						+ Parameters.VARIABLE_DUTY_COST
								* (postBreakTask.getEndTime() - preBreakTask.getEndTime())
						+ postBreakTask.getDual() 
						+ shortestPathMap.get(postBreakTask).getDistance(endTask)
						+ distance
						+ returnTravelCost;
				n++;
				//stampe per controllare i valori 
				
				System.out.println("\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\");
				
				System.out.println("Number of iteration\n"+n);
				
				System.out.println("Reduced cost startTask\n"+startTask.getID()+"\n"+":"+ getReducedCostStart(startTask));
				//System.out.println(shortestPathMap.get(startTask).getDistance(preBreakTask));
				System.out.println("postBreakTask dual\n" +postBreakTask.getID()+"\n"+":"+ postBreakTask.getDual());
				
				System.out.println("endTask choosed\n"+endTask.getID());
				
				System.out.println("Computation of the cost of the duty\n "+ reducedCost);
				
				System.out.println(returnTravelCost);
				
				System.out.println("\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\");
				
				
				if (reducedCost < -Parameters.PRECISION) {
	                    List<Task> tasks= shortestPathMap.get(startTask).getPath(preBreakTask);
	                    tasks.addAll(shortestPathMap.get(postBreakTask).getPath(endTask));
	                    duties.addFirst(new Pair<>(new Duty(totalDutyCost, tasks), reducedCost));
	                    // Uniamo i percorsi per formare il duty completo
					} 
	            }
	            }
			}
			
		return duties;
	}
	
	 */  
	private Map<Task, Pair<List<Task>, double[]>> createArrayMap1(PricingGraph graph,
			Map<Task, ShortestPath> shortestPathMap)
	{
		Map<Task, Pair<List<Task>, double[]>> postBreakArrayMap1 = new LinkedHashMap<>();
		        
		for (Task postBreakTask : postBreakTasks)
		{
			List<Task> endTask= new LinkedList<>();
			double[] distancefrompostBreak = new double[tasks.size()];
            
			for (int i = 0; i < tasks.size(); i++)
			{
				// Task should end at depot.
				Task task = tasks.get(i);
				distancefrompostBreak[i] = Double.MAX_VALUE;
				if (shortestPathMap.get(postBreakTask).containsPath(task)) 
						
				{					
					//!shortestPathMap.get(postBreakTask).pathContainsWaitConnection(task))
					// Update distance if it is shorter.
					double distance = shortestPathMap.get(postBreakTask).getDistance(task);
					endTask.add(task);
					distancefrompostBreak[i] = distance;
				}
			}

						//System.out.println("----------------------------------------");
						//System.out.println("Key postBreakTask ID: " + postBreakTask.getID());
						//System.out.print("  Associated 'endTask' IDs: [");
						
						for (int i = 0; i < endTask.size(); i++) {
						//	System.out.print(endTask.get(i).getID());
							if (i < endTask.size() - 1) {
								System.out.print(", ");
							}
						}
						//System.out.println("]"); // Close the bracket
						//System.out.println("----------------------------------------");		
			
			Pair<List<Task>, double[]> pair = new Pair<List<Task>, double[]>(endTask,distancefrompostBreak);
			postBreakArrayMap1.put(postBreakTask, pair);
			
		}
		//System.out.println(postBreakArrayMap1);
		return postBreakArrayMap1;
	}
	
	
	public void debugDuty455(PricingGraph graph, List<Task> tasks) {
	    System.out.println("\n--- DEBUG DUTY 455 CHAIN ---");
	    
	    // Task IDs from reference solution for Duty 455
	    int[] sequence = {2222, 2223, 336, 490, 491, 492, 1112, 2287, 2288, 2289, 2290, 2291, 2292};
	    
	    // Helper to find task by ID
	    java.util.Map<Integer, Task> taskMap = new java.util.HashMap<>();
	    for(Task t : tasks) taskMap.put(t.getID(), t);

	    boolean chainBroken = false;

	    for (int i = 0; i < sequence.length - 1; i++) {
	        Task from = taskMap.get(sequence[i]);
	        Task to = taskMap.get(sequence[i+1]);
	        
	        if (from == null || to == null) {
	            System.out.println("ERROR: Task not found in instance: " + (from==null?sequence[i]:sequence[i+1]));
	            return;
	        }

	        boolean arcFound = false;
	        // Check ALL outgoing arcs from 'from'
	        for (Connection arc : graph.getOutArcs(from)) {
	            if (arc.getTo().equals(to)) {
	                System.out.printf("OK: T%d -> T%d exists (Type: %s, Cost: %d)\n", 
	                    from.getID(), to.getID(), arc.getConnectionType(), arc.getCost());
	                arcFound = true;
	                break;
	            }
	        }

	        if (!arcFound) {
	            System.out.printf("FAIL: No arc between T%d (End: %d, Stn: %d) -> T%d (Start: %d, Stn: %d)\n",
	                from.getID(), from.getEndTime(), from.getEndStation(),
	                to.getID(), to.getStartTime(), to.getStartStation());
	            chainBroken = true;
	        }
	    }
	    
	    if (!chainBroken) {
	        System.out.println("SUCCESS: The graph allows Duty 455 fully!");
	    } else {
	        System.out.println("FAILURE: Graph is missing connections.");
	    }
	}
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
}
