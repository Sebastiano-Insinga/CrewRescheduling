package columnGeneration;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

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
public class columnGeneratioFast
{
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
			rmp.addDuty(new Duty(slackCost, tasks));
			
		}
		System.out.println("slack duty generated");
	}

	
	
	//print of Matrix.csv
	public static void printAndExportSolution(RMP rmp, Instance instance) throws IloException, IOException {
	    IloCplex cplex = rmp.getCplex();
	    
	    // Blocco 1: Stampa dei valori della soluzione
	    System.out.println("[TEST] Soluzione trovata. Valori delle variabili:");
	    System.out.printf("[TEST] Obj = %.9f%n", rmp.getObjectiveValue());

	    for (Map.Entry<Duty, IloNumVar> entry : rmp.getDutyEntries()) {
	        IloNumVar var = entry.getValue();
	        double value = cplex.getValue(var);
	        if (value > 1e-12) { 
	            System.out.printf("%-15s = %.6f%n", var.getName(), value);
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
	    Path matrixFilePath = Paths.get("C:\\Users\\sebastiano insinga\\Desktop\\Tesi\\BartvanRossum\\results","Matrix_frac.csv");
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
	    
	    Path cplexValuesPath = Paths.get("C:\\Users\\sebastiano insinga\\Desktop\\Tesi\\BartvanRossum\\results", "CplexValues.csv");
	    try (BufferedWriter writer = Files.newBufferedWriter(cplexValuesPath, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING)) {
	        writer.write("DutyID,CplexValue");
	        writer.newLine();
	        for (Map.Entry<Duty, IloNumVar> entry : rmp.getDutyEntries()) {
	            Duty duty = entry.getKey();
	            IloNumVar var = entry.getValue();
	            double value = cplex.getValue(var);
	            if (value > 1e-9) {
	                writer.write(String.format("%d,%.9f", duty.getID(), value));
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




}

	   

	
	


