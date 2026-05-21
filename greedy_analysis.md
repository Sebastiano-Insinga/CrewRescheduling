# Crew Rescheduling Greedy — Analysis

## Problem Structure

The sequential pipeline (RS greedy → Crew greedy) creates a fundamental mismatch:

- **RS greedy** reassigns locomotives to train trips, ignoring crew positions
- **Crew greedy** tries to assign drivers to the new locomotive trips, starting from positions fixed by the original crew schedule

### Station Mismatch (Instance S01)

```
Driver positions (from original crew schedule): 24 distinct stations
Task origins (from new RS solution):            48 distinct stations
Stations with tasks but no driver:              25 stations
```

Result: **43/95 tasks (45.3%) are structurally uncoverable** — no driver is at
the right station, regardless of assignment order or heuristic used.

Breakdown of why tasks have 0 eligible drivers:

| Reason        | Count | Description |
|---------------|-------|-------------|
| wrong_station | 43    | No driver at task origin |
| too_late      | 0     | Driver at right station but arrives after departure |
| duty_full     | 0     | Driver would exceed max duty length (720 min) |
| break_fail    | 0     | Adding task makes duty break-infeasible |

### Task Eligibility Distribution

| Category | Count | % |
|----------|-------|---|
| 0 eligible drivers (structurally uncoverable) | 43 | 45.3% |
| Exactly 1 eligible driver | 27 | 28.4% |
| ≥2 eligible drivers (contested) | 25 | 26.3% |

Only 26.3% of tasks are contested — meaning ordering heuristics can only affect
at most 1 in 4 tasks. In practice, this fraction is even smaller because
set covering allows multiple drivers to cover the same task independently.

---

## Why All Non-Deadhead Variants Produce Identical Results

Three compounding reasons:

1. **Disjoint feasible sets**: drivers start at different stations → each driver
   can only reach tasks at their own station. Virtually no competition.

2. **Set covering semantics**: `available_tasks` is never depleted. Even if two
   drivers compete for the same task, both can take it from `available_tasks`.
   The "winner" is the first to pop it from `open_tasks`, but `crew_uncovered`
   is unaffected because the task was already covered.

3. **45.3% structurally fixed**: nearly half the tasks are uncoverable by any
   driver regardless of ordering. These tasks dominate the `crew_uncovered`
   metric and mask any difference between heuristics.

---

## Greedy Variants

### `calculateInitialSolution` (base)
**Loop**: driver-first. For each driver, greedily extend chain while feasible tasks exist.  
**Task selection**: originally-assigned tasks → min departure; otherwise → min departure.  
**Break check**: yes (`_is_task_feasible_break`).  
**Result**: baseline.

### `calculateInitialSolution_slack`
**Loop**: round-based. Each round, sort drivers by slack (most remaining duty time first).  
**Task selection**: same as base.  
**Break check**: yes.  
**Result**: identical to base — slack ordering irrelevant when feasible sets are disjoint.

### `calculateInitialSolution_driverMRV`
**Loop**: round-based. Each round, sort drivers by number of currently feasible tasks (ascending) — most constrained driver goes first.  
**Task selection**: same as base.  
**Break check**: yes.  
**Result**: identical to base — driver ordering irrelevant when feasible sets are disjoint. Would differentiate only with heterogeneous `suitable_tasks` (different driver qualifications).

### `calculateInitialSolutionBreak`
**Loop**: driver-first (same as base).  
**Task selection**: same as base.  
**Break check**: yes, stricter — uses `_is_task_feasible_break` during assignment.  
**Result**: slightly worse than base on some instances — break constraint rejects tasks the base would accept.

### `calculateInitialSolution_taskScarcity`
**Loop**: driver-first.  
**Task selection**: pick feasible task with fewest eligible drivers globally (most scarce) — MRV at task-selection level while preserving chain building.  
**Break check**: yes.  
**Result**: worse than base — scarcity scoring selects sub-optimal tasks in terms of chain continuity.

### `calculateInitialSolution_connectivity`
**Loop**: driver-first.  
**Task selection**: pick feasible task whose destination has most follow-up tasks reachable — maximizes future chain length.  
**Break check**: yes.  
**Result**: worse than base on large instances — connectivity scoring degrades for large open_tasks pools.

### `calculateInitialSolution_driverMRV` (with scarcity at selection)
Not implemented as standalone — `taskScarcity` already applies MRV logic at the task-selection level within each driver's chain.

### `calculateInitialSolution_deadhead`
**Loop**: driver-first, chain building.  
**Feasibility**: relaxes station constraint — driver can reach task at a different station by deadheading (travelling as passenger) using shortest-path distances at 60 km/h.  
**Task selection**: originally-assigned, no deadhead → originally-assigned with deadhead → any task (min deadhead, min departure).  
**Break check**: yes, with break flag awareness.  
**Result**: **significantly better** — addresses the root cause (station mismatch) directly.

---

## Empirical Results (S01, randomized_greedy RS)

| Crew Method | crew_uncovered |
|-------------|---------------|
| calculateInitialSolution | 44 |
| calculateInitialSolution_slack | 44 |
| calculateInitialSolution_driverMRV | 44 |
| calculateInitialSolutionBreak | 44 |
| calculateInitialSolution_taskScarcity | 44 |
| calculateInitialSolution_connectivity | 44 |
| **calculateInitialSolution_deadhead** | **21** |

## Empirical Results (S10, randomized_greedy RS)

| Crew Method | crew_uncovered |
|-------------|---------------|
| calculateInitialSolution | 612 |
| calculateInitialSolution_slack | 612 |
| calculateInitialSolution_driverMRV | 612 |
| calculateInitialSolutionBreak | 624 |
| calculateInitialSolution_taskScarcity | 660 |
| calculateInitialSolution_connectivity | 662 |
| **calculateInitialSolution_deadhead** | **175** |

---

## Conclusion

Station mismatch is the **binding bottleneck**. No reordering heuristic can
cover a task when no driver is at its origin station. The 45.3% uncoverable
rate on S01 (and higher on larger instances) is determined by how much the
RS greedy solution diverges from the original locomotive routing.

Deadhead is the only approach that addresses the root cause: it expands each
driver's feasible set from {tasks at current station} to {tasks reachable
within time budget at 60 km/h}, reducing uncovered tasks by 50–75% depending
on instance size.

An integrated RS + crew scheduling approach (solving both simultaneously)
would eliminate the station mismatch by construction, but is computationally
far more complex.
