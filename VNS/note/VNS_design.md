# VNS Rescheduling — Design and Implementation Notes

## Goal

Implement a Variable Neighborhood Search (VNS) on top of the greedy solution produced by `IntegratedRescheduler`, exploring alternative solutions by forcing different assignments for individual trips.

---

## Architecture

### Setup / solve split

`run_instance` was split into two functions:

- `setup_instance(instance_id)` — loads files, builds `mapper` and `net` (invariant across iterations)
- `solve_instance(instance, mapper, net, ...)` — builds `LocoChecker` + `IntegratedRescheduler` and solves

`run_instance` remains as a transparent wrapper for compatibility with existing code.

**Motivation:** `VNSRescheduler` calls `setup_instance` once in `__init__` and `solve_instance` on every iteration, avoiding reloading files and rebuilding the network each time.

---

## Data structure: `SolveResult`

`solve_instance` returns a dataclass instead of a 7-tuple:

```python
@dataclass
class SolveResult:
    solution:        list
    existing_duties: dict
    duty_breaks:     dict
    loco_duties:     dict
    canceled_tasks:  list
    all_candidates:  dict   # {trip_id: [pair, ...]}
    dh_stats:        dict   # loco_dh_m, crew_dh_m, disruption_start/end_min
```

Field access: `r.all_candidates`, `r.canceled_tasks`, etc.

---

## `all_candidates`

`IntegratedRescheduler.run()` now builds and returns `all_candidates: {trip_id: [pairs]}`.

Each `pair` contains:
```python
{
    'loco':         int,
    'driver_chain': [(task, driver_id), ...],
    'n_feasible':   int,
    'drivers':      list[int],   # flat set of drivers in the chain
}
```

- `all_candidates[trip_id][0]` = pair chosen by `IntegratedRescheduler` (always `pairs[0]`)
- `all_candidates[trip_id][1:]` = alternatives not chosen → input for `swap`

**Motivation:** candidates are computed with the correct state at the moment of the trip in the sequential run — no need to recompute.

### A "pair" is (loco, driver **chain**), not (loco, single crew)

`driver_chain` can hold more than one `(task, driver_id)` entry, and **each task can be covered by a different driver**. This isn't optional richness — it's required whenever the candidate loco isn't already sitting at the trip's origin station: `_candidate_pairs` prepends the deadhead legs needed to reposition the loco (`_checker_loco.deadhead_tasks(...)`) before the trip task itself, and `_find_driver_chain` assigns a (possibly different) feasible driver to each leg independently (e.g. one driver covers the deadhead repositioning, a different one takes over for the actual trip — a relief/handoff).

So forcing a trip means forcing the **entire chain**, not just "the driver on the trip" — committing only the final leg would leave the loco with no way to have physically reached the trip's origin. `all_candidates[trip_id][k]['drivers']` is the flat, de-duplicated set of all driver ids in that chain (for quick inspection); `driver_chain` itself keeps the task-by-task assignment.

### The `id` field inside each task dict is always `None` and unused

Task dicts (both `type='trip'` and `type='loco_deadhead'`) carry an `'id'` key created as `None` in `LocoChecker.py` (task-dict templates). It is populated only **after** a pair is committed, and only on a **copy** made at that point (`IntegratedRescheduling.py`, commit blocks: `t = dict(task); t['id'] = task_id[0]; task_id[0] += 1`) — the original task dict inside a candidate pair (what you see in `all_candidates`/`forced`) never gets touched, so it stays `None` there by design, not by bug.

That committed `id` is a bare incrementing counter, and — checked across `CrewState.py`, `TaskFeasibilityChecker.py`, `DebugExport.py` — it is **never read anywhere**. It plays no role in feasibility or correctness. Correctness of an applied task is established by other fields *before* commit (`origin`/`destination` continuity, `departure`/`arrival` timing, `TaskFeasibilityChecker.evaluate(...)`), and by a **separate, different** id — `tid` from `self._trip_to_task_id` (RS `trip_id` → crew task_id, built only for `task_type == 'regular'` in `mapper.id_mapping`) — used solely to match `original_schedule` for the priority tiers in `_select_driver`.

Don't try to unify `id` with `trip_id` for "consistency": deadhead tasks have no `trip_id` at all (they're synthetic repositioning moves, not `train_section`s), and the `trip_id` namespace is already distinct from the crew-side `tid` namespace via `_trip_to_task_id` — overloading `id` would just create a third, partially-defined identifier space on top of two that already exist and already do their jobs.

---

## Perturbation: `swap`

```python
def swap(self, k: int, all_candidates: dict) -> tuple[int, dict] | None
```

Iterates trips in `departure_time` order. For each trip, checks whether alternatives exist in `all_candidates[trip_id][1:]`. Returns `(trip_id, forced_pair)` for the first trip with available alternatives.

**Neighborhood k=1:** all trips (increasing departure order).
**Expansion to k>1:** partially implemented — see `FORCED_ALTERNATIVE` below.

**Note:** the logic for selecting which trip/alternative to force has been extracted into a strategy pattern (`SwapStrategies.py`), to support multiple shaking variants without bloating `VNSRescheduler`. Implementation details in [SwapStrategies_design.md](SwapStrategies_design.md).

---

## Forced assignment

`solve_instance` accepts `forced: dict = {trip_id: pair}`.

In `IntegratedRescheduler.run()`:
```python
if trip_id in forced:
    pairs = [forced[trip_id]]
else:
    pairs, fail_stats = self._candidate_pairs(...)
```

The forced pair is applied **without re-checking feasibility**. This is safe under the state invariant described below.

### State invariant (k=1)

`solve_instance` recreates `rng = CppMT19937(seed)` on every call. Same seed → same sequence → same choices for all trips before `trip_id`. So:

```
run 1 (no forced):  crew_state before trip_id = S0
run 2 (forced):     crew_state before trip_id = S0  ← identical
```

The alternative pair in `all_candidates[trip_id][1:]` was computed in run 1 with `crew_state = S0` (via snapshot/restore in `_candidate_pairs`). Since in run 2 the state is still S0, the pair is feasible by construction — no re-check needed.

**Note on rng's role in feasibility:** `rng` only chooses WHICH driver among the feasible ones, not WHETHER a driver is feasible. Feasibility depends solely on `crew_state`. So rng diverging after the forced trip doesn't cause constraint violations in later trips — it only changes which drivers get selected among the eligible ones.

### When the invariant breaks

The invariant only holds if there is a **single** forced trip. With multiple forced trips (`forced = {trip_k: pair_k, trip_m: pair_m}`):

- `pair_m` was computed in run 1 with state S_m (original, after committing the baseline choice for trip_k)
- In run 2, trip_k uses `pair_k` (different) → the state at trip_m is **S_m_new ≠ S_m**
- The `pair_m` stored from run 1 might not be feasible on S_m_new

### Correct implementation for k>1

Do not re-invoke `solve_instance` with multiple pre-computed `forced` pairs. What's needed is a **sequential solve that accumulates the changes**:

```
1. Process trips 1..k₁-1 normally             → state S_k1
2. Force trip_k₁ with the alternative pair    → state S_k1_new
3. From S_k1_new, process trips k₁+1..k₂-1    → state S_k2_new
4. At trip_k₂: compute FRESH candidates
   with _candidate_pairs on the current state → valid alternatives
5. Force trip_k₂ with the chosen alternative  → continue
```

This means that with k>1 you cannot pre-compute `all_candidates` from run 1 and reuse it for trips after the first forced one. Candidates for every forced trip after the first must be computed **on-the-fly** during the solve, starting from the modified state.

In practice: the current architecture natively supports k=1. For general k>1, `IntegratedRescheduler.run()` would need to accept an ordered list of trips to force and compute candidates on-the-fly for each, instead of receiving pre-computed pairs from outside.

### On-the-fly mechanism: `FORCED_ALTERNATIVE`

First (partial) implementation of the point above: `IntegratedRescheduler.FORCED_ALTERNATIVE` is a sentinel object. In `forced = {trip_id: pair}`, if `pair is FORCED_ALTERNATIVE` (instead of a concrete pre-computed pair), `run()` does **not** use run 1's `all_candidates` — it recomputes candidates on the current `crew_state` via `_candidate_pairs` and picks randomly among the alternatives (`pairs[1:]`), falling back to `pairs[0]` if there are none.

This solves the problem described above for the **second** forced trip onward: the state at that point is the real state of the current run (not run 1's), so the candidates are always valid by construction — no rng invariant needed.

Used today by `SwapStrategies.multiple_swap` (see [SwapStrategies_design.md](SwapStrategies_design.md)): first forced trip uses a pre-computed pair from `all_candidates` (as in normal k=1), second forced trip uses `FORCED_ALTERNATIVE` (on-the-fly recomputation). Not generalized to k>2 — works for exactly two forced trips.

---

## `SolutionEvaluator`

Separate class that keeps the history of evaluations:

```python
class SolutionEvaluator:
    def __init__(self, mapper, net)
    def evaluate(self, canceled_tasks, loco_dh_m, crew_dh_m, existing_duties) -> float
    def check_back_home(self, existing_duties) -> float
```

### Objective function

```
obj = W1 * |canceled| + W2 * loco_dh_m + W3 * crew_dh_m + W4 * back_home_penalty
W1=0.1, W2=0.2, W3=0.7, W4=0.5
```

`check_back_home`: for each driver, computes the distance (meters, via `sp_raw`) from the last arrival station to the departure station of the original duty. Uses `sp_raw` because the disruption has ended by the time of this computation.

---

## `VNSRescheduler`

```python
class VNSRescheduler:
    def __init__(self, instance_id, seed)                                  # setup_instance + SolutionEvaluator
    def run_once(self, strategy_fn, export_gantt=True)                     # one shake, one re-solve
    def run_loop(self, strategies, max_iter=50, max_no_improve=10,
                 export_gantt=True)                                        # full RVNS loop
```

State attributes maintained on the instance (not inside `SolutionEvaluator`, which stays stateless — see below): `current_forced` (accumulated `{trip_id: pair}` accepted so far), `current_result` (last accepted `SolveResult`), `current_obj` (its objective value), `history` (list of `(forced_dict, obj)` for every *accepted* step, in order).

### `run_once()` — single shake, for targeted tests

1. `solve_instance(forced={})` → baseline solution + `all_candidates`, `obj_0 = evaluate(...)`
2. `strategy_fn(candidates, trips)` → one `forced` dict (single trip, or a small multi-trip dict for strategies like `multiple_swap`)
3. If `None` → nothing to swap, return the baseline unchanged
4. `solve_instance(forced=forced)` → new solution, `obj = evaluate(...)`
5. Prints `baseline_obj` vs `new_obj` and whether it improved (no state is kept beyond this one attempt — `run_once` doesn't chain into further shakes)
6. Gantt (if `export_gantt`)

### `run_loop()` — Reduced VNS (RVNS)

Implements the classic RVNS scheme (Hansen & Mladenović): repeatedly shake at neighborhood `k`, accept on improvement and reset to `k=1`, otherwise widen to `k+1`; stop after `max_iter` outer iterations or `max_no_improve` consecutive iterations without an accepted improvement (whichever comes first — this *is* the stopping condition; the loop is not open-ended).

`strategies: list` maps neighborhood level to shaking function by **position**: `strategies[0]` is used at `k=1`, `strategies[1]` at `k=2`, etc. — passed in explicitly by the caller (CLI: `-s name1 name2 ...`, in k-order), not hardcoded.

```
r0 = solve_instance(forced={})                     # baseline
current_forced, current_result, current_obj = {}, r0, evaluate(r0)
history = [({}, current_obj)]

repeat (until max_iter or max_no_improve):
    k = 1
    while k <= len(strategies):
        forced_delta = strategies[k-1](current_result.all_candidates, trips)
        if forced_delta is None: k += 1; continue
        candidate_forced = current_forced | forced_delta      # NOT mutated in place
        r_candidate = solve_instance(forced=candidate_forced)   # always a fresh, from-scratch solve
        obj_candidate = evaluate(r_candidate)
        if obj_candidate < current_obj:
            current_forced, current_result, current_obj = candidate_forced, r_candidate, obj_candidate
            history.append((candidate_forced, obj_candidate))
            k = 1                     # accepted → back to smallest neighborhood
        else:
            k += 1                    # rejected → widen
```

**No explicit rollback needed on rejection.** `solve_instance` rebuilds `LocoChecker`/`TaskFeasibilityChecker`/`crew_state` from scratch on every call, reading only from the immutable `mapper`/`net` plus whatever `forced` dict is passed in — there is no shared mutable state to restore. Accepting a candidate just means promoting `candidate_forced`/`r_candidate` to `current_*`; rejecting it means simply not doing that (the rejected objects are discarded, garbage collected). "Continuing from the best state" is exactly: keep re-solving with the accumulated `current_forced` dict — that dict *is* the memory of the best state found so far, nothing else needs to be carried across iterations.

**Known limitation (not addressed yet):** both implemented strategies pick the trip to force deterministically — always the earliest in time among those with alternatives (see `SwapStrategies_design.md`). So repeated iterations tend to retry the *same* first blocked trip (with a different random alternative, or with a second trip appended via `multiple_swap`) instead of exploring other parts of the timeline. `multiple_swap` as `k=2` is not an independent neighborhood — it's "the same k=1 choice, plus one more trip appended" (nested growth, which is valid RVNS structure), not "a different trip". Breaking out of this needs `swap_random_trip` (see `SwapStrategies_design.md`, Open decisions).

### Verifying a swap actually happened (manual evidence, no dedicated test file)

On every accepted step, `run_loop` prints, per forced trip: the baseline greedy assignment (`all_candidates[trip_id][0]`, loco + drivers) vs. the one in the accepted candidate — e.g.:
```
swap trip=22620: baseline loco=22551 drivers=[28] → loco=22553 drivers=[18, 28]
swap trip=22622: baseline loco=22551 drivers=[28] → FORCED_ALTERNATIVE (resolved on-the-fly)
```
For a trip forced via `FORCED_ALTERNATIVE`, the concrete pair actually committed isn't known outside `IntegratedRescheduler.run()` (it's resolved on-the-fly, in a local variable, never returned) — to see what it resolved to, look it up post-hoc in `r_candidate.loco_duties` for the task with matching `rs_trip_id`, rather than modifying `IntegratedRescheduling.py` to expose it.

### Timing: what `computation_time` should include

`VNSRescheduler(instance_id, seed=...)` (i.e. `setup_instance`) is expensive — file loading + `RailwayNetwork` Dijkstra shortest-path augmentation, ~6-7s on S01 alone, dwarfing the solve/shake time itself (well under 1s). The CLI's timer must start **before** constructing `VNSRescheduler`, not after, otherwise the measured `computation_time` covers only the shake/solve portion and isn't comparable to `IntegratedRescheduling.py`'s own benchmark (which times `run_instance`, i.e. setup + solve together). Comparing a "swap-only" number against a "setup+solve" number will make VNS look faster than plain greedy, which is not real.

### Gantt generation only in single-instance runs

Mirrors `IntegratedRescheduling.py`'s own `__main__`: the CLI only calls `_export_gantt` when exactly one instance id is being run (`export_gantt = len(instance_ids) == 1`), passed through to `run_once`/`run_loop`. Batch/CSV benchmark runs over many instances skip HTML generation entirely — otherwise plotting time (which can grow with instance size) would leak into the `computation_time` CSV column and skew larger instances.

### CSV export (`-i inst1 inst2 ... -csv FILE.csv`)

`export_vns_csv(results, output_path)` appends `{instance_id, total_trip, n_cancel, computation_time [s]}` per instance (rows with an `'error'` key, from a caught exception during that instance's run, are skipped on write but still show up in the console log). Default output (when `-csv` isn't passed): `VNS/results/vns_results_<timestamp>.csv` — a fresh, uniquely-named file per script invocation, so repeated runs never silently overwrite or get mixed with a previous run's results. Passing `-csv path.csv` explicitly overrides this and always appends to that exact path (across separate invocations too, if reused deliberately).

---

## Side effects of the forced swap (verified on S01)

The forced swap can cause **cascade cancellations**: the loco from the alternative (e.g. 22553) gets committed to the forced trip and is no longer available for later trips that used it as their only candidate. On S01 with seed=42: +1 net cancellation (2 trips lose their candidate, 1 is recovered by the rescue pass).

No structural violations (station, timing, duty length, break) were found in the produced solutions — verified with the diagnostic test in `test_integrated/test_forced_constraints.py` (single forced trip) and manually for `run_loop`'s accumulated multi-trip `current_forced` (constraint checks on `existing_duties`: 0 violations).

---

## Open decisions

- `swap_random_trip` — to break the stagnation described above (see `SwapStrategies_design.md`)
- Acceptance criterion beyond plain RVNS: classic VNS variants that also accept some worsening moves
- Neighborhood expansion k>2: requires generalizing the `FORCED_ALTERNATIVE` mechanism (currently works for exactly 2 forced trips, see Forced assignment section)
- Objective function weights W1..W4 — to be calibrated
