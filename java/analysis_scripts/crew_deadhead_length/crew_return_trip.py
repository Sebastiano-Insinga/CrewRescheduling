#!/usr/bin/env python3
import argparse
import csv
import glob
import json
import os
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SP_DEFAULT = os.path.join(os.path.dirname(ROOT), "Instances", "single_type",
                          "validation", "single_type", "network-shortestpaths.json")

COLUMNS = ["duty_id", "instance", "n_tasks", "start_station", "end_station",
           "distance_km", "time_minutes", "status", "over_cap"]


def read_tasks(path):
    tasks = {}
    with open(path) as f:
        for line in f:
            cells = line.rstrip("\n").split("\t")
            if len(cells) < 5 or not cells[0].strip():
                continue
            tasks[cells[0].strip()] = {
                "origin": int(cells[1]),
                "destination": int(cells[2]),
                "departure": int(cells[3]),
            }
    return tasks


def read_duties(path, instance):
    duties = []
    with open(path) as f:
        lines = f.read().splitlines()
    for number, line in enumerate(lines[1:], start=1):
        task_ids = [c.strip() for c in line.split("\t")[2:] if c.strip()]
        if task_ids:
            duties.append({"id": f"{instance}#{number}", "task_ids": task_ids})
    return duties


def read_duties_csv(path, instance):
    duties = []
    with open(path) as f:
        for row in csv.DictReader(f):
            task_ids = row["TaskIDs"].split()
            if task_ids:
                duties.append({"id": f"{instance}#{row['DutyID']}", "task_ids": task_ids})
    return duties


def read_duties_plan(path, instance):
    duties = []
    with open(path) as f:
        for line in f:
            cells = [c.strip() for c in line.strip().split("\t")]
            task_ids = [c for c in cells[1:] if c]
            if task_ids:
                duties.append({"id": f"{instance}#{cells[0]}", "task_ids": task_ids})
    return duties


KNOWN_SUFFIXES = ("_duties_with_tasks.csv", "_sol.txt")


def instance_name(path, strip):
    base = os.path.basename(path)
    for suffix in KNOWN_SUFFIXES:
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    else:
        base = os.path.splitext(base)[0]
    for prefix in strip:
        if base.startswith(prefix):
            base = base[len(prefix):]
    return base


def find_duty_files(chain, chain_dir):
    if "crew_schedule_glob" in chain:
        paths = sorted(glob.glob(os.path.join(chain_dir, chain["crew_schedule_glob"])))
    else:
        duties_dir = os.path.join(chain_dir, chain["crew_schedule"])
        paths = sorted(os.path.join(duties_dir, f) for f in os.listdir(duties_dir)
                       if f.endswith("_sol.txt"))
    strip = chain.get("crew_schedule_strip", [])
    return [(instance_name(p, strip), p) for p in paths]


def duty_reader(path):
    if path.endswith("_duties_with_tasks.csv"):
        return read_duties_csv
    if path.endswith("_sol.txt"):
        return read_duties
    return read_duties_plan


def task_file(chain, chain_dir, instance):
    pattern = chain.get("crew_task_pattern", "{instance}.tsv")
    return os.path.join(chain_dir, chain["crew_task"], pattern.format(instance=instance))


def distance_meters(sp, origin, destination):
    entry = sp.get(str(origin), {}).get(str(destination))
    return None if entry is None else entry["weight"]


def compute_return_trip(duty, tasks, sp):
    unmatched = [t for t in duty["task_ids"] if t not in tasks]
    if unmatched:
        return {"status": "mapping_error", "start": None, "end": None,
                "meters": None, "unmatched": unmatched}

    ordered = sorted(duty["task_ids"], key=lambda t: tasks[t]["departure"])
    start = tasks[ordered[0]]["origin"]
    end = tasks[ordered[-1]]["destination"]
    result = {"start": start, "end": end, "unmatched": []}

    if start == end:
        return {**result, "status": "ok", "meters": 0}

    meters = distance_meters(sp, end, start)
    if meters is not None:
        return {**result, "status": "ok", "meters": meters}

    meters = distance_meters(sp, start, end)
    if meters is not None:
        return {**result, "status": "reversed", "meters": meters}

    return {**result, "status": "missing", "meters": None}


def report(duty, result):
    if result["status"] == "mapping_error":
        print(f"[mapping_error] {duty['id']}: task ids not found "
              f"{' '.join(result['unmatched'])}")
    elif result["status"] == "reversed":
        print(f"[reversed] {duty['id']}: used the distance {result['start']} -> "
              f"{result['end']}, the return direction is missing")
    elif result["status"] == "missing":
        print(f"[missing] {duty['id']}: no distance between {result['end']} and "
              f"{result['start']} in either direction")


def csv_row(duty, result, instance, speed_kmh, cap):
    if result["meters"] is None:
        distance_km, time_minutes = "", ""
        over_cap = "" if cap is None else 1
    else:
        minutes = result["meters"] / 1000.0 / speed_kmh * 60.0
        distance_km = f"{result['meters'] / 1000.0:.3f}"
        time_minutes = f"{minutes:.2f}"
        over_cap = "" if cap is None else int(minutes > cap)
    return {
        "duty_id": duty["id"],
        "instance": instance,
        "n_tasks": len(duty["task_ids"]),
        "start_station": result["start"] if result["start"] is not None else "",
        "end_station": result["end"] if result["end"] is not None else "",
        "distance_km": distance_km,
        "time_minutes": time_minutes,
        "status": result["status"],
        "over_cap": over_cap,
    }


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Distance and travel time for the driver's return trip from the "
                    "end-of-duty station to the start-of-duty station, one csv per instance.")
    parser.add_argument("-chain",
                        default=os.path.join(os.path.dirname(ROOT), "manuel_chain", "chain.json"),
                        help="chain.json of the run: ties duties and tasks together")
    parser.add_argument("-shortestpaths", default=None,
                        help="overrides the network declared by the chain")
    parser.add_argument("-speed", type=float, default=57.0,
                        help="crew deadhead speed in km/h")
    parser.add_argument("-cap", type=float, default=None,
                        help="crew deadhead cap in minutes, fills the over_cap column")
    args = parser.parse_args()

    with open(args.chain) as f:
        chain = json.load(f)
    chain_dir = os.path.dirname(os.path.abspath(args.chain))
    out_dir = os.path.join(chain_dir, "crew_deadhead_length")
    os.makedirs(out_dir, exist_ok=True)

    if args.shortestpaths:
        network = args.shortestpaths
    elif "railway_network" in chain:
        network = os.path.join(chain_dir, chain["railway_network"])
    else:
        network = SP_DEFAULT
    network = os.path.normpath(network)
    print(f"network: {network}")
    with open(network) as f:
        sp = json.load(f)

    duty_files = find_duty_files(chain, chain_dir)

    counts = {"ok": 0, "reversed": 0, "missing": 0, "mapping_error": 0}
    times = []
    over_cap = 0
    over_cap_single_task = 0

    for instance, duty_path in duty_files:
        tasks = read_tasks(task_file(chain, chain_dir, instance))
        duties = duty_reader(duty_path)(duty_path, instance)

        rows = []
        for duty in duties:
            result = compute_return_trip(duty, tasks, sp)
            report(duty, result)
            row = csv_row(duty, result, instance, args.speed, args.cap)
            counts[row["status"]] += 1
            if row["time_minutes"]:
                times.append(float(row["time_minutes"]))
            if row["over_cap"] == 1:
                over_cap += 1
                if row["n_tasks"] == 1:
                    over_cap_single_task += 1
            rows.append(row)

        csv_path = os.path.join(out_dir, instance + ".csv")
        write_csv(csv_path, rows)
        print(f"{instance}: {len(rows)} duties -> {csv_path}")

    print(f"\n=== summary ({chain['name']}, {args.speed} km/h) ===")
    print(f"total duties: {sum(counts.values())}")
    for status, how_many in counts.items():
        print(f"  {status:<14} {how_many}")
    if times:
        print(f"return travel time over {len(times)} duties with a distance (minutes):")
        print(f"  min     {min(times):.2f}")
        print(f"  max     {max(times):.2f}")
        print(f"  mean    {statistics.mean(times):.2f}")
        print(f"  median  {statistics.median(times):.2f}")
    if args.cap is not None:
        print(f"duties over the {args.cap:.0f} minute cap: {over_cap}, "
              f"of which {over_cap_single_task} with a single task")


if __name__ == "__main__":
    main()
