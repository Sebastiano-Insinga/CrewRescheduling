
import csv
import os
from pathlib import Path

# Configurazione
CSV_INPUT_DIR = r"c:\Users\sebastiano insinga\Desktop\Vienna\TESI\Austrian Istances\results\Original_solution_from_CrewScheduling(csv)"
INSTANCE_DIR = r"C:\Users\sebastiano insinga\Desktop\WU\Crew Rescheduling\CrewScheduling\Weekly_Minutes_Transformed_Instances"
TXT_OUTPUT_DIR = r"c:\Users\sebastiano insinga\Desktop\Vienna\TESI\Austrian Istances\results\Twan_format(txt)"

def read_instance(instance_file):
    """Legge file istanza e estrae info task: {task_id: {departure, arrival, ...}}"""
    tasks = {}
    with open(instance_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            if len(row) < 5:
                continue
            try:
                task_id = int(row[0])
                origin = int(row[1])
                destination = int(row[2])
                departure = int(row[3])
                arrival = int(row[4])
                
                tasks[task_id] = {
                    'origin': origin,
                    'destination': destination,
                    'departure': departure,
                    'arrival': arrival,
                    'duration': arrival - departure
                }
            except (ValueError, IndexError):
                continue
    
    print(f"✓ Istanza letta: {len(tasks)} task")
    return tasks

def read_duties_csv(csv_file):
    """Legge CSV con DutyID e TaskIDs"""
    duties = {}
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            duty_id = row['DutyID']
            task_ids_str = row['TaskIDs'].strip()
            # Parsa TaskIDs (possono essere separati da spazi)
            task_ids = [int(tid) for tid in task_ids_str.split() if tid.strip().isdigit()]
            duties[duty_id] = task_ids
    
    print(f"✓ CSV letto: {len(duties)} duty")
    return duties

def calculate_duty_metrics(duty_task_ids, tasks):
    """Calcola Duration e Costs per un duty"""
    if not duty_task_ids:
        return 0, 0
    
    # Filtra task che esistono nell'istanza
    valid_tasks = [tasks[tid] for tid in duty_task_ids if tid in tasks]
    
    if not valid_tasks:
        return 0, 0
    
    # Duration = Arrival ultimo task - Departure primo task
    departures = [t['departure'] for t in valid_tasks]
    arrivals = [t['arrival'] for t in valid_tasks]
    
    min_departure = min(departures)
    max_arrival = max(arrivals)
    duration = max_arrival - min_departure
    
    # Costs: calcolo semplice (es. proporzionale alla durata + numero task)
    costs = duration + len(valid_tasks) * 10
    
    return costs, duration

def write_twan_format(output_file, duties, tasks):
    """Scrive nel formato TXT di Twan"""
    # Crea la directory se non esiste
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"✓ Directory creata: {output_dir}")
    
    # Primo passaggio: raccogliere tutte le righe e trovare il massimo numero di task
    rows_data = []
    max_tasks = 0
    
    for duty_id, task_ids in duties.items():
        costs, duration = calculate_duty_metrics(task_ids, tasks)
        rows_data.append((costs, duration, task_ids))
        max_tasks = max(max_tasks, len(task_ids))
    
    # Scrivi nel file
    with open(output_file, 'w', encoding='utf-8') as f:
        # Scrivi header
        header_parts = ["Costs", "Duration"]
        header_parts.extend([f"Task_{i+1}" for i in range(max_tasks)])
        header = "\t".join(header_parts) + "\n"
        f.write(header)
        
        # Scrivi righe di dati
        for costs, duration, task_ids in rows_data:
            task_ids_str = '\t'.join(str(tid) for tid in task_ids)
            line = f"{costs:.1f}\t{duration:.1f}\t{task_ids_str}\n"
            f.write(line)
        
        # Sezione uncovered tasks (per ora vuota)
        f.write("\nCosts\n")  # Marker per inizio sezione uncovered
        f.write("MyIndex\n")  # Header uncovered
        # Aggiungere qui task non assegnati se necessario
    
    print(f"✓ File TXT scritto: {output_file}")

def main():
    print("=" * 80)
    print("Conversione batch CSV → Formato TXT Twan")
    print("=" * 80)
    
    # Verifica cartelle di input
    if not os.path.exists(CSV_INPUT_DIR):
        print(f"❌ Errore: Cartella CSV non trovata: {CSV_INPUT_DIR}")
        return
    
    if not os.path.exists(INSTANCE_DIR):
        print(f"❌ Errore: Cartella Istanze non trovata: {INSTANCE_DIR}")
        return
    
    # Crea cartella output se non esiste
    if not os.path.exists(TXT_OUTPUT_DIR):
        os.makedirs(TXT_OUTPUT_DIR, exist_ok=True)
        print(f"✓ Directory creata: {TXT_OUTPUT_DIR}")
    
    # Trova tutti i CSV nella cartella
    csv_files = sorted(Path(CSV_INPUT_DIR).glob("*_duties_with_tasks.csv"))
    
    if not csv_files:
        print(f"❌ Errore: Nessun file CSV trovato in {CSV_INPUT_DIR}")
        return
    
    print(f"\n✓ Trovati {len(csv_files)} file CSV da convertire\n")
    
    successful = 0
    failed = 0
    
    for csv_file in csv_files:
        csv_name = csv_file.name
        # Estrai il nome dell'istanza dal CSV (es: Transformed-52-A-2000T-105L)
        instance_name = csv_name.replace("_duties_with_tasks.csv", "")
        
        # Trova il file TSV corrispondente
        instance_file = os.path.join(INSTANCE_DIR, f"{instance_name}.tsv")
        
        if not os.path.exists(instance_file):
            print(f"⚠ SKIP: {csv_name}")
            print(f"   → Istanza non trovata: {instance_file}")
            failed += 1
            continue
        
        # File di output
        txt_output = os.path.join(TXT_OUTPUT_DIR, f"{instance_name}_sol.txt")
        
        print(f"Elaborazione: {csv_name}")
        
        try:
            # Leggi istanza
            tasks = read_instance(instance_file)
            
            # Leggi CSV
            duties = read_duties_csv(str(csv_file))
            
            # Converti
            write_twan_format(txt_output, duties, tasks)
            
            print(f"✓ OK: {txt_output}\n")
            successful += 1
            
        except Exception as e:
            print(f"❌ ERRORE: {csv_name}")
            print(f"   → {str(e)}\n")
            failed += 1
    
    # Statistiche finali
    print("=" * 80)
    print(f"✓ Conversione completata!")
    print(f"  - Successi: {successful}")
    print(f"  - Errori: {failed}")
    print(f"  - Totale: {len(csv_files)}")
    print(f"\nOutput: {TXT_OUTPUT_DIR}")
    print("=" * 80)

if __name__ == "__main__":
    main()
