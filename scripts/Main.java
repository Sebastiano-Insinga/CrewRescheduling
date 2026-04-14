package scripts;

import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Random;

import columnGeneration.ColumnGeneration;
import ilog.concert.IloException;
import instance.Instance;
import instance.InstanceGenerator;
import instance.Parameters;
import instance.Task;
import pricingProblem.CubicBreak;
import pricingProblem.PricingProblemSolver;
import pricingProblem.QuadraticBreak;
import pricingProblem.QuadraticBreak2;
import pricingProblem.QuadraticNoBreak;
import util.InstanceReader;
import columnGeneration.Duty;
import columnGeneration.RMP;
import graph.PricingGraph;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;


public class Main
{
    public static void main(String[] args) throws IloException, IOException
    {
        // Parameters.
    	//Random random = new Random(11235);
        //int[] numTasks =  {1000};
      
        int numRuns = 1;
        int numSolvers = 1;

        // Initialise output file.
        //StringBuilder sb = new StringBuilder();
        //sb.append("solver;totalRunTime;Source File\n");
    
        String validation="C:\\Users\\sebastiano insinga\\Desktop\\Vienna\\TESI\\BartvanRossum\\results\\Final_Duties\\Repaired_solutions_twan\\Repaired_solution_twan_15-A-190T-21L.tsv";
        
        // Lista di istanze da processare
        String baseDir = "C:\\Users\\sebastiano insinga\\Desktop\\WU\\Crew Rescheduling\\CrewScheduling\\Weekly_Minutes_Transformed_Instances\\";
        String[] instances = {
          "Transformed-01-A-50T-10L.tsv",
       "Transformed-05-A-90T-16L-randomized.tsv",
       "Transformed-08-A-120T-18L-randomized.tsv",
            "Transformed-09-A-130T-19L-randomized.tsv",
            "Transformed-10-A-140T-19L.tsv",
           "Transformed-14-A-180T-21L.tsv",
            "Transformed-15-A-190T-21L-randomized.tsv",
         "Transformed-17-A-250T-24L-randomized.tsv",
            "Transformed-19-A-350T-30L.tsv",      
        "Transformed-21-A-450T-37L-randomized.tsv",
         "Transformed-23-A-550T-43L.tsv",
             "Transformed-27-A-750T-54L-randomized.tsv",
             "Transformed-35-A-1150T-70L.tsv",
             "Transformed-37-A-1250T-72L.tsv",
           "Transformed-38-A-1300T-76L.tsv",
             "Transformed-39-A-1350T-79L-randomized.tsv",
             "Transformed-41-A-1450T-82L-randomized.tsv",
              "Transformed-45-A-1650T-91L.tsv",
              "Transformed-50-A-1900T-102L-randomized.tsv",
               "Transformed-51-A-1950T-103L.tsv",
             "Transformed-52-A-2000T-105L.tsv",
        };
        
        // Itera su tutte le istanze
        for (String instanceFile : instances) {
            String taskFilePath = baseDir + instanceFile;
            System.out.println("\n========================================");
            System.out.println("PROCESSING: " + instanceFile);
            System.out.println("========================================\n");
            
            try {
                // Initialise array to store time spent pricing and number of pricing iterations
                // of each solver.
                double[][] statistics = new double[numSolvers][2];

                for (int i = 0; i < numRuns; i++) {
                    // Genera un'istanza casuale di dimensione n.
                   
               
          //      	Instance instance = InstanceGenerator.generateInstance(random, n, Parameters.NUM_DEPOTS,Parameters.NUM_STATIONS);           	
               	  	//System.out.println("Lettura dell'istanza dal file: " + taskFilePath);
                	 //lettura da file  
               	  	Instance instance = InstanceReader.readInstanceFromFile(taskFilePath);
           	  	
                    // Controlla immediatamente se l'istanza è valida, prima di usarla
                    if (instance.getTasks() == null || instance.getTasks().isEmpty()) {
                        System.out.println("Istanza senza task o con task null: salto la risoluzione.");
                        continue; // Passa all'iterazione successiva del ciclo
                    }
                    
                    // blocco di stampa
                /*    for (Task t : instance.getTasks()) {
                        // Stampa nel formato: ID StartStation EndStation StartTime EndTime
                        System.out.printf("%d\t%d\t%d\t%d\t%d%n",
                                t.getID(),
                                t.getStartStation(),
                                t.getEndStation(),
                                t.getStartTime(),
                                t.getEndTime());
                    }
                  */
                   // System.out.println("-----------------------------------------------------\n");
             /*
              * Path csv = Paths.get(String.format("tasks.csv", n));
                    try (BufferedWriter w = Files.newBufferedWriter(csv, StandardCharsets.UTF_8,
                            StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING)) {
                        w.write("taskId,startTime,endTime,duration,startStation,endStation\n");
                        for (instance.Task t : instance.getTasks()) {
                            int d = t.getEndTime() - t.getStartTime();
                            w.write(String.format(Locale.ROOT, "%d,%d,%d,%d,%d,%d%n",
                                t.getID(), t.getStartTime(), t.getEndTime(), d,
                                t.getStartStation(), t.getEndStation()));
                        }
                    }
              */
                   
                  
                
                    // Solve this instance with each different pricing problem solver.
                    PricingProblemSolver[] solvers = new PricingProblemSolver[numSolvers];
                    solvers[0] = new QuadraticBreak2(instance);             
                    //QuadraticBreak qb = (QuadraticBreak) solvers[0]; 
                    //debugDuty455(qb.getGraph(), instance.getTasks());
                    long runStartTime = System.currentTimeMillis();
                  
                    // Estrai il nome dell'istanza dal path del file
                    String instanceName = Paths.get(taskFilePath).getFileName().toString()
                        .replaceAll("\\.[^.]*$", "");  // rimuove estensione
                    
                    ColumnGeneration.applyColumnGeneration0SI(instance, solvers, statistics, instanceName);
                    long runEndTime = System.currentTimeMillis();
                    long totalRunTime = runEndTime - runStartTime;
                    for (int j=0;j< numSolvers; j++) {
                    	String solverName = solvers[j].getClass().getSimpleName();
                    
                  //  	sb.append(String.format(Locale.ROOT, "%s;%d;%s\n", solverName, totalRunTime,taskFilePath ));
                    	util.DutyValidator.validateExternalDuties(validation, instance);	
                    	util.DutyValidator.analyzeDeadheading(validation, instance);
                    	System.out.println(totalRunTime+" ms");
                    }         
                }
            } catch (Exception e) {
                System.err.println("ERRORE nel processare " + instanceFile + ": " + e.getMessage());
                e.printStackTrace();
                continue; // Continua con l'istanza successiva
            }
        } 
    
    
    
    }

	private static void debugDuty455(PricingGraph graph, List<Task> tasks) {
		// TODO Auto-generated method stub
		
	}
	
		
		
  /*  public static void main (String[] args) throws IloException, IOException {
        
        // Parametri
        int numSolvers = 1;

        // Inizializza il file di output CSV
        StringBuilder sb = new StringBuilder();
        sb.append("solver;totalRunTime;Source File\n");

        // --- INIZIO MODIFICA ---

        // 1. Definisci il percorso di base della tua cartella
        String basePath = "C:\\Users\\sebastiano insinga\\Desktop\\Tesi\\Austrian Istances\\";
        
        // 2. Crea l'elenco dei file che vuoi processare (dalla tua immagine)
        List<String> fileNames = Arrays.asList(
            "Transformed-15-A-190T-21L.txt",
            "Transformed-41-A-1450T-82L-randomized.txt",
            "Transformed-45-A-1650T-91L.txt",
            "Transformed-50-A-1900T-102L-randomized.txt",
            "Transformed-51-A-1950T-103L.txt",
            "Transformed-58-A-2290T-114L.txt"
        );

        // 3. Sostituisci i vecchi cicli 'for' con un ciclo su 'fileNames'
        for (String fileName : fileNames) 
        {
            // Ricrea le statistiche per ogni nuova istanza
            double[][] statistics = new double[numSolvers][2];

            // Costruisci il percorso completo del file
            String taskFilePath = basePath + fileName;
            
            // Stampa di controllo per sapere quale file stai processando
            System.out.println("\n--- Inizio processamento istanza: " + taskFilePath + " ---");

            // Lettura da file
            Instance instance = InstanceReader.readInstanceFromFile(taskFilePath);
            
            // Controlla se l'istanza è valida
            if (instance.getTasks() == null || instance.getTasks().isEmpty()) {
                System.out.println("Istanza senza task o con task null: salto la risoluzione.");
                continue; // 'continue' salta al prossimo file
            }
    */        
            /*
            System.out.println("Stampa dei task:");
            for (Task t : instance.getTasks()) {
                System.out.printf("%d\t%d\t%d\t%d\t%d%n",
                        t.getID(),
                        t.getStartStation(),
                        t.getEndStation(),
                        t.getStartTime(),
                        t.getEndTime());
            }
            System.out.println("-----------------------------------------------------\n");
            */

            // Risolvi questa istanza
      /*      PricingProblemSolver[] solvers = new PricingProblemSolver[numSolvers];
            solvers[0] = new QuadraticBreak(instance);
            
            // Avvia il cronometro
            long runStartTime = System.currentTimeMillis();
            
            ColumnGeneration.applyColumnGeneration0S(instance, solvers, statistics);
            
            // Ferma il cronometro
            long runEndTime = System.currentTimeMillis();
            long totalRunTime = runEndTime - runStartTime;
            
            System.out.printf("Tempo esecuzione: %.3f secondi%n", totalRunTime / 1000.0);

            // Aggiungi i risultati al CSV
            for (int j = 0; j < numSolvers; j++) {
                String solverName = solvers[j].getClass().getSimpleName();
                sb.append(String.format(Locale.ROOT, "%s;%d;%s\n", solverName, totalRunTime, taskFilePath));
            }
            
            System.out.println("--- Fine processamento: " + fileName + " ---");
        } 
        
        // --- FINE MODIFICA ---

        // Questa parte finale del tuo codice è corretta e rimane invariata.
        // Scrive TUTTI i risultati accumulati in 'sb' nel file CSV.
        Path out = Paths.get("results.csv").toAbsolutePath();
        System.out.println("\nScrivo il CSV in: " + out);

        try (BufferedWriter bw = Files.newBufferedWriter(out,
                StandardCharsets.UTF_8,
                StandardOpenOption.CREATE,
                StandardOpenOption.TRUNCATE_EXISTING)) {
            bw.write(sb.toString());
        }

        System.out.println("Scrittura completata. Righe totali (incl. header): " +
                sb.toString().lines().count());
    }	
	
*/


}
		
	
	
	
	
		
	

	
	

	
	

