# Documentazione: Lettura e Gestione delle Istanze

## Panoramica Generale

Il codice Main.py gestisce il **crew scheduling** (pianificazione iniziale dell'equipaggio) e il **crew rescheduling** (ripianificazione in caso di disruption). Entrambi i procedimenti leggono istanze diverse da cartelle specifiche.

---

## 🔵 PARTE 1: CREW SCHEDULING (Pianificazione Iniziale)

### 1.1 File di Input per il Crew Scheduling

#### **Istanza di Crew Scheduling**
- **Percorso**: `path_instance_folder\Crew_Scheduling_Instances\Transformed-{instance}.tsv`
- **Esempio**: `Transformed-52-A-2000T-105L.tsv`
- **Formato**: TSV (Tab-Separated Values)
- **Contenuto**:
  ```
  Task_ID | From_Location | To_Location | Start_Time | End_Time
  1       | 3638          | 4621        | 365        | 426
  2       | 4621          | 3125        | 930        | 955
  ...
  ```

**Dati Contenuti**:
- **Task_ID**: Identificatore univoco del compito (es. 1, 2, 3...)
- **From_Location**: Stazione di partenza
- **To_Location**: Stazione di arrivo
- **Start_Time**: Ora inizio task (in minuti dal giorno 0)
- **End_Time**: Ora fine task

**Esempio di istanza**:
- **52-A-2000T-105L**: 2000 task, 105 locations
- **15-A-190T-21L**: 190 task, 21 locations

---

#### **ID Mapping per il Crew Scheduling**
- **Percorso**: `path_instance_folder\ID_Mappings_Scheduling\ID-Mapping-Transformed-{instance}.tsv`
- **Formato**: TSV
- **Contenuto**: Mappa tra ID interni e ID originali
  ```
  Internal_ID | Original_ID | locomotive | section_type | other_metadata
  1           | 2607        | 1         | 3            | ...
  2           | 1182        | 2         | 1            | ...
  ...
  ```

**Dati Contenuti**:
- **Internal_ID**: ID usato durante l'elaborazione
- **Original_ID**: ID dal file istanza originale
- **locomotive**: Tipo di locomotiva assegnato al task
- **section_type**: Tipo di sezione ferroviaria

**Lettura nel codice**:
```python
id_mapping = readIDMapping(path_instance_folder + "\\ID_Mappings_Scheduling\\ID-Mapping-Transformed-" + instance)
```

---

#### **Soluzione Iniziale (Twan Format)**
- **Percorso**: `path_instance_folder\Original_Crew_Plans\Transformed-{instance}_sol_{time_limit}_{sol_type}.txt`
- **Parametri**:
  - `time_limit`: "10" o "12" ore (massimo tempo di lavoro nel turno)
  - `sol_type`: "1" (solo turni fattibili) o "2" (include turni non fattibili)
- **Formato**: Tab-separated con header
  ```
  Costs   Duration   Task_1  Task_2  Task_3  ...
  106.0   96.0       2607
  116.0   106.0      1182
  ...
  798.0   668.0      1341  1340  1339  1338  1337  1336  ...
  ```

**Dati Contenuti**:
- **Costs**: Costo del turno (corrisponde alla durata)
- **Duration**: Durata effettiva del turno
- **Task_N**: ID dei task assegnati al turno N

**Lettura nel codice**:
```python
internal_format_solution_twan, uncovered_tasks_twan, duty_breaks, loco_knowledge, section_knowledge, suitable_tasks = readSolution_Twan_txt_Format_incl_Uncovered(
    solution_twan_txt_format, crew_scheduling_instance, id_mapping, 
    loco_types, section_types, min_loco_knowledge, min_section_knowledge
)
```

---

### 1.2 Dati Elaborati nel Crew Scheduling

Dopo la lettura, il sistema produce:

| Variabile | Descrizione |
|-----------|-------------|
| `internal_format_solution_twan` | Soluzione nel formato interno: dizionario con `duty_id -> lista di task` |
| `uncovered_tasks_twan` | Task non coperti dalla soluzione iniziale |
| `duty_breaks` | Pause previste per ogni turno (conformità normative) |
| `loco_knowledge` | Conoscenza dell'equipaggio per tipo di locomotiva |
| `section_knowledge` | Conoscenza dell'equipaggio per tipo di sezione |
| `suitable_tasks` | Task idonei per ogni membro dell'equipaggio |

---

## 🔴 PARTE 2: CREW RESCHEDULING (Ripianificazione)

### 2.1 File di Input per il Rescheduling

#### **File di Disruption**
- **Percorso**: `path_instance_folder\Disruption_Files\manuel-{instance}-disrupted_1.json`
- **Formato**: JSON
- **Contenuto**: Specifica quale sezione è interrotta e per quanto tempo
  ```json
  {
    "disruption_start": 1717,
    "disruption_end": 2112,
    "disrupted_sections": [3, 5, 7]
  }
  ```

**Dati Contenuti**:
- **disruption_start**: Inizio della disruption (in minuti)
- **disruption_end**: Fine della disruption (in minuti)
- **disrupted_sections**: ID delle sezioni ferroviarie interessate

**Lettura nel codice**:
```python
disruption_start, disruption_end, disrupted_sections = readDisruption(disruption_file)
```

---

#### **Istanza di Rescheduling (Task Aperti)**
- **Percorso**: `path_instance_folder\Crew_Rescheduling_Instances\Transformed-{instance}.tsv`
- **Formato**: TSV, stesso formato dell'istanza di crew scheduling
- **Contenuto**: Task che rimangono da coprire dopo la disruption
  ```
  Task_ID | From_Location | To_Location | Start_Time | End_Time
  2045    | 1014          | 5100        | 1800       | 1850
  2046    | 5100          | 2997        | 1860       | 1890
  ...
  ```

**Differenza dal Crew Scheduling**:
- Contiene solo i task che devono essere ripianificati
- I task con `departure <= disruption_start` vengono già rimossi

**Lettura nel codice**:
```python
rescheduled_open_tasks = readOpenRescheduledTasks(path_rescheduled_open_tasks)

# Rimozione task già completati
tasks_already_performed = []
for task_id, task in rescheduled_open_tasks.items():
    if task["departure"] <= disruption_start:
        tasks_already_performed.append(task_id)
for task_id in tasks_already_performed:
    rescheduled_open_tasks.pop(task_id, None)
```

---

#### **ID Mapping per il Rescheduling**
- **Percorso**: `path_instance_folder\ID_Mappings_Rescheduling\ID-Mapping-Transformed-{instance}.tsv`
- **Formato**: TSV, come l'ID mapping del crew scheduling
- **Contenuto**: Mapping solo per i task di rescheduling

**Lettura nel codice**:
```python
rescheduled_id_mapping = readIDMapping(path_instance_folder + "\\ID_Mappings_Rescheduling\\ID-Mapping-Transformed-" + instance)
```

---

### 2.2 Dati Elaborati nel Rescheduling

| Variabile | Descrizione |
|-----------|-------------|
| `driver_status` | Stato di ogni membro dell'equipaggio (location, tempo libero, ecc.) |
| `disrupted_tasks` | Task affetti dalla disruption |
| `open_tasks` | Task che devono essere ripianificati |
| `existing_duties` | Turni della soluzione originale (potenzialmente modificati) |
| `uncovered_tasks` | Task che non possono essere coperti nella ripianificazione |
| `suitable_tasks` | Per ogni membro dell'equipaggio, i task che può coprire |

**Lettura nel codice**:
```python
driver_status, disrupted_tasks, open_tasks = generateReschedulingInput(
    fixed_internal_format_solution_twan, 
    fixed_duty_breaks, 
    disruption_file, 
    id_mapping
)

existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, spare_driver_ids = calculateInitialSolution(
    fixed_internal_format_solution_twan, 
    driver_status, 
    rescheduled_open_tasks, 
    disruption_start, 
    disruption_end, 
    720, 
    id_mapping, 
    suitable_tasks
)
```

---

## 📊 Flusso di Lettura Dati: Diagramma

```
┌─────────────────────────────────────────────────────────────┐
│            CREW SCHEDULING (Fase Iniziale)                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Leggi Istanza di Scheduling                              │
│     ↓                                                         │
│     Transformed-{instance}.tsv                               │
│     (2000 task × 105 locations)                              │
│                                                               │
│  2. Leggi ID Mapping Scheduling                              │
│     ↓                                                         │
│     ID-Mapping-Transformed-{instance}.tsv                    │
│     (Mappa ID interni → originali)                           │
│                                                               │
│  3. Leggi Soluzione Iniziale (Twan)                          │
│     ↓                                                         │
│     Transformed-{instance}_sol_12_2.txt                      │
│     (Turni, costi, assegnamenti task)                        │
│                                                               │
│  Output: internal_format_solution_twan                       │
│          uncovered_tasks_twan                                │
│          duty_breaks, loco_knowledge, section_knowledge      │
│                                                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│            CREW RESCHEDULING (Fase Disruption)               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Leggi File di Disruption                                 │
│     ↓                                                         │
│     manuel-{instance}-disrupted_1.json                       │
│     (disruption_start, disruption_end, disrupted_sections)   │
│                                                               │
│  2. Leggi Task Aperti (Rescheduling)                         │
│     ↓                                                         │
│     Transformed-{instance}.tsv (nella cartella Rescheduling) │
│     (Task da ripianificare)                                  │
│                                                               │
│  3. Leggi ID Mapping Rescheduling                            │
│     ↓                                                         │
│     ID-Mapping-Transformed-{instance}.tsv (cartella Rescheduling)
│     (Mappa per i task di rescheduling)                       │
│                                                               │
│  4. Elimina task già completati                              │
│     ↓                                                         │
│     if task["departure"] <= disruption_start:                │
│         remove task                                          │
│                                                               │
│  Output: driver_status                                       │
│          open_tasks (dopo eliminazione)                      │
│          existing_duties (potenzialmente modificati)         │
│          uncovered_tasks                                     │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Parametri Configurabili

Nel codice principale sono definiti:

```python
time_limit = "12"              # Massimo orario di lavoro (10 o 12 ore)
sol_type = "2"                 # Tipo soluzione (1=feasible, 2=include infeasible)

loco_types = [0,1,2,3]         # Tipi di locomotiva
section_types = [0,1,2,3,4,5,6,7,8,9]  # Tipi di sezione

max_dh_duration = 720          # Max durata deadhead (in minuti, no limit)
min_loco_knowledge = 1.0       # Conoscenza minima locomotiva richiesta
min_section_knowledge = 1.0    # Conoscenza minima sezione richiesta

window_size = 300              # Dimensione finestra ottimizzazione (minuti)
runs_per_window = 1            # Numero di run per finestra
method = "DP"                  # Metodo: "DP" (Dynamic Programming) o "model"
```

---

## 📁 Struttura Cartelle

```
path_instance_folder/
├── Crew_Scheduling_Instances/
│   └── Transformed-{instance}.tsv          [Input Crew Scheduling]
├── ID_Mappings_Scheduling/
│   └── ID-Mapping-Transformed-{instance}.tsv
├── Original_Crew_Plans/
│   └── Transformed-{instance}_sol_12_2.txt [Soluzione iniziale]
├── Disruption_Files/
│   └── manuel-{instance}-disrupted_1.json  [Parametri disruption]
├── Crew_Rescheduling_Instances/
│   └── Transformed-{instance}.tsv          [Input Rescheduling]
└── ID_Mappings_Rescheduling/
    └── ID-Mapping-Transformed-{instance}.tsv
```

---

## 🎯 Esempio Concreto: Istanza 52

### Crew Scheduling
- Input: 2000 task, 105 locations
- Soluzione: `Transformed-52-A-2000T-105L_sol_12_2.txt`
  - Es: Turno 1 copre i task [2607, 1182, 970, 1288] con costo 106.0 e durata 96.0 minuti
  - Es: Turno 14 copre i task [1341, 1340, 1339, ...] con costo 798.0 e durata 668.0 minuti

### Rescheduling (scenario disruption)
- Disruption dalle 1717 ai 2112 minuti nelle sezioni [3, 5, 7]
- Task aperti: Solo i task con `departure > 1717` rimangono
- Obiettivo: Ripianificare questi task mantenendo/modificando i turni esistenti

---

## 📋 Funzioni Principali di Lettura

| Funzione | Descrizione |
|----------|-------------|
| `readIDMapping()` | Legge file ID mapping (TSV → dizionario) |
| `readOpenRescheduledTasks()` | Legge task aperti dal file TSV |
| `readSolution_Twan_txt_Format_incl_Uncovered()` | Legge soluzione Twan + task non coperti |
| `readDisruption()` | Legge file disruption (JSON) |
| `generateReschedulingInput()` | Genera input per rescheduling da soluzione e disruption |
| `calculateInitialSolution()` | Crea soluzione iniziale per rescheduling |
| `read_network_data()` | Legge dati della rete ferroviaria |

---

## ✅ Checklist Lettura Dati

**Prima di avviare l'algoritmo, il sistema:**

- ✅ Legge l'istanza di crew scheduling
- ✅ Legge gli ID mappings per crew scheduling
- ✅ Legge la soluzione iniziale (Twan format)
- ✅ Valida e ripara la soluzione Twan (se necessario)
- ✅ Legge il file di disruption
- ✅ Legge i task aperti di rescheduling
- ✅ Rimuove i task già completati prima della disruption
- ✅ Legge gli ID mappings per rescheduling
- ✅ Genera lo stato iniziale dell'equipaggio
- ✅ Calcola le assegnazioni idonee per task (suitability matrix)
- ✅ Avvia l'algoritmo VNS o DP

