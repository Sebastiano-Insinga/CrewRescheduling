# Implementation Plan: Full VNS Loop over IntegratedRescheduler

> Instructions for Claude Code. Implement incrementally, one stage at a time, running the test suite after each stage. Do not refactor existing modules beyond what each stage requires. Ask before changing any public interface of `IntegratedRescheduler` or `SwapStrategies`.

## Context (existing architecture — do not reimplement)

- `IntegratedRescheduler`: greedy sequential trip-by-trip constructor (ordered by `departure_time`), progressive `crew_state`, deterministic seed-based RNG for selection among feasible candidates.
- `all_candidates[trip_id]`: list of feasible `(loco, driver_chain)` pairs at the moment the greedy processed that trip; `[0]` = chosen, `[1:]` = discarded alternatives.
- Shaking today: `forced = {trip_id: pair}` → re-run the deterministic solve. Thanks to the seeded RNG, state before the forced trip is identical to the original run, so the pre-computed alternative stays feasible **with no re-check** (valid only for k=1).
- k=2: `multiple_swap` forces two trips; the second uses the `FORCED_ALTERNATIVE` sentinel → feasible candidates recomputed **on-the-fly** on the committed current state (the state invariant breaks with >1 forced trip).
- `SwapStrategies.py`: strategy pattern, signature `strategy_fn(all_candidates, trips) -> (trip_id, pair) | None` or `{trip_id: pair}` for multi-trip shaking; selectable at runtime/CLI.
- Objective: weighted linear combination of (W1) cancelled trips, (W2) locomotive deadheading, (W3) crew deadheading, (W4) back-home penalty.

## Target design (what to build)

A `VNSController` module implementing the standard BVNS control loop:

```
best = greedy_solution (seed run)
k = 1
iter = 0; no_improve = 0
while iter < max_iter and no_improve < max_no_improve:
    x' = shake(best, k)          # force k trips to alternatives
    # (local search hook — Stage 5, optional/off by default)
    if accept(x', best):
        best = x'
        k = 1                    # RESET on success
        no_improve = 0
    else:
        k = k + 1                # ESCALATE on failure
        if k > k_max: k = 1      # wrap around
        no_improve += 1
    iter += 1
return best
```

Key semantics: **k = number of forced trips** (neighborhood size). k escalates on failure, resets to 1 on success, wraps at `k_max`. Typical `k_max` in the applied literature: 3–5 (large shakes approach random restart and waste the greedy seed).

---

## Stage 1 — Generalize forced assignment to k trips (prerequisite)

**Goal:** make the on-the-fly `FORCED_ALTERNATIVE` mechanism work for an arbitrary ordered set of forced trips, not just 2.

1. In `IntegratedRescheduler.run()`, refactor the forcing logic into a loop over `forced` (ordered by `departure_time`):
   - The **first** forced trip (earliest) may use a pre-computed alternative from `all_candidates` — the seeded-RNG state invariant guarantees feasibility with no re-check.
   - **Every subsequent** forced trip must use the on-the-fly path: recompute feasible `(loco, driver_chain)` candidates against the actual committed current state at the moment that trip is processed. Never reuse pre-computed alternatives beyond the first forced trip.
2. If an on-the-fly forced trip has no feasible candidate matching the requested alternative (or no candidates at all), the shake **fails gracefully**: return a sentinel/None so the controller can count it as a non-improving iteration (do not raise, do not fall back silently to the greedy choice — log it).
3. Add unit tests:
   - k=1 reproduces the current single-swap behavior bit-for-bit (same seed → same output).
   - k=2 reproduces the current `multiple_swap` behavior.
   - k=3 runs end-to-end and produces a feasible schedule (validate with the existing feasibility checks).
   - A forced trip with an impossible alternative returns the failure sentinel.

## Stage 2 — Objective function as a standalone, testable component

**Goal:** one canonical `evaluate(solution) -> ObjectiveValue`.

1. Extract (or wrap) the objective computation into a pure function/class `Objective` with explicit weights `W1..W4` passed at construction (CLI-configurable; defaults = current values).
2. `ObjectiveValue` should expose both the scalar total and the four components (needed later for reporting and for lexicographic/threshold acceptance).
3. Unit tests with hand-computed small fixtures for each component.

## Stage 3 — `VNSController` with improvement-only acceptance

**Goal:** the loop in the pseudocode above, as a new module `VNSController.py` (or fitting the project's naming convention).

1. Constructor parameters: `max_iter`, `max_no_improve`, `k_max`, `seed`, `objective`, `shake_strategy` (a `SwapStrategies` function), `acceptance` (default: `"improve_only"`).
2. `shake(best, k)`:
   - Ask the strategy for k `(trip_id, pair)` selections. Extend `SwapStrategies` with a k-aware entry point, e.g. `select_k(all_candidates, trips, k, rng) -> {trip_id: pair} | None`, implemented for the existing strategies (repeat single selection k times on distinct trips; skip trips with no alternatives).
   - Call `IntegratedRescheduler.run(forced=...)` from Stage 1.
3. Acceptance `improve_only`: accept iff `objective(x') < objective(best)` (strict).
4. Deterministic reproducibility: the controller has its own seeded RNG (separate from the constructor's seed) so a full VNS run is replayable from `(constructor_seed, vns_seed)`.
5. Logging: per iteration log `iter, k, accepted, objective_total, objective_components, shake_strategy, forced_trips`. CSV or JSONL — pick whatever the project already uses for experiment output.
6. CLI wiring: expose `--vns`, `--max-iter`, `--max-no-improve`, `--k-max`, `--vns-seed`, `--acceptance` alongside the existing strategy selection flags.
7. Integration test: on a small fixture instance, a 50-iteration run terminates, never returns an infeasible solution, and the returned objective is ≤ the greedy objective.

## Stage 4 — Pluggable acceptance criteria

**Goal:** acceptance as a strategy, mirroring `SwapStrategies`.

1. Interface: `acceptance_fn(candidate_value, incumbent_value, ctx) -> bool` where `ctx` carries iteration count, k, rng, and parameters.
2. Implement:
   - `improve_only` (default; matches Hoogervorst et al.).
   - `threshold`: accept if `candidate <= eta * best` with `eta` slightly > 1 (e.g. 1.02, CLI-configurable).
   - `skewed` (SVNS): accept if `candidate - alpha * distance(x', best) < incumbent`. Define `distance` as the number of trips whose `(loco, driver_chain)` assignment differs between the two solutions. `alpha` CLI-configurable.
3. Important: track **incumbent** (current search point) and **best-so-far** separately once non-improving acceptance exists; always return best-so-far.
4. Tests: with `eta=1.0` / `alpha=0`, `threshold` and `skewed` must behave identically to `improve_only` on the same seeds.

## Stage 5 (optional, after 1–4 are green) — hooks for later work

Do **not** implement now; just leave clean extension points:
- A local-search hook between shake and acceptance (future GVNS: e.g. pairwise swap of two trips' assignments with delta evaluation on the four objective components).
- A `swap_random_trip` strategy (randomize the trip choice, not only the alternative) — trivial once `select_k` exists; implement it if time permits, it is a one-liner variant.

## Constraints and conventions

- Python + CPLEX project; do not add heavy dependencies for this work (stdlib + what the project already uses).
- Everything must stay deterministic given `(constructor_seed, vns_seed)`.
- Never silently repair an infeasible forced shake — fail the iteration and log.
- Keep `IntegratedRescheduler`'s public behavior unchanged when `forced` is empty (regression: seed run output must be byte-identical to before the refactor).

## Definition of done

- All stages 1–4 implemented with passing unit + integration tests.
- A single CLI command runs: greedy seed → VNS loop → prints greedy vs final objective (total + components) and writes the per-iteration log.
- README/docstring snippet explaining the k semantics (escalate on failure, reset on success, wrap at k_max) and the k=1 feasibility-inheritance invariant vs the on-the-fly path for k≥2.
