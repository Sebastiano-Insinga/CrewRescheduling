"""
Compare Integrated Rescheduling (joint loco+crew, per trip) against the
Sequential baseline (RS greedy alone, then crew greedy alone), using the
"scored_greedy" (loco) + "calculateInitialSolution_deadhead" (crew) methods.

Reuses SequentialRescheduling.run_instance and IntegratedRescheduling.run_instance
without modifying either — only imports and post-processes their results into
one combined row per instance.
"""

import argparse
import contextlib
import csv
import glob
import io
import os
import time
from datetime import datetime

from RollingStockGreedy import count_canceled
import SequentialRescheduling as SR
import IntegratedRescheduling as IR
from SequentialRescheduling import (
    run_instance as run_sequential,
    INSTANCE_DIR, NETWORK_FILE, SHORTESTPATHS_FILE,
)
from IntegratedRescheduling import run_instance as run_integrated


COMBINED_CSV_COLUMNS = [
    'instance_id', 'seed',
    'seq_rs_canceled', 'seq_crew_uncovered', 'seq_cancel_total', 'int_n_cancel',
    'seq_setup_time_sec', 'seq_rs_time_sec', 'seq_crew_prep_time_sec', 'seq_crew_time_sec',
    'seq_solve_time_sec', 'seq_total_time_sec',
    'int_setup_time_sec', 'int_solve_time_sec', 'int_metrics_time_sec', 'int_time_sec',
    'seq_crew_dh_km', 'seq_loco_dh_m', 'int_loco_dh_m', 'int_crew_dh_m', 'int_total_dh_m',
    'error_sequential', 'error_integrated',
]


def compute_sequential_loco_dh_m(rs_solution, instance, network, sp) -> float:
    """
    Ex-post locomotive deadhead for a Sequential rs_solution (scored_greedy
    output), mirroring IntegratedRescheduling.py's loco_dh_m computation:
    same sp_raw-meters convention, applied to the gaps between consecutive
    trips assigned to the same locomotive.

    Kept isolated here (not in RollingStockGreedy.py) since it's a derived
    comparison metric, easy to drop if the resulting numbers are out of scale.
    """
    sections_by_id = {s['id']: s for s in network['sections']}
    trips_by_id = {t['id']: t for t in instance['train_sections']}

    loco_trips = {}
    for entry in rs_solution:
        if entry['locomotive'] == 'canceled':
            continue
        loco_trips.setdefault(entry['locomotive'], []).append(entry)

    total_m = 0.0
    for _, entries in loco_trips.items():
        sorted_entries = sorted(entries, key=lambda e: trips_by_id[e['id_trip']]['departure_time'])
        prev_dest = None
        for entry in sorted_entries:
            trip = trips_by_id[entry['id_trip']]
            sec = sections_by_id[trip['section']]
            origin, dest = sec['origin'], sec['destination']
            if origin == dest:
                prev_dest = dest
                continue
            if prev_dest is not None and prev_dest != origin:
                sp_entry = sp.get(str(prev_dest), {}).get(str(origin))
                if sp_entry is not None:
                    total_m += sp_entry['weight']
            prev_dest = dest
    return total_m


def run_sequential_with_rs_time(instance_id, seed=42) -> dict:
    """
    Sequential con tempi per fase. Il greedy RS gira una volta sola, dentro
    run_instance: il deadhead locomotive si calcola dopo, sulla soluzione che
    run_instance restituisce, perche' e' una metrica ex-post e non deve entrare
    nel tempo di calcolo (nessuna funzione obiettivo lo usa).
    """
    seq_result = run_sequential(
        instance_id, seed=seed,
        rs_method='scored_greedy',
        method='calculateInitialSolution_deadhead',
    )

    seq_result['seq_total_time_sec'] = round(
        seq_result['setup_time_sec'] + seq_result['rs_time_sec']
        + seq_result['crew_prep_time_sec'] + seq_result['crew_time_sec'], 3)

    loco_dh_m = compute_sequential_loco_dh_m(
        seq_result['_rs_solution'], seq_result['_instance'],
        seq_result['_network'], seq_result['_sp'])
    seq_result['loco_dh_m'] = round(loco_dh_m, 1)
    return seq_result


def run_integrated_timed(instance_id, seed=42) -> dict:
    t0 = time.time()
    r = run_integrated(instance_id, seed=seed)
    elapsed = round(time.time() - t0, 3)
    t = r.timings
    return {
        'total_trip': len(r.solution),
        'n_cancel': count_canceled(r.solution),
        'loco_dh_m': r.dh_stats['loco_dh_m'],
        'crew_dh_m': r.dh_stats['crew_dh_m'],
        'total_dh_m': r.dh_stats['loco_dh_m'] + r.dh_stats['crew_dh_m'],
        'setup_time_sec': t['setup_sec'],
        'solve_time_sec': t['solve_sec'],
        'metrics_time_sec': t['metrics_sec'],
        'time_sec': elapsed,
    }


def compare_instance(instance_id, seed=42) -> dict:
    row = {'instance_id': instance_id, 'seed': seed}

    seq = None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            seq = run_sequential_with_rs_time(instance_id, seed=seed)
    except Exception as e:
        row['error_sequential'] = str(e)

    integ = None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            integ = run_integrated_timed(instance_id, seed=seed)
    except Exception as e:
        row['error_integrated'] = str(e)

    if seq is not None:
        row.update({
            'seq_rs_canceled': seq['rs_canceled'],
            'seq_crew_uncovered': seq['crew_uncovered'],
            'seq_cancel_total': seq['rs_canceled'] + seq['crew_uncovered'],
            'seq_setup_time_sec': seq['setup_time_sec'],
            'seq_rs_time_sec': seq['rs_time_sec'],
            'seq_crew_prep_time_sec': seq['crew_prep_time_sec'],
            'seq_crew_time_sec': seq['crew_time_sec'],
            'seq_solve_time_sec': seq['solve_time_sec'],
            'seq_total_time_sec': seq['seq_total_time_sec'],
            'seq_crew_dh_km': seq['crew_dh_km'],
            'seq_loco_dh_m': seq['loco_dh_m'],
        })
    if integ is not None:
        row.update({
            'int_n_cancel': integ['n_cancel'],
            'int_setup_time_sec': integ['setup_time_sec'],
            'int_solve_time_sec': integ['solve_time_sec'],
            'int_metrics_time_sec': integ['metrics_time_sec'],
            'int_time_sec': integ['time_sec'],
            'int_loco_dh_m': integ['loco_dh_m'],
            'int_crew_dh_m': integ['crew_dh_m'],
            'int_total_dh_m': integ['total_dh_m'],
        })
    return row


def export_to_csv(rows, output_path):
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    file_exists = os.path.isfile(output_path)
    with open(output_path, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=COMBINED_CSV_COLUMNS, extrasaction='ignore')
        if not file_exists:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', nargs='+', metavar='S01',
                         help='Instance IDs to run (default: all S*.json in single_type/)')
    parser.add_argument('-s', type=int, default=42)
    parser.add_argument('--instance-dir', default=INSTANCE_DIR, dest='instance_dir',
                        help=f'Directory of the S*.json instances (default: {INSTANCE_DIR})')
    parser.add_argument('--crew-schedule-dir', default=SR.CREW_SCHEDULE_DIR, dest='crew_schedule_dir',
                        help=f'Directory of the Transformed-{{id}}_sol.txt files (default: {SR.CREW_SCHEDULE_DIR})')
    parser.add_argument('--crew-task-dir', default=SR.CREW_TASK_DIR, dest='crew_task_dir',
                        help=f'Directory of the Transformed-{{id}}.tsv files (default: {SR.CREW_TASK_DIR})')
    parser.add_argument('--id-mapping-dir', default=SR.ID_MAPPING_DIR, dest='id_mapping_dir',
                        help=f'Directory of the ID-Mapping-Transformed-{{id}}.tsv files (default: {SR.ID_MAPPING_DIR})')
    parser.add_argument('-o', '--out', dest='out',
                        help='CSV di output (default: comparison_results/sequential_vs_integrated_<timestamp>.csv)')
    args = parser.parse_args()

    # I tre file della pipeline sono vincolati fra loro: gli id dei task hanno
    # senso solo dentro la conversione che li ha prodotti. Mescolare directory
    # di run diverse non da' errore, da' risultati sbagliati in silenzio.
    #
    # run_instance rilegge queste globali dal proprio modulo (SequentialRescheduling
    # righe 152-154, IntegratedRescheduling righe 543-545), quindi vanno impostate
    # li'. Riassegnare i nomi importati qui sopra non basterebbe: "from ... import"
    # ne crea copie locali, scollegate dal modulo di origine.
    INSTANCE_DIR = args.instance_dir
    NETWORK_FILE = os.path.join(INSTANCE_DIR, "network.json")
    SHORTESTPATHS_FILE = os.path.join(INSTANCE_DIR, "network-shortestpaths.json")

    for mod in (SR, IR):
        mod.INSTANCE_DIR = INSTANCE_DIR
        mod.NETWORK_FILE = NETWORK_FILE
        mod.SHORTESTPATHS_FILE = SHORTESTPATHS_FILE
        mod.CREW_SCHEDULE_DIR = args.crew_schedule_dir
        mod.CREW_TASK_DIR = args.crew_task_dir
        mod.ID_MAPPING_DIR = args.id_mapping_dir

    if args.i:
        instance_ids = args.i
    else:
        all_files = sorted(glob.glob(os.path.join(INSTANCE_DIR, "S*.json")))
        instance_ids = [
            os.path.basename(f).replace('.json', '')
            for f in all_files if 'network' not in f
        ]

    if args.out:
        csv_path = args.out
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = os.path.join('comparison_results', f'sequential_vs_integrated_{timestamp}.csv')

    header = (f"{'Instance':<10} {'Seq_Canc':>9} {'Int_Canc':>9} "
              f"{'Seq_Time':>9} {'Int_Time':>9} {'Seq_LocoDH_m':>13} {'Int_LocoDH_m':>13}")
    print(header, flush=True)
    print('-' * len(header), flush=True)

    rows = []
    for iid in instance_ids:
        print(f"{iid:<10} running...", flush=True)
        row = compare_instance(iid, seed=args.s)
        rows.append(row)
        export_to_csv([row], csv_path)
        print(f"{iid:<10} "
              f"{row.get('seq_cancel_total', 'ERR'):>9} "
              f"{row.get('int_n_cancel', 'ERR'):>9} "
              f"{row.get('seq_total_time_sec', 'ERR'):>9} "
              f"{row.get('int_time_sec', 'ERR'):>9} "
              f"{row.get('seq_loco_dh_m', 'ERR'):>13} "
              f"{row.get('int_loco_dh_m', 'ERR'):>13}", flush=True)

    print(f"\nWritten: {csv_path}")
