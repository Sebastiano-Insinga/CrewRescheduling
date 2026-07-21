import csv
import json
import os
import glob
import math
from datetime import datetime
import pandas as pd

from RollingStockGreedy import load_data, randomized_greedy, scored_greedy, original_greedy, count_canceled, compute_disrupted_sp
from InstanceReader import read_instance_data
from RollingStockSolutionReader import readRollingStockSolution

RS_METHODS = {
    'randomized_greedy': randomized_greedy,
    'scored_greedy':     scored_greedy,
    'original_greedy':   original_greedy,   # counterfactual: no RS rescheduling
}
from ReadSolution_Twan import readSolution_Twan_txt_Format
from ReschedulingPreprocessor import generateReschedulingInput
from IDMappingReader import readIDMapping
from VNS_Rescheduling import calculateInitialSolution, calculateInitialSolution_slack, calculateInitialSolutionBreak, calculateInitialSolution_driverMRV, calculateInitialSolution_taskScarcity, calculateInitialSolution_connectivity, calculateInitialSolution_deadhead, run_VNS

INSTANCE_DIR       = "single_type"
NETWORK_FILE       = os.path.join(INSTANCE_DIR, "network.json")
SHORTESTPATHS_FILE = os.path.join(INSTANCE_DIR, "network-shortestpaths.json")
CREW_SCHEDULE_DIR  = "results_twan_txt"
CREW_TASK_DIR      = "Final_Rescheduled_Instances"
ID_MAPPING_DIR     = "Final_Rescheduled_ID_Mappings"
OUTPUT_RS_DIR      = "output/rs_solution"
OUTPUT_CREW_DIR    = "output/crew_solution"

BASELINE_DAY = datetime(2018, 9, 10)


def epoch_to_minutes(epoch_seconds):
    dt = datetime.fromtimestamp(epoch_seconds)
    diff = dt - BASELINE_DAY
    return diff.days * 1440 + math.ceil(dt.hour * 60 + dt.minute + dt.second / 60.0)


def rs_solution_to_open_tasks(rs_solution, instance, network, sp):
    sections_by_id = {s['id']: s for s in network['sections']}
    loco_classes   = {lc['id']: lc for lc in network['locomotive_classes']}
    trips_by_id    = {t['id']: t for t in instance['train_sections']}

    dh_speed  = list(loco_classes.values())[0]['deadhead_speed']
    maint_dur = list(loco_classes.values())[0]['maintenance_duration']

    loco_trips = {}
    for entry in rs_solution:
        if entry['locomotive'] == 'canceled':
            continue
        lid = entry['locomotive']
        loco_trips.setdefault(lid, []).append(entry)

    open_tasks = {}
    task_id = 1

    for _, entries in loco_trips.items():
        sorted_entries = sorted(entries, key=lambda e: trips_by_id[e['id_trip']]['departure_time'])
        prev_arrival = prev_dest = prev_maint_arr = None

        for entry in sorted_entries:
            tid    = entry['id_trip']
            trip   = trips_by_id[tid]
            sec    = sections_by_id[trip['section']]
            origin = sec['origin']
            dest   = sec['destination']
            dep    = trip['departure_time']
            arr    = trip['arrival_time']
            m_dep  = entry['maintenance_at_departure'] == 'true'
            m_arr  = entry['maintenance_at_destination'] == 'true'

            if origin == dest:
                prev_arrival, prev_dest, prev_maint_arr = arr, dest, m_arr
                continue

            if prev_dest is not None and prev_dest != origin:
                sp_entry = sp.get(str(prev_dest), {}).get(str(origin))
                if sp_entry is not None:
                    dh_dist_km  = sp_entry['weight'] / 1000.0
                    dh_time_sec = (dh_dist_km / dh_speed) * 3600.0
                    dh_start = prev_arrival
                    if prev_maint_arr:
                        dh_start += maint_dur
                    if m_dep:
                        dh_start = dep - maint_dur - dh_time_sec
                    dh_end = dh_start + dh_time_sec
                    open_tasks[task_id] = {
                        'id': task_id, 'origin': prev_dest, 'destination': origin,
                        'departure': epoch_to_minutes(dh_start), 'arrival': epoch_to_minutes(dh_end),
                    }
                    task_id += 1

            open_tasks[task_id] = {
                'id': task_id, 'origin': origin, 'destination': dest,
                'departure': epoch_to_minutes(dep), 'arrival': epoch_to_minutes(arr),
            }
            task_id += 1
            prev_arrival, prev_dest, prev_maint_arr = arr, dest, m_arr

    return open_tasks


def rs_solution_to_open_tasks_via_reader(instance_id, rs_solution, network_raw, sp):
    """
    Task generation using readRollingStockSolution.
    Uses in-memory return value — does not read back from disk.
    Use task_source='reader' in run_instance to activate.
    """
    network_dict  = {"sections": {s["id"]: s for s in network_raw["sections"]}}
    instance_dict = read_instance_data(os.path.join(INSTANCE_DIR, f"{instance_id}.json"))

    tasks_to_write, _ = readRollingStockSolution(
        f"{instance_id}_rescheduled", rs_solution, network_dict, instance_dict,
        sp, 57.0, 10800.0, 3, False, "2018-09-10",
    )

    open_tasks = {}
    for row in tasks_to_write:
        tid = int(row[0])
        open_tasks[tid] = {
            "id": tid, "origin": int(row[1]), "destination": int(row[2]),
            "departure": int(row[3]), "arrival": int(row[4]),
        }
    return open_tasks


CREW_METHODS = {
    'calculateInitialSolution':               calculateInitialSolution,
    'calculateInitialSolution_slack':         calculateInitialSolution_slack,
    'calculateInitialSolutionBreak':          calculateInitialSolutionBreak,
    'calculateInitialSolution_driverMRV':     calculateInitialSolution_driverMRV,
    'calculateInitialSolution_taskScarcity':  calculateInitialSolution_taskScarcity,
    'calculateInitialSolution_connectivity':  calculateInitialSolution_connectivity,
    'calculateInitialSolution_deadhead':      calculateInitialSolution_deadhead,
}

VNS_METHODS = ['DP', 'model']


def run_instance(instance_id, seed=42, rs_method='randomized_greedy', method='calculateInitialSolution',
                 vns_method=None, window_size=120, runs_per_window=5, max_dh_duration=60, rand_iter=1,
                 task_source='reader'):  # task_source: 'reader' (default) | 'inline' (legacy)
    instance_file      = os.path.join(INSTANCE_DIR, f"{instance_id}.json")
    crew_schedule_file = os.path.join(CREW_SCHEDULE_DIR, f"Transformed-{instance_id}_sol.txt")
    crew_task_file     = os.path.join(CREW_TASK_DIR, f"Transformed-{instance_id}.tsv")
    id_mapping_file    = os.path.join(ID_MAPPING_DIR, f"ID-Mapping-Transformed-{instance_id}.tsv")

    for f in [instance_file, crew_schedule_file, crew_task_file, id_mapping_file]:
        if not os.path.exists(f):
            raise FileNotFoundError(f"Missing: {f}")

    instance, network, sp = load_data(instance_file, NETWORK_FILE, SHORTESTPATHS_FILE)
    disrupted_section_ids = set(instance.get('disrupted_sections', []))
    dsp = compute_disrupted_sp(network, sp, disrupted_section_ids)
    disrupted_edges = {
        (s['origin'], s['destination'])
        for s in network.get('sections', [])
        if s['id'] in disrupted_section_ids
    }
    # Step 1: RS Greedy
    rs_fn = RS_METHODS[rs_method]
    rs_solution = rs_fn(instance, network, sp, seed=seed) if rs_method == 'randomized_greedy' else rs_fn(instance, network, sp)
    rs_canceled = count_canceled(rs_solution)
    rs_covered  = len(rs_solution) - rs_canceled
    print(f"[{rs_method}] trips total={len(rs_solution)}, covered={rs_covered}, canceled={rs_canceled}")
    os.makedirs(OUTPUT_RS_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_RS_DIR, f"{instance_id}.json"), 'w') as f:
        json.dump(rs_solution, f, indent=2)

    # Step 2: driver_status from original crew schedule
    id_mapping = readIDMapping(id_mapping_file)
    print(f"[ID Mapping] loaded {len(id_mapping)} entries")
    original_schedule, duty_breaks = readSolution_Twan_txt_Format(crew_schedule_file, crew_task_file)
    driver_status, _, _ = generateReschedulingInput(
        original_schedule, duty_breaks, instance_file, id_mapping
    )

    # Step 3: open_tasks from new RS solution
    if task_source == 'reader':
        open_tasks = rs_solution_to_open_tasks_via_reader(instance_id, rs_solution, network, sp)
    else:
        open_tasks = rs_solution_to_open_tasks(rs_solution, instance, network, sp)
    print(f"[open_tasks/{task_source}] {len(open_tasks)} tasks vs id_mapping {len(id_mapping)} entries (delta={len(open_tasks)-len(id_mapping):+d})")
    suitable_tasks = {driver_id: list(open_tasks.keys()) for driver_id in driver_status}

    # Step 4: Crew Rescheduling (greedy initial solution)
    disruption_start = epoch_to_minutes(instance['disruption_start'])
    disruption_end   = epoch_to_minutes(instance['disruption_end'])

    crew_fn = CREW_METHODS[method]
    crew_start = datetime.now()
    crew_dh_km = 0.0
    if method == 'calculateInitialSolution_deadhead':
        existing_duties, duty_breaks_crew, uncovered_tasks, suitable_tasks, spare_duty_id_list, crew_dh_km = crew_fn(
            original_schedule, driver_status, open_tasks,
            disruption_start, disruption_end, 720, id_mapping, suitable_tasks,
            sp=sp, dsp=dsp, crew_speed_kmh=57.0, disrupted_edges=disrupted_edges
        )
    else:
        existing_duties, duty_breaks_crew, uncovered_tasks, suitable_tasks, spare_duty_id_list = crew_fn(
            original_schedule, driver_status, open_tasks,
            disruption_start, disruption_end, 720, id_mapping, suitable_tasks
        )
    crew_time_sec = round((datetime.now() - crew_start).total_seconds(), 3)
    print(f"[{method}] duties={len(existing_duties)}, uncovered tasks={len(uncovered_tasks)}, time={crew_time_sec}s")

    # Validation checks
    print(f"[CHECK] Validating {len(existing_duties)} duties...")
    task_assignment_count = {}
    for did, duty in existing_duties.items():
        for task in duty:
            tid = task["id"]
            task_assignment_count[tid] = task_assignment_count.get(tid, 0) + 1
    duplicates = {tid: cnt for tid, cnt in task_assignment_count.items() if cnt > 1}
    if duplicates:
        print(f"[WARN] {len(duplicates)} task assegnati a più driver: {list(duplicates.items())[:5]}")
    else:
        print(f"[CHECK] Nessun task duplicato.")
    for did, duty in existing_duties.items():
        if not duty:
            continue
        dl = duty[-1]["arrival"] - duty[0]["departure"]
        if dl > 43200:
            print(f"[WARN] Duty {did} troppo lunga: {dl/3600:.1f}h ({dl}s)")
        for i in range(len(duty) - 1):
            if duty[i]["destination"] != duty[i + 1]["origin"]:
                print(f"[WARN] Duty {did} task {i}: destination={duty[i]['destination']} != origin={duty[i+1]['origin']}")
            if duty[i + 1]["departure"] < duty[i]["arrival"]:
                print(f"[WARN] Duty {did} task {i}: overlap departure={duty[i+1]['departure']} < arrival={duty[i]['arrival']}")
    
    # Diagnose uncovered tasks: timing vs location
    if uncovered_tasks:
        print(f"[UNCOVERED] Diagnosing {len(uncovered_tasks)} uncovered tasks...")
        CREW_SPEED_KMH = 57.0
        for task in uncovered_tasks:
            tid = task['id']
            best_gap = None
            no_path_count = 0
            for did, d in driver_status.items():
                sp_entry = sp.get(str(d['available_from_station']), {}).get(str(task['origin']))
                if sp_entry is None:
                    no_path_count += 1
                    continue
                travel_min = (sp_entry['weight'] / 1000.0) / CREW_SPEED_KMH * 60.0
                gap = task['departure'] - (d['available_at_time'] + travel_min)
                if best_gap is None or gap > best_gap:
                    best_gap = gap
            if best_gap is None:
                print(f"  task={tid} origin={task['origin']} dep={task['departure']} → NO PATH from any driver ({no_path_count} drivers)")
            elif best_gap < 0:
                print(f"  task={tid} origin={task['origin']} dep={task['departure']} → TIMING: best_gap={best_gap:.0f}min (all drivers arrive too late)")
            else:
                print(f"  task={tid} origin={task['origin']} dep={task['departure']} → REACHABLE but unassigned: best_gap={best_gap:.0f}min (duty/break constraint?)")

    #
    #   if method == 'calculateInitialSolution_deadhead':
    #    from DeadheadAudit import audit_deadhead_solution, print_duties
    #    print_duties(existing_duties)
    #    audit_deadhead_solution(existing_duties, sp, crew_speed_kmh=60.0,
    #                            network=network, disrupted_section_ids=disrupted_section_ids,
    #                            disruption_start=disruption_start, disruption_end=disruption_end)

    os.makedirs(OUTPUT_CREW_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_CREW_DIR, f"{instance_id}.json"), 'w') as f:
        json.dump({str(k): v for k, v in existing_duties.items()}, f, indent=2)

    result = {
        'instance_id':        instance_id,
        'rs_method':          rs_method,
        'crew_method':        method,
        'rs_trips_total':     len(rs_solution),
        'rs_covered':         rs_covered,
        'rs_canceled':        rs_canceled,
        'id_mapping_entries': len(id_mapping),
        'crew_duties':        len(existing_duties),
        'crew_uncovered':     len(uncovered_tasks),
        'crew_dh_km':         round(crew_dh_km, 2),
        'crew_time_sec':      crew_time_sec,
        'vns_method':         vns_method or '',
        'vns_uncovered':      '',
        'vns_deadheading':    '',
        'vns_breaks_violated':'',
        'vns_time_sec':       '',
    }

    # Step 5: VNS (optional)
    if vns_method is not None:
        locomotives = {t['locomotive'] for t in id_mapping.values()}
        network_for_vns = {**network, 'sections': {s['id']: s for s in network['sections']}}
        _, _, vns_metrics = run_VNS(
            vns_method, original_schedule, existing_duties, duty_breaks_crew, uncovered_tasks,
            open_tasks, 0, 0, id_mapping, disruption_start, disruption_end,
            window_size, runs_per_window, network_for_vns, locomotives, suitable_tasks,
            max_dh_duration, rand_iter, spare_duty_id_list
        )
        print(f"[VNS/{vns_method}] uncovered={vns_metrics['nr_uncovered_tasks']}, deadheading={vns_metrics['deadheading_costs']:.1f}, breaks_violated={vns_metrics['nr_breaks_violated']}, time={vns_metrics['total_time_seconds']:.1f}s")
        result.update({
            'vns_uncovered':       vns_metrics['nr_uncovered_tasks'],
            'vns_deadheading':     vns_metrics['deadheading_costs'],
            'vns_breaks_violated': vns_metrics['nr_breaks_violated'],
            'vns_time_sec':        round(vns_metrics['total_time_seconds'], 2),
        })

    return result


CSV_COLUMNS = ['instance_id', 'rs_method', 'crew_method', 'rs_trips_total', 'rs_covered',
               'rs_canceled', 'id_mapping_entries', 'crew_duties', 'crew_uncovered', 'crew_dh_km',
               'crew_time_sec', 'vns_method', 'vns_uncovered', 'vns_deadheading', 'vns_breaks_violated',
               'vns_time_sec']


def export_to_csv(results, output_path):
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    file_exists = os.path.isfile(output_path)
    with open(output_path, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction='ignore')
        if not file_exists:
            writer.writeheader()
        for r in results:
            if 'error' not in r:
                writer.writerow(r)
    print(f"[CSV] appended {len([r for r in results if 'error' not in r])} rows → {output_path}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--instances',   nargs='+', metavar='S01',
                        help='Instance IDs to run (default: all)')
    parser.add_argument('--rs-methods',  nargs='+', choices=list(RS_METHODS),
                        default=list(RS_METHODS), dest='rs_methods',
                        help=f'RS methods (default: all). Choices: {list(RS_METHODS)}')
    parser.add_argument('--crew-methods', nargs='+', choices=list(CREW_METHODS),
                        default=list(CREW_METHODS), dest='crew_methods',
                        help=f'Crew methods (default: all). Choices: {list(CREW_METHODS)}')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--vns-method', choices=VNS_METHODS, default=None, dest='vns_method',
                        help='VNS optimization method to run after greedy (default: skip VNS). Choices: DP, model')
    parser.add_argument('--window-size', type=int, default=120, dest='window_size',
                        help='VNS time window size in minutes (default: 120)')
    parser.add_argument('--runs-per-window', type=int, default=5, dest='runs_per_window',
                        help='VNS iterations per time window (default: 5)')
    parser.add_argument('--max-dh-duration', type=int, default=60, dest='max_dh_duration',
                        help='Max deadhead duration in minutes (default: 60)')
    parser.add_argument('--rand-iter', type=int, default=1, dest='rand_iter',
                        help='VNS random seed multiplier (default: 1)')
    parser.add_argument('--task-source', choices=['reader', 'inline'], default='reader', dest='task_source',
                        help='Task generation method (default: reader)')
    args = parser.parse_args()

    all_files    = sorted(glob.glob(os.path.join(INSTANCE_DIR, "S*.json")))
    all_ids      = [os.path.basename(f).replace('.json', '') for f in all_files if 'network' not in f]
    instance_ids = args.instances if args.instances else all_ids

    SEED = args.seed
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path  = f'test_greedy/results_{timestamp}.csv'

    header = f"{'Instance':<10} {'RS_Method':<18} {'Crew_Method':<32} {'RS_Total':>8} {'RS_Cov':>6} {'RS_Canc':>7} {'IDMap':>5} {'Duties':>6} {'Uncov':>5}"
    print(header)
    print('-' * len(header))

    all_results = []
    for iid in instance_ids:
        print(f"\n=== Instance: {iid} ===")
        for rs_method in args.rs_methods:
            for crew_method in args.crew_methods:
                try:
                    r = run_instance(iid, seed=SEED, rs_method=rs_method, method=crew_method,
                                     vns_method=args.vns_method, window_size=args.window_size,
                                     runs_per_window=args.runs_per_window, max_dh_duration=args.max_dh_duration,
                                     rand_iter=args.rand_iter, task_source=args.task_source)
                    all_results.append(r)
                    print(f"{r['instance_id']:<10} {r['rs_method']:<18} {r['crew_method']:<32} {r['rs_trips_total']:>8} {r['rs_covered']:>6} {r['rs_canceled']:>7} {r['id_mapping_entries']:>5} {r['crew_duties']:>6} {r['crew_uncovered']:>5}")
                except Exception as e:
                    all_results.append({'instance_id': iid, 'rs_method': rs_method, 'crew_method': crew_method, 'error': str(e)})
                    print(f"{iid:<10}  ERROR: {e}")
    export_to_csv(all_results, csv_path)
