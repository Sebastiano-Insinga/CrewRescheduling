"""
Diagnostic: compare open_tasks produced by rs_solution_to_open_tasks (inline)
vs readRollingStockSolution (original) on the same RS solution.

Run:  python compare_open_tasks.py [instance_id]
      default instance_id = S01
"""
import json
import os
import sys
import tempfile
import csv

from InstanceReader import read_instance_data
from RollingStockSolutionReader import readRollingStockSolution
from RollingStockGreedy import load_data, randomized_greedy
from SequentialRescheduling import rs_solution_to_open_tasks, epoch_to_minutes

INSTANCE_DIR       = "single_type"
NETWORK_FILE       = os.path.join(INSTANCE_DIR, "network.json")
SHORTESTPATHS_FILE = os.path.join(INSTANCE_DIR, "network-shortestpaths.json")

TRAIN_SPEED_KMH   = 57.0
MAINTENANCE_SEC   = 10800.0


def build_network_dict(network_raw):
    """Convert raw network JSON to dict format expected by readRollingStockSolution."""
    return {"sections": {s["id"]: s for s in network_raw["sections"]}}


def tasks_from_reader(instance_name, rs_solution, network_raw, instance_raw, sp):
    """Call readRollingStockSolution and read back the TSV it writes."""
    network_dict   = build_network_dict(network_raw)
    instance_dict  = read_instance_data(os.path.join(INSTANCE_DIR, f"{instance_name}.json"))

    # readRollingStockSolution writes to Final_Rescheduled_Instances/
    os.makedirs("Final_Rescheduled_Instances", exist_ok=True)
    os.makedirs("Final_Rescheduled_ID_Mappings", exist_ok=True)

    readRollingStockSolution(
        f"Transformed-{instance_name}.tsv",
        rs_solution,
        network_dict,
        instance_dict,
        sp,
        TRAIN_SPEED_KMH,
        MAINTENANCE_SEC,
        3,           # format: minutes since 2018-09-10
        False,
        "2018-09-10",
    )

    tsv_path = os.path.join("Final_Rescheduled_Instances", f"Transformed-{instance_name}.tsv")
    tasks = {}
    with open(tsv_path) as f:
        for row in csv.reader(f, delimiter="\t"):
            tid = int(row[0])
            tasks[tid] = {
                "id":          tid,
                "origin":      int(row[1]),
                "destination": int(row[2]),
                "departure":   int(row[3]),
                "arrival":     int(row[4]),
            }
    return tasks


def task_key(t):
    """Content key: IDs are sequential counters and not comparable across implementations."""
    return (t["origin"], t["destination"], t["departure"], t["arrival"])


def compare(a: dict, b: dict, label_a: str, label_b: str):
    keys_a = {task_key(t) for t in a.values()}
    keys_b = {task_key(t) for t in b.values()}

    only_a = keys_a - keys_b
    only_b = keys_b - keys_a
    common = keys_a & keys_b

    print(f"\n{'='*60}")
    print(f"  {label_a}: {len(a)} tasks")
    print(f"  {label_b}: {len(b)} tasks")
    print(f"  Identical tasks (by origin/dest/dep/arr): {len(common)}")
    print(f"  Only in {label_a}: {len(only_a)}")
    print(f"  Only in {label_b}: {len(only_b)}")

    if only_a:
        print(f"\n  Tasks only in {label_a} (first 10):")
        for k in sorted(only_a)[:10]:
            print(f"    origin={k[0]} dest={k[1]} dep={k[2]} arr={k[3]}")

    if only_b:
        print(f"\n  Tasks only in {label_b} (first 10):")
        for k in sorted(only_b)[:10]:
            print(f"    origin={k[0]} dest={k[1]} dep={k[2]} arr={k[3]}")

    origins_a = sorted(set(t["origin"] for t in a.values()))
    origins_b = sorted(set(t["origin"] for t in b.values()))
    print(f"\n  Distinct origin stations {label_a}: {len(origins_a)}")
    print(f"  Distinct origin stations {label_b}: {len(origins_b)}")
    only_orig_a = set(origins_a) - set(origins_b)
    only_orig_b = set(origins_b) - set(origins_a)
    if only_orig_a:
        print(f"  Origins only in {label_a}: {sorted(only_orig_a)}")
    if only_orig_b:
        print(f"  Origins only in {label_b}: {sorted(only_orig_b)}")


if __name__ == "__main__":
    instance_id = sys.argv[1] if len(sys.argv) > 1 else "S01"
    seed        = int(sys.argv[2]) if len(sys.argv) > 2 else 42

    instance_file = os.path.join(INSTANCE_DIR, f"{instance_id}.json")
    instance_raw, network_raw, sp = load_data(instance_file, NETWORK_FILE, SHORTESTPATHS_FILE)

    print(f"Running randomized_greedy on {instance_id} seed={seed}...")
    rs_solution = randomized_greedy(instance_raw, network_raw, sp, seed=seed)
    assigned = sum(1 for e in rs_solution if e["locomotive"] != "canceled")
    print(f"RS solution: {len(rs_solution)} trips, {assigned} assigned")

    print("\nBuilding open_tasks via rs_solution_to_open_tasks...")
    tasks_inline = rs_solution_to_open_tasks(rs_solution, instance_raw, network_raw, sp)

    print("Building open_tasks via readRollingStockSolution...")
    tasks_reader = tasks_from_reader(instance_id, rs_solution, network_raw, instance_raw, sp)

    compare(tasks_inline, tasks_reader, "rs_solution_to_open_tasks", "readRollingStockSolution")
