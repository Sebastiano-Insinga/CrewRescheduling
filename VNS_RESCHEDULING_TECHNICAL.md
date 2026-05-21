# VNS_Rescheduling — Technical Documentation

## Overview

`VNS_Rescheduling.py` implements a **window-based crew rescheduling algorithm** for railway operations. Given a disruption that invalidates part of an existing crew schedule, it computes a repaired schedule that minimises deviation from the original plan while satisfying operational constraints (duty length, breaks, coverage, deadheading).

The file name says "VNS" (Variable Neighbourhood Search), but the current implementation is a **sliding time-window heuristic** with two interchangeable solvers per window: a Dynamic Programming (DP) heuristic and an exact Gurobi MIP model. The neighbourhood operators defined in `NeighborhoodOperators.py` are available but are not called inside `run_VNS` — they exist as building blocks for a future VNS layer.

---

## Key Concepts

| Term | Meaning |
|------|---------|
| **Task** | A single train service segment: `{id, origin, destination, departure, arrival, locomotive}` |
| **Duty** | An ordered sequence of tasks assigned to one driver |
| **Open task** | Task within the disruption window that needs reassignment |
| **Deadhead** | A driver travelling as a passenger (no driving) to reposition |
| **Suitable task** | A task a specific driver is certified/qualified to perform |
| **Break 30 / Break 45** | Mandatory rest within a duty: 30 min if duty ≤ 8 h, 45 min if > 8 h |
| **Duty category** | Role of a duty within a time window (see below) |

---

## Module Structure

```
VNS_Rescheduling.py          ← main logic (this file)
GraphBuilder.py              ← DAG construction + duty categorisation
DynamicProgramming_GraphSolver.py ← DP solver on DAG
NeighborhoodOperators.py     ← swap / remove-insert operators (unused in run_VNS)
ModelBuilder.py              ← Gurobi MIP formulation
CrewSchedule.py              ← schedule state container
CrewDuty.py                  ← single duty container + feasibility checks
```

---

## Entry Points

### `calculateInitialSolution(...)`

Builds a **greedy feasible starting solution** before optimisation.

**Algorithm:**

1. For each driver in `driver_status`, iterate over `available_tasks` and greedily append the earliest feasible task, preferring tasks that appeared in the driver's original schedule.
2. Feasibility check (`_is_task_feasible`): origin continuity, departure ≥ current time, resulting duty length < `max_duty_length`, task in driver's `suitable_tasks` set.
3. After greedy assignment, any task not assigned becomes an **uncovered task**.
4. **Break planning** per duty: checks duty length and prior break status (`break30done`, `break45done`) to decide required break length (0, 15, 30, or 45 min). Tries to place the break after the first quarter of duty time; falls back to end-of-idle-time placement.
5. Optionally duplicates a fraction (`spare_driver_fraction`, currently 0.0) of duties to simulate spare drivers.

**Returns:** `(existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, spare_duty_id_list)`

---

### `run_VNS(...)`

Main optimisation loop.

**Inputs (key parameters):**

| Parameter | Type | Description |
|-----------|------|-------------|
| `method` | `str` | `"DP"` or `"model"` |
| `original_schedule` | `dict[int, list[task]]` | Pre-disruption crew schedule |
| `initial_solution` | output of `calculateInitialSolution` | Starting point |
| `disruption_start` | `int` | Minutes from week start |
| `window_size` | `int` | Time window width in minutes |
| `runs_per_window` | `int` | Repeated DP runs per window (randomised order) |
| `max_dh_duration` | `int` | Max deadhead travel time in minutes |
| `rand_iter` | `int` | Outer iteration index (for reproducible seeds) |

**High-level flow:**

```
1. Compute all-pairs shortest paths (Dijkstra) over station network
2. Wrap initial solution in CrewSchedule object
3. Slice [disruption_start, 10080) into non-overlapping time windows of width window_size
4. For each window:
     a. Build DAG for this window (buildGraph_shortestPath)
     b. Categorise duties
     c. Solve with DP or Gurobi
     d. Update incumbent schedule (updateScheduleFromWindow)
5. Post-process: makeScheduleBreakFeasible()
6. Return step_results, schedule_figures, final_metrics
```

Time horizon is one week = 10080 minutes.

---

## Shortest Path Preprocessing

`compute_shortest_path_matrix_dijkstra(stations, sections, station_list)`

Runs Dijkstra from every station in `station_list`. Result is `shortest_path[dest][origin]` = distance in metres. Used to price deadhead arcs in the DAG.

---

## Time-Window Graph

`buildGraph_shortestPath(incumbent_schedule, time_window, shortest_path_matrix, max_dh_duration, spare_driver_ids)` — defined in `GraphBuilder.py`.

For each duty, constructs a per-window DAG with these node types:

| Type | Description |
|------|-------------|
| 1 | Regular task node |
| 2 | Start node (real departure) |
| 3 | Dummy start node |
| 4 | Termination node |
| 5 | Dummy termination node |

Arc types encode: task arc, deadhead arc, start/end connector arcs.

Uncovered tasks get `duty_id = -1`.

---

## Duty Categories

`categorizeDuties(currentSolution, timeWindow)` classifies each duty relative to the current window:

| Category | Condition | Meaning |
|----------|-----------|---------|
| 1 | starts before window, ends after window | Continuing duty — only middle tasks free |
| 2 | starts inside window, ends after window | Starting duty — start time fixed, end free |
| 3 | starts before window, ends inside window | Terminating duty — start fixed, end constrained |
| 4 | entirely inside window | Flexible duty — fully re-optimisable |
| 5 | no overlap | Ignored |

This classification drives different DP formulations (see below).

---

## DP Solver (`DP_SingleDuty`)

Solves the shortest path from `source` to `sink` on the per-duty DAG using **topological-order DP** (Kahn's algorithm for topo sort).

**Objective:** minimise arc costs − bonus for each newly covered task.

- `bonus_task_covered = 3000` — large bonus incentivises covering uncovered tasks over minimising deadhead.
- `max_duty_length = 720` min — hard constraint on path length.

**Category-specific logic:**

- **Category 3 (terminating):** tracks `duration_to[node]` from known duty start time; enforces `duration ≤ 720`.
- **Category 2 (starting):** filters valid start nodes (departure such that duty end − departure ≤ 720); runs standard DP from those nodes.
- **Category 4 (flexible):** DP state is `(node_id, start_node)` — tries all possible start nodes and picks the globally cheapest feasible path.
- **Category 1 / default:** standard source-to-sink DP with bonus logic.

Passenger deadheading is allowed only if another driver already covers the task (`neighbor_id in covered_nodes`); otherwise the arc is skipped for unsuitable drivers.

**`runs_per_window`** re-runs the DP with shuffled duty ordering. Because duties compete for nodes, ordering matters. Best result across runs is kept.

**Seed:** `rand_iter * RANDOM_SEED + time_window[0] + i` — deterministic and non-overlapping across outer iterations.

---

## Gurobi Model Solver

When `method == "model"`, `WindowBasedModel_GUROBI_ComplicatedBreaks` (from `ModelBuilder.py`) solves an exact MIP for the window.

Solution extraction reconstructs node paths per duty from binary arc variables `x[k][a]`, filters out dummy nodes, sorts by departure, then calls `updateScheduleFromWindow`.

---

## Objective Function (Schedule-Level)

`CrewSchedule.evaluteScheduleObjective()` returns:

- `nr_deadheads` — total deadhead movements
- `deadheading_costs` — weighted deadhead distance
- `nr_uncovered_tasks` — tasks with no driver
- `nr_breaks_violated` — duties where mandatory break not satisfied
- `nr_spared_drivers` — duties with no tasks (potential savings)

`calcDifferenceToOriginalSchedule_ScheduleClass` measures **stability**: number of task-driver assignments that differ from the original schedule.

---

## Post-Processing

After the window loop:

1. `makeScheduleBreakFeasible()` — re-inserts break slots where violated.
2. Duty length histogram bucketed into `[0-360, 361-480, 481-600, 601-720]` minutes.
3. Final metrics dict returned to caller.

---

## Neighbourhood Operators (Available, Not Yet Used in `run_VNS`)

Defined in `NeighborhoodOperators.py`:

| Operator | Description |
|----------|-------------|
| `swapNeighborhoodOperator` | Swap one task between two duties (same origin/destination only) |
| `removeInsertNeighborhoodOperator` | Move one task from duty1 to duty2 |
| `removeInsertTrainBlockNeighborhoodOperator` | Move a consecutive same-locomotive block between duties |
| `doubleRemoveInsertNeighborhoodOperator` | Move two tasks from duty1 to duty2 |
| `doubleSplitRemoveInsertNeighborhoodOperator` | Move two tasks from duty1 to duty2 and duty3 respectively |

All operators call `check_feasibility()` and return `False` if the result is infeasible.

---

## Data Flow Diagram

```
Input
  original_schedule
  driver_status
  open_tasks
  network_data
        │
        ▼
calculateInitialSolution()
  → greedy duty assignment
  → break planning
        │
        ▼
run_VNS()
  → Dijkstra all-pairs shortest paths
  → CrewSchedule initialisation
  │
  └─ for each time_window:
       buildGraph_shortestPath()   → DAG
       categorizeDuties()          → duty categories
       │
       ├─ method=="DP"
       │    DP_SingleDuty() × runs_per_window × |duties|
       │    best paths selected
       │
       └─ method=="model"
            WindowBasedModel_GUROBI_ComplicatedBreaks()
            exact MIP solve
       │
       updateScheduleFromWindow()
       evaluteScheduleObjective()
  │
  makeScheduleBreakFeasible()
        │
        ▼
  final_metrics, step_results, schedule_figures
```

---

## Constraints Summary

| Constraint | Where enforced |
|------------|----------------|
| Origin continuity | `_is_task_feasible`, DAG arc construction |
| Departure ≥ current time | `_is_task_feasible`, DAG arc construction |
| Duty length ≤ 720 min | `_is_task_feasible`, `DP_SingleDuty` (duration tracking) |
| Driver qualification | `suitable_tasks[driver_id]` check throughout |
| Mandatory break (30 or 45 min) | `calculateInitialSolution` + `makeScheduleBreakFeasible` |
| No double-coverage (DP) | `covered_nodes` set prevents bonus duplication |