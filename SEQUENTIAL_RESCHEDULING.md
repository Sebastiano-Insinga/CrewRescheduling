# Sequential Rescheduling Pipeline

`SequentialRescheduling.py` implements a two-stage integrated rescheduling approach: first **Rolling Stock**, then **Crew**. The RS output defines the open tasks for the crew solver. Driver states at disruption time are extracted from the original pre-disruption crew schedule.

---

## Input File Preparation

> [!note]- Instances and RS Solutions
> Each instance `S01`–`S20` is stored in `single_type/S{id}.json` and contains:
> - `train_sections`: trip segments with departure/arrival times (epoch seconds)
> - `locomotives`: available locomotives
> - `solution`: original pre-disruption rolling stock assignment
> - `disruption_start`, `disruption_end`: disruption window in epoch seconds
> - `disrupted_sections`: section IDs affected by the disruption
>
> Reference RS rescheduled solutions (Roberto's C++ solver) are in `single/S{id}.json_*.sol`.

> [!note]- Generating Crew Task Files and ID Mappings
> Run `run_rollingstock_mapping.py` on all instances:
> ```bash
> python3 run_rollingstock_mapping.py \
>   --instance-folder single_type \
>   --solution-folder single \
>   --network single_type/network.json \
>   --shortest-path single_type/network-shortestpaths.json
> ```
> This calls `RollingStockSolutionReader.readRollingStockSolution()` and produces for each instance:
>
> - `Final_Rescheduled_Instances/Transformed-S{id}.tsv`
>   Crew tasks: `task_id | origin | destination | departure_minutes | arrival_minutes`
>   Times in minutes from `2018-09-10 00:00:00`.
>
> - `Final_Rescheduled_ID_Mappings/ID-Mapping-Transformed-S{id}.tsv`
>   Maps each crew task ID to `{task_type, locomotive, train_section, section, departure_time, arrival_time}`.
>   Used to determine whether a task runs on a disrupted section.

> [!note]- Generating the Original Crew Schedule (Twan Format)
> The pre-disruption crew schedule was solved via column generation / CPLEX.
> Output: `results/Transformed-S{id}_duties_with_tasks.csv` with columns `DutyID` and `TaskIDs`.
>
> `convert_csv_to_twan_format.py` converts these to the TXT format expected by `readSolution_Twan_txt_Format()`:
> ```
> Costs | Duration | Task_1 | Task_2 | ...
> ```
> Output: `results_twan_txt/Transformed-S{id}_sol.txt`
>
> The script looks up task details (origin, destination, departure, arrival) from
> `Final_Rescheduled_Instances/Transformed-S{id}.tsv`.

---

## Pipeline Steps

> [!info]- Step 1 — Rolling Stock Greedy
> ```python
> rs_solution = randomized_greedy(instance, network, sp, seed=seed)
> ```
> `RollingStockGreedy.randomized_greedy()` is a Python port of Roberto's `frisch_solution.cc::RandomizedGreedy()`.
> It replicates C++11 `std::mt19937` RNG for exact reproducibility.
> The algorithm assigns locomotives to trips, inserts deadhead trips where needed, and schedules maintenance.
> Trips with no feasible locomotive assignment are marked as `'canceled'`.
>
> Output saved to `output/rs_solution/S{id}.json`.

> [!info]- Step 2 — Driver Status Extraction
> To respect each driver's position at disruption time, three inputs are combined:
>
> **2a. Original crew schedule:**
> ```python
> original_schedule, duty_breaks = readSolution_Twan_txt_Format(crew_schedule_file, crew_task_file)
> ```
> Returns `{duty_id: [task, ...]}` with times in minutes, and `duty_breaks: {duty_id: (start, end) | None}`.
>
> **2b. ID mapping:**
> ```python
> id_mapping = readIDMapping(id_mapping_file)
> ```
> Maps crew task IDs to section and type metadata. Used to identify tasks on disrupted sections.
>
> **2c. Driver status:**
> ```python
> driver_status, _, _ = generateReschedulingInput(original_schedule, duty_breaks, instance_file, id_mapping)
> ```
> `ReschedulingPreprocessor.generateReschedulingInput()` iterates over all duties and determines each driver's state at `disruption_start`:
> - Task crossing disruption on a **disrupted section**: available at destination, at time `arrival + (disruption_end - disruption_start)`
> - Task crossing disruption on a **non-disrupted section**: available at destination, at task arrival time
> - Driver **idle** during disruption: available at origin of next scheduled task, at `disruption_start`
>
> Each `driver_status[duty_id]` entry:
> ```python
> {
>   "available_from_station": int,
>   "available_at_time": int,    # minutes from baseline
>   "duty_length": int,          # minutes already worked
>   "break30done": bool,
>   "break45done": bool
> }
> ```

> [!info]- Step 3 — Open Tasks from RS Solution
> ```python
> open_tasks = rs_solution_to_open_tasks(rs_solution, instance, network, sp)
> ```
> Converts the RS greedy output into crew tasks to cover. For each assigned locomotive:
> - Creates a **regular task** for each assigned trip (times converted to minutes via `epoch_to_minutes()`)
> - Inserts a **deadhead task** between consecutive trips when destination of trip _i_ ≠ origin of trip _i+1_,
>   using the shortest path matrix to compute travel time
>
> Task IDs are assigned sequentially (1, 2, 3, …).

> [!info]- Step 4 — Crew Rescheduling
> ```python
> suitable_tasks = {driver_id: list(open_tasks.keys()) for driver_id in driver_status}
>
> existing_duties, _, uncovered_tasks, _, _ = calculateInitialSolution(
>     original_schedule, driver_status, open_tasks,
>     disruption_start, disruption_end, 720, id_mapping, suitable_tasks
> )
> ```
> `VNS_Rescheduling.calculateInitialSolution()` implements a greedy crew rescheduling heuristic.
> For each driver it iterates greedily:
> 1. Finds feasible tasks: same origin as current position, departure ≥ availability time, resulting duty ≤ 720 min, task in `suitable_tasks[driver_id]`
> 2. Among feasible tasks, **prefers tasks originally assigned to this driver** in `original_schedule` (minimal deviation)
> 3. Falls back to earliest feasible task if none match the original plan
> 4. Repeats until no more tasks can be appended
>
> `suitable_tasks` is initialized to all open task IDs for all drivers (no knowledge-based filtering).
>
> Output saved to `output/crew_solution/S{id}.json`.

> [!summary]- Score
> ```
> Total uncovered = RS canceled trips + crew uncovered tasks
> ```
> - **RS canceled**: trips with no feasible locomotive assignment
> - **Crew uncovered**: tasks in `open_tasks` not assigned to any duty

---

## File Summary

| File | Description |
|------|-------------|
| `single_type/S{id}.json` | Disrupted instance (trips, locos, disruption window) |
| `single/S{id}.json_*.sol` | Reference RS rescheduled solution (Roberto) |
| `Final_Rescheduled_Instances/Transformed-S{id}.tsv` | Crew tasks in minutes format |
| `Final_Rescheduled_ID_Mappings/ID-Mapping-Transformed-S{id}.tsv` | Task ID → section/loco metadata |
| `results/Transformed-S{id}_duties_with_tasks.csv` | Original crew schedule (CPLEX output) |
| `results_twan_txt/Transformed-S{id}_sol.txt` | Original crew schedule in Twan TXT format |
| `output/rs_solution/S{id}.json` | RS greedy output |
| `output/crew_solution/S{id}.json` | Crew rescheduling output |
