package util;



import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import instance.Instance;
import instance.Task;



public class InstanceReader {

	public static Instance readInstanceFromFile(String filePath)
		throws IOException {
        List<Task> tasks = new ArrayList<>();
        Set<Integer> uniqueStations = new HashSet<>();
        
        /*
         * BufferReader ---> inserimento in un Buffer di memoria il contenuto del file "filePath" perchè 
         * più efficiente rispetto all'utilizzo del solo FileReader
         * 
         */
        try (BufferedReader reader = new BufferedReader(new FileReader(filePath))) {
            String line;
            /* ciclo di lettura per ogni variabile riga del file di testo 
             * il ciclo while termina nel momento in cui non vengono lette più righe
             */        
            while ((line = reader.readLine()) != null) {  
                // Dividi la riga in base a uno o più spazi 
                String[] parts = line.split("\\s+");
                /*
                 * controllo che la riga sia correttamente formatta e che abbia effettivamente 5 caratteri
                 * seguiti da spazio
                 */         
                if (parts.length != 5) {
                    System.err.println("Attenzione: Riga mal formattata, la salto: " + line);
                    continue;
                }
                try {
                    /*
                     * conversione della stringa (parts[] in un intero
                     *	esempio la stringa "1" viene convertita nell'intero numero 1
                     */
                	
                	int id = Integer.parseInt(parts[0]);
                    int startStation = Integer.parseInt(parts[1]);
                    int endStation = Integer.parseInt(parts[2]);
                    int startTime = Integer.parseInt(parts[3]);
                    int endTime = Integer.parseInt(parts[4]);

                    // Crea l'oggetto Task e aggiungilo alla lista
                    tasks.add(new Task(id, startTime, endTime, startStation, endStation));            
                    uniqueStations.add(startStation);
                    uniqueStations.add(endStation);             
                } catch (NumberFormatException e) {
                    System.err.println("Warning on task parsing: " + line);
                }
            }
        }
       
       //Generazione dei depot, uniqueStations in questo momento contiene la lista di tutte le stazioni
        List<Integer> depotIds = new ArrayList<>(uniqueStations);
        System.out.println("List of depots: " + depotIds);
        
        //---------------GENERAZIONE DELLA MATRICE DELLE DISTANZE---------//
        /*
         * associa ad ogni stazione che sarà la chiave della nostra mappa una lista in cui associa 
         * ad ogni stazione, la
         * distanza da quella stazione
         */
        Map<Integer, Map<Integer, Double>> stationDistances = new LinkedHashMap<>();
        final double DEFAULT_TRAVEL_COST = 20.0; 

        /*
         * Itera su tutte le stazioni della lista uniqueStations e controlla se la stazione è la stessa
         * allora nella Mappa delle distanze viene inserito il valore 0.0 mentre se la stazione non è la stessa
         * allora viene inserito il valore di DEFAULT
         */
        
        for (Integer station1 : uniqueStations) {
 	
        	Map<Integer, Double> distancesFromStation1 = new LinkedHashMap<>();
            for (Integer station2 : uniqueStations) {
                if (station1.equals(station2)) {
                    distancesFromStation1.put(station2, 0.0);
                } else {
                    distancesFromStation1.put(station2, DEFAULT_TRAVEL_COST);
                }
            }
            stationDistances.put(station1, distancesFromStation1);
        }

        
        
        
        
        
        // Crea e restituisci l'oggetto Instance
        return new Instance(depotIds,tasks,stationDistances);
    }
	
	
}
