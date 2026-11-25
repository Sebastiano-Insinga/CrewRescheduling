# Pipeline: from Rolling Stock solution to Sequential Rescheduling

Full data path, from raw instances to crew rescheduling results. Four stages, each
with its own inputs and outputs.

Reference run: `java/results0709/`.

---

## Overview

```
instance .json ──┐
network .json  ──┼─► [F0] run_rollingstock_mapping.py ─► .tsv  +  ID-Mapping .tsv
shortest paths ──┘                                        │            │
                                                          │            │
                        [F1] Column Generation (Java) ─► _duties_with_tasks.csv
                                                          │            │
                                                          ▼            │
                     [F2] convert_csv_to_twan_format.py ─► _sol.txt    │
                                                          │            │
                                                          ▼            ▼
                          [F3] SequentialRescheduling.py ─► crew results
```

The three files reaching F3 (`_sol.txt`, `.tsv`, `ID-Mapping-*.tsv`) are
**complementary and mutually constrained**: task ids only make sense within the
conversion that produced them. Mixing files from different runs yields silently
wrong results, not an error.

---

## F0 — Rolling Stock solution mapping

Turns a locomotive→trip assignment into a list of **crew tasks**, inserting
deadhead tasks wherever a locomotive has to reposition empty.

**Script**: `run_rollingstock_mapping.py` → `RollingStockSolutionReader.readRollingStockSolution()`

### Input

| File | Content |
|---|---|
| `<instance-folder>/S*.json` | `train_sections` (epoch times), `locomotives`, `disruption_start/end`, `disrupted_sections`, and the `solution` key — the rolling stock assignment |
| `Instances/single_type/network.json` | sections: origin, destination, distance |
| `Instances/single_type/network-shortestpaths.json` | shortest path matrix (deadhead travel times) |

The rolling stock solution is read from the **`solution` key embedded in the
instance JSON**. `--solution-folder` is left out.

### Output

| File | Content |
|---|---|
| `Final_Rescheduled_Instances/Transformed-S01.tsv` | `task_id ⇥ origin ⇥ destination ⇥ departure ⇥ arrival` — minutes from `2018-09-10` |
| `Final_Rescheduled_ID_Mappings/ID-Mapping-Transformed-S01.tsv` | `task_id ⇥ {task_type, locomotive, train_section, section, departure_time, arrival_time}` — epoch |

Both written in the **same pass**, which is why their task ids always match.

### How each row is built

The reader groups trips by locomotive, then walks each locomotive's sequence
assigning an incremental id:

- an actual trip → `task_type: 'regular'`
- destination of trip *i* ≠ origin of trip *i+1* → a `'deadhead'` task is inserted,
  carrying the `first_*` / `second_*` fields of the two trips it bridges

### Command

Output goes to a separate working directory so existing mappings are not
overwritten:

```bash
mkdir -p validation_mapping/Final_Rescheduled_{Instances,ID_Mappings}
cd validation_mapping
PYTHONPATH=<repo> python3 ../run_rollingstock_mapping.py \
  --instance-folder ../Instances/single_type/validation/single_type \
  --network ../Instances/single_type/network.json \
  --shortest-path ../Instances/single_type/network-shortestpaths.json
```

> **Gotcha** — write paths are relative and hardcoded in the reader
> (`RollingStockSolutionReader.py:237-242`): `Final_Rescheduled_Instances//` and
> `Final_Rescheduled_ID_Mappings//`. They must exist beforehand, and the current
> working directory decides where files land. Changing the cwd is the only way to
> redirect output without touching the code.
>
> The `Generated instance: ...` message prints a path derived from `__file__`, not
> from the actual cwd — misleading when running from elsewhere.

---

## F1 — Crew Scheduling by Column Generation

Solves the **pre-disruption** crew scheduling problem. Two-phase approach:

1. columns (duties) generated iteratively over the continuous relaxation of the RMP;
   terminates when no duty with negative reduced cost can be found
2. `switchToInteger()` — duty variables switched from continuous to integer, with a
   39,600 s (11 h) time limit, overridable with `-Dmip.timelimit=<seconds>`

Method: `applyColumnGeneration0SI()`.

| Parameter | Value |
|---|---|
| `MAX_DUTY_LENGTH` | 720 min |
| `BREAK_LENGTH` | 30 min |

### Input

`Final_Rescheduled_Instances/Transformed-S*.tsv` (output of F0).

### Output

`Transformed-S01_duties_with_tasks.csv` — two columns:

```csv
DutyID,TaskIDs
260,"59 58 57 102 101 100 60"
311,"62 61 99 98 97 64 63"
```

In run 0709: `java/results0709/resultsCG/`, 20 instances S01–S20.

---

## F2 — Conversion to Twan format

The column generation CSV carries task ids only. The format read by the Sequential
step also needs per-duty costs and duration, which are **recomputed** by reading
times from the `.tsv`.

**Script**: `convert_csv_to_twan_format.py`

### Input

| Environment variable | Default | Content |
|---|---|---|
| `CSV_INPUT_DIR` | `results` | the `*_duties_with_tasks.csv` files |
| `INSTANCE_DIR` | `Final_Rescheduled_Instances` | the `Transformed-S*.tsv` files (for times) |
| `TXT_OUTPUT_DIR` | `results_twan_txt` | destination |

### Output

`Transformed-S01_sol.txt`:

```
Costs	Duration	Task_1	Task_2	...
239.0	229.0	38
66.0	56.0	67
```

Ends with an uncovered section (`Costs` / `MyIndex`) that is always left empty.

### Computation

```
duration = max(arrival over the duty's tasks) - min(departure over the duty's tasks)
costs    = duration + 10 * number_of_tasks
```

### Command

```bash
CSV_INPUT_DIR=java/results0709/resultsCG \
INSTANCE_DIR=Final_Rescheduled_Instances \
TXT_OUTPUT_DIR=java/results0709/results_twan_txt \
python3 convert_csv_to_twan_format.py
```

> **Gotchas**
> - Costs and Duration do **not** come from the column generation, they are
>   recomputed here. Getting the true CG costs means changing this formula.
> - `INSTANCE_DIR` must be the same conversion the CG ran on, otherwise identical
>   ids point to different tasks.
> - Tasks present in the CSV but missing from the `.tsv` are dropped silently.
> - Naming matters: the file must be named `Transformed-S01_duties_with_tasks.csv`,
>   the S-id is extracted from the dash-separated parts.

---

## F3 — Sequential Rescheduling

Two-stage rescheduling: rolling stock first, then crew. The RS output defines the
open tasks for the crew solver; driver states at disruption time are derived from
the pre-disruption crew schedule.

**Script**: `SequentialRescheduling.py`

### Input — three files per instance

| File | Role |
|---|---|
| `results_twan_txt/Transformed-S01_sol.txt` | which tasks in which duty (from F2) |
| `Final_Rescheduled_Instances/Transformed-S01.tsv` | what each task is: stations and times (from F0) |
| `Final_Rescheduled_ID_Mappings/ID-Mapping-Transformed-S01.tsv` | metadata: type, locomotive, section (from F0) |

plus the instance `S01.json`, the network and the shortest paths.

### Internal steps

| Step | What it does |
|---|---|
| 1 | **RS greedy** — `randomized_greedy` (Python port of the C++ `RandomizedGreedy()`, replicating the `mt19937` RNG), `scored_greedy`, or `original_greedy`. Trips with no feasible locomotive → `canceled` |
| 2 | **Driver status** — position and availability of each driver at `disruption_start`, from the original schedule plus the ID mapping |
| 3 | **Open tasks** — tasks to cover, generated from the rescheduled RS solution |
| 4 | **Crew rescheduling** — 7 greedy variants, `calculateInitialSolution` being the baseline. Max duty length 720 min |
| 4b | **Validation** — duplicate tasks, duty length, location continuity, time overlaps |
| 5 | **VNS** (optional, `--vns-method DP\|model`) — skipped by default |

### Output

| Path | Content |
|---|---|
| `output/rs_solution/{id}.json` | rolling stock solution |
| `output/crew_solution/{id}.json` | crew solution |
| `test_greedy/results_<timestamp>.csv` | metrics per instance × RS method × crew method |

### Command

```bash
python3 SequentialRescheduling.py \
  --crew-schedule-dir java/results0709/results_twan_txt \
  --rs-methods randomized_greedy scored_greedy \
  --crew-methods calculateInitialSolution
```

Without `--instances` it runs on every `S*.json` found.

> **Watch the defaults**: omitting `--rs-methods` and `--crew-methods` runs every
> combination — 3 RS × 7 crew = 21 runs per instance, 420 across 20 instances.

### Directory flags

Added so different runs can coexist without overwriting each other:

| Flag | Default |
|---|---|
| `--instance-dir` | `Instances/single_type` |
| `--crew-schedule-dir` | `results_twan_txt` |
| `--crew-task-dir` | `Final_Rescheduled_Instances` |
| `--id-mapping-dir` | `Final_Rescheduled_ID_Mappings` |
| `--network` | `<instance-dir>/network.json` |
| `--shortest-paths` | `<instance-dir>/network-shortestpaths.json` |

---

## Run layout

```
java/results0709/
├── resultsCG/                          20 column generation CSVs   (F1)
├── results_twan_txt/                   20 _sol.txt files           (F2)
└── mapping/
    ├── Final_Rescheduled_Instances/    20 Transformed-S*.tsv       (F0)
    └── Final_Rescheduled_ID_Mappings/  20 ID-Mapping-*.tsv         (F0)
```

## Consistency constraint

The `_sol.txt` files hold bare task ids. Those ids are defined by the `.tsv` they
were generated against, and by the `ID-Mapping` produced alongside that `.tsv`. The
practical rule: **always take the three files from the same F0 → F1 → F2 chain**.
Crossing them between runs raises no exception, it just produces wrong numbers.
