# Research brief: VNS state-of-the-art per Crew/Loco Rescheduling

> Prompt di ricerca da passare a Claude (o altro strumento di ricerca) per posizionare il lavoro descritto in `VNS_design.md` e `SwapStrategies_design.md` all'interno della letteratura VNS più recente.

## Contesto del progetto

Sto sviluppando un modulo di **Variable Neighborhood Search** sopra una soluzione greedy iniziale prodotta da `IntegratedRescheduler`, nel dominio del **crew/loco rescheduling ferroviario a seguito di disruption** (ritardi/cancellazioni che rompono la programmazione originale di treni, locomotive e conducenti).

### Architettura attuale (implementata)

- **Soluzione iniziale**: costruzione greedy sequenziale trip-by-trip (ordine per `departure_time`), con stato di crew/locomotive (`crew_state`) aggiornato progressivamente e un RNG deterministico (seed-based) per la selezione tra candidati feasible.
- **Rappresentazione dei candidati**: per ogni trip, `all_candidates[trip_id]` è una lista di coppie `(loco, driver_chain)` feasible al momento in cui il greedy ha processato quel trip; `all_candidates[trip_id][0]` è la scelta effettivamente fatta, `[1:]` sono le alternative scartate.
- **Shaking (perturbazione)**: forzare l'assegnazione di un trip a una delle alternative scartate (`forced = {trip_id: pair}`), poi ri-eseguire il solve deterministico. Grazie all'RNG seedato, lo stato prima del trip forzato è identico al run originale → l'alternativa pre-calcolata resta feasible per costruzione (nessun re-check necessario). Questo realizza in modo semplice il **neighborhood k=1**.
- **Neighborhood k=2 (parziale)**: `multiple_swap` forza due trip. Il primo usa l'alternativa pre-calcolata (come k=1); il secondo usa un meccanismo *on-the-fly* (`FORCED_ALTERNATIVE`, un sentinel) che ricalcola i candidati feasible sullo stato reale corrente (dopo aver committato il primo forcing), invece di riusare candidati pre-calcolati nel run originale che potrebbero non essere più validi (l'invariante di stato si rompe con >1 trip forzato). Il meccanismo non è generalizzato oltre 2 trip.
- **Strategy pattern per lo shaking**: `SwapStrategies.py` incapsula diverse varianti di selezione trip/alternativa dietro una firma comune `strategy_fn(all_candidates, trips) -> (trip_id, pair) | None` (o un dict `{trip_id: pair}` per shaking multi-trip), selezionabili a runtime/CLI. Strategie implementate: `swap_first_in_time` (primo trip in ordine temporale con alternative disponibili, alternativa scelta random) e `multiple_swap` (k=2, vedi sopra).
- **Funzione obiettivo**: combinazione lineare pesata di trip cancellati, deadheading locomotiva, deadheading crew, penalità "back-home" (distanza tra ultima stazione raggiunta e stazione di fine turno originale del conducente).
- **Non ancora implementato**: loop VNS iterativo completo (max_iter, max_no_improve, criterio di accettazione classico VNS con possibilità di accettare peggioramenti durante lo shaking), neighborhood k>2 generale, calibrazione dei pesi della funzione obiettivo, strategia `swap_random_trip` (che randomizzi anche la scelta del trip, non solo dell'alternativa).

### Nodo aperto architetturale rilevante per la ricerca

Per generalizzare a k>2 sono state considerate due opzioni:
- **Opzione B (scelta)**: forcing on-the-fly dentro `IntegratedRescheduler.run()` — ricalcolo dei candidati feasible al momento, sullo stato corrente, per ciascun trip forzato in sequenza.
- **Opzione C (scartata)**: re-solve a finestra mobile via DP/MILP sopra la porzione di schedule intorno ai trip forzati (ispirata a un vecchio modulo `VNS_Rescheduling.py` del progetto), scartata per costo computazionale più alto, meno adatta a molte iterazioni VNS veloci.

Questo è un punto su cui un confronto con la letteratura sarebbe utile: è una scelta di design comune (shaking "cheap" ricomputato incrementalmente vs. re-ottimizzazione esatta locale)?

## Cosa cercare

1. **Survey/rassegne recenti su VNS** (ultimi ~5 anni) — varianti principali: VNS di base, General VNS (GVNS), VNDS (Variable Neighborhood Decomposition Search), Skewed VNS, Reduced VNS, VNS con Large Neighborhood Search (LNS) ibrido.
2. **Applicazioni VNS a crew scheduling / crew rescheduling ferroviario o aereo**, in particolare:
   - Disruption management (gestione di ritardi/cancellazioni in tempo reale o quasi-reale).
   - Rescheduling integrato di locomotive + conducenti (loco-driver coupling), non solo crew scheduling puro.
   - Rolling stock / crew recovery problems (railway recovery problem, "RRP").
3. **Definizione di neighborhood strutture** in questi lavori: come definiscono k (dimensione del neighborhood)? Swap singolo/multiplo di assegnazioni? Riassegnazione a blocchi (rolling window)? Ricombinazione di duty/turni?
4. **Criteri di accettazione** usati in pratica in VNS applicati a scheduling (accettazione solo di miglioramenti vs. accettazione con soglia/simulated-annealing-like vs. classico "first improvement" nello shaking).
5. **Come gestiscono la feasibility incrementale**: quando si forza una modifica locale, ricalcolano da zero la feasibility globale o usano tecniche incrementali/stato-invariante come quella descritta sopra? Cercare termini come "incremental feasibility check", "delta evaluation", "warm start" in ambito scheduling.
6. **Ibridazione con altre metaeuristiche o matheuristics**: VNS + MILP per il refinement locale (rilevante per confrontare la scelta "opzione B vs C" sopra), VNS + column generation, VNS + ALNS (Adaptive Large Neighborhood Search).
7. **Benchmark e metriche standard** nel dominio crew/loco rescheduling: quali obiettivi vengono tipicamente ottimizzati (numero di cancellazioni, deadheading, ore di lavoro extra, "return to base/home"), per confrontare con la funzione obiettivo attuale (W1..W4 sopra).

## Output desiderato dalla ricerca

- Una mappa dei lavori più rilevanti (ultimi 5 anni preferibilmente, ok anche capisaldi più vecchi se fondamentali) con: riferimento, tipo di problema affrontato, struttura di neighborhood usata, criterio di accettazione, come gestiscono la feasibility incrementale.
- Un confronto esplicito tra l'approccio "shaking con stato pre-invariante + on-the-fly per k>1" descritto qui e le tecniche di neighborhood/feasibility-check trovate in letteratura — indicare se questa è una scelta comune, una variante originale, o se esistono alternative più efficienti/standard.
- Suggerimenti su come posizionare il contributo (novità, gap coperto) rispetto allo stato dell'arte, utile per un'eventuale sezione "related work".
