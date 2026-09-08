"""
Export the driver state at the start of the disruption as JSON.

For each duty (= driver) of the pre-disruption crew schedule it writes the
station the driver becomes available at, the time it becomes available and
whether the mandatory break was already taken before the disruption.

The state is the one consumed by SequentialRescheduling / IntegratedRescheduling,
i.e. the driver_status produced by ReschedulingPreprocessor.generateReschedulingInput.

Times are in minutes from the baseline day 2018-09-10 (display time format 3),
consistent with the transformed instance TSV files.

Usage:
    python export_driver_status.py                      # all instances
    python export_driver_status.py --instances S01 S03
    python export_driver_status.py --instances S01 --out-dir DriverStatus
"""

import argparse
import glob
import json
import os

from DriverStatusMapper import DriverStatusMapper
from ReschedulingPreprocessor import readDisruption

INSTANCE_DIR      = os.path.join("Instances", "single_type")
CREW_SCHEDULE_DIR = "results_twan_txt"
CREW_TASK_DIR     = "Final_Rescheduled_Instances"
ID_MAPPING_DIR    = "Final_Rescheduled_ID_Mappings"
#NB: not "driver_status" - that folder already holds the feasible-driver debug CSVs
OUTPUT_DIR        = "DriverStatus"


def instance_files(instance_id):
    return {
        'instance_file':      os.path.join(INSTANCE_DIR, f"{instance_id}.json"),
        'crew_schedule_file': os.path.join(CREW_SCHEDULE_DIR, f"Transformed-{instance_id}_sol.txt"),
        'crew_task_file':     os.path.join(CREW_TASK_DIR, f"Transformed-{instance_id}.tsv"),
        'id_mapping_file':    os.path.join(ID_MAPPING_DIR, f"ID-Mapping-Transformed-{instance_id}.tsv"),
    }


def build_driver_status_json(instance_id):
    files = instance_files(instance_id)

    for f in files.values():
        if not os.path.exists(f):
            raise FileNotFoundError(f"Missing input file: {f}")

    disruption_start, disruption_end, disrupted_sections = readDisruption(files['instance_file'])

    mapper = DriverStatusMapper(files['crew_schedule_file'],
                                files['crew_task_file'],
                                files['id_mapping_file'],
                                files['instance_file'])

    drivers = []
    for duty_id, status in sorted(mapper.driver_status.items()):
        drivers.append({
            'duty_id':      duty_id,
            'station':      status['available_from_station'],
            'available_at': status['available_at_time'],
            'break30done':  status['break30done'],
            'break45done':  status['break45done'],
            'duty_length':  status['duty_length'],
        })

    return {
        'instance':             instance_id,
        'time_format':          'minutes from 2018-09-10',
        'disruption_start':     disruption_start,
        'disruption_end':       disruption_end,
        #the full list of disrupted section ids is already in Instances/single_type/<instance>.json
        'n_disrupted_sections': len(disrupted_sections),
        'n_duties_total':       len(mapper.original_schedule),
        'n_drivers':            len(drivers),
        'drivers':              drivers,
    }


def export_instance(instance_id, out_dir):
    data = build_driver_status_json(instance_id)

    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, f"{instance_id}_driver_status.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print(f"[DriverStatus] {data['n_drivers']} drivers "
          f"(of {data['n_duties_total']} duties) → {output_path}")
    return output_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Export the driver state at the start of the disruption as JSON.")
    parser.add_argument('--instances', nargs='+', metavar='S01',
                        help='Instance IDs to export (default: all S*.json in Instances/single_type/)')
    parser.add_argument('--out-dir', default=OUTPUT_DIR, dest='out_dir',
                        help=f'Output directory (default: {OUTPUT_DIR})')
    args = parser.parse_args()

    if args.instances:
        instance_ids = args.instances
    else:
        all_files    = sorted(glob.glob(os.path.join(INSTANCE_DIR, "S*.json")))
        instance_ids = [os.path.basename(f).replace('.json', '') for f in all_files
                        if 'network' not in f]

    for iid in instance_ids:
        print(f"\n=== Instance: {iid} ===")
        try:
            export_instance(iid, args.out_dir)
        except Exception as e:
            print(f"ERROR on {iid}: {e}")
