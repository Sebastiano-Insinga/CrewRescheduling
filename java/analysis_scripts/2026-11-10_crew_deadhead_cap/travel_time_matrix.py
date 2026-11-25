#!/usr/bin/env python3
import argparse
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
JAVA = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(JAVA)
SP_DEFAULT = os.path.join(REPO, "Instances", "single_type", "validation",
                          "single_type", "network-shortestpaths.json")
TASK_DEFAULT = os.path.join(JAVA, "nocap", "mapping", "Final_Rescheduled_Instances")


def read_stations_and_tasks(task_dir):
    stations, tasks = set(), []
    for name in sorted(os.listdir(task_dir)):
        if not name.endswith(".tsv"):
            continue
        with open(os.path.join(task_dir, name)) as f:
            for line in f:
                cells = line.rstrip("\n").split("\t")
                if len(cells) < 5 or not cells[0].strip():
                    continue
                origin, destination = int(cells[1]), int(cells[2])
                stations.add(origin)
                stations.add(destination)
                tasks.append((name[:-4], cells[0].strip(), origin, destination))
    return sorted(stations), tasks


def minutes(sp, frm, to, speed):
    if frm == to:
        return 0.0, "same"
    entry = sp.get(str(frm), {}).get(str(to))
    if entry is not None:
        return entry["weight"] / 1000.0 / speed * 60.0, "direct"
    entry = sp.get(str(to), {}).get(str(frm))
    if entry is not None:
        return entry["weight"] / 1000.0 / speed * 60.0, "reversed"
    return None, "missing"


def main():
    parser = argparse.ArgumentParser(
        description="Exports the crew deadhead time matrix Java would need for a hard cap, "
                    "and counts the pairs the network cannot price.")
    parser.add_argument("-shortestpaths", default=SP_DEFAULT)
    parser.add_argument("-tasks", default=TASK_DEFAULT)
    parser.add_argument("-speed", type=float, default=57.0)
    parser.add_argument("-caps", default="180,240")
    parser.add_argument("-out", default=os.path.join(HERE, "out"))
    args = parser.parse_args()

    caps = [float(c) for c in args.caps.split(",")]
    with open(args.shortestpaths) as f:
        sp = json.load(f)
    stations, tasks = read_stations_and_tasks(args.tasks)
    os.makedirs(args.out, exist_ok=True)

    counts = {"same": 0, "direct": 0, "reversed": 0, "missing": 0}
    matrix_path = os.path.join(args.out, "crew_deadhead_minutes.tsv")
    with open(matrix_path, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["from_station", "to_station", "minutes", "source"])
        for frm in stations:
            for to in stations:
                value, source = minutes(sp, frm, to, args.speed)
                counts[source] += 1
                if value is not None:
                    writer.writerow([frm, to, f"{value:.2f}", source])

    print(f"stations used: {len(stations)}")
    print(f"ordered pairs: {sum(counts.values())}  " +
          "  ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"matrix written: {matrix_path}")

    single = {cap: 0 for cap in caps}
    missing_pairs = 0
    rows = []
    for instance, task_id, origin, destination in tasks:
        value, source = minutes(sp, destination, origin, args.speed)
        if value is None:
            missing_pairs += 1
            continue
        row = {"instance": instance, "task_id": task_id, "origin": origin,
               "destination": destination, "return_minutes": f"{value:.2f}",
               "source": source}
        for cap in caps:
            over = value > cap
            row[f"over_{int(cap)}"] = int(over)
            if over:
                single[cap] += 1
        rows.append(row)

    out_path = os.path.join(args.out, "single_task_duty_return.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\ntasks: {len(tasks)}  unpriceable return: {missing_pairs}")
    for cap in caps:
        pct = 100.0 * single[cap] / len(rows)
        print(f"cap {int(cap)} min: {single[cap]} tasks ({pct:.1f}%) have no feasible "
              "single task duty, their slack column breaks the cap")
    print(f"per task detail: {out_path}")


if __name__ == "__main__":
    main()
