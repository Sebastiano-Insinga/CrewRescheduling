# DSP vs SP Analysis in `calculateInitialSolution_deadhead`

## Context

Railway crew rescheduling after disruption. `calculateInitialSolution_deadhead` is a greedy algorithm that assigns drivers to tasks (train sections), allowing **deadhead** travel (driver travels as passenger to reach a task).

Two shortest-path matrices are used:
- **SP** (Shortest Path): precomputed on the full undisrupted network. Format: `{str(station): {str(station): {"weight": meters, "path": [...]}}}`
- **DSP** (Disrupted Shortest Path): recomputed after removing disrupted sections. Format: `{int(station): {int(station): meters}}` — weights only, no path list.

---

## When DSP vs SP is Used

Function `_get_deadhead_minutes(from_station, to_station, current_time, task_departure, sp, dsp, disruption_start, disruption_end, crew_speed_kmh)`:

```python
crosses_disruption = (dsp is not None and
                      current_time <= disruption_end and
                      task_departure >= disruption_start)
```

**DSP is selected when:**
1. DSP matrix exists
2. Current time of driver ≤ disruption end
3. Task departure ≥ disruption start

**SP is selected otherwise.**

The function returns `(minutes, used_dsp)` — a tuple indicating travel time and which matrix was used.

---

## Driver Availability During Disruption

With `VARIANT_AVAILABLE_WHEN_IDLE_DURING_DISRUPTION = 2` (active in production):

- Drivers **not performing a task during disruption** get `available_at_time = disruption_start`
- These drivers are **candidates for DSP** usage because their `available_at_time <= disruption_end`

Instrumentation print `[CANDIDATE DSP]` confirms: in S03, **28+ drivers** have `available_at_time` within the disruption window.

---

## Feasibility Checking vs Task Selection

Two distinct phases:

### Phase 1: Feasibility check (`_is_task_feasible_with_deadhead`)

For every (driver, task) candidate pair, DSP **is used** when the condition is met.

Instrumentation `[FIRST DH]` output from S03:
```
[FIRST DH] driver=X task=Y dh=Z.Z min used_dsp=True
```
DSP is correctly invoked during feasibility evaluation for candidate drivers.

### Phase 2: Actual task selection (`calculateInitialSolution_deadhead` main loop)

Instrumentation `[DH]` output from S01, S02, S03:
```
[DH] driver=X task=Y dh=Z.Z min matrix=SP ...
```
**All selected deadheads use SP, never DSP.**

---

## Root Cause: Why DSP Is Never Selected

The greedy algorithm assigns tasks in order of departure time. For each unassigned task, it finds the best available driver.

**Structural reason:**
1. Driver is idle at station X, `available_at_time = disruption_start`
2. Greedy first considers the task departing from station X (same station as driver)
3. Deadhead distance = 0 → `used_dsp` is irrelevant, no matrix is consulted
4. Driver is assigned to this local task → `available_at_time` and `available_at_station` update to end of that task
5. Next task for this driver is evaluated **after** the first task ends → `current_time > disruption_end` → SP is used

**Consequence:** The DSP condition is satisfied **during feasibility checking** but the winning assignment is always the zero-deadhead local task. No driver is ever selected for a task that requires deadheading through a disrupted section during the disruption window.

---

## What Would Be Needed to Trigger DSP in Selection

A hand-crafted instance where:
1. Driver is idle at station X during disruption
2. **No task departs from station X** in the task list
3. Driver must deadhead to station Y to reach any task
4. The direct path X→Y passes through a disrupted section
5. DSP provides an alternative route (longer but unblocked)
6. The task at Y departs within the disruption window

In production instances (S01, S02, S03), this configuration does not occur: every driver has at least one task originating at their current station, or the disruption window has expired before their next deadhead.

---

## Summary of Findings

| Instance | DSP candidates | DSP in feasibility | DSP in selection |
|----------|---------------|-------------------|-----------------|
| S01      | Yes           | Yes (inferred)    | **No**          |
| S02      | Yes           | Yes (inferred)    | **No**          |
| S03      | 28+           | Yes (confirmed)   | **No**          |

**DSP matrix is correctly built and correctly queried during feasibility evaluation. It never determines the final assignment in real instances because the greedy algorithm always finds a zero-deadhead assignment first.**

---

## Instrumentation Added to `VNS_Rescheduling.py`

Three print points added to `calculateInitialSolution_deadhead`:

1. **`[CANDIDATE DSP]`** — printed before the inner loop for drivers whose `available_at_time <= disruption_end`. Shows which drivers are in scope for DSP usage.

2. **`[FIRST DH]`** — printed inside the feasibility loop when `driver_id not in existing_duties and dh > 0`. Shows the first deadhead check per driver, including `used_dsp` flag.

3. **`[DH]`** — printed when a deadheading assignment is actually selected. Shows `matrix=SP` or `matrix=DSP`, distance in km, and path stations.

`_get_deadhead_minutes` modified to return `(minutes, used_dsp: bool)`.
`_is_task_feasible_with_deadhead` modified to return `(feasible, dh_minutes, new_duty_length, used_dsp)` — all early returns emit 4 values.

---

## Next Steps

- Build hand-crafted instance (based on `mini-network.json` topology) where a driver **must** deadhead through a disrupted section → forces DSP into actual selection
- Add plotly visualization showing:
  - Original SP path (dashed, grey)
  - Disrupted section (red)
  - DSP rerouted path (solid, blue)
  - Driver movement as annotated edge
- Fix known bug: `max(existing_duties.keys())` in `calculateInitialSolution:107` crashes when no tasks assigned (currently documented with `@unittest.expectedFailure` in `test_crew_scheduling.py`)
