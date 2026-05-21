# `calculateInitialSolution` — Technical Documentation (Manuel Refactorized)

## Purpose

`calculateInitialSolution` constructs a **feasible initial crew schedule** after a disruption, to be used as the starting point for the VNS optimization loop. It does not optimize — it produces the first rescheduled plan greedily, respecting duty length and break constraints.

---

## Signature

```python
def calculateInitialSolution(
    original_schedule,   # dict[int, list[dict]] — pre-disruption plan
    driver_status,       # dict[int, dict]        — driver state at disruption time
    input_open_tasks,    # dict[int, dict]         — tasks to be re-assigned
    disruption_start,    # int                     — disruption start (minutes)
    disruption_end,      # int                     — disruption end (minutes)
    max_duty_length,     # int                     — max allowed duty length (minutes, typically 720)
    id_mapping,          # dict[int, dict]          — task metadata (loco type, section, etc.)
    suitable_tasks       # dict[int, list[int]]     — per-driver list of assignable task IDs
) -> (existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, spare_duty_id_list)
```

---

## Input Data Structures

### `original_schedule`
Pre-disruption plan. Used only to determine **which tasks were originally assigned to each driver** (priority logic).
```python
{
    duty_id: [
        {"id": int, "origin": int, "destination": int, "departure": int, "arrival": int},
        ...
    ]
}
```

### `driver_status`
State of each driver **at the moment the disruption starts**. Built by `generateReschedulingInput`.
```python
{
    duty_id: {
        "duty_length":            int,   # minutes already worked
        "break30done":            bool,
        "break45done":            bool,
        "available_from_station": int,   # current station
        "available_at_time":      int    # earliest minute the driver can start a new task
    }
}
```

### `input_open_tasks`
Tasks that must be covered post-disruption. Each task has `departure > disruption_start`.
```python
{
    task_id: {"id": int, "origin": int, "destination": int, "departure": int, "arrival": int}
}
```

### `suitable_tasks`
For each driver, the list of task IDs they are qualified to perform (filtered by `loco_type` and `section_type` compatibility).
```python
{ duty_id: [task_id, ...] }
```

---

## Algorithm — Three Phases

### Phase 1 — Greedy Task Assignment

For each driver, tasks are assigned iteratively in a `while` loop until no more feasible tasks exist.

**Feasibility check** (encapsulated in `_is_task_feasible`):

| Condition | Description |
|-----------|-------------|
| `task["origin"] == current_origin` | Task starts where the driver currently is |
| `task["departure"] >= current_time` | Task does not depart before driver is available |
| `new_duty_length < max_duty_length` | Adding the task does not exceed the duty length limit |
| `task_id in suitable_tasks[driver_id]` | Driver is qualified for the task |

**Duty length calculation:**
- If the driver already has accumulated duty time: `new_duty_length = task["arrival"] - available_at_time + duty_length`
- If the driver has not started yet: `new_duty_length = task["arrival"] - first_departure`

**Task selection priority:**
1. Among feasible tasks, prefer those that were **originally assigned to this driver** in `original_schedule` → minimizes deviation from the original plan.
2. If none of the feasible tasks were originally assigned to this driver → pick the one with **earliest departure**.

**Note on `open_tasks` vs `available_tasks`:**
Both are deep copies of `input_open_tasks`. The distinction handles tasks shared across multiple duties in Twan's solution format:
- `available_tasks` is never modified — all drivers can always see all tasks.
- `open_tasks` tracks which tasks remain truly uncovered: a task is removed from `open_tasks` once it is assigned to any driver.

---

### Phase 2 — Spare Drivers (currently disabled)

A fraction `spare_driver_fraction` (currently `0.0`) of existing duties can be duplicated to create spare driver slots. Each spare driver is assumed qualified for all tasks. This phase produces no output at present.

---

### Phase 3 — Break Planning

For each duty in `existing_duties`, a mandatory break is scheduled based on:

| Condition | Required break |
|-----------|---------------|
| 30-min break already done AND duty ≤ 8h | 0 min (no break needed) |
| 45-min break already done | 0 min (no break needed) |
| 30-min break already done AND duty > 8h | 15 min (top-up) |
| No break done AND duty ≤ 8h | 30 min |
| No break done AND duty > 8h | 45 min |

Break placement strategy (two attempts):
1. Place break at the **start of the first idle window** that occurs after the first quarter of the duty.
2. If that fails, place it at the **end of the idle window** (just before the next task departs).
3. If no suitable idle window exists → `duty_breaks[duty_id] = None`.

---

## Return Values

| Value | Type | Description |
|-------|------|-------------|
| `existing_duties` | `dict[int, list[dict]]` | New rescheduled duties per driver |
| `duty_breaks` | `dict[int, tuple or None]` | Break window `(start, end)` per duty |
| `uncovered_tasks` | `list[dict]` | Tasks that could not be assigned to any driver |
| `suitable_tasks` | `dict[int, list[int]]` | Updated (may include spare driver entries) |
| `spare_duty_id_list` | `list[int]` | IDs of spare driver duties (empty when `spare_driver_fraction=0`) |

---

## Numerical Example

### Setup

```
disruption_start = 500
max_duty_length  = 720

driver_status:
  driver 3: available_from_station=20, available_at_time=500, duty_length=60, no breaks done
  driver 5: available_from_station=30, available_at_time=500, duty_length=60, no breaks done

original_schedule:
  driver 3: [task 101 (10→20, 400–460), task 102 (20→30, 510–570)]
  driver 5: [task 201 (30→40, 420–480), task 203 (30→40, 590–650)]

open_tasks (post-disruption):
  102: origin=20, destination=30, departure=510, arrival=570
  103: origin=30, destination=40, departure=590, arrival=650
  201: origin=30, destination=40, departure=510, arrival=570
  203: origin=30, destination=40, departure=590, arrival=650

suitable_tasks:
  driver 3: [102, 103]
  driver 5: [201, 203, 103]
```

### Phase 1 walkthrough

**Driver 3 — iteration 1**
- `current_origin=20`, `current_time=500`
- Feasible: task 102 (origin=20 ✓, departure=510≥500 ✓, duty_length=570−500+60=130<720 ✓, in suitable ✓)
- task 102 was originally assigned to driver 3 → `previously_assigned = {102}`
- Assign task 102 → `existing_duties[3] = [task102]`, remove 102 from `open_tasks`

**Driver 3 — iteration 2**
- `current_origin=30` (destination of task102), `current_time=570`
- Feasible: task 103 (origin=30 ✓, departure=590≥570 ✓, duty_length=650−500+60=210<720 ✓)
- task 103 was NOT originally assigned to driver 3 → `previously_assigned = {}` → pick earliest = task 103
- Assign task 103 → `existing_duties[3] = [task102, task103]`, remove 103 from `open_tasks`

**Driver 3 — iteration 3**
- No more feasible tasks → stop

**Driver 5 — iteration 1**
- `current_origin=30`, `current_time=500`
- Feasible: task 201 (510≥500 ✓), task 203 (590≥500 ✓), task 103 already removed from `open_tasks` but still in `available_tasks` → task 103 feasible too
- Previously assigned to driver 5: task 201 and 203 → `previously_assigned = {201, 203}`
- Pick earliest departure among previously assigned: task 201 (departure=510) < task 203 (departure=590)
- Assign task 201 → `existing_duties[5] = [task201]`, remove 201 from `open_tasks`

**Driver 5 — iteration 2**
- `current_origin=40` (destination of task201), `current_time=570`
- No task with origin=40 in `available_tasks` → no feasible tasks → stop

### Result

```
existing_duties:
  driver 3: [task102, task103]
  driver 5: [task201]

uncovered_tasks: [task203]

duty_breaks:
  driver 3: None  (no idle gap ≥ 30 min between task102 and task103: gap = 590−570 = 20 min)
  driver 5: None  (single task, no consecutive pair to place break)
```

---

## Testing

A dedicated test module [`test_initial_solution.py`](test_initial_solution.py) is available in the project root. It constructs a minimal hand-crafted instance and calls `calculateInitialSolution` directly, printing `existing_duties`, `duty_breaks`, `uncovered_tasks`, and `spare_driver_ids`.

Run with:
```bash
python3 test_initial_solution.py
```

The test instance corresponds exactly to the numerical example above and can be modified to probe different disruption scenarios, break conditions, or suitability constraints.