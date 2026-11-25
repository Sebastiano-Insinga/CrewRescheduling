#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crew_return_trip as chainlib
import distribution_report as report

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHAIN_DEFAULT = os.path.join(os.path.dirname(ROOT), "manuel_chain", "chain.json")

LAST_EXACT = 9
LABELS = [str(n) for n in range(1, LAST_EXACT + 1)] + [f">={LAST_EXACT + 1}"]
LEGEND_LABELS = {label: ("1 trip" if label == "1" else
                         f"{label} trips" if label.isdigit() else
                         f"{LAST_EXACT + 1} trips or more")
                 for label in LABELS}

COLUMNS = ["duty_id", "instance", "n_trips"]

instance_tasks = {}


def class_of(n_trips):
    return str(n_trips) if n_trips <= LAST_EXACT else LABELS[-1]


def read_instance(path):
    df = pd.read_csv(path)
    df["class"] = [class_of(n) for n in df["n_trips"]]
    return df


def summary_row(name, df):
    trips = df["n_trips"]
    tasks = instance_tasks.get(name)
    return {
        "instance": name,
        "duties": len(df),
        "min": int(trips.min()),
        "median": round(float(trips.median()), 2),
        "mean": round(float(trips.mean()), 2),
        "max": int(trips.max()),
        "trips_total": int(trips.sum()),
        "tasks": tasks,
        "avg_cover": round(trips.sum() / tasks, 3) if tasks else None,
    }


def write_duty_csv(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Number of trips per duty: one csv per instance, frequency tables and charts.")
    parser.add_argument("-chain", default=CHAIN_DEFAULT,
                        help="chain.json of the run: says where duties and tasks are")
    parser.add_argument("-instances", default=None,
                        help="comma separated subset, e.g. S01,S05 (default: all)")
    parser.add_argument("-out", default=None,
                        help="output folder (default: <chain folder>/trips_per_duty)")
    args = parser.parse_args()

    with open(args.chain) as f:
        chain = json.load(f)
    chain_dir = os.path.dirname(os.path.abspath(args.chain))
    out_dir = args.out or os.path.join(chain_dir, "trips_per_duty")
    analysis_dir = os.path.join(out_dir, "analysis")
    os.makedirs(analysis_dir, exist_ok=True)

    duty_files = chainlib.find_duty_files(chain, chain_dir)
    if args.instances:
        wanted = [w.strip() for w in args.instances.split(",") if w.strip()]
        duty_files = [(name, path) for name, path in duty_files
                      if any(w in name for w in wanted)]
        if not duty_files:
            sys.exit(f"no instance of {wanted} in {args.chain}")

    csv_files = []
    total_duties = 0
    for instance, duty_path in duty_files:
        duties = chainlib.duty_reader(duty_path)(duty_path, instance)
        rows = [{"duty_id": duty["id"], "instance": instance,
                 "n_trips": len(duty["task_ids"])} for duty in duties]
        tasks = (chainlib.read_tasks(chainlib.task_file(chain, chain_dir, instance))
                 if "crew_task" in chain else None)
        instance_tasks[report.short_name(instance + ".csv")] = len(tasks) if tasks else None

        csv_path = os.path.join(out_dir, instance + ".csv")
        write_duty_csv(csv_path, rows)
        csv_files.append(csv_path)
        total_duties += len(rows)
        over = f" over {len(tasks)} tasks" if tasks else ""
        print(f"{instance}: {len(rows)} duties, {sum(r['n_trips'] for r in rows)} trips"
              f"{over} -> {csv_path}")

    print(f"\ntotal duties: {total_duties}\n")

    report.write_report(
        csv_files, analysis_dir, LABELS, LEGEND_LABELS, read_instance, summary_row,
        xlsx_name="trips_per_duty.xlsx",
        chart_name="trips_per_duty_by_instance",
        chart_title=f"Trips per duty ({chain['name']})",
        legend_title="Trips in the duty",
        table_title="Share of duties per number of trips",
        colormap="YlGnBu")


if __name__ == "__main__":
    main()
