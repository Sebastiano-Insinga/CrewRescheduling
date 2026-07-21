# Swap Strategies — Design and Implementation Notes

> Extends [VNS_design.md](VNS_design.md), section "Perturbation: `swap`". See there for context on `all_candidates` and forced assignment.

## Goal

Make the shaking phase (`swap`) of the VNS **interchangeable**: multiple strategies for selecting the trip/alternative to force, selectable without modifying `VNSRescheduler`.

---

## Why a strategy pattern

The original `swap` logic (see `VNS_design.md`) was a fixed method on `VNSRescheduler`. With multiple variants in view (scan in time order, random trip choice, possibly in the future heuristics borrowed from the old `VNS_Rescheduling.py` — see `VNS_design.md` for the comparison), keeping them all as methods of the same class would have turned `VNSRescheduler` into a container of unrelated logic, distracting from its main job (orchestrating setup → solve → forced re-solve → visualization).

Choice: strategies live in a separate module, `SwapStrategies.py`, and `VNSRescheduler` receives them as an external dependency.

---

## Strategy contract

Each strategy is a function with a fixed signature:

```python
strategy_fn(all_candidates: dict, trips: list) -> tuple[int, dict] | None
```

- `all_candidates`: `{trip_id: [pair, ...]}` from `SolveResult.all_candidates` (see `VNS_design.md`).
- `trips`: raw list of trips (`instance['train_sections']`), **not pre-sorted** — each strategy decides for itself whether/how to order them. This avoids imposing a preprocessing step (e.g. sort by `departure_time`) on strategies that don't need it.
- Returns `(trip_id, forced_pair)` for the first/chosen trip with available alternatives, or `None` if no trip can be forced.

**Note:** for strategies that force more than one trip, the return value is `{trip_id: pair, ...}` (a dict with multiple entries), not a single `(trip_id, forced_pair)` tuple — see `multiple_swap` below. `VNSRescheduler.run()` passes this dict straight through to `solve_instance(forced=...)`, which accepts a `{trip_id: pair}` mapping of any size.

`VNSRescheduler.run()` explicitly handles the `None` case (no perturbation possible in this iteration) instead of letting an unpacking error propagate.

---

## `SwapStrategies` as a namespace, not a stateful object

The strategies implemented so far are **stateless** (they keep no history across calls), so:

- `SwapStrategies` is a class that is never instantiated, used only as a container/namespace.
- Every strategy is a `@staticmethod` — no `self`, callable via `SwapStrategies.function_name(...)`.

Implementation note: the `SWAP_STRATEGIES` dict (string name → function) is defined **outside** the class body, after its definition, and references the functions via `SwapStrategies.swap_first_in_time`. Inside the class body, `swap_first_in_time` at that point would still be the unresolved `staticmethod` object (descriptor), not the callable function — building the dict at module level avoids this ambiguity.

If in the future a strategy needed state across iterations (e.g. a counter of how many times a trip has been attempted, to avoid always proposing it again), the static namespace would no longer be enough — at that point it would make sense to move to stateful instances (one class per strategy, not all inside `SwapStrategies`).

---

## Selection by name (CLI-driven)

`SwapStrategies.get_swap_strategy(name)` looks up `SWAP_STRATEGIES` and raises `ValueError` with the list of valid keys if `name` doesn't exist — avoids a silent `KeyError` and makes the error readable from the terminal.

`VNSRescheduler.py`'s `__main__` block uses `argparse` to expose `-i/--instance` (one or more, default: all instances), `--seed`, `-s/--strategy` (**one or more** names, `nargs='+'`, in k-order), `--loop`. Each name is resolved to a function through `get_swap_strategy` before being passed in. Without `--loop`, only `strategies[0]` is used (single shake via `run_once`, see `VNS_design.md`); with `--loop`, the full list maps to neighborhoods k=1,2,... for `run_loop`'s RVNS cycle.

```
python3 VNSRescheduler.py -i S01 -s first_in_time                              # run_once, k=1 only
python3 VNSRescheduler.py -i S01 --loop -s first_in_time multiple_swap         # run_loop, kmax=2
python3 VNSRescheduler.py -s nonexistent_name -i S01                           # ValueError with valid options
```

---

## Strategy passed per call, not fixed in the constructor

`VNSRescheduler.run_once(self, strategy_fn, ...)` and `VNSRescheduler.run_loop(self, strategies: list, ...)` receive the strategy/strategies **on every call**, never stored as an instance attribute in `__init__`. `run_loop` in particular relies on this: it maps neighborhood level `k` to `strategies[k-1]` by position, so a wider or different shake at higher `k` is just "another entry in the list passed to this call" — no need to touch `VNSRescheduler` itself to add/reorder neighborhoods (see `VNS_design.md`, `run_loop()`).

`VNSRescheduler.swap()` (an intermediate method that only acted as an adapter between `run()` and `strategy_fn`) has been removed: it added no behavior, just an extra level of indirection. `run_once`/`run_loop` call `strategy_fn`/`strategies[k-1]` directly.

---

## Implemented strategies

### `swap_first_in_time`

Iterates trips sorted by `departure_time` (increasing order), returns the first trip with available alternatives in `all_candidates`, picking the alternative randomly among the available ones (`random.choice`). Forces a single trip (k=1).

Known limitation: deterministic in the choice of *trip* (always the earliest in time among forceable ones) — over repeated VNS iterations it tends to re-propose the same trip if the shaking isn't accepted, exploring little of the solution space. Discussed but not yet implemented: a `swap_random_trip` variant that also randomizes the trip choice among all those with alternatives, closer to classic VNS theory (shaking = random point in the neighborhood).

### `multiple_swap`

Forces **two** trips at once (a step toward neighborhood k=2). Iterates trips sorted by `departure_time`, collects up to the first two with available alternatives in `all_candidates`.

- 0 found → returns `None`.
- 1 found → behaves like `swap_first_in_time`: forces that one trip with a random alternative (`{trip_id: pair}`).
- 2 found → forces the first trip with a random alternative pre-computed from `all_candidates` (same k=1 mechanism, safe under the state invariant — see `VNS_design.md`), and forces the second trip with `IntegratedRescheduler.FORCED_ALTERNATIVE` (a sentinel), so that `IntegratedRescheduler.run()` recomputes its candidates on-the-fly against the state produced after committing the first forced trip, instead of reusing a pre-computed pair that could be stale (see "When the invariant breaks" / "On-the-fly mechanism: `FORCED_ALTERNATIVE`" in `VNS_design.md`). Returns `{trip1_id: pair1, trip2_id: FORCED_ALTERNATIVE}`.

Limitation: hardcoded to exactly two trips, not a general k. Also asymmetric — only the second forced trip gets on-the-fly recomputation; a third forced trip is not supported by this mechanism as-is.

---

## Open decisions

- `swap_random_trip` (randomizes the trip too, not just the alternative) — to be implemented.
- Generalizing `multiple_swap` beyond exactly two trips: requires extending the `FORCED_ALTERNATIVE` on-the-fly mechanism to a list of forced trips instead of a single sentinel slot (see `VNS_design.md`, "On-the-fly mechanism: `FORCED_ALTERNATIVE`").
- Expansion to general neighborhood k>2: **on-the-fly forcing** inside `IntegratedRescheduler.run()` (option B, see discussion — not yet fully generalized in `VNS_design.md`), discarding the "rolling window re-solve via DP/MILP" alternative (option C, borrowed from `VNS_Rescheduling.py`) due to higher per-iteration computational cost, less suited to many fast VNS iterations.
- Iterative VNS loop with acceptance criterion — still TODO (see `VNS_design.md`).
