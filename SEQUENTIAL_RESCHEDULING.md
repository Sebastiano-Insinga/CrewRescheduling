# Sequential Rescheduling Pipeline

`SequentialRescheduling.py` implements a two-stage integrated rescheduling approach: first **Rolling Stock**, then **Crew**. The RS output defines the open tasks for the crew solver. Driver states at disruption time are extracted from the original pre-disruption crew schedule.

---

## Input File Preparation

> [!note]- Instances and RS Solutions
> Each instance is stored in `single_type/{id}.json` and contains:
> - `train_sections`: trip segments with departure/arrival times (epoch seconds)
> - `locomotives`: available locomotives
> - `solution`: original pre-disruption rolling stock assignment
> - `disruption_start`, `disruption_end`: disruption window in epoch seconds
> - `disrupted_sections`: section IDs affected by the disruption
>
> Network topology: `single_type/network.json`
> Shortest paths: `single_type/network-shortestpaths.json`

> [!note]- Generating Crew Task Files and ID Mappings
> Run `run_rollingstock_mapping.py` on all instances:
> ```bash
> python3 run_rollingstock_mapping.py \
>   --instance-folder single_type \
>   --solution-folder single \
>   --network single_type/network.json \
>   --shortest-path single_type/network-shortestpaths.json
> ```
> Calls `RollingStockSolutionReader.readRollingStockSolution()` and produces for each instance:
>
> - `Final_Rescheduled_Instances/Transformed-{id}.tsv`
>   Crew tasks: `task_id | origin | destination | departure_minutes | arrival_minutes`
>   Times in minutes from `2018-09-10 00:00:00`.
>
> - `Final_Rescheduled_ID_Mappings/ID-Mapping-Transformed-{id}.tsv`
>   Maps each crew task ID to `{task_type, locomotive, train_section, section, departure_time, arrival_time}`.
>   Used to identify tasks on disrupted sections.

> [!note]- Generating the Original Crew Schedule (Twan Format)
> The pre-disruption crew schedule was solved via column generation / CPLEX.
> Output: `results/Transformed-{id}_duties_with_tasks.csv` with columns `DutyID` and `TaskIDs`.
>
> `convert_csv_to_twan_format.py` converts these to the TXT format expected by `readSolution_Twan_txt_Format()`:
> ```
> Costs | Duration | Task_1 | Task_2 | ...
> ```
> Output: `results_twan_txt/Transformed-{id}_sol.txt`

---

## Pipeline Steps

> [!info]- Step 1 — Rolling Stock Greedy
> Three RS methods available (`--rs-methods`):
>
> | Method | Description |
> |--------|-------------|
> | `randomized_greedy` | Python port of Roberto's `RandomizedGreedy()`. Replicates C++11 `std::mt19937` RNG for exact reproducibility. Accepts `seed`. |
> | `scored_greedy` | Scored variant of the greedy algorithm. |
> | `original_greedy` | Counterfactual: no RS rescheduling. |
>
> ```python
> rs_solution = rs_fn(instance, network, sp, seed=seed)  # randomized_greedy
> rs_solution = rs_fn(instance, network, sp)              # scored_greedy / original_greedy
> ```
> The algorithm assigns locomotives to trips, inserts deadhead trips where needed, and schedules maintenance.
> Trips with no feasible locomotive assignment are marked as `'canceled'`.
>
> Output saved to `output/rs_solution/{id}.json`.

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
> `ReschedulingPreprocessor.generateReschedulingInput()` determines each driver's state at `disruption_start`:
> - Task crossing disruption on **disrupted section**: available at destination at `arrival + (disruption_end - disruption_start)`
> - Task crossing disruption on **non-disrupted section**: available at destination at task arrival time
> - Driver **idle** during disruption: available at origin of next scheduled task at `disruption_start`
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
> Default (`task_source='reader'`): uses `rs_solution_to_open_tasks_via_reader()`.
> Writes the RS solution to `Final_Rescheduled_Instances/Transformed-{id}.tsv` via `readRollingStockSolution()`, then reads it back.
> This ensures task IDs and times are consistent with the ID mapping format.
>
> Legacy (`task_source='inline'`): uses `rs_solution_to_open_tasks()` directly.
> For each assigned locomotive:
> - Creates a **regular task** for each assigned trip (times converted via `epoch_to_minutes()`)
> - Inserts a **deadhead task** between consecutive trips when destination of trip _i_ ≠ origin of trip _i+1_,
>   using the shortest path matrix to compute travel time
>
> Parameters used by `readRollingStockSolution`: `crew_speed_kmh=57.0`, `maintenance_duration=10800.0`, `baseline="2018-09-10"`.
>
> Delta between `open_tasks` count and `id_mapping` entries is logged at runtime.

> [!info]- Step 4 — Crew Rescheduling
> Seven crew methods available (`--crew-methods`):
>
> | Method | Notes |
> |--------|-------|
> | `calculateInitialSolution` | Base greedy |
> | `calculateInitialSolution_slack` | Slack-aware greedy |
> | `calculateInitialSolutionBreak` | Break-aware greedy |
> | `calculateInitialSolution_driverMRV` | Minimum remaining values ordering |
> | `calculateInitialSolution_taskScarcity` | Task scarcity ordering |
> | `calculateInitialSolution_connectivity` | Connectivity-aware greedy |
> | `calculateInitialSolution_deadhead` | Deadhead-aware greedy; returns extra `crew_dh_km` |
>
> All methods share the same base signature:
> ```python
> existing_duties, duty_breaks_crew, uncovered_tasks, suitable_tasks, spare_duty_id_list = crew_fn(
>     original_schedule, driver_status, open_tasks,
>     disruption_start, disruption_end, 720, id_mapping, suitable_tasks
> )
> ```
> `calculateInitialSolution_deadhead` takes additional args and returns one extra value:
> ```python
> existing_duties, duty_breaks_crew, uncovered_tasks, suitable_tasks, spare_duty_id_list, crew_dh_km = crew_fn(
>     ..., sp=sp, dsp=dsp, crew_speed_kmh=57.0, disrupted_edges=disrupted_edges
> )
> ```
> `suitable_tasks` is initialized to all open task IDs for all drivers (no knowledge-based filtering).
>
> `disrupted_edges` is derived from `disrupted_section_ids` → set of `(origin, destination)` tuples.
> `dsp` (disrupted shortest paths) computed via `compute_disrupted_sp(network, sp, disrupted_section_ids)`.
>
> Max duty length: 720 minutes.
>
> Output saved to `output/crew_solution/{id}.json`.

> [!info]- Step 4b — Validation
> After crew rescheduling, sanity checks are run:
> - **Duplicate tasks**: any task assigned to more than one driver
> - **Duty length**: warns if `last_arrival - first_departure > 43200` seconds
> - **Location continuity**: warns if `duty[i].destination != duty[i+1].origin`
> - **Time overlap**: warns if `duty[i+1].departure < duty[i].arrival`

> [!info]- Step 5 — VNS Optimization (optional)
> Activated with `--vns-method {DP,model}`. Skipped by default.
>
> ```python
> _, _, vns_metrics = run_VNS(
>     vns_method, original_schedule, existing_duties, duty_breaks_crew, uncovered_tasks,
>     open_tasks, 0, 0, id_mapping, disruption_start, disruption_end,
>     window_size, runs_per_window, network_for_vns, locomotives, suitable_tasks,
>     max_dh_duration, rand_iter, spare_duty_id_list
> )
> ```
>
> Key parameters:
>
> | Arg | CLI flag | Default |
> |-----|----------|---------|
> | `window_size` | `--window-size` | 120 min |
> | `runs_per_window` | `--runs-per-window` | 5 |
> | `max_dh_duration` | `--max-dh-duration` | 60 min |
> | `rand_iter` | `--rand-iter` | 1 |
>
> Metrics returned: `nr_uncovered_tasks`, `deadheading_costs`, `nr_breaks_violated`, `total_time_seconds`.

---

## Output & CSV Export

Results appended to `test_greedy/results_{timestamp}.csv` after each run.

Columns:

| Column | Description |
|--------|-------------|
| `instance_id` | Instance identifier |
| `rs_method` | RS method used |
| `crew_method` | Crew method used |
| `rs_trips_total` | Total trips in RS solution |
| `rs_covered` | Trips assigned to a locomotive |
| `rs_canceled` | Trips with no feasible assignment |
| `id_mapping_entries` | Entries in ID mapping file |
| `crew_duties` | Number of duties in crew solution |
| `crew_uncovered` | Tasks not assigned to any duty |
| `crew_dh_km` | Total deadhead km (deadhead method only) |
| `crew_time_sec` | Crew solver wall time |
| `vns_method` | VNS method (empty if skipped) |
| `vns_uncovered` | Uncovered tasks after VNS |
| `vns_deadheading` | Deadheading cost after VNS |
| `vns_breaks_violated` | Break violations after VNS |
| `vns_time_sec` | VNS wall time |

> [!summary]- Score
> ```
> Total uncovered = RS canceled trips + crew uncovered tasks
> ```
> - **RS canceled**: trips with no feasible locomotive assignment
> - **Crew uncovered**: tasks in `open_tasks` not assigned to any duty
> - **crew_dh_km**: total deadhead km added by crew solver (tracked separately, not a penalty component)

---

## File Summary

| File | Description |
|------|-------------|
| `single_type/{id}.json` | Disrupted instance (trips, locos, disruption window) |
| `single_type/network.json` | Network topology |
| `single_type/network-shortestpaths.json` | Precomputed shortest paths |
| `Final_Rescheduled_Instances/Transformed-{id}.tsv` | Crew tasks in minutes format |
| `Final_Rescheduled_ID_Mappings/ID-Mapping-Transformed-{id}.tsv` | Task ID → section/loco metadata |
| `results_twan_txt/Transformed-{id}_sol.txt` | Original crew schedule in Twan TXT format |
| `output/rs_solution/{id}.json` | RS greedy output |
| `output/crew_solution/{id}.json` | Crew rescheduling output |
| `test_greedy/results_{timestamp}.csv` | Aggregated results per run |
