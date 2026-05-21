# Perché driver-MRV non differenzia da calculateInitialSolution in SequentialRescheduling

## Idea

Driver-MRV ordina i driver per numero di task feasibili correnti (crescente): il driver più
vincolato (meno opzioni) costruisce la sua catena per primo, evitando che altri driver "rubino"
i pochi task che può coprire.

A differenza del task-MRV, preserva il chain building (loop interno greedy) — quindi non soffre
del problema di frammentazione temporale descritto in `MRV_analysis.md`.

---

## Perché i risultati sono identici a calculateInitialSolution

In `SequentialRescheduling.py`, `suitable_tasks` viene costruito così:

```python
suitable_tasks = {driver_id: list(open_tasks.keys()) for driver_id in driver_status}
```

Tutti i driver possono fare tutti i task. Il check `task_id in suitable_tasks[driver_id]`
in `_is_task_feasible` passa sempre per qualunque coppia (driver, task).

Conseguenza: l'unico vincolo differenziante tra driver è **stazione + tempo disponibile**,
non le qualifiche. In questo contesto:

- Driver alla stessa stazione con tempi simili hanno lo stesso numero di task feasibili
- Il riordinamento per count non cambia l'ordine effettivo di assegnazione
- Tutti e tre i greedy convergono allo stesso risultato

### Dati empirici (scored_greedy, S01–S05)

| Istanza | calculateInitialSolution | calculateInitialSolution_slack | calculateInitialSolution_driverMRV |
|---------|--------------------------|-------------------------------|-------------------------------------|
| S01     | 37                       | 37                            | 37                                  |
| S02     | 112                      | 112                           | 112                                 |
| S03     | 44                       | 44                            | 44                                  |
| S04     | 84                       | 84                            | 84                                  |
| S05     | 144                      | 144                           | 144                                 |

Risultati identici su tutte le istanze.

---

## Quando driver-MRV avrebbe impatto

Driver-MRV differenzierebbe se `suitable_tasks` fosse eterogeneo — cioè se driver diversi
potessero coprire insiemi diversi di task. Questo accade nel flusso `Main.py`, dove
`suitable_tasks` viene calcolato da `loco_knowledge` e `section_knowledge`:

```python
internal_format_solution_twan, ..., suitable_tasks = readSolution_Twan_txt_Format_incl_Uncovered(
    ..., loco_types, section_types, min_loco_knowledge, min_section_knowledge
)
```

In quel contesto, un driver con conoscenza limitata di locomotive/sezioni ha un insieme ristretto
di task feasibili — esattamente il caso in cui MRV sul driver ha senso. In `SequentialRescheduling`
questa informazione non è disponibile perché il flusso costruisce `suitable_tasks` senza
distinguere le qualifiche dei driver.

---

## Conclusione

Driver-MRV è concettualmente corretto per problemi con **eterogeneità delle qualifiche** tra
driver. Nel contesto di `SequentialRescheduling.py`, dove tutti i driver sono equivalenti per
qualifiche, il criterio di ordinamento diventa irrilevante e il risultato collassa a quello
del greedy base.

La variante è stata rimossa per evitare complessità senza beneficio misurabile nel contesto
attuale.
