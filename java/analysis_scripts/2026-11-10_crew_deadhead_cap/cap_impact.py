#!/usr/bin/env python3
import argparse
import csv
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
JAVA = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(JAVA)
SP_DEFAULT = os.path.join(REPO, "Instances", "single_type", "validation",
                          "single_type", "network-shortestpaths.json")

DUTY_COLUMNS = ["duty_id", "instance", "n_tasks", "start_station", "end_station",
                "return_minutes", "status", "truncated_tasks", "kept_tasks",
                "truncation_status"]


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
                "arrival": int(cells[4]),
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


def minutes(sp, frm, to, speed):
    if frm == to:
        return 0.0, "ok"
    entry = sp.get(str(frm), {}).get(str(to))
    if entry is not None:
        return entry["weight"] / 1000.0 / speed * 60.0, "ok"
    entry = sp.get(str(to), {}).get(str(frm))
    if entry is not None:
        return entry["weight"] / 1000.0 / speed * 60.0, "reversed"
    return None, "missing"


def truncate(ordered, tasks, sp, speed, cap):
    """Longest chronological prefix whose return trip fits the cap."""
    start = tasks[ordered[0]]["origin"]
    for cut in range(len(ordered), 0, -1):
        end = tasks[ordered[cut - 1]]["destination"]
        value, status = minutes(sp, end, start, speed)
        if value is not None and value <= cap:
            return cut, len(ordered) - cut, "ok"
    return 0, len(ordered), "no_feasible_prefix"


def main():
    parser = argparse.ArgumentParser(
        description="Impact of a hard cap on the crew return deadhead, measured on "
                    "the duties of an existing column generation run.")
    parser.add_argument("-chain", default=os.path.join(JAVA, "results0709", "chain.json"))
    parser.add_argument("-shortestpaths", default=SP_DEFAULT)
    parser.add_argument("-speed", type=float, default=57.0)
    parser.add_argument("-caps", default="180,240")
    parser.add_argument("-out", default=os.path.join(HERE, "out"))
    args = parser.parse_args()

    caps = [float(c) for c in args.caps.split(",")]
    with open(args.chain) as f:
        chain = json.load(f)
    chain_dir = os.path.dirname(os.path.abspath(args.chain))
    sched_dir = os.path.join(chain_dir, chain["crew_schedule"])
    task_dir = os.path.join(chain_dir, chain["crew_task"])
    with open(args.shortestpaths) as f:
        sp = json.load(f)
    os.makedirs(args.out, exist_ok=True)

    duty_rows = []
    per_instance = []
    for name in sorted(os.listdir(sched_dir)):
        if not name.endswith("_sol.txt"):
            continue
        instance = name[: -len("_sol.txt")]
        tasks = read_tasks(os.path.join(task_dir, instance + ".tsv"))
        duties = read_duties(os.path.join(sched_dir, name), instance)

        values, singles, violations = [], 0, {cap: 0 for cap in caps}
        single_violations = {cap: 0 for cap in caps}
        orphans = {cap: 0 for cap in caps}
        infeasible = {cap: 0 for cap in caps}
        covered = 0
        for duty in duties:
            unmatched = [t for t in duty["task_ids"] if t not in tasks]
            if unmatched:
                continue
            ordered = sorted(duty["task_ids"], key=lambda t: tasks[t]["departure"])
            start = tasks[ordered[0]]["origin"]
            end = tasks[ordered[-1]]["destination"]
            value, status = minutes(sp, end, start, args.speed)
            covered += len(ordered)
            if value is not None:
                values.append(value)
            if len(ordered) == 1:
                singles += 1
            row = {
                "duty_id": duty["id"], "instance": instance,
                "n_tasks": len(ordered), "start_station": start, "end_station": end,
                "return_minutes": "" if value is None else f"{value:.2f}",
                "status": status,
            }
            for cap in caps:
                over = value is not None and value > cap
                if over:
                    violations[cap] += 1
                    if len(ordered) == 1:
                        single_violations[cap] += 1
                    kept, dropped, tstatus = truncate(ordered, tasks, sp, args.speed, cap)
                    orphans[cap] += dropped
                    if tstatus != "ok":
                        infeasible[cap] += 1
                    if cap == caps[0]:
                        row.update({"kept_tasks": kept, "truncated_tasks": dropped,
                                    "truncation_status": tstatus})
            row.setdefault("kept_tasks", "")
            row.setdefault("truncated_tasks", "")
            row.setdefault("truncation_status", "")
            duty_rows.append(row)

        entry = {"instance": instance, "duties": len(duties), "tasks_covered": covered,
                 "single_task_duties": singles,
                 "median_return": round(statistics.median(values), 1) if values else "",
                 "max_return": round(max(values), 1) if values else ""}
        for cap in caps:
            tag = int(cap)
            entry[f"over_{tag}"] = violations[cap]
            entry[f"over_{tag}_pct"] = round(100.0 * violations[cap] / len(duties), 1)
            entry[f"over_{tag}_single_task"] = single_violations[cap]
            entry[f"orphan_tasks_{tag}"] = orphans[cap]
            entry[f"no_feasible_prefix_{tag}"] = infeasible[cap]
        per_instance.append(entry)

    with open(os.path.join(args.out, "duties_vs_cap.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=DUTY_COLUMNS)
        writer.writeheader()
        writer.writerows(duty_rows)

    fields = list(per_instance[0].keys())
    total = {"instance": "All instances"}
    for key in fields[1:]:
        if key.endswith("_pct") or key.startswith("median") or key.startswith("max"):
            continue
        total[key] = sum(e[key] for e in per_instance)
    for cap in caps:
        tag = int(cap)
        total[f"over_{tag}_pct"] = round(100.0 * total[f"over_{tag}"] / total["duties"], 1)
    with open(os.path.join(args.out, "cap_impact_by_instance.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(per_instance + [total])

    for entry in per_instance + [total]:
        print(entry)


if __name__ == "__main__":
    main()
