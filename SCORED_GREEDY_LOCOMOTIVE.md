# `scored_greedy()` — Implementazione con Km Slack Scoring

## Obiettivo

Estendere il greedy per il rolling stock rescheduling introducendo un sistema di punteggio per la selezione delle locomotive. La funzione `randomized_greedy()` esistente rimane **invariata** (replica esatta del C++). La nuova `scored_greedy()` condivide tutta l'infrastruttura ma sostituisce la logica di selezione.

---

## Confronto: `randomized_greedy()` vs `scored_greedy()`

| | `randomized_greedy()` | `scored_greedy()` |
|---|---|---|
| Loco considerate | Solo la loco originale del piano | Tutte le loco compatibili per classe (via `candidate_locomotives`) |
| Selezione | Random tra candidati (lista 0 o 1) | Top-5 per km slack score, poi random tra questi |
| Score dinamico | N/A | Sì — riflette km accumulati durante il loop greedy |
| Output format | `List[Dict]` | `List[Dict]` (identico) |
| Parità C++ | Sì | No (estensione intenzionale) |

---

## Architettura

```
RollingStockGreedy.py
├── update_loco_km()        calcola km attuali della loco (dinamico, usa loco_trips + maintenance)
├── compute_loco_score()    km slack score in [0,1], chiama update_loco_km
├── five_best_scores()      top-N candidates per score decrescente
└── scored_greedy()         loop principale
```

---

## `update_loco_km()`

Calcola i km accumulati dalla loco al momento della chiamata, traversando l'intera sequenza di trip in `loco_trips[loco_id]`. Include deadhead e rispetta i reset da manutenzione.

**Score è dinamico**: ogni chiamata vede `loco_trips` e `maintenance` aggiornati con le assegnazioni definitive già fatte nei trip precedenti.

---

## `compute_loco_score()`

```
score = (max_km - current_km) / max_km
```

- `current_km` = `update_loco_km(...)` — km reali accumulati fino ad ora
- `max_km` = `loco_classes[...]['max_kilometers_before_maintenance']`
- Score in `[0, 1]`: vicino a 1 = loco fresca, vicino a 0 = prossima a manutenzione

---

## `five_best_scores()`

Prende lista `candidates` (già filtrati per feasibility da `candidate_locomotives`), li ordina per score decrescente, ritorna i top-N.

---

## Loop principale `scored_greedy()`

Per ogni `trip_id` in `trip_order`:

1. `candidate_locomotives()` → lista loco feasibili (check conflitti, tipo, km)
2. `five_best_scores()` → top-5 per km slack (con `loco_trips`/`maintenance` correnti)
3. Random tra top-5 → `best_loco`
4. `assign_loco_to_trip()` + `assign_maintenance_all()` → aggiorna stato
5. Prossimo trip vede stato aggiornato → score ricalcolato su km reali

---

## Costo computazionale

`randomized_greedy()`: `candidate_locomotives` chiama 1 try/undo per loco candidata.  
`scored_greedy()`: stessa `candidate_locomotives`, poi `five_best_scores` itera su candidati feasibili (O(N) con N piccolo).

Overhead rispetto a `randomized_greedy` minimo: `update_loco_km` per ogni candidato feasibile, ma N candidati feasibili tipicamente << N loco totali.

---

## Verifica

```python
from RollingStockGreedy import randomized_greedy, scored_greedy, count_canceled, load_data

instance, network, sp = load_data(...)
sol_orig   = randomized_greedy(instance, network, sp, seed=42)
sol_scored = scored_greedy(instance, network, sp)

print(f"randomized_greedy canceled: {count_canceled(sol_orig)}")
print(f"scored_greedy     canceled: {count_canceled(sol_scored)}")
```

**Aspettativa:** `scored_greedy` canceled ≤ `randomized_greedy` (più loco considerate = più chance di assegnare).  
Se canceled è maggiore → bug in `candidate_locomotives` o `five_best_scores`.  
Se risultati identici con loco tutte della stessa classe e km simili → comportamento atteso (score uniformi).

---

## Estensioni future

| Componente | Formula | Logica |
|---|---|---|
| Deadhead cost | `1 - dh_time / max_dh_time` | Preferisce loco già vicina al trip |
| Avail margin | `(trip_dep - avail_time) / trip_dep` | Preferisce loco con più margine temporale |
| Score combinato | `w1 * km_slack + w2 * dh_score + w3 * margin` | Pesi configurabili |
