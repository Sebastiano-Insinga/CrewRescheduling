package util;

import instance.Instance;
import instance.Parameters;
import instance.Task;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class DutyValidator {

    /**
     * Legge un file di duty esterni e valida ogni riga rispetto ai vincoli dell'istanza e dei Parametri.
     * Formato atteso file: [DutyID] [TaskID_1] [TaskID_2] ...
     * * @param filePath Percorso assoluto del file da validare
     * @param instance L'istanza caricata contenente i Task originali
     */
    public static void validateExternalDuties(String filePath, Instance instance) {
        // 1. Mappa veloce per trovare i Task dal loro ID
        Map<Integer, Task> taskMap = instance.getTasks().stream()
                .collect(Collectors.toMap(Task::getID, t -> t));

        int totalDuties = 0;
        int validDuties = 0;
        int invalidDuties = 0;

        try (BufferedReader br = new BufferedReader(new FileReader(filePath))) {
            String line;
            System.out.println("--- VALIDAZIONE FILE: " + filePath + " ---");
            
            while ((line = br.readLine()) != null) {
                if (line.trim().isEmpty()) continue;
                totalDuties++;

                // Parsing della riga
                String[] parts = line.trim().split("\\s+");
                
                // Controllo base: deve esserci almeno ID Duty e un Task
                if (parts.length < 2) {
                    System.out.println("Riga ignorata (troppo corta): " + line);
                    continue;
                }

                // Recuperiamo l'ID del Duty (prima colonna) per il log
                String dutyIdStr = parts[0]; 

                List<Task> dutyTasks = new ArrayList<>();
                boolean tasksFound = true;

                // 2. CICLO DI LETTURA TASK: Parte da i=1 per saltare l'ID del Duty
                for (int i = 1; i < parts.length; i++) {
                    String part = parts[i];
                    try {
                        int id = Integer.parseInt(part);
                        Task t = taskMap.get(id);
                        if (t == null) {
                            System.out.println("Duty " + dutyIdStr + " -> ERRORE CRITICO: Task ID " + id + " non esiste nell'istanza caricata.");
                            tasksFound = false;
                            break;
                        }
                        dutyTasks.add(t);
                    } catch (NumberFormatException e) {
                        continue; // Ignora eventuali caratteri non numerici
                    }
                }

                if (!tasksFound || dutyTasks.isEmpty()) {
                    invalidDuties++;
                    continue;
                }

                // 3. VALIDAZIONE LOGICA SUI VINCOLI
                String error = checkConstraints(dutyTasks);
                
                if (error == null) {
                    validDuties++;
                } else {
                    // Stampa l'errore specifico per capire perché il tuo codice lo scarterebbe
                    System.out.println("Duty " + dutyIdStr + " [INVALIDO]: " + error);
                    invalidDuties++;
                }
            }
            
            System.out.println("--------------------------------------------------");
            System.out.println("RISULTATO VALIDAZIONE:");
            System.out.println("Totale Duty letti: " + totalDuties);
            System.out.println("Duty VALIDI (compatibili col tuo codice): " + validDuties);
            System.out.println("Duty INVALIDI (violano i tuoi vincoli): " + invalidDuties);
            System.out.println("--------------------------------------------------\n");

        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    /**
     * Controlla i vincoli fisici e legali del duty.
     * Ritorna null se è valido, oppure una stringa con la descrizione dell'errore.
     */
    private static String checkConstraints(List<Task> tasks) {
        Task first = tasks.get(0);
        Task last = tasks.get(tasks.size() - 1);

        // --- 1. Vincolo Lunghezza Massima Duty ---
        int totalDuration = last.getEndTime() - first.getStartTime();
        if (totalDuration > Parameters.MAX_DUTY_LENGTH) {
            return "Supera MAX_DUTY_LENGTH (" + totalDuration + " > " + Parameters.MAX_DUTY_LENGTH + ")";
        }

        boolean hasValidBreak = false;
        int currentWorkBlockStart = first.getStartTime();

        for (int i = 0; i < tasks.size() - 1; i++) {
            Task t1 = tasks.get(i);
            Task t2 = tasks.get(i + 1);

            // --- 2. Connettività Spaziale (Stazioni) ---
            // Il tuo GraphConstructor.stationsMatch richiede che endStation == startStation.
            if (t1.getEndStation() != t2.getStartStation()) {
                return "Discontinuità Stazioni (T" + t1.getID() + " arriva a " + t1.getEndStation() + 
                       " != T" + t2.getID() + " parte da " + t2.getStartStation() + ")";
            }

            // --- 3. Connettività Temporale ---
            if (t1.getEndTime() > t2.getStartTime()) {
                return "Errore Temporale (T" + t1.getID() + " finisce dopo l'inizio di T" + t2.getID() + ")";
            }

            // --- 4. Calcolo e Verifica Pausa ---
            int gap = t2.getStartTime() - t1.getEndTime();
            
            // Se c'è un gap sufficiente per essere considerato pausa
            if (gap >= Parameters.MIN_BREAK_LENGTH) {
                // Controlla se il blocco di lavoro PRIMA di questa pausa ha rispettato il limite
                if ((t1.getEndTime() - currentWorkBlockStart) <= Parameters.MAX_TIME_WITHOUT_BREAK) {
                    hasValidBreak = true;
                    // Reset del timer per il blocco successivo alla pausa
                    currentWorkBlockStart = t2.getStartTime();
                } else {
                    // Nota: se guidi troppo a lungo PRIMA di fare la pausa valida, è comunque una violazione
                    return "Supera MAX_TIME_WITHOUT_BREAK prima della pausa (tra T" + t1.getID() + " e T" + t2.getID() + ")";
                }
            }
        }

        // --- 5. Controllo finale sul blocco di lavoro dopo l'ultima pausa (o unica se non c'è pausa) ---
        if ((last.getEndTime() - currentWorkBlockStart) > Parameters.MAX_TIME_WITHOUT_BREAK) {
            return "Supera MAX_TIME_WITHOUT_BREAK nel blocco finale (o unico blocco)";
        }
        
        // --- 6. Obbligo di Pausa ---
        // Se il tuo algoritmo QuadraticBreak richiede OBBLIGATORIAMENTE una pausa per duty lunghi, 
        // e qui non ne abbiamo trovata una valida, è una violazione.
        // La logica standard del paper prevede pausa obbligatoria se il duty supera una certa durata.
         if (!hasValidBreak) {
             // Esempio: se il duty dura più di 5h30 deve avere una pausa, altrimenti è illegale
             if (totalDuration > Parameters.MAX_TIME_WITHOUT_BREAK) {
                 return "Manca Pausa Obbligatoria (Duty lungo senza pause valide)";
             }
        }
        

        return null; // Nessun errore trovato, il duty è valido
    }

    /**
     * Analizza un file di duty e stampa un report specifico sui cambi stazione (Deadheading).
     * Utile per capire quanti duty della soluzione di riferimento sfruttano spostamenti non modellati.
     */
    public static void analyzeDeadheading(String filePath, Instance instance) {
        Map<Integer, Task> taskMap = instance.getTasks().stream()
                .collect(Collectors.toMap(Task::getID, t -> t));

        int totalDuties = 0;
        int dutiesWithDeadheading = 0;
        int totalDeadheads = 0;

        System.out.println("\n==================================================");
        System.out.println("REPORT DEADHEADING (Spostamenti tra Stazioni)");
        System.out.println("File: " + filePath);
        System.out.println("==================================================");

        try (BufferedReader br = new BufferedReader(new FileReader(filePath))) {
            String line;
            while ((line = br.readLine()) != null) {
                if (line.trim().isEmpty()) continue;
                
                String[] parts = line.trim().split("\\s+");
                if (parts.length < 2) continue; // Salta righe vuote o malformate

                List<Task> tasks = new ArrayList<>();
                // Salta il primo elemento se è l'ID del duty (adatta in base al formato del file)
                int startIndex = 1; 
                
                for (int i = startIndex; i < parts.length; i++) {
                    try {
                        int id = Integer.parseInt(parts[i]);
                        Task t = taskMap.get(id);
                        if (t != null) tasks.add(t);
                    } catch (NumberFormatException e) { /* ignore */ }
                }

                if (tasks.isEmpty()) continue;
                totalDuties++;

                boolean hasDeadhead = false;
                for (int i = 0; i < tasks.size() - 1; i++) {
                    Task t1 = tasks.get(i);
                    Task t2 = tasks.get(i+1);

                    if (t1.getEndStation() != t2.getStartStation()) {
                        hasDeadhead = true;
                        totalDeadheads++;
                        
                        // Calcola il gap temporale per capire se è uno spostamento in orario di lavoro o pausa
                        int gap = t2.getStartTime() - t1.getEndTime();
                        String tipo = (gap >= 30) ? "PAUSA" : "LAVORO";

                        System.out.printf("Duty %s [RIGA %d]: Cambio Stazione %d -> %d (Gap: %d min - %s)\n", 
                                parts[0], totalDuties, t1.getEndStation(), t2.getStartStation(), gap, tipo);
                        System.out.printf("   Tra Task %d (Fine %d) e Task %d (Inizio %d)\n", 
                                t1.getID(), t1.getEndTime(), t2.getID(), t2.getStartTime());
                    }
                }
                
                if (hasDeadhead) {
                    dutiesWithDeadheading++;
                }
            }

            System.out.println("==================================================");
            System.out.println("STATISTICHE FINALI DEADHEADING");
            System.out.println("Totale Duty Analizzati: " + totalDuties);
            System.out.println("Duty con almeno un cambio stazione: " + dutiesWithDeadheading);
            System.out.println("Totale spostamenti (salti) trovati: " + totalDeadheads);
            System.out.printf("Percentuale Duty 'Impossibili' senza deadheading: %.2f%%\n", 
                    (double)dutiesWithDeadheading / totalDuties * 100);
            System.out.println("==================================================");

        } catch (IOException e) {
            e.printStackTrace();
        }
    }


}