# Implementazione BVNS su IntegratedRescheduler

> Traccia operativa a stage. Il codice viene scritto a mano; questo documento è il riferimento
> di design e la checklist di verifica, non uno script da eseguire alla lettera.

## Context

[VNS_implementation_plan.md](VNS_implementation_plan.md) descrive un loop BVNS completo sopra la
soluzione greedy di `IntegratedRescheduler`. Oggi in repo esiste solo un abbozzo:

- `VNSRescheduler.run_loop` ([VNSRescheduler.py:97](../../VNSRescheduler.py#L97)) usa `k` come
  **indice nella lista di strategie**, non come **numero di trip forzati** — semantica sbagliata
  rispetto al piano.
- Il forcing in [IntegratedRescheduling.py:199-215](../../IntegratedRescheduling.py#L199-L215)
  gestisce solo 2 casi: pair concreto (k=1) e un singolo sentinel `FORCED_ALTERNATIVE`. Non
  generalizza a k trip.
- L'objective ha i pesi hardcoded come variabili locali dentro `evaluate`
  ([SolutionEvaluator.py:8](../../SolutionEvaluator.py#L8)) — non configurabili, quindi non si
  possono fare esperimenti né fine tuning.
- Lo shaking usa `random.choice` globale non seedato
  ([SwapStrategies.py:13](../scripts/SwapStrategies.py#L13)) → **le run VNS non sono riproducibili**
  nemmeno con `--seed`, che raggiunge solo il greedy interno.
- Nessun criterio di accettazione pluggabile.

Obiettivo: loop BVNS corretto (k = numero di trip forzati, escalation su fallimento, reset su
successo, wrap a `k_max`), objective parametrizzabile da CLI, shaking deterministico, acceptance
intercambiabile.

**Decisioni prese:**

- `select_k` aggiunto a `SwapStrategies`, vecchie funzioni mantenute come wrapper (la CLI attuale
  non si rompe).
- Pesi objective passati da CLI, default = valori attuali, per esperimenti e fine tuning successivo.
- Refactor di `run_loop` **in place**, nessun nuovo modulo `VNSController`.
- **Niente test automatici in questa fase**: verifica manuale via CLI.

---

## Stage 1 — Forced assignment generalizzato a k trip

File: [IntegratedRescheduling.py](../../IntegratedRescheduling.py)

**Stato: Stage 1 completo e verificato.** Implementato come `resolve_forced` (senza underscore,
scelta dell'autore) in [IntegratedRescheduling.py:177](../../IntegratedRescheduling.py#L177):

- estrazione a comportamento invariato;
- criterio `is_first` — flag booleano accumulato nel loop di `run()` (`seen_forced`) invece della
  pre-scansione di `trip_order` per `first_forced`: nessuna scansione O(n) e il metodo riceve
  l'informazione già interpretata invece di ri-derivarla;
- fallimento graceful: `resolve_forced` ritorna `(pairs, fail_stats, failed)`, `run()` accumula
  `forced_failures` e lo porta in `SolveResult`.

Verifica fatta su S01: `first_in_time` e `multiple_swap` danno output identico bit a bit pre/post
refactor (obj, cancellazioni, assegnazioni trip→loco), con entrambi i rami esercitati. Il fallimento
è stato verificato a parte forzando 40 trip: 19 fallimenti, coincidenti esattamente con i
`Failed shake on` del log, nessun trip riuscito marcato come fallito, baseline con `forced` vuoto →
lista vuota.

**Manca ancora**: il matching del pair concreto non-primo (vedi Stage 3, serve ai pair accumulati in
`incumbent_forced` dal loop, non a `select_k`).

Harness di regressione: `regr_worker.py` — esegue greedy + strategia + solve forzata su S01 con
`random.seed(42)`, e confronta due varianti del modulo via `sys.path`. Da conservare fuori da
scratchpad se serve agli stage successivi.

**Invariante da rispettare:** `solve_instance` ricrea `CppMT19937(seed)` a ogni chiamata, quindi lo
stato prima del **primo** trip forzato (in ordine di `departure_time`) è bit-identico alla run da cui
il pair è stato raccolto. Da lì in poi l'invariante si rompe: ogni trip forzato successivo deve
ricalcolare i candidati sullo stato committed reale.

1. In `run()`, prima del loop su `trip_order`, identificare `first_forced` = primo `trip_id` di
   `self._checker_loco.trip_order` presente in `forced` (`trip_order` è già in ordine di partenza).
2. Sostituire il blocco [IntegratedRescheduling.py:199-215](../../IntegratedRescheduling.py#L199-L215)
   con una logica normalizzata in `_resolve_forced(trip_id, locos, crew_state, rng, forced, first_forced)`:
   - se `trip_id is first_forced` **e** l'entry è un pair concreto → usa il pair così com'è, nessun
     re-check (invariante).
   - altrimenti (sentinel, oppure pair concreto ma non primo) → percorso **on-the-fly**:
     `fresh_pairs, fail_stats = self._candidate_pairs(...)`, poi:
     - se l'entry è un pair concreto, cerca un match su `(loco, frozenset(drivers))` **in
       `fresh_pairs[1:]`, non in tutto `fresh_pairs`**; se trovato usalo. L'esclusione dell'indice 0 è
       necessaria: `fresh_pairs[0]` è ciò che il greedy sceglierebbe da solo sullo stato corrente,
       quindi forzarlo sarebbe uno shake no-op — nessuna perturbazione, ma il controller conterebbe
       comunque l'iterazione come esplorata e non migliorante. È lo stesso motivo per cui il codice
       esistente scrive `alternatives = fresh_pairs[1:]`;
     - se non c'è match, oppure l'entry è il sentinel, prendi un'alternativa da `fresh_pairs[1:]`
       con `rng.uniform_int`;
     - se `fresh_pairs[1:]` è vuoto → **fallimento**, vedi punto 3.
   - Nota da mettere nel docstring: un pair concreto su un trip non-primo viene di fatto ri-risolto
     contro lo stato reale.
3. **Fallimento graceful.** Oggi assente: [IntegratedRescheduling.py:212](../../IntegratedRescheduling.py#L212)
   fa `pairs = fresh_pairs`, ricadendo silenziosamente sulla scelta greedy — uno shake no-op
   mascherato da successo. Nuovo comportamento: accumulare `forced_failures: list[int]` con i
   trip_id non risolvibili, **non** ricadere su `fresh_pairs[0]`, e loggare. Usare `pairs = []`,
   così l'iterazione ha un costo esplicito e il controller la scarta comunque.
4. Propagare `forced_failures`: restituito da `run()` nella tupla; nuovo campo
   `forced_failures: list = field(default_factory=list)` in `SolveResult`
   ([IntegratedRescheduling.py:34](../../IntegratedRescheduling.py#L34)); popolato in
   `solve_instance` ([IntegratedRescheduling.py:520](../../IntegratedRescheduling.py#L520)).
5. Mantenere `all_candidates[trip_id] = pairs` (collasso a un solo pair sui trip forzati): è ciò che
   impedisce a `select_k` di ri-scegliere un trip già forzato, perché `[1:]` risulta vuoto.
   Comportamento voluto — commentarlo, altrimenti sembra un bug.

**Regressione:** con `forced` vuoto l'output deve restare identico a prima
(`python3 IntegratedRescheduling.py -i S01`, stesso `n_cancel` e `total_deadhead_length`).

## Stage 2 — Objective parametrizzabile

File: [SolutionEvaluator.py](../../SolutionEvaluator.py)

1. Pesi nel costruttore: `__init__(self, mapper, net, w1=0.1, w2=0.2, w3=0.7, w4=0.5)`. Default =
   valori attuali, per non invalidare i risultati esistenti.
2. `ObjectiveValue` dataclass: `total`, `n_canceled`, `loco_dh_m`, `crew_dh_m`, `back_home`
   (componenti **grezze**, non pesate — servono per il reporting e per il fine tuning dei pesi).
3. `evaluate_components(...) -> ObjectiveValue`; `evaluate(...) -> float` resta e delega a `.total`,
   così [VNSRescheduler.py:39](../../VNSRescheduler.py#L39) non cambia.
4. Riusare `check_back_home` ([SolutionEvaluator.py:16](../../SolutionEvaluator.py#L16)) invariato.

**Nota di modellazione** (da tenere presente, non da "fixare" ora): `w1` moltiplica un *conteggio*
(~O(10)) mentre `w2`/`w3` moltiplicano *metri* (~O(10^5–10^6)). Con i default il termine
cancellazioni è numericamente irrilevante e l'objective è di fatto solo-deadhead. Esporre i pesi da
CLI è esattamente ciò che permette di correggerlo sperimentalmente (es. `--w1 100000`).

## Stage 3 — `run_loop` con semantica k corretta

File: [VNSRescheduler.py](../../VNSRescheduler.py), [SwapStrategies.py](../scripts/SwapStrategies.py)

1. `SwapStrategies.select_k(all_candidates, trips, k, rng) -> dict | None`:
   - scansiona i trip per `departure_time`, raccoglie i primi `k` con alternative non vuote;
   - **forma del dict restituito: 1 pair concreto + (k-1) sentinel muti**, cioè `multiple_swap`
     generalizzato da 2 a k:

     ```python
     {t1: pair_scelto_con_rng, t2: FORCED_ALTERNATIVE, ..., tk: FORCED_ALTERNATIVE}
     ```

     `select_k` gira **prima** della solve e vede solo l'`all_candidates` della run precedente:
     sui trip dal secondo in poi non può sapere cosa sarà feasible, perché dipende da come lo stato
     cambia dopo aver forzato il primo. Il sentinel esiste proprio per non far finta di saperlo — la
     scelta è delegata al solver, che durante lo sweep guarda lo stato reale.
   - il pair del primo trip si sceglie con `rng.uniform_int(0, len(alts)-1)` (**mai** `random.choice`);
   - `None` se trova meno di `k` trip con alternative → il controller conta l'iterazione come non
     migliorante ed escala `k`;
   - `swap_first_in_time` e `multiple_swap` restano, delegando a `select_k` con `k=1`/`k=2` e un rng
     di default, così `-s` continua a funzionare;
   - registrare `select_k` in `SWAP_STRATEGIES` come `"select_k"`.

   **Sentinel muto, decisione presa.** La scelta interna del solver resta casuale fra le alternative
   (`rng.uniform_int`). Scartata l'idea di un "sentinel parlante" (un sentinel che porta un criterio,
   es. minimizza il crew deadhead): costa poco ma rende lo shake goloso, e uno shake goloso riporta
   ogni volta nello stesso bacino di attrazione, riducendo la diversificazione. In BVNS
   l'intelligenza sta nella local search e nell'acceptance, non nella perturbazione.

   Nota sui due assi, per non riconfonderli: *quando* si decide (prima della solve vs durante lo
   sweep) e *come* si decide (a caso vs con un criterio) sono indipendenti. La degenerazione verso
   una greedy randomizzata dipende dal **come**, non dal quando.

   **Filtro anti-baseline (necessario, non opzionale).** `alternatives = new_pairs[1:]` esclude
   l'indice 0, cioè la scelta greedy sullo stato **corrente**, già divergente. Ma la mossa della
   baseline è la scelta greedy sullo stato **originale**: dal secondo trip forzato in poi le due non
   coincidono più, quindi `new_pairs[1:]` può contenere proprio la mossa di baseline. Pescarla
   significa non aver perturbato quel trip — lo shake dichiara k trip e ne perturba meno di k.

   Rimedio, a costo trascurabile: passare a `run()` l'esito della run incumbent (non il `crew_state`,
   che è inutile una volta divergente) e scartare dalle alternative la mossa che coincide:

   ```python
   baseline_move = {trip_id: (p[0]['loco'], frozenset(p[0]['drivers']))
                    for trip_id, p in incumbent.all_candidates.items() if p}
   ```

   ~65 tuple su S01, confronto O(1) per trip.
   **Memoria delle mosse già provate (da valutare qui).** `resolve_forced` vede un trip alla volta e
   non ha memoria fra una solve e l'altra: non può evitare che il loop riproponga combinazioni già
   visitate nelle iterazioni precedenti. È il controller che vede la sequenza, quindi la memoria —
   stile tabu list, chiave `(trip_id, loco, frozenset(drivers))` — va tenuta in `run_loop` e passata a
   `select_k` per filtrare le alternative.

   Oggi esiste solo una protezione parziale e accidentale: `all_candidates[trip_id] = pairs` collassa
   la lista a un elemento sui trip forzati, quindi `[1:]` è vuoto e le strategie non riselezionano un
   trip già forzato. Vale per i trip, **non** per le singole combinazioni.

   **Decisione da prendere qui: il tipo di `forced`.** Oggi `forced` è un
   `dict[int, pair | FORCED_ALTERNATIVE]`, cioè un dizionario i cui valori sono di due tipi diversi
   e la distinzione si fa con `is` su un `object()` sentinella
   ([IntegratedRescheduling.py:155](../../IntegratedRescheduling.py#L155)). La semantica non è
   visibile nel tipo: è già costata due bug in fase di refactor (sentinel trattato come pair valido,
   ramo del pair concreto dimenticato).

   Alternativa da valutare: un value type esplicito, es. `ForcedAssignment(trip_id, pair=None)` dove
   `pair is None` significa "risolvi on-the-fly". Il cambio tocca insieme `select_k`, `run_loop` e
   `_resolve_forced`, quindi **va fatto qui**, non prima: con `select_k` che genera k assegnazioni
   la scelta ha conseguenze concrete, mentre in Stage 1 sarebbe stata prematura.

   Motivo per cui `_resolve_forced` **resta un metodo privato di `IntegratedRescheduler`** e non
   diventa un modulo a sé in `VNS/scripts/`: `forced` è già nel contratto pubblico di `run()`, e un
   resolver esterno avrebbe comunque bisogno di `_candidate_pairs` (privato), del sentinel e — dallo
   step 3 in poi — di accumulare `forced_failures` che `run()` restituisce in `SolveResult`. Sarebbe
   la stessa dipendenza con un livello di indirezione in più.

2. Riscrivere `run_loop` ([VNSRescheduler.py:97](../../VNSRescheduler.py#L97)) — `k` = **numero di
   trip forzati**, non indice di strategia:

```
best_forced = {}; best = r0; best_val = obj0
incumbent_forced, incumbent_val = best_forced, best_val
k = 1; iter = 0; no_improve = 0
while iter < max_iter and no_improve < max_no_improve:
    delta = strategy.select_k(incumbent.all_candidates, trips, k, vns_rng)
    if delta is None or solve fallisce (forced_failures non vuoto):
        accepted = False
    else:
        cand_forced = {**incumbent_forced, **delta}
        r   = solve_instance(..., seed, forced=cand_forced)
        val = objective.evaluate_components(r)
        accepted = acceptance_fn(val, incumbent_val, ctx)
    if accepted:
        incumbent = r; incumbent_forced = cand_forced; incumbent_val = val
        if val.total < best_val.total: best, best_forced, best_val = r, cand_forced, val
        k = 1; no_improve = 0
    else:
        k += 1
        if k > k_max: k = 1
        no_improve += 1
    iter += 1
return best
```

   Differenze chiave rispetto a oggi: niente loop interno su `strategies[k-1]`; `k` si resetta a 1
   sul successo e wrappa a `k_max`; **incumbent e best-so-far tracciati separatamente** (necessario
   appena si accetta un peggioramento, Stage 4) e si restituisce sempre il best-so-far.
3. Determinismo: rng dedicato `self.vns_rng = CppMT19937(vns_seed)` in `__init__` (riusare
   `CppMT19937` da [RollingStockGreedy.py:24](../../RollingStockGreedy.py#L24)), separato dal seed del
   greedy. Una run è replayabile da `(seed, vns_seed)`.
4. Log per-iterazione: `VNS/results/vns_iterations_<ts>.csv` via `csv.DictWriter`, stessa convenzione
   di `export_vns_csv` ([VNSRescheduler.py:15](../../VNSRescheduler.py#L15)). Colonne:
   `iter, k, accepted, obj_total, n_canceled, loco_dh_m, crew_dh_m, back_home, strategy, acceptance,
   forced_trips, forced_failures`.
5. `run_once` ([VNSRescheduler.py:71](../../VNSRescheduler.py#L71)) resta invariato.

## Stage 4 — Acceptance pluggabile

Nuovo file: `VNS/scripts/AcceptanceStrategies.py`, stesso pattern di `SwapStrategies` (staticmethod +
dict `ACCEPTANCE_STRATEGIES` + `get_acceptance_strategy(name)` che alza `ValueError`).

1. Firma: `acceptance_fn(candidate: ObjectiveValue, incumbent: ObjectiveValue, ctx) -> bool`, con
   `ctx` che porta `iter`, `k`, `rng`, `eta`, `alpha` e le due soluzioni (servono a `skewed` per la
   distanza).
2. Implementare:
   - `improve_only` (default): `candidate.total < incumbent.total`;
   - `threshold`: `candidate.total <= eta * incumbent.total`, `eta` da CLI (es. 1.02);
   - `skewed` (SVNS): `candidate.total - alpha * distance < incumbent.total`, dove `distance` =
     numero di trip con `(loco, frozenset(drivers))` diverso fra le due soluzioni (da
     `SolveResult.solution` + `loco_duties`).
3. Con `eta=1.0` / `alpha=0` devono coincidere con `improve_only` — verificarlo su S01.

## Stage 5 — Estensioni (non implementare ora)

Lasciare solo i punti di aggancio: hook di local search fra shake e acceptance; `swap_random_trip`
(randomizza anche la scelta del trip, banale una volta che `select_k` esiste).

**Shake incrementale** — eventuale variante sperimentale, non pianificata. Invece di k-1 sentinel:
forzi un trip, risolvi, scegli il secondo su `all_candidates` del risultato (quindi su stato
realmente osservato), risolvi di nuovo, e così via. Ogni pair è concreto perché scelto su stato
osservato. Costo: k solve per shake invece di 1 (~8 s a solve su S01, quindi sopportabile lì ma non
sulle istanze grandi). Se la scelta a ogni passo resta casuale **non** è più goloso di (a) — è solo
più caro a parità di esplorazione. Ha senso solo come confronto sperimentale shake cieco vs
incrementale, dietro un flag CLI.

## CLI

Aggiungere in [VNSRescheduler.py:160](../../VNSRescheduler.py#L160): `--k-max` (default 3),
`--vns-seed` (default 42), `--acceptance` (default `improve_only`), `--eta`, `--alpha`,
`--w1 --w2 --w3 --w4`. `--max-iter` / `--max-no-improve` esistono già.

**Bug da correggere nello stesso file:** [VNSRescheduler.py:212](../../VNSRescheduler.py#L212) scrive
la chiave `'Instance'` mentre `VNS_CSV_COLUMNS` dichiara `'instance_id'`; con
`extrasaction='ignore'` la colonna esce vuota in ogni riga. Aggiungere anche `obj_total` e le 4
componenti alle colonne del CSV riassuntivo.

## Doc da aggiornare a fine lavoro

[VNS_design.md](VNS_design.md) e [SwapStrategies_design.md](SwapStrategies_design.md) — quest'ultimo è
**stale**: documenta `-> tuple[int, dict]` mentre il codice restituisce un `dict`. Documentare:
semantica di k, invariante di feasibility per il primo trip forzato vs percorso on-the-fly per i
successivi, fallimento graceful.

---

## Verifica (manuale, nessun test automatico)

Molti `Final_Rescheduled_ID_Mappings/*.tsv` risultano **cancellati** nel working tree — verificare che
`single_type/S01.json`, `results_twan_txt/Transformed-S01_sol.txt`,
`Final_Rescheduled_Instances/Transformed-S01.tsv` e
`Final_Rescheduled_ID_Mappings/ID-Mapping-Transformed-S01.tsv` esistano prima di iniziare
(`setup_instance`, [IntegratedRescheduling.py:497](../../IntegratedRescheduling.py#L497)), altrimenti
nessuna run parte.

1. **Regressione greedy** (dopo Stage 1): `python3 IntegratedRescheduling.py -i S01 --seed 42` prima e
   dopo → `n_cancel` e `total_deadhead_length [m]` identici.
2. **Stage 1**: `python3 VNSRescheduler.py -i S01 --loop --max-iter 5 --k-max 3` → il log
   per-iterazione mostra k=1,2,3 con `forced_trips` di cardinalità crescente, nessuna eccezione,
   `forced_failures` compare quando previsto.
3. **Stage 2**: stessa run con `--w1 100000` → l'objective cambia e le cancellazioni iniziano a pesare.
4. **Stage 3**: due run identiche con `--seed 42 --vns-seed 7` → log per-iterazione byte-identici
   (oggi impossibile: `random` non seedato).
5. **Stage 4**: `--acceptance threshold --eta 1.0` e `--acceptance skewed --alpha 0` → stesso
   risultato di `improve_only` sugli stessi seed.
6. **Sanity finale**: objective finale ≤ objective greedy e soluzione feasible — riusare
   `check_driver_chain` ([test_forced_constraints.py:27](../../test_integrated/test_forced_constraints.py#L27)),
   unico verificatore end-to-end esistente (rileva `OVERLAP`, `UNREACHABLE`, `DUTY_TOO_LONG`).
