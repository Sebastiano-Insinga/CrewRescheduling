package columnGeneration;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import ilog.concert.IloException;
import ilog.concert.IloLPMatrix;
import ilog.concert.IloNumVar;
import ilog.cplex.IloCplex;
import instance.Instance;
import instance.Parameters;
import instance.Task;
import pricingProblem.PricingProblemSolver;
import util.Pair;

/**
 * Simple column generation framework to solve the LP-relaxation of a crew
 * scheduling problem.
 * 
 * @author B.T.C. van Rossum
 */
public class ColumnGeneration
{
	
	private static final String LOG_FILE_PATH = "results/rejected_duties_log.csv";
	private static boolean logHeaderWritten = false;
	private static final String LOG_DIR_PATH = "C:\\Users\\sebastiano insinga\\Desktop\\Vienna\\TESI\\Austrian Istances\\results";
	
	static {
		// Crea la cartella dei risultati se non esiste
		try {
			Files.createDirectories(Paths.get(LOG_DIR_PATH));
		} catch (IOException e) {
			System.err.println("Errore nella creazione della cartella: " + LOG_DIR_PATH);
			e.printStackTrace();
		}
	}
	
	
	/**
	 * Solve the LP-relaxation of an instance of the crew scheduling problem using
	 * specified pricing problem solvers, and add the time spent pricing and number
	 * of pricing iterations to an array.
	 * 
	 * @param instance   instance of the crew scheduling problem
	 * @param solvers    array of pricing problem solvers to be used
	 * @param statistics array that stores cumulative time spent pricing and number
	 *                   of pricing iterations for each solver
	 * @throws IloException exception thrown by CPLEX
	 * @throws IOException
	 */
	public static void applyColumnGeneration(Instance instance, PricingProblemSolver[] solvers, double[][] statistics)
			throws IloException, IOException
	{
		RMP rmp = new RMP(instance);
	    // DisjointSelector selector = new DisjointSelector(Parameters.SIMILARITY_THRESHOLD); // Rimosso se non lo usi
	    int n = 0;

	    addSlackDuties(rmp, instance);

	    mainLoop: while (true) {
	        exportModel(rmp.getCplex(), LOG_DIR_PATH + "\\rmp_model.lp");
	        
	        try {
	            System.out.println("Risoluzione RMP");
	            rmp.solve();
	            n++;
	            System.out.println("n_iterations:" + n);

	            // Set duals
	            for (Task task : instance.getTasks()) {
	                task.setDual(-rmp.getCoverDual(task));
	            }

	            // Variabile per tenere traccia delle duty da aggiungere
	            List<Pair<Duty, Double>> newDuties = new ArrayList<>();
	            
	            
	               
	            for (int i = 0; i < solvers.length; i++) {
	                if (i < solvers.length - 1) {
	                    continue;
	                }
	                
	                PricingProblemSolver solver = solvers[i];
	                statistics[i][1]++;
	                statistics[i][0] -= System.currentTimeMillis();
	                
	                /*
	                 * vengono resettati i costi degli archi perchè contenevano le informazioni dei duali associate ad ogni 
	                 * nodo
	                 */
	                
	                solver.prepareGraphs();
	                List<Pair<Duty, Double>> duties = solver.generateDuties();
	               //aggiungiamo le duty che sono state create in newDuties
	                statistics[i][0] += System.currentTimeMillis();
	                newDuties.addAll(duties);    
	            }
	            
	            // Logica di stampa e aggiunta delle duty
	            System.out.println("\n--- Duty generate in questa iterazione ---");
	            if (newDuties.isEmpty()) {
	                System.out.println("Nessuna duty generata.");
	                break mainLoop;
	            } else {
	                for (Pair<Duty, Double> dutyPair : newDuties) {
	                    //printDutyDetails("Duty aggiunta", dutyPair.getKey(), dutyPair.getValue());
	                    rmp.addDuty(dutyPair.getKey());
	                }
	            }
	            System.out.println("------------------------------------------");
	            
	        } catch (IloException e) {
	            System.err.println("Errore durante la risoluzione RMP: " + e.getMessage());
	            e.printStackTrace();
	            break;
	        }
	    }
	    
	    try {
	        printAndExportSolution(rmp, instance, instanceName);
	    } catch (IloException | IOException e) {
	        System.err.println("Errore durante la stampa o l'esportazione: " + e.getMessage());
	    }
	    rmp.clean();
	}
	
	/**
	 * Add a slack variable for each task in the instance such that a feasible
	 * solution always exists.
	 * 
	 * @param rmp      restricted master problem
	 * @param instance instance of the crew scheduling problem
	 * @throws IloException exception thrown by CPLEX
	 */
	private static void addSlackDuties(RMP rmp, Instance instance) throws IloException
	{
		// The cost of a slack variable is the maximum cost of a feasible duty.
		int slackCost = Parameters.FIXED_DUTY_COST + Parameters.MAX_DUTY_LENGTH * Parameters.VARIABLE_DUTY_COST;
		for (Task task : instance.getTasks())
		{
			List<Task> tasks = new ArrayList<>();
			tasks.add(task);
			rmp.addDuty(new Duty(slackCost,tasks));
			
		}
		System.out.println("slack duty generated");
	}

	//print of Matrix.csv
	public static void printAndExportSolution(RMP rmp, Instance instance, String instanceName) throws IloException, IOException {
	    IloCplex cplex = rmp.getCplex();
	    
	    // Blocco 1: Stampa dei valori della soluzione
	    System.out.println("[TEST] Soluzione trovata. Valori delle variabili:");
	    System.out.printf("[TEST] Obj = %.9f%n", rmp.getObjectiveValue());

	    for (Map.Entry<Duty, IloNumVar> entry : rmp.getDutyEntries()) {
	        IloNumVar var = entry.getValue();
	        double value = cplex.getValue(var);
	        if (value > 1e-12) { 
	          //  System.out.printf("%-15s = %.6f%n", var.getName(), value);
	        }
	    }
	    
	    
	    // ---
	    
	    // Blocco 2: Creazione della matrice di incidenza e identificazione dei duty selezionati
	    List<Task> allTasks = instance.getTasks();
	    List<Duty> selectedDuties = new ArrayList<>();
	    Map<Task, Integer> taskIndexMap = new HashMap<>();
	    
	    for (int i = 0; i < allTasks.size(); i++) {
	        taskIndexMap.put(allTasks.get(i), i);
	    }
	    
	    Map<Duty, Integer> dutyIndexMap = new HashMap<>();
	    int colIndex = 0;
	    for (Map.Entry<Duty, IloNumVar> entry : rmp.getDutyEntries()) {
	        IloNumVar var = entry.getValue();
	        double value = cplex.getValue(var);
	        if (value > 1e-9) {
	            Duty duty = entry.getKey();
	            selectedDuties.add(duty);
	            dutyIndexMap.put(duty, colIndex++);
	        }
	    }
	    
	    int[][] incidenceMatrix = new int[allTasks.size()][selectedDuties.size()];
	    
	    for (Duty duty : selectedDuties) {
	        int dutyCol = dutyIndexMap.get(duty);
	        for (Task task : duty.getTasks()) {
	            int taskRow = taskIndexMap.get(task);
	            incidenceMatrix[taskRow][dutyCol] = 1;
	        }
	    }

	    // ---

	    // Blocco 3: Esportazione della matrice e dei valori in file CSV
	    Path matrixFilePath = Paths.get(LOG_DIR_PATH, instanceName + "_Matrix_frac.csv");
	    try (BufferedWriter writer = Files.newBufferedWriter(matrixFilePath, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING)) {
	        StringBuilder header = new StringBuilder("TaskId");
	        for (Duty duty : selectedDuties) {
	            header.append(",D").append(duty.getID());
	        }
	        writer.write(header.toString());
	        writer.newLine();

	        for (int i = 0; i < allTasks.size(); i++) {
	            Task task = allTasks.get(i);
	            StringBuilder row = new StringBuilder();
	            row.append(task.getID());
	            for (int j = 0; j < selectedDuties.size(); j++) {
	                row.append(",").append(incidenceMatrix[i][j]);
	            }
	            writer.write(row.toString());
	            writer.newLine();
	        }
	        System.out.println("Matrice di Incidenza esportata in: " + matrixFilePath.toAbsolutePath());
	    }
	    
	    Path cplexValuesPath = Paths.get(LOG_DIR_PATH, "CplexValues.csv");
	    try (BufferedWriter writer = Files.newBufferedWriter(cplexValuesPath, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING)) {
	        writer.write("DutyID,CplexValue");
	        writer.newLine();
	        for (Map.Entry<Duty, IloNumVar> entry : rmp.getDutyEntries()) {
	            Duty duty = entry.getKey();
	            IloNumVar var = entry.getValue();
	            double value = cplex.getValue(var);
	            if (value > 1e-9) {
	                writer.write(String.format("%d,%.9f",duty.getID(), value));
	                writer.newLine();
	            }
	        }
	        System.out.println("Valori Cplex esportati in: " + cplexValuesPath.toAbsolutePath());
	    }
	}
	public static void printAndExportSolution1(RMP rmp, Instance instance, String instanceName) throws IloException, IOException {
	    IloCplex cplex = rmp.getCplex();
	    
	    // Blocco 1: Stampa dei valori della soluzione
	    System.out.println("[TEST] Soluzione trovata. Valori delle variabili:");
	    System.out.printf("[TEST] Obj = %.9f%n", rmp.getObjectiveValue());

	    for (Map.Entry<Duty, IloNumVar> entry : rmp.getDutyEntries()) {
	        IloNumVar var = entry.getValue();
	        double value = cplex.getValue(var);
	        if (value > 1e-12) { 
	          //  System.out.printf("%-15s = %.6f%n", var.getName(), value);
	        }
	    }
	    
	    
	    // ---
	    
	    // Blocco 2: Creazione della matrice di incidenza e identificazione dei duty selezionati
	    List<Task> allTasks = instance.getTasks();
	    List<Duty> selectedDuties = new ArrayList<>();
	    Map<Task, Integer> taskIndexMap = new HashMap<>();
	    
	    for (int i = 0; i < allTasks.size(); i++) {
	        taskIndexMap.put(allTasks.get(i), i);
	    }
	    
	    Map<Duty, Integer> dutyIndexMap = new HashMap<>();
	    int colIndex = 0;
	    for (Map.Entry<Duty, IloNumVar> entry : rmp.getDutyEntries()) {
	        IloNumVar var = entry.getValue();
	        double value = cplex.getValue(var);
	        if (value > 1e-9) {
	            Duty duty = entry.getKey();
	            selectedDuties.add(duty);
	            dutyIndexMap.put(duty, colIndex++);
	        }
	    }
	    
	    int[][] incidenceMatrix = new int[allTasks.size()][selectedDuties.size()];
	    
	    for (Duty duty : selectedDuties) {
	        int dutyCol = dutyIndexMap.get(duty);
	        for (Task task : duty.getTasks()) {
	            int taskRow = taskIndexMap.get(task);
	            incidenceMatrix[taskRow][dutyCol] = 1;
	        }
	    }

	    // ---

	    // Blocco 3: Esportazione della matrice e dei valori in file CSV
	    Path matrixFilePath = Paths.get(LOG_DIR_PATH, instanceName + "_Matrix_frac.csv");
	    try (BufferedWriter writer = Files.newBufferedWriter(matrixFilePath, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING)) {
	        StringBuilder header = new StringBuilder("TaskId");
	        for (Duty duty : selectedDuties) {
	            header.append(",D").append(duty.getID());
	        }
	        writer.write(header.toString());
	        writer.newLine();

	        for (int i = 0; i < allTasks.size(); i++) {
	            Task task = allTasks.get(i);
	            StringBuilder row = new StringBuilder();
	            row.append(task.getID());
	            for (int j = 0; j < selectedDuties.size(); j++) {
	                row.append(",").append(incidenceMatrix[i][j]);
	            }
	            writer.write(row.toString());
	            writer.newLine();
	        }
	        System.out.println("Matrice di Incidenza esportata in: " + matrixFilePath.toAbsolutePath());
	    }
	    
	    Path cplexValuesPath = Paths.get(LOG_DIR_PATH, instanceName + "_CplexValues1.csv");
	    try (BufferedWriter writer = Files.newBufferedWriter(cplexValuesPath, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING)) {
	        writer.write("DutyID,CplexValue");
	        writer.newLine();
	        for (Map.Entry<Duty, IloNumVar> entry : rmp.getDutyEntries()) {
	            Duty duty = entry.getKey();
	            IloNumVar var = entry.getValue();
	            double value = cplex.getValue(var);
	            if (value > 1e-9) {
	                writer.write(String.format("%d,%.9f",duty.getID(), value));
	                writer.newLine();
	            }
	        }
	        System.out.println("Valori Cplex esportati in: " + cplexValuesPath.toAbsolutePath());
	    }
	}

	private static void printDutyDetails(String label, Duty duty, Double reducedCost) {
	    StringBuilder tasksList = new StringBuilder();
	    for (Task task : duty.getTasks()) {
	        tasksList.append("T").append(task.getID()).append(" ");
	    }
	    System.out.printf("%s: D%d | Costo Ridotto: %.2f | Tasks: [%s]%n", 
	                      label, duty.getID(), reducedCost, tasksList.toString().trim());
	}

	 public static void exportModel(IloCplex cplex, String filePath) {
	        try {
	            cplex.exportModel(filePath);
	            System.out.println("Modello esportato con successo in: " + filePath);
	        } catch (IloException e) {
	            System.err.println("Errore durante l'esportazione del modello: " + e.getMessage());
	            e.printStackTrace();
	        }
	    }
	 
	 public static void applyColumnGenerationFast(Instance instance, PricingProblemSolver[] solvers, double[][] statistics, String instanceName)
				throws IloException, IOException
		{
			RMP rmp = new RMP(instance);
		    DisjointSelector selector = new DisjointSelector(Parameters.SIMILARITY_THRESHOLD); // Rimosso se non lo usi
		    int n = 0;

		    addSlackDuties(rmp, instance);

		    mainLoop: while (true) {
		        exportModel(rmp.getCplex(), LOG_DIR_PATH + "\\rmp_model.lp");
		        
		            System.out.println("Risoluzione RMP");
		            rmp.solve();
		            n++;
		            System.out.println("n_iterations:" + n);

		            
		            
		            
		            // Set duals
		            for (Task task : instance.getTasks()) {
		                task.setDual(-rmp.getCoverDual(task));
		            }

		            // Variabile per tenere traccia delle duty da aggiungere
		            List<Pair<Duty, Double>> newDuties = new ArrayList<>();
		            
		            for (int i = 0; i < solvers.length; i++) {
		                if (i < solvers.length - 1) {
		                    continue;
		                }
		                
		                PricingProblemSolver solver = solvers[i];
		                statistics[i][1]++;
		                statistics[i][0] -= System.currentTimeMillis();
		                solver.prepareGraphs();
		                List<Pair<Duty, Double>> duties = solver.generateDuties();
		               //aggiungiamo le duty che sono state create in newDuties
		                statistics[i][0] += System.currentTimeMillis();
		                newDuties.addAll(duties);
		              
		            }
		            // call the selectiomethod on the duty that have been generated by generateDuties
		            
		            List<Duty> selectedDuties = selector.selectColumns1(newDuties);
		  
		            // Logica di stampa e aggiunta delle duty
		            System.out.println("\n--- Duty generate in questa iterazione ---");
		            if (newDuties.isEmpty()) {
		                System.out.println("Nessuna duty generata.");
		                break mainLoop;
		            }
		           
		            System.out.println("\n--- Duty selezionata per l'aggiunta all'RMP ---");
		            
		            /*dato che selectedDuties è la lista di Duty ordinata secondo il loro valore di RC
		             * vado a prendere il primo valore che avrà il costo ridotto più negativo e lo vado ad
		             *aggiungere
		             */
		            
		            
		            if (!selectedDuties.isEmpty()) {
		            	Duty selectedDuty = selectedDuties.get(0);
			        	Double reducedCost = newDuties.stream()
			                .filter(p -> p.getKey().equals(selectedDuty))
			                .map(Pair::getValue)
			                .findFirst()
			                .orElse(0.0);
			        	printDutyDetails("Duty aggiunta", selectedDuty, reducedCost);
			        	rmp.addDuty(selectedDuty);
			        } else {
			        	System.out.println("Nessuna duty selezionata.");
			        	break mainLoop;
			        }
	                              
		        }
		    
		    try {
		        printAndExportSolution(rmp, instance, instanceName);
		    } catch (IloException | IOException e) {
		        System.err.println("Errore durante la stampa o l'esportazione: " + e.getMessage());
		    }
		    rmp.clean();
		}
//applyColumnGeneration versione originale 
	 public static void applyColumnGeneration0(Instance instance, PricingProblemSolver[] solvers, double[][] statistics)
				throws IloException, IOException
		{
			// Initialise RMP.
			RMP rmp = new RMP(instance);
			DisjointSelector selector = new DisjointSelector(Parameters.SIMILARITY_THRESHOLD);
			int n=0;
			
			// Reset lo stato del logger all'inizio
			logHeaderWritten = false; 	
			// Add slack duties.
			addSlackDuties(rmp, instance);
			exportModel(rmp.getCplex(), LOG_DIR_PATH + "\\rmp_model"+0+".lp");
			// Main loop.
			mainLoop: while (true)
			{
				n++; 
				
				rmp.solve();
				// Solve RMP.
				exportModel(rmp.getCplex(), LOG_DIR_PATH + "\\rmp_model.lp");
				// Set duals.
				for (Task task : instance.getTasks())
				{
					task.setDual(-rmp.getCoverDual(task));
				}
				List<Pair<Duty, Double>> generatedDuties = new ArrayList<>();
		
				// Solve pricing problems. We use multiple solvers here such that we are sure
				// they use the same dual values.
				for (int i = 0; i < solvers.length; i++)
				{
					PricingProblemSolver solver = solvers[i];
					statistics[i][1]++;
					statistics[i][0] -= System.currentTimeMillis();
					solver.prepareGraphs();
					List<Pair<Duty, Double>> duties = solver.generateDuties();
					statistics[i][0] += System.currentTimeMillis();
					generatedDuties.addAll(duties);
					// Add the columns of the last column generation procedure only.
					if (i < solvers.length - 1)
					{
						continue;
					}

					// Add duties to RMP or terminate if no duties exist.
					
					if (generatedDuties.size() > 0)
					{
						List<Duty> selectedDuties = selector.selectColumns(generatedDuties);
						// Add a subset of the generated columns to the RMP.
						List<Pair<Duty, Double>> rejectedDuties = new ArrayList<>();
						for(Pair<Duty, Double> dutyPair : generatedDuties) {
						    if (!selectedDuties.contains(dutyPair.getKey())) {
						        rejectedDuties.add(dutyPair);
						    }
						}
						
						logRejectedDuties(n, rejectedDuties);
						
						for (Duty duty : selectedDuties)
						{
							rmp.addDuty(duty);
							
						}
					}
					else
					{
						// No duties are found, the RMP is solved to optimality.
						break mainLoop;
					}
				}		
			}

			
			try {
		        printAndExportSolution(rmp, instance, instanceName);
		    } catch (IloException | IOException e) {
		        System.err.println("Errore durante la stampa o l'esportazione: " + e.getMessage());
		    }
			
			// Clean model.
			rmp.clean();
		}
	
	  public static void logRejectedDuties(int iteration, List<Pair<Duty, Double>> rejectedDuties) {
	        
	        // Crea il nome del file univoco per questa iterazione
	        String fileName = String.format("rejected_duties_ITER_%d.csv", iteration);
	        String filePath = LOG_DIR_PATH + File.separator + fileName;

	        // Se non ci sono duty da loggare, usciamo
	        if (rejectedDuties.isEmpty()) {
	            // Optional: System.out.println("Nessuna duty scartata nell'iterazione " + iteration);
	            return;
	        }

	        // Usa try-with-resources per garantire che il PrintWriter venga chiuso
	        // new FileWriter(filePath) creerà un nuovo file o sovrascriverà l'esistente
	        try (FileWriter fw = new FileWriter(filePath);
	             PrintWriter pw = new PrintWriter(fw)) {

	            // Scrive l'intestazione (una sola volta per questo nuovo file)
	            pw.println("Iteration,Duty_Cost,Reduced_Cost,Task_IDs,Reason");

	            // Scrive i dettagli per ogni duty scartata
	            for (Pair<Duty, Double> dutyPair : rejectedDuties) {
	                Duty duty = dutyPair.getKey();
	                double reducedCost = dutyPair.getValue();

	                // Costruisci la lista di Task IDs come stringa
	                StringBuilder taskIds = new StringBuilder();
	                for (Task task : duty.getTasks()) {
	                    taskIds.append(task.getID()).append(" ");
	                }
	                // Rimuovi lo spazio finale e racchiudi tra virgolette per il CSV
	                String taskIdsStr = "\"" + taskIds.toString().trim() + "\"";
	                
	                // Scrive la riga CSV. Mantenuta la correzione del casting.
	                pw.printf(Locale.ROOT, "%d,%.2f,%.6f,%s,"
	                		+ "ejected_By_Selector\n",
	                    iteration,
	                    (double)((int)duty.getCost()), 
	                    reducedCost,
	                    taskIdsStr
	                );
	            }
	            
	        } catch (IOException e) {
	            System.err.println("Errore durante la scrittura del log per l'iterazione " + iteration + ": " + e.getMessage());
	            e.printStackTrace();
	        }
	    }
//applyColumnGeneration standard + implementazione euristica 1&2
	  public static void applyColumnGeneration0S(Instance instance, PricingProblemSolver[] solvers, double[][] statistics)
				throws IloException, IOException
		{
			// Initialise RMP.
			RMP rmp = new RMP(instance);
			DisjointSelector selector = new DisjointSelector(Parameters.SIMILARITY_THRESHOLD);
			int nn=0;
			// Reset lo stato del logger all'inizio
			logHeaderWritten = false; 	
			// Add slack duties.
			addSlackDuties(rmp, instance);			
		    // --- INIZIO BLOCCO DI ARRESTO PREMATURO (Variabili) ---		   
			double bestObjective = Double.MAX_VALUE;
		    int iterationsWithoutImprovement = 0;
		    final int PATIENCE = 4; // N. di iterazioni consecutive senza miglioramento prima di fermarsi
		    final double MIN_IMPROVEMENT = 0.0001; // Miglioramento minimo per resettare il contatore		
			// Main loop.
			mainLoop: while (true)
			{	 
				
				nn++;	
				// Solve RMP.					
				rmp.solve();
				exportModel(rmp.getCplex(), LOG_DIR_PATH + "\\rmp_model_new"+nn+".lp");
				// Set duals.				
		        // --- INIZIO BLOCCO DI ARRESTO PREMATURO (Logica di controllo)
		        double currentObjective = rmp.getObjectiveValue();
		        System.out.println("Valore Obiettivo RMP: " + currentObjective);
		        /*
		         * se c'è un miglioramento nella funzione obiettivo allora il valore bestObjective viene aggiornato con il nuovo valore 
		         * della funzione obiettivo e imposta il valore a 0 del numero di iterazioni senza miglioramento. 
		         * In alternativa viene incrementato il contatore
		         *  if (currentObjective < bestObjective - MIN_IMPROVEMENT) {
		            System.out.println("Miglioramento trovato! (Nuovo: " + currentObjective + ", Precedente: " + bestObjective + ")");
		            bestObjective = currentObjective;
		            iterationsWithoutImprovement = 0; // Resetta il contatore
		        } else {
		            iterationsWithoutImprovement++;
		            System.out.println("Nessun miglioramento significativo. Contatore pazienza: " 
		                + iterationsWithoutImprovement + "/" + PATIENCE);
		        }		         
		        */                
		        		    
		       /*
		        * Quando il numero di iterazioni senza miglioramento supera il parametro PATIENCE, quindi il numero di iterazioni in cui ci aspettiamo 
		        * che non migliori, allora blocchiamo il ciclo
		        *  if (iterationsWithoutImprovement >= PATIENCE) {
		            System.out.println("\n--- ARRESTO PREMATURO: L'algoritmo non migliora da " 
		                + PATIENCE + " iterazioni");
		            break mainLoop;
		        }
		        */
		      
		        
		        for (Task task : instance.getTasks())
		        {	
		        	task.setDual(-rmp.getCoverDual(task));
						double value= -rmp.getCoverDual(task);
					/*	System.out.println("Value of duals\n"+ 
								task.getID()+":"+value);		     		
		        */
		        }
				
				// Solve pricing problems. We use multiple solvers here such that we are sure
				// they use the same dual values.
				for (int i = 0; i < solvers.length; i++)
				{
					PricingProblemSolver solver = solvers[i];
					statistics[i][1]++;
					statistics[i][0] -= System.currentTimeMillis();
					solver.prepareGraphs();
					List<Pair<Duty, Double>> duties = solver.generateDuties();
					statistics[i][0] += System.currentTimeMillis();
					// Add the columns of the last column generation procedure only.
					if (i < solvers.length - 1)
					{
						continue;
					}
					// Add duties to RMP or terminate if no duties exist.					
					if (duties.size() > 0)
					{
						
						for(Duty duty: selector.selectColumns(duties)){   
							rmp.addDuty(duty);
					    // addedDuties.add(new Pair<>(dutyToAdd,reducedCost));
			                 //  printDuty("Created duty",duty);
			                  // System.out.println("\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\");
			                   
			                   /*   if (nn == 2) {
			                    	//rmp.AddForcedDutyConstraint(duty);
			                        System.out.println("Forced constraint added");
			                    }                
					    */
					    }
					   }					
					else
					{
						// No duties are found, the RMP is solved to optimality.
						break mainLoop;
					}
				}		
			}			
			try {
		        printAndExportSolution(rmp, instance, instanceName);
		        
		        List<Duty> selectedDuties = new ArrayList<>(rmp.getDuties());
		    
		  /*      util.GanttChartGenerator.plotGanttChart(
		     
		        	    "C:\\Users\\sebastiano insinga\\Desktop\\Tesi\\BartvanRossum\\results\\final_schedule_gantt.png", 
		        	    selectedDuties
		        	);
		  */     
		        // --- CHIAMATA AL NUOVO METODO DI ESPORTAZIONE ---
		        exportFinalDutiesWithTasks(rmp, instanceName); 
		        // ---------------------------------------------

		    } catch (IloException | IOException e) {
		        System.err.println("Errore durante la stampa o l'esportazione: " + e.getMessage());
		    }		
			// Clean model.
			
			rmp.clean();
		}	 
  
//metodo per stampare le duty che vengono aggiunte in base al rmp
	  public static void logAddedDuties(int iteration, List<Pair<Duty, Double>> addedDuties) {
	        
	        // Crea il nome del file univoco per questa iterazione
	        String fileName = String.format("added_duties_ITER_%d.csv", iteration);
	        String filePath = LOG_DIR_PATH + File.separator + fileName;

	        // Se non ci sono duty da loggare, usciamo
	        if (addedDuties.isEmpty()) {
	            // Optional: System.out.println("Nessuna duty scartata nell'iterazione " + iteration);
	            return;
	        }

	        // Usa try-with-resources per garantire che il PrintWriter venga chiuso
	        // new FileWriter(filePath) creerà un nuovo file o sovrascriverà l'esistente
	        try (FileWriter fw = new FileWriter(filePath);
	             PrintWriter pw = new PrintWriter(fw)) {

	            // Scrive l'intestazione (una sola volta per questo nuovo file)
	        	pw.println("Iteration,Duty_ID,Duty_Cost,Reduced_Cost,Task_IDs");

	            // Scrive i dettagli per ogni duty scartata
	            for (Pair<Duty, Double> dutyPair : addedDuties) {
	                Duty duty = dutyPair.getKey();
	                double reducedCost = dutyPair.getValue();

	                // Costruisci la lista di Task IDs come stringa
	                StringBuilder taskIds = new StringBuilder();
	                for (Task task : duty.getTasks()) {
	                    taskIds.append(task.getID()).append(" ");
	                }
	                // Rimuovi lo spazio finale e racchiudi tra virgolette per il CSV
	                String taskIdsStr = "\"" + taskIds.toString().trim() + "\"";
	                
	                // Scrive la riga CSV. Mantenuta la correzione del casting.
	                pw.printf(Locale.ROOT, "%d,%d,%d,%.6f,%s\n",
	                        iteration,
	                        duty.getID(),
	                        duty.getCost(), 
	                        reducedCost,
	                        taskIdsStr
	                    );
	            }
	            
	        } catch (IOException e) {
	            System.err.println("Errore durante la scrittura del log per l'iterazione " + iteration + ": " + e.getMessage());
	            e.printStackTrace();
	        }
	    }	  
	  
	  private static void printDuty(String label,Duty duty) {
		    StringBuilder tasksList = new StringBuilder();
		    for (Task task : duty.getTasks()) {
		        tasksList.append("T").append(task.getID()).append(" ");
		    }
		    System.out.printf("%s: D%d | Tasks: [%s]| Dutycost:%f\n",
		                      label, duty.getID(), tasksList.toString().trim(),duty.getCost());
		}	  
	  
public static void exportFinalDutiesWithTasks(RMP rmp, String instanceName) throws IloException, IOException {
        Path outputPath = Paths.get(LOG_DIR_PATH, instanceName + "_duties_with_tasks.csv");

	        try (BufferedWriter writer = Files.newBufferedWriter(outputPath, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING)) {
	            // Scrive l'intestazione del file CSV
	            writer.write("DutyID,TaskIDs");
	            writer.newLine();

	            // Itera su tutte le duty nell'RMP
	            for (Map.Entry<Duty, IloNumVar> entry : rmp.getDutyEntries()) {
	                Duty duty = entry.getKey();
	                IloNumVar var = entry.getValue();
	                double value = rmp.getCplex().getValue(var);                            
	                if (value > 0) {  
	                // Concatena gli ID dei task in una stringa separata da spazi
	                    String taskIds = duty.getTasks().stream()
	                                         .map(task -> String.valueOf(task.getID()))
	                                         .collect(Collectors.joining(" "));

	                    // Scrive la riga nel file CSV
	                    writer.write(String.format("%d,\"%s\"", duty.getID(), taskIds));
	                    writer.newLine();
	               }      
	            }
	            System.out.println("Esportazione delle duty finali con i task completata in: " + outputPath.toAbsolutePath());
	        }
	    }
  
	  /**
	 * @param instance
	 * @param solvers
	 * @param statistics
	 * @throws IloException
	 * @throws IOException
	 */
	public static void applyColumnGeneration0S1(Instance instance, PricingProblemSolver[] solvers, double[][] statistics, String instanceName)
				throws IloException, IOException
		{
			// Initialise RMP.
			RMP rmp = new RMP(instance);
			DisjointSelector selector = new DisjointSelector(Parameters.SIMILARITY_THRESHOLD);
			int nn=0;
			// Reset lo stato del logger all'inizio
			logHeaderWritten = false; 	
			// Add slack duties.
			addSlackDuties(rmp, instance);
			
			// --- INIZIO BLOCCO DI ARRESTO PREMATURO (Variabili) ---
			
			double bestObjective = Double.MAX_VALUE;
			int iterationsWithoutImprovement = 0;
			final int PATIENCE = 3; // N. di iterazioni consecutive senza miglioramento prima di fermarsi
			final double MIN_IMPROVEMENT = 0.0001; // Miglioramento minimo per resettare il contatore
		
			
			// Main loop.
			mainLoop: while (true)
			{	
				nn++;	
				
				// =================== FIX: CHECK IF SOLVE SUCCEEDED ===================
				// Solve RMP.
				
				rmp.solve();
				exportModel(rmp.getCplex(), LOG_DIR_PATH + "\\rmp_model"+nn+".lp");

				
				// =================== END OF FIX ====================================
				
				// Set duals.				
				// --- INIZIO BLOCCO DI ARRESTO PREMATURO (Logica di controllo)
				double currentObjective = rmp.getObjectiveValue();
				System.out.println("Valore Obiettivo RMP: " + currentObjective);

				/*
				 * se c'è un miglioramento nella funzione obiettivo allora il valore bestObjective viene aggiornato con il nuovo valore 
				 * della funzione obiettivo e imposta il valore a 0 del numero di iterazioni senza miglioramento. 
				 * In alternativa viene incrementato il contatore
				 *  .
				 */
				if (currentObjective < bestObjective - MIN_IMPROVEMENT) {
					System.out.println("Improvement! (New: " + currentObjective + ", Before: " + bestObjective + ")");
					bestObjective = currentObjective;
					iterationsWithoutImprovement = 0; // Resetta il contatore
				} else {
					iterationsWithoutImprovement++;
					System.out.println("No improvement, Patience: " 
							+ iterationsWithoutImprovement + "/" + PATIENCE);
				}		
				/*
				 * Quando il numero di iterazioni senza miglioramento supera il parametro PATIENCE, quindi il numero di iterazioni in cui ci aspettiamos
				 * che non migliori, allora blocchiamo il ciclo
				 * 
				 */
				if (iterationsWithoutImprovement >= PATIENCE) {
					System.out.println("\n--- ARRESTO PREMATURO: L'algoritmo non migliora da " 
							+ PATIENCE + " iterazioni");
					break mainLoop;
				}
				
				for (Task task : instance.getTasks())
				{
						double value1= -rmp.getCoverDual(task);
						task.setDual(-rmp.getCoverDual(task));
						double value2= -rmp.getCoverDual(task);
						
				}
				
				// Solve pricing problems. We use multiple solvers here such that we are sure
				// they use the same dual values.
				for (int i = 0; i < solvers.length; i++)
				{
					PricingProblemSolver solver = solvers[i];
					statistics[i][1]++;
					statistics[i][0] -= System.currentTimeMillis();
					solver.prepareGraphs();
					List<Pair<Duty, Double>> duties = solver.generateDuties();
					statistics[i][0] += System.currentTimeMillis();
					// Add the columns of the last column generation procedure only.
					if (i < solvers.length - 1)
					{
						continue;
					}
					// Add duties to RMP or terminate if no duties exist.					
					if (duties.size() > 0)
					{							
						// 2. Get a *COPY* of the duties already in the RMP.
						// We use the getDuties() method from RMP.java
						List<Duty> existingDuties = new ArrayList<>(rmp.getDuties());
						// 3. Loop through the NEW duties
						for(Duty newDuty: selector.selectColumns(duties)) {
							
							boolean isDuplicate = false;
							
							// 4. Loop through the "existing" list *only to check*
							for (Duty existingDuty : existingDuties) {	
							if (areDutiesEquivalent(newDuty, existingDuty)) {
									System.out.println("New duty not added");
									isDuplicate = true;
									break; // Found a duplicate
								}						
							}
							rmp.addDuty(newDuty);
							printDuty("Duty aggiunta",newDuty);
							// 6. Apply your heuristic *only if* it was a duplicate and we are stalling
							/*
							 * if (isDuplicate) {
							 * 	rmp.AddForcedDutyConstraint(newDuty);
								System.out.println("Forced constraint added for DUPLICATE Duty: D" + newDuty.getID());
							}
							 * 
							 */
							
							
							// 7. Add this new duty to our *local copy* so that if the
							// next newDuty is a duplicate of *this* one, we catch it.
							existingDuties.add(newDuty); 
						}
						// =================== END OF NEW LOGIC =================================
					}					
					else
					{
						// No duties are found, the RMP is solved to optimality.
						break mainLoop;
					}
				}		
			}			
			try {
				printAndExportSolution(rmp, instance, instanceName);
				
				// --- CHIAMATA AL NUOVO METODO DI ESPORTAZIONE ---
				exportFinalDutiesWithTasks(rmp, instanceName); 
				// ---------------------------------------------

			} catch (IloException | IOException e) {
				System.err.println("Errore durante la stampa o l'esportazione: " + e.getMessage());
			}		
			// Clean model.
			rmp.clean(); // <-- Fixed this line, was missing ()
		}
	  private static boolean areDutiesEquivalent(Duty d1, Duty d2) {
			// 1. Check if costs are different
			if (d1.getCost() != d2.getCost()) {
				return false;
			}

			// 2. Check if they have a different number of tasks
			List<Task> tasks1 = d1.getTasks(); //
			List<Task> tasks2 = d2.getTasks(); //
			if (tasks1.size() != tasks2.size()) {
				return false;
			}

			// 3. Check if they contain the exact same set of tasks
			// We use a HashSet for efficient, order-independent comparison
			Set<Task> taskSet1 = new HashSet<>(tasks1);
			Set<Task> taskSet2 = new HashSet<>(tasks2);
			
			return taskSet1.equals(taskSet2);
		}
	  
	  public static void applyColumnGeneration_Original(Instance instance, PricingProblemSolver[] solvers, double[][] statistics)
				throws IloException, IOException
		{
			// Initialise RMP.
			RMP rmp = new RMP(instance);
			DisjointSelector selector = new DisjointSelector(Parameters.SIMILARITY_THRESHOLD);

			// Add slack duties.
			addSlackDuties(rmp, instance);

			// Main loop.
			mainLoop: while (true)
			{
				// Solve RMP.
				rmp.solve();

				// Set duals.
				for (Task task : instance.getTasks())
				{
					task.setDual(-rmp.getCoverDual(task));
				}

				// Solve pricing problems. We use multiple solvers here such that we are sure
				// they use the same dual values.
				for (int i = 0; i < solvers.length; i++)
				{
					PricingProblemSolver solver = solvers[i];
					statistics[i][1]++;
					statistics[i][0] -= System.currentTimeMillis();
					solver.prepareGraphs();
					List<Pair<Duty, Double>> duties = solver.generateDuties();
					statistics[i][0] += System.currentTimeMillis();

					// Add the columns of the last column generation procedure only.
					if (i < solvers.length - 1)
					{
						continue;
					}

					// Add duties to RMP or terminate if no duties exist.
					if (duties.size() > 0)
					{
						// Add a subset of the generated columns to the RMP.
						for (Duty duty : selector.selectColumns(duties))
						{
							rmp.addDuty(duty);
						}
					}
					else
					{
						// No duties are found, the RMP is solved to optimality.
						break mainLoop;
					}
				}
			}

			// Clean model.
			rmp.clean();
		}


 public static void applyColumnGeneration0SI(Instance instance, PricingProblemSolver[] solvers, double[][] statistics, String instanceName)
				throws IloException, IOException
		{
	 
	 RMP rmp = new RMP(instance);
	DisjointSelector selector = new DisjointSelector(Parameters.SIMILARITY_THRESHOLD);
	addSlackDuties(rmp, instance);	
	int nn=0;
	mainLoop: while (true)
	{	 
		nn++;				
		rmp.solve();
		exportModel(rmp.getCplex(), LOG_DIR_PATH + "\\rmp_model_new"+nn+".lp");
        double currentObjective = rmp.getObjectiveValue();
        System.out.println("Valore Obiettivo RMP: " + currentObjective);     
        for (Task task : instance.getTasks())
        {	
        	task.setDual(-rmp.getCoverDual(task));
				double value= -rmp.getCoverDual(task);
				//System.out.println("Value of duals\n"+ task.getID()+":"+value);		     		
        }
		for (int i = 0; i < solvers.length; i++)
		{
			PricingProblemSolver solver = solvers[i];
			statistics[i][1]++;
			statistics[i][0] -= System.currentTimeMillis();
			solver.prepareGraphs();
			List<Pair<Duty, Double>> duties = solver.generateDuties();
			statistics[i][0] += System.currentTimeMillis();
			if (i < solvers.length - 1)
			{
				continue;
			}					
			if (duties.size() > 0)
			{
				for(Duty duty: selector.selectColumns(duties)){   
					rmp.addDuty(duty);
	                   //printDuty("Created duty",duty);
	                   //System.out.println("\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\");
	                      
			    }
			}					
			else
			{
				// No duties are found, the RMP is solved to optimality.
				break mainLoop;
			}
		}		
	} 
	printAndExportSolution1(rmp, instance, instanceName);
	System.out.println("\n--- START PHASE 2: CALCULATING INTEGER SOLUTION (IP) ---");
    System.out.println("Switching variable types from Continuous to Integer...");
    
    // 1. Convert all duty variables in the model to Integer type
    rmp.switchToIntegerAggressive(); 
    
    // 2. Solve again. 
    // Since variables are now Integer, CPLEX will automatically use Branch-and-Bound/Cut.
    // It will assume duals are no longer needed.
    
    double timeLimitSeconds=14400;
    System.out.println("Time limit set:"+ timeLimitSeconds);
    rmp.setTimeLimit(timeLimitSeconds);
    
    rmp.solve();
    
    double integerObjective = rmp.getObjectiveValue();
    
    System.out.println("**************************************************");
    System.out.println("FINAL INTEGER OPTIMAL SOLUTION: " + integerObjective);
    System.out.println("**************************************************");

   
    //////////////////////////// Exporting solution /////////////////////////////////////////////
    
    
    try {
        printAndExportSolution(rmp, instance, instanceName);
        
        List<Duty> selectedDuties = new ArrayList<>(rmp.getDuties());
     
      // util.GanttChartGenerator.plotGanttChart(
      // "C:\\Users\\sebastiano insinga\\Desktop\\Tesi\\BartvanRossum\\results\\final_schedule_gantt.png", 
      // selectedDuties);
      
        	    
        	
        
        exportFinalDutiesWithTasks(rmp, instanceName);
        // ---------------------------------------------

    } catch (IloException | IOException e) {
        System.err.println("Errore durante la stampa o l'esportazione: " + e.getMessage());
    }	
    
    
////////////////////////////Exporting solution ///////////////////////////////////////////// 
    
    
    
    
    rmp.clean();
	 
		}
	   
//Aggiungi questo metodo alla classe ColumnGeneration

 public static void applyHeuristicIntegerFixing(Instance instance, PricingProblemSolver[] solvers, double[][] statistics, String instanceName) 
	       throws IloException, IOException {
	  
	  RMP rmp = new RMP(instance);
	  DisjointSelector selector = new DisjointSelector(Parameters.SIMILARITY_THRESHOLD);
	  addSlackDuties(rmp, instance);
	  boolean integerSolutionFound = false;

	  while (!integerSolutionFound) {         
	      
	      // 1. Column Generation (Loop Interno)
	      boolean pricingImproved;
	      do {
	          pricingImproved = false;
	          rmp.solve();

	          for (Task task : instance.getTasks()) {
	              task.setDual(-rmp.getCoverDual(task));
	          }
	          
	          List<Pair<Duty, Double>> newDuties = new ArrayList<>();
	          for (int i = 0; i < solvers.length; i++) {
	              solvers[i].prepareGraphs();
	              List<Pair<Duty, Double>> duties = solvers[i].generateDuties();
	              if (!duties.isEmpty()) {
	                  newDuties.addAll(duties);
	              }
	          }

	          if (!newDuties.isEmpty()) {
	              List<Duty> selectedDuties = selector.selectColumns(newDuties);
	              int dutiesAddedCount = 0;
	              for (Duty d : selectedDuties) {         
	                  rmp.addDuty(d); 
	                  dutiesAddedCount++;
	              }
	              if (dutiesAddedCount > 0) {
	                  pricingImproved = true;
	              }
	          }
	      } while (pricingImproved); 
	      
	      Map<Duty, Double> fractionalSolution = rmp.getDutyValuesMap();
	      
	      Duty bestCandidate = null;
	      double maxFractionalPart = -1.0;
	      boolean allInteger = true; 

	      // Lista temporanea: salviamo COSA fissare, ma NON LO FISSIAMO ANCORA
	      List<Duty> dutiesToLock = new ArrayList<>();

	      for (Map.Entry<Duty, Double> entry : fractionalSolution.entrySet()) {
	          Duty duty = entry.getKey();
	          double value = entry.getValue();

	          if (value < 1e-6) continue;

	          if (value ==1) {
	              if (!rmp.isDutyLocked(duty)) {
	                  //list of duties that we want to block because they are already at 1
	            	  dutiesToLock.add(duty); 
	              }
	              continue; 
	          }

	          allInteger = false;

	          if (value > maxFractionalPart) {
	              maxFractionalPart = value;
	              bestCandidate = duty;
	          }
	      }     
	      
	      if (allInteger) {
	          System.out.println("\n*** INTEGER SOLUTION FOUND! ***");
	          integerSolutionFound = true;
	          
	          try {
	              System.out.println("Exporting solution...");
              printAndExportSolution(rmp, instance, instanceName);
              exportFinalDutiesWithTasks(rmp, instanceName);
          } catch (IloException | IOException e) {
              System.err.println("Errore durante l'esportazione: " + e.getMessage());
          }
      } else {
          for (Duty d : dutiesToLock) {
              rmp.lockDuty(d);
              System.out.println("   -> Consolidating duty D" + d.getID() + " (value 1.0)");
          }

          if (bestCandidate != null) {
              System.out.println("   -> Heuristic Fixing: Locking duty D" + bestCandidate.getID() + 
                                 " with current value: " + maxFractionalPart);
              rmp.lockDuty(bestCandidate);
          } else {
              System.err.println("No fractional candidate found but solution is not integer. Stopping.");
              break;
          }
      }
      
      // Il ciclo ricomincia -> RMP.solve()
  }
  
  rmp.clean();
  }
}
