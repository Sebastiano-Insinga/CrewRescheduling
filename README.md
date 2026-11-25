# Integrated Crew and Rolling Stock Rescheduling

Code and data to reproduce the experiments of the technical documentation
("Integrated Crew and Rolling Stock Rescheduling", November 2026). Section numbers below refer to
that document.

## Requirements

- Python 3.9 or later: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Only for Figure 1: Google Chrome installed, which `kaleido` uses to export the PNG files.
- Only for the column generation (Section 3): Java 17 and IBM CPLEX (the runs used CPLEX Studio
  22.2), which is not distributed here. The crew plans it produced are included, so every other
  step runs without it.

Every command runs from the repository root. Outputs go under `runs/<tag>/`, which is not
versioned; pick a new tag for each run.

## What is where

| Folder | Content |
|---|---|
| `Instances/single_type/validation/single_type/` | instances S01 to S20, network, shortest paths |
| `java/src/` | column generation solver (Section 3) |
| `java/cap180/` | crew plans with the 180 min limit on the return trip: the chain every result uses |
| `java/results0709/` | crew plans with no limit on the return trip |
| `java/runs/cap180/` | column generation output the `cap180` chain is converted from |
| `pipeline/` | stages F0 and F2 of the data chain (Section 3) |
| `rescheduling/` | sequential and integrated rescheduling (Sections 4, 5, 6) |
| `VNS/scripts/` | swap local search, and the explicit move redesign (Section 8) |
| `validator/` | independent ex post validator (Section 7) |
| `Comparison_Integrated_Sequential/scripts/` | sequential against integrated campaign |
| `experiments/slurm/`, `java/slurm/` | SLURM job scripts used on the cluster |

A chain (`chain.json`) ties together the three crew files of one conversion. Pass it as a single
token, `--chain java/cap180`: task identifiers only make sense inside the conversion that produced
them, and mixing files of two runs gives wrong numbers rather than an error.

## Reproducing the results

### Crew plans (Section 3)

```bash
python3 pipeline/run_rollingstock_mapping.py \
    --instance-folder Instances/single_type/validation/single_type \
    --network Instances/single_type/validation/single_type/network.json \
    --shortest-path Instances/single_type/validation/single_type/network-shortestpaths.json \
    -out-dir runs/<tag>/mapping

CREWDEADHEAD=180 sbatch java/slurm/run_columngeneration.slurm \
    runs/<tag>/mapping/Final_Rescheduled_Instances cg_<tag>

CSV_INPUT_DIR=runs/cg_<tag> \
INSTANCE_DIR=runs/<tag>/mapping/Final_Rescheduled_Instances \
TXT_OUTPUT_DIR=runs/<tag>/results_twan_txt \
python3 pipeline/convert_csv_to_twan_format.py
```

The second command needs a SLURM cluster with CPLEX; without `CREWDEADHEAD=180` it produces the
plans with no limit. To check the other two stages without it, run the third one with
`CSV_INPUT_DIR=java/runs/cap180`: the first and the third reproduce `java/cap180` byte for byte.

Return trip, Table 1 (Section 3.4), for each of the two chains:

```bash
python3 java/analysis_scripts/crew_deadhead_length/crew_return_trip.py \
    -chain java/cap180/chain.json \
    -shortestpaths Instances/single_type/validation/single_type/network-shortestpaths.json -cap 180
python3 java/analysis_scripts/crew_deadhead_length/return_time_distribution.py \
    -input java/cap180/crew_deadhead_length
```

### Sequential against integrated (Tables 2 and 3)

```bash
python3 Comparison_Integrated_Sequential/scripts/CompareSequentialIntegrated.py \
    -i S01 S02 S03 S04 S05 S06 S07 S08 S09 S10 S11 S12 S13 S14 S15 S16 S17 S18 S19 S20 \
    -s 42 --chain java/cap180 \
    --instance-dir Instances/single_type/validation/single_type \
    -o runs/<tag>/<tag>.csv --export-solution runs/<tag>/solutions
```

Add `--no-maintenance` for Table 3. The sequential column is `seq_trip_lost_total`, not the total
printed on screen.

### Swap local search, three minute budget (Tables 4 and 5)

```bash
python3 VNS/scripts/VNSRescheduler.py \
    -i S01 S02 S03 S04 S05 S06 S07 S08 S09 S10 S11 S12 S13 S14 S15 S16 S17 S18 S19 S20 \
    -loop --shake random -k-max 5 -max-iter 20 --time-limit 180 \
    --accept-delta 0 -seed 42 -vns-seed 42 \
    --chain java/cap180 \
    --instance-dir Instances/single_type/validation/single_type \
    -csv runs/<tag>/<tag>.csv --export-solution runs/<tag>/solutions
```

Cheaper iterations: add `--early-exit --replay --min-alternatives 2 --shake window --window-hours 4`.
Reference run (Table 5): the command above without `-max-iter 20`, that is with no iteration cap.

Run the instances one at a time: the time limit is wall clock, and parallel runs change the
number of iterations that fit in it.

### Validation (Section 7)

```bash
python3 -m validator.Validator -s runs/<tag>/solutions/S01_k5_random_seed42_vns42.json
```

### Figure 1

```bash
python3 LaTex/img/scripts/export_swap_gantt.py S01 runs/<tag>/figures
```
