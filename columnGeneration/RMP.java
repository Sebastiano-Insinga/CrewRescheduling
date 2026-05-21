package columnGeneration;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import ilog.concert.IloColumn;
import ilog.concert.IloException;
import ilog.concert.IloNumVar;
import ilog.concert.IloNumVarType;
import ilog.concert.IloObjective;
import ilog.concert.IloRange;
import ilog.cplex.IloCplex;
import instance.Instance;
import instance.Task;

/**
 * Models the restricted master problem of a crew scheduling problem. It
 * contains a coverage constraint for each task, and a nonnegative variable for
 * each duty.
 * 
 * @author B.T.C. van Rossum
 */
public class RMP
{
	private List<Task> tasks;
	private IloCplex cplex;
	private IloObjective objective;

	private Map<Duty, IloNumVar> dutyVarMap; // associa ad ogni duty il x(delta)
	private Map<Task, IloRange> coverConstraintMap;
	/**
	 * Initialise restricted master problem based on instance of the crew scheduling
	 * problem.
	 * 
	 * @param instance instance of the crew scheduling problem
	 * @throws IloException exception thrown by CPLEX
	 */
	public RMP(Instance instance) throws IloException
	{
		// Initialisation.
		this.tasks = instance.getTasks();

		this.cplex = new IloCplex();
		cplex.setOut(null);
		this.objective = cplex.addMinimize();

		this.dutyVarMap = new LinkedHashMap<>();
		this.coverConstraintMap = new LinkedHashMap<>();

		// Add constraints.
		addCoverConstraints();
	}

	/**
	 * Solve the problem.
	 * 
	 * @throws IloException exception thrown by CPLEX
	 */
	public void solve() throws IloException
	{
		cplex.solve();
	}

	/**
	 * Clean the problem to free up memory.
	 * 
	 * @throws IloException exception thrown by CPLEX
	 */
	public void clean() throws IloException
	{
		cplex.clearModel();
		cplex.end();
	}

	/**
	 * Returns objective value of optimal solution.
	 * 
	 * @return objective value of optimal solution
	 * @throws IloException exception thrown by CPLEX
	 */
	public double getObjectiveValue() throws IloException
	{
		return cplex.getObjValue();
	}

	/**
	 * Returns dual value of coverage constraint of a given task.
	 * 
	 * @param task task
	 * @return dual value of coverage constraint of task
	 * @throws IloException exception thrown by CPLEX
	 */
	public double getCoverDual(Task task) throws IloException
	{
		//System.out.println("Stampa valore duale\n"+cplex.getDual(coverConstraintMap.get(task)));
		return cplex.getDual(coverConstraintMap.get(task));		
	}

	/**
	 * Initialises a coverage constraint for each task.
	 * 
	 * @throws IloException exception thrown by CPLEX
	 */
	private void addCoverConstraints() throws IloException
	{
		for (Task task : tasks)  
		{
			//IloRange range = cplex.addGe(cplex.constant(0.0),1); //per ogni riga di task imposta il vincolo di copertura del RMP
			//coverConstraintMap.put(task, range);
			String constraintName = "c" + task.getID();
			//IloRange range = cplex.addGe(cplex.constant(0.0),1); //per ogni riga di task imposta il vincolo di copertura del RMP
			IloRange range = cplex.addGe(cplex.constant(0.0), 1, constraintName);
			coverConstraintMap.put(task, range);			
		}
	}

	/**
	 * Adds a new duty to the restricted master problem.
	 * 
	 * @param duty duty to be added to the restricted master problem
	 * @throws IloException exception thrown by CPLEX
	 */
	public void addDuty(Duty duty) throws IloException
	{
		// Make a new column.
		IloColumn column = cplex.column(objective, duty.getCost());

		
		
		
		// Add to coverage constraint.
		for (Task task : duty.getTasks())
		{
			if (coverConstraintMap.containsKey(task)) //per ognuno dei task coperti se un codice corrisponde con il codice della task coperto da quella duty allora
			{
				IloColumn coefficient = cplex.column(coverConstraintMap.get(task), 1); //aggiorna il valore ad 1 di quella task
				column = column.and(coefficient);
			}
		}
		String varName="D"+duty.getID();
		// Add column.
		dutyVarMap.put(duty, cplex.numVar(column, 0, Double.MAX_VALUE,varName));
		//System.out.println(cplex.toString());
	}

	 public IloCplex getCplex() {
	        return cplex;
	    }
	
	 public Map<Duty, Double> getDutyValues() throws IloException {
	        Map<Duty, Double> sol = new LinkedHashMap<>();
	  for (Map.Entry<Duty, IloNumVar> e : dutyVarMap.entrySet()) {
	            sol.put(e.getKey(), cplex.getValue(e.getValue()));
	        }
	        return sol;
	    }
	


//nuovi metodi per test
	 
	 public java.util.List<Duty> getDuties() {
		    return new java.util.ArrayList<>(dutyVarMap.keySet()); // stesso ordine della mappa
		}
	

		public double getValueOf(Duty d) throws ilog.concert.IloException {
		    ilog.concert.IloNumVar v = dutyVarMap.get(d);
		    if (v == null) throw new IllegalArgumentException("Duty non presente nell'RMP");
		    return cplex.getValue(v);
		}

		public java.util.Set<java.util.Map.Entry<Duty, ilog.concert.IloNumVar>> getDutyEntries() {
		    return dutyVarMap.entrySet();
		}

		public int getDutyVarMapSize() {
		    return dutyVarMap.size();
		}


		public java.util.LinkedHashMap<Duty, Double> getDutyValuesMap() throws ilog.concert.IloException {
		    java.util.LinkedHashMap<Duty, Double> out = new java.util.LinkedHashMap<>();
		    for (java.util.Map.Entry<Duty, ilog.concert.IloNumVar> e : dutyVarMap.entrySet()) {
		        out.put(e.getKey(), cplex.getValue(e.getValue()));
		    }
		    return out;
		}

		
		public void AddForcedDutyConstraint(Duty duty) throws IloException
		{
				IloNumVar dutyVar = dutyVarMap.get(duty);
				
				if (dutyVar != null) {
					// 2. Create a name for the new constraint
					String constraintName = "ForcedConstraint_" + duty.getID();
					
					// 3. Add the new constraint (row) directly to CPLEX.
					// This creates the constraint: 1.0 * dutyVar >= 1.0
					cplex.addEq(dutyVar, 1.0, constraintName);
				} 
			}
			

		// In RMP.java, aggiungi questo metodo alla fine della classe:

		/**
		 * Converte tutte le variabili di duty da Continue a Binarie/Intere.
		 * Da chiamare SOLO dopo che la Column Generation è terminata.
		 */
		public void switchToIntegerMode() throws IloException {
			
			// 1. Definisci una soglia di tolleranza (epsilon)
			double epsilon = 1e-5; 
			
			int mapSize = dutyVarMap.size();
			System.out.println("[STEP 1] Scanning " + mapSize + " variables to find non-zero values...");
			
			// Lista per contenere SOLO le variabili che vogliamo convertire (quelle > 0)
			List<IloNumVar> variablesToConvert = new ArrayList<>();

			// 2. Itera su tutte le variabili nella mappa
			for (IloNumVar var : dutyVarMap.values()) {
				try {
					// Ottieni il valore della variabile dalla soluzione LP rilassata
					double value = cplex.getValue(var);
					
					// 3. Controlla se il valore è significativamente maggiore di 0
					if (value > epsilon) {
						variablesToConvert.add(var);
					}
				} catch (IloException e) {
					// Questo può succedere se il modello non è stato risolto (solve()) prima di chiamare questo metodo
					System.err.println("[ERROR] Impossibile recuperare il valore per una variabile. Assicurati di aver chiamato rmp.solve() prima.");
					throw e;
				}
			}
			if (variablesToConvert.isEmpty()) {
				System.out.println("[WARN] Nessuna variabile con valore > 0 trovata. Nessuna conversione effettuata.");
				return;
			}

			System.out.println("[INFO] Trovate " + variablesToConvert.size() + " variabili con valore > 0 da convertire in Intere.");

			// 4. Crea gli array per CPLEX solo con le variabili filtrate
			IloNumVar[] varsArray = variablesToConvert.toArray(new IloNumVar[0]);			
			IloNumVarType[] typesArray = new IloNumVarType[varsArray.length];			
			
			for (int i = 0; i < varsArray.length; i++) {
				typesArray[i] = IloNumVarType.Bool; // Imposta a Bool (o Int)
			}
			
			System.out.println("[STEP 2] Applying conversion to detected variables...");
			
			// 5. Applica la conversione al modello
			cplex.add(cplex.conversion(varsArray, typesArray));
			
			/*
			 * NOTA IMPORTANTE:
			 * Le variabili che NON sono state aggiunte a 'varsArray' rimarranno 
			 * di tipo continuo (Float/NumVar). Se vuoi forzare quelle a 0, 
			 * dovresti aggiungere un vincolo (UpperBound = 0) per quelle escluse.
			 */
						
			System.out.println("RMP convertito in MIP (Solo per le variabili attive).");
		}
		public void switchToIntegerMode1() throws IloException {
		    System.out.println("--- Conversione RMP da Continuo a Intero (MIP) ---");
		    
		    // 1. Recupera TUTTE le variabili attualmente nel modello
		    // Non filtriamo in base al valore attuale: ci servono tutte le opzioni possibili
		    // per trovare un incastro intero valido.
		    Collection<IloNumVar> allDutyVars = dutyVarMap.values();
		    
		    if (allDutyVars.isEmpty()) {
		        System.out.println("[WARN] Nessuna variabile di turno presente. Impossibile convertire.");
		        return;
		    }

		    // 2. Prepara gli array per CPLEX
		    IloNumVar[] varsArray = allDutyVars.toArray(new IloNumVar[0]);
		    IloNumVarType[] typesArray = new IloNumVarType[varsArray.length];

		    // 3. Imposta il tipo a BOOLEAN (0 o 1) per TUTTE le variabili
		    for (int i = 0; i < varsArray.length; i++) {
		        typesArray[i] = IloNumVarType.Bool; 
		    }

		    // 4. Applica la conversione al modello
		    cplex.add(cplex.conversion(varsArray, typesArray));
		    
		    System.out.println("[INFO] Convertite " + varsArray.length + " variabili in Binarie.");
		    System.out.println("CPLEX ora cercherà la combinazione ottima intera tra tutte le colonne generate.");
		}
		
		
		public void switchToIntegerAggressive() throws IloException {
		    System.out.println("--- MEMORY SAVER: Rimuovo tutte le colonne a valore 0 (Versione Ottimizzata) ---");
		    
		    // Lista per dire a CPLEX cosa cancellare (veloce da riempire)
		    List<IloNumVar> cplexDeleteList = new ArrayList<>();
		    
		    // Lista per dire a CPLEX cosa convertire (veloce da riempire)
		    List<IloNumVar> cplexConvertList = new ArrayList<>();

		    // 1. Usiamo l'ITERATORE per scansionare e rimuovere in un colpo solo
		    // Questo è il trucco per evitare la lentezza O(N^2)
		    java.util.Iterator<Map.Entry<Duty, IloNumVar>> it = dutyVarMap.entrySet().iterator();
		    
		    int kept = 0;
		    int removed = 0;
		    
		    while (it.hasNext()) {
		        Map.Entry<Duty, IloNumVar> entry = it.next();
		        IloNumVar var = entry.getValue();
		        
		        double val = 0.0;
		        try {
		            val = cplex.getValue(var);
		        } catch (IloException e) {
		            // Se la variabile è nuova o non ha valore, assumiamo 0
		            val = 0.0;
		        }

		        if (val > 1e-5) {
		            // MANTIENI: Aggiungi alla lista di conversione
		            cplexConvertList.add(var);
		            kept++;
		        } else {
		            // RIMUOVI: 
		            // 1. Aggiungi alla lista per CPLEX
		            cplexDeleteList.add(var);
		            // 2. Rimuovi dalla mappa Java immediatamente tramite iteratore (efficientissimo)
		            it.remove(); 
		            removed++;
		        }
		    }
		    
		    System.out.println("[JAVA] Pulizia Mappa completata. Rimossi: " + removed + ", Mantenuti: " + kept);
		    System.out.println("[CPLEX] Inizio cancellazione variabili dal solver...");

		    // 2. Cancellazione massiva da CPLEX
		    if (!cplexDeleteList.isEmpty()) {
		        IloNumVar[] removeArray = cplexDeleteList.toArray(new IloNumVar[0]);
		        // Questa operazione può comunque richiedere qualche secondo perché CPLEX deve
		        // ristrutturare la matrice interna, ma è inevitabile.
		        cplex.delete(removeArray);
		    }
		    
		    // Forza la pulizia della memoria RAM Java ora che la mappa è leggera
		    cplexDeleteList = null; // Aiuta il Garbage Collector
		    System.gc(); 

		    System.out.println("[CPLEX] Inizio conversione a Interi...");

		    // 3. Conversione variabili rimaste
		    if (!cplexConvertList.isEmpty()) {
		        IloNumVar[] keepArray = cplexConvertList.toArray(new IloNumVar[0]);
		        ilog.concert.IloNumVarType[] types = new ilog.concert.IloNumVarType[keepArray.length];
		        for(int i=0; i<keepArray.length; i++) types[i] = ilog.concert.IloNumVarType.Bool;
		        
		        cplex.add(cplex.conversion(keepArray, types));
		    }
		    
		    System.out.println("--- MODELLO OTTIMIZZATO E PRONTO PER IL MIP ---");
		}
		
		
		//put the LB of the variable to 1.0
		public void lockDuty(Duty duty) throws IloException {
		    IloNumVar var = dutyVarMap.get(duty);
		    if (var != null) {
		        var.setLB(1.0);
		    } else {
		        System.err.println("Errore: Tentativo di fissare una duty non presente nella mappa variabili.");
		    }
		}
		
		public boolean isDutyLocked(Duty duty) throws IloException {
		    IloNumVar var = dutyVarMap.get(duty);
		    if (var != null) {
		        return var.getLB() > 0.99;
		    }
		    return false;
		}
		
		
		/**
		 * Imposta un limite di tempo (in secondi) per la risoluzione del problema.
		 * Utile per la fase Integer (MIP) per evitare esecuzioni infinite.
		 * * @param seconds il tempo limite in secondi
		 * @throws IloException
		 */
		public void setTimeLimit(double seconds) throws IloException {
		    // IloCplex.Param.TimeLimit accetta il valore in secondi
		    cplex.setParam(IloCplex.Param.TimeLimit, seconds);
		}
		
		
		
		
		
		
		
}







