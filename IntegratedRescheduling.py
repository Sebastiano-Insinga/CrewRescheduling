from __future__ import annotations

import csv
import glob
import math
import os
from dataclasses import dataclass
from datetime import datetime

from RollingStockGreedy import load_data, CppMT19937, count_canceled, get_deadhead_info
from VNS_Rescheduling import _required_break_length

from RailwayNetwork import RailwayNetwork
from DriverStatusMapper import DriverStatusMapper
from LocoChecker import LocoChecker
from TaskFeasibilityChecker import TaskFeasibilityChecker
from CrewState import CrewState
from DebugExport import (export_task_list, export_feasible_drivers,
                          export_loco_driver_selection, export_loco_sequence)

INSTANCE_DIR       = "single_type"
NETWORK_FILE       = os.path.join(INSTANCE_DIR, "network.json")
SHORTESTPATHS_FILE = os.path.join(INSTANCE_DIR, "network-shortestpaths.json")
CREW_SCHEDULE_DIR  = "results_twan_txt"
CREW_TASK_DIR      = "Final_Rescheduled_Instances"
ID_MAPPING_DIR     = "Final_Rescheduled_ID_Mappings"

BASELINE_DAY = datetime(2018, 9, 10)

CSV_COLUMNS = ['instance_id', 'total_trip', 'n_cancel',
               'total_deadhead_length [m]', 'computation_time [s]']


@dataclass
class SolveResult:
    solution:        list
    existing_duties: dict
    duty_breaks:     dict
    loco_duties:     dict
    canceled_tasks:  list
    all_candidates:  dict
    dh_stats:        dict
    forced_failures: list



def epoch_to_minutes(epoch_seconds: float) -> int:
    dt   = datetime.fromtimestamp(epoch_seconds)
    diff = dt - BASELINE_DAY
    return diff.days * 1440 + math.ceil(dt.hour * 60 + dt.minute + dt.second / 60.0)


def loco_duties_from_excel(excel_path: str, instance_id: str = None) -> tuple:
    """Read an Excel solution file (trips + summary sheets) and build loco_duties
    in the format expected by plot_loco_crew_gantt.

    Returns (loco_duties, metrics, disruption_start_min).
    disruption_start_min is loaded from the instance JSON when instance_id is given
    (aligns the time axis with other Gantt charts); falls back to 0.
    Rows with NaN departure (dh_start_* entries) use arrival as departure.
    Rows with NaN crew are assigned driver id 'unknown'.
    """
    import json as _json
    import pandas as pd

    xl = pd.ExcelFile(excel_path)
    df = xl.parse('trips')

    disruption_start_min = 0
    disruption_end_min   = None
    if instance_id:
        inst_path = os.path.join(INSTANCE_DIR, f"{instance_id}.json")
        try:
            with open(inst_path) as f:
                inst = _json.load(f)
            disruption_start_min = epoch_to_minutes(inst['disruption_start'])
            disruption_end_min   = epoch_to_minutes(inst['disruption_end'])
        except (FileNotFoundError, KeyError):
            pass

    loco_duties: dict = {}
    for _, row in df.iterrows():
        arr_unix = row['Arrival Time (unix)']
        if pd.isna(arr_unix):
            continue

        dep_unix = row['Departure Time (unix)']
        arr = epoch_to_minutes(arr_unix)
        dep = epoch_to_minutes(dep_unix) if not pd.isna(dep_unix) else arr

        loco_id   = int(row['Locomotive'])
        origin    = int(row['Origin Station ID'])
        dest      = int(row['Destination Station ID'])
        crew = row['Crew Member']
        if pd.isna(crew):
            continue
        driver_id = str(crew)

        if row['Trip Type'] == 'productive':
            try:
                rs_trip_id = int(row['Trip ID'])
            except (ValueError, TypeError):
                rs_trip_id = str(row['Trip ID'])
            task_type = 'trip'
        else:
            rs_trip_id = None
            task_type  = 'loco_deadhead'

        task = {
            'type':        task_type,
            'origin':      origin,
            'destination': dest,
            'departure':   dep,
            'arrival':     arr,
            'rs_trip_id':  rs_trip_id,
        }
        loco_duties.setdefault(loco_id, []).append((task, driver_id))

    for loco_id in loco_duties:
        loco_duties[loco_id].sort(key=lambda x: x[0]['departure'])

    metrics = None
    if 'summary' in xl.sheet_names:
        sm = xl.parse('summary').set_index('metric')['value'].to_dict()
        n_prod   = int(sm.get('n_productive_total', sm.get('n_productive', 0)))
        n_canc   = int(sm.get('n_canceled', 0))
        metrics  = {
            'total_trips':   n_prod,
            'cancellations': n_canc,
        }
        if disruption_end_min is not None:
            metrics['disruption_start_min'] = disruption_start_min
            metrics['disruption_end_min']   = disruption_end_min

    return loco_duties, metrics, disruption_start_min


def deadhead_priority_pool(dh_by_key: dict, original_keys) -> dict:
    """Tiered candidate pool mirroring the selection rule of VNS
    calculateInitialSolution_deadhead. dh_by_key: {key: deadhead_minutes}.
    Tiers: originally-assigned with dh==0 → originally-assigned → all."""
    original = {k: dh for k, dh in dh_by_key.items() if k in original_keys}
    return ({k: dh for k, dh in original.items() if dh == 0}
            or original
            or dh_by_key)




class IntegratedRescheduler:
    """
    Joint RS + Crew rescheduling loop.

    For each trip finds all (loco, driver_chain) pairs that are simultaneously
    feasible, selects one via CppMT19937, and commits both assignments.
    """
    FORCED_ALTERNATIVE = object()

    def __init__(
        self,
        checker_loco: LocoChecker,
        checker_crew: TaskFeasibilityChecker,
        mapper:       DriverStatusMapper,
        net:          RailwayNetwork,
        max_time_without_break: int = 360,
    ):
        self._checker_loco         = checker_loco
        self._checker_crew         = checker_crew
        self._mapper               = mapper
        self._net                  = net
        self._max_time_without_break = max_time_without_break

        # RS trip_id → crew task_id (regular tasks only)
        self._trip_to_task_id: dict[int, int] = {
            v['train_section']: k
            for k, v in mapper.id_mapping.items()
            if v.get('task_type') == 'regular'
        }
    def resolve_forced(self, forced, trip_id, locos, crew_state, rng, is_first ):
        entry=forced[trip_id]
        fail_stats={}
        failed = False
        
        if entry is not self.FORCED_ALTERNATIVE and is_first:
            pairs = [entry]
        else:
            pairs = []
            new_pairs, fail_stats = self._candidate_pairs(trip_id, locos, crew_state, rng)
            alternatives = new_pairs[1:]
            if alternatives:
                pairs= [alternatives[rng.uniform_int(0, len(alternatives)-1)]]
                print(f"Pairs found for {trip_id}: {pairs}")
            else:
                print(f"Failed shake on {trip_id}")
                failed = True

                                              
        return pairs, fail_stats, failed

    def run(self, seed: int = 42, forced: dict = None) -> tuple[list, dict, dict, dict]:
        """
        Returns (solution, existing_duties, duty_breaks, loco_duties, canceled_tasks, all_candidates).
        loco_duties: {loco_id: [(task, driver_id), ...]} — trips + loco_deadheads only.
        canceled_tasks: list of trip task dicts (with 'rs_trip_id' and 'cancel_stats')
        for trips that found no feasible (loco, driver_chain) pair.
        forced: {trip_id: pair} — pair from a previous all_candidates to force instead of searching.
        all_candidates: {trip_id: [pairs]} — all feasible pairs found per trip.
        """
        rng        = CppMT19937(seed)
        crew_state = CrewState(self._mapper.driver_status)
        task_id    = [1]
        solution   = []
        loco_duties = {}
        canceled_tasks = []
        all_candidates = {}
        forced = forced or {}
        seen_forced = False       
        forced_failures = []     

        for trip_id in self._checker_loco.trip_order:
            locos = self._checker_loco.candidates(trip_id)
            if trip_id in forced:
                pairs, fail_stats,failed = self.resolve_forced(forced,trip_id, locos, crew_state, rng, is_first = not seen_forced)
                seen_forced= True
                if failed:
                    forced_failures.append(trip_id)
            else:
                pairs, fail_stats = self._candidate_pairs(trip_id, locos, crew_state, rng)
            all_candidates[trip_id] = pairs

            if not pairs:
                solution.append(self._canceled(trip_id))
                ct = dict(self._checker_loco.trip_task(trip_id))
                ct['rs_trip_id']   = trip_id
                ct['cancel_stats'] = fail_stats
                canceled_tasks.append(ct)
                continue

            #chosen = pairs[rng.uniform_int(0, len(pairs) - 1)]
            chosen=pairs[0]
            # Commit loco
            maint = self._checker_loco.commit(trip_id, chosen['loco'])
            solution.append({
                'id_trip':    trip_id,
                'locomotive': chosen['loco'],
                'maintenance_at_departure':   'true' if maint['at_departure']   else 'false',
                'maintenance_at_destination': 'true' if maint['at_destination'] else 'false',
            })

            # Commit crew — re-apply chosen chain to crew_state
            for task, driver_id in chosen['driver_chain']:
                t_tagged = dict(task)
                if task.get('type') == 'trip':
                    t_tagged['rs_trip_id'] = trip_id
                loco_duties.setdefault(chosen['loco'], []).append((t_tagged, driver_id))
                t = dict(task)
                t['id'] = task_id[0]
                task_id[0] += 1
                crew_state.apply_task(driver_id, t)

        existing_duties = {d: crew_state.tasks(d)
                           for d in crew_state.driver_ids()
                           if crew_state.tasks(d)}
        duty_breaks     = self._plan_breaks(existing_duties)

        changed=True
        while changed:
            changed=False
            still_canceled=[]
            for ct in canceled_tasks:
                trip_id=ct["rs_trip_id"]
                locos=self._checker_loco.candidates(trip_id)
                pairs,_=self._candidate_pairs(trip_id, locos, crew_state, rng)
                if pairs:
                            chosen=pairs[0]
                            maint = self._checker_loco.commit(trip_id, chosen['loco'])
                            solution.append({
                                'id_trip':    trip_id,
                                'locomotive': chosen['loco'],
                                'maintenance_at_departure':   'true' if maint['at_departure']   else 'false',
                                'maintenance_at_destination': 'true' if maint['at_destination'] else 'false',
                            })
                            changed=True
                            # Commit crew — re-apply chosen chain to crew_state
                            for task, driver_id in chosen['driver_chain']:
                                t_tagged = dict(task)
                                if task.get('type') == 'trip':
                                    t_tagged['rs_trip_id'] = trip_id
                                loco_duties.setdefault(chosen['loco'], []).append((t_tagged, driver_id))
                                t = dict(task)
                                t['id'] = task_id[0]
                                task_id[0] += 1
                                crew_state.apply_task(driver_id, t)
                else:
                    still_canceled.append(ct)
            canceled_tasks=still_canceled
        existing_duties = {d: crew_state.tasks(d)
                                        for d in crew_state.driver_ids()
                                        if crew_state.tasks(d)}     
        duty_breaks     = self._plan_breaks(existing_duties)
        print(f"Rescue pass: canceled residui = {len(canceled_tasks)}")

        return solution, existing_duties, duty_breaks, loco_duties, canceled_tasks, all_candidates, forced_failures

 
    # ------------------------------------------------------------------
    # Candidate pair search
    # ------------------------------------------------------------------

    def _candidate_pairs(self, trip_id: int, locos: list,
                         crew_state: CrewState, rng: CppMT19937) -> list[dict]:
        """
        For each candidate loco, try to find a driver chain covering all tasks
        (deadhead segments + trip task). Returns (pairs, fail_stats) where
        pairs is a list of {'loco', 'driver_chain'} and fail_stats counts why
        candidate locos were rejected. crew_state is fully restored on return.
        """
        trip_task = self._checker_loco.trip_task(trip_id)

        pairs = []
        fail_stats = {'n_candidates': len(locos), 'unreachable': 0, 'no_chain': 0}
        for loco_id in locos:
            dh_tasks  = self._checker_loco.deadhead_tasks(
                loco_id, trip_id, epoch_to_minutes, self._max_time_without_break
            )
            if dh_tasks is None:  # loco cannot reach trip — candidates() should have excluded it
                fail_stats['unreachable'] += 1
                continue
            task_list = dh_tasks + [trip_task]
            if trip_id == 23319:
                export_task_list(task_list, trip_id, loco_id)

            snap  = crew_state.snapshot()
            debug_lid = loco_id if loco_id == 22550 else None
            chain,n_feasible = self._find_driver_chain(task_list, trip_id, crew_state, rng,
                                             debug_loco_id=debug_lid, loco_id=loco_id)
            crew_state.restore(snap)

            if chain is not None:
                pairs.append({
                    'loco':         loco_id,
                    'driver_chain': chain,
                    'n_feasible':   n_feasible,
                    'drivers':      list({driver_id for _, driver_id in chain}),
                })
            else:
                fail_stats['no_chain'] += 1
            pairs.sort(key=lambda p:p['n_feasible'])

        return pairs, fail_stats

    def _find_driver_chain(self, task_list: list, trip_id: int,
                            crew_state: CrewState, rng: CppMT19937,
                            debug_loco_id: int = None,
                            loco_id: int = None) -> list | None:
        """
        Assign a driver to each task in task_list.
        Modifies crew_state tentatively — caller restores if pair not chosen.
        Returns list[(task, driver_id)] or None if any task is uncoverable.
        """
        chain   = []
        applied = []

        for task_idx, task in enumerate(task_list):
            tid      = self._trip_to_task_id.get(trip_id) if task.get('type') == 'trip' else None
            # Idle gap after this task, before the next one in the chain: also
            # a valid break slot for the driver who covers only this task.
            if task.get('type') == 'loco_deadhead' and task_idx + 1 < len(task_list):
                next_gap = task_list[task_idx + 1]['departure'] - task['arrival']
            else:
                next_gap = None
            feasible = {}  # driver_id -> deadhead minutes, in driver_status order
            for d_id in self._mapper.driver_status:
                ok, dh, _ = self._checker_crew.evaluate(
                    task, tid, d_id,
                    crew_state.station(d_id),
                    crew_state.available_at(d_id),
                    crew_state.first_departure(d_id),
                    crew_state.tasks(d_id),
                    next_gap_minutes=next_gap,
                )
                if ok:
                    feasible[d_id] = dh
            export_feasible_drivers(list(feasible), trip_id, crew_state, task, task_idx, loco_id)
            if not feasible:
                for d_id, prev in reversed(applied):
                    crew_state.restore_driver(d_id, prev)
                return None, 0

            driver_id = self._select_driver(feasible, task, tid, rng)
            if debug_loco_id is not None:
                export_loco_driver_selection(trip_id, debug_loco_id, task, list(feasible), driver_id, crew_state)
            applied.append((driver_id, crew_state.snapshot_driver(driver_id)))
            crew_state.apply_task(driver_id, task)
            chain.append((task, driver_id))
        n_feasible=len(feasible)

        return chain, n_feasible

    def _select_driver(self, feasible: dict, task: dict, tid: int | None,
                       rng: CppMT19937) -> int:
        """VNS-aligned tiers via deadhead_priority_pool:
        original driver with dh==0 → original driver → random among all feasible.
        feasible: {driver_id: deadhead_minutes}.
        Original match by task id (tid) when available, else by
        (origin, destination, departure) fields."""
        orig_sched = self._mapper.original_schedule
        original_keys = set()
        for d_id in feasible:
            for orig in orig_sched.get(d_id, []):
                if (tid is not None and orig.get('id') == tid) or (
                        orig.get('origin')      == task.get('origin') and
                        orig.get('destination') == task.get('destination') and
                        orig.get('departure')   == task.get('departure')):
                    original_keys.add(d_id)
                    break
        pool = deadhead_priority_pool(feasible, original_keys)
        if original_keys:  # pool is an original tier: deterministic min-dh
            return min(pool, key=lambda d: pool[d])
        keys = list(pool)
        return keys[rng.uniform_int(0, len(keys) - 1)]

    # ------------------------------------------------------------------
    # Break planning (Phase 3)
    # ------------------------------------------------------------------

    def _plan_breaks(self, existing_duties: dict) -> dict:
        ds = self._mapper.driver_status
        duty_breaks = {}
        for duty_id, duty in existing_duties.items():
            if not duty:
                duty_breaks[duty_id] = (-45, 0)
                continue
            duty_length = duty[-1]['arrival'] - duty[0]['departure']
            b30 = ds[duty_id]['break30done']
            b45 = ds[duty_id]['break45done']
            base = _required_break_length(duty_length)
            if b45 or (b30 and duty_length <= 480):
                required = 0
            elif b30:
                required = max(0, base - 30)
            else:
                required = base
            if required == 0:
                duty_breaks[duty_id] = (-45, 0)
                continue
            slot = next(
                ((a['arrival'], a['arrival'] + required)
                 for a, b in zip(duty, duty[1:])
                 if b['departure'] - a['arrival'] >= required),
                None,
            )
            if slot is None:
                # No gap between recorded tasks — the break falls in the idle
                # time after the duty's last task, which isn't represented as
                # a task here. Matches the lookahead accepted in
                # TaskFeasibilityChecker.evaluate() via next_gap_minutes.
                last_arrival = duty[-1]['arrival']
                slot = (last_arrival, last_arrival + required)
            duty_breaks[duty_id] = slot
        return duty_breaks

    @staticmethod
    def _canceled(trip_id: int) -> dict:
        return {'id_trip': trip_id, 'locomotive': 'canceled',
                'maintenance_at_departure': 'false',
                'maintenance_at_destination': 'false'}



            


def check_deadhead(canceled_tasks, existing_duties, net):
    seen = set()
    deadhead_couple = []
    for ct in canceled_tasks:
        ct_origin = ct["origin"]
        ct_dep = ct["departure"]
        for tasks in existing_duties.values():
            for t in tasks:
                s_dest = t["destination"]
                if t["arrival"] > ct_dep:
                    continue
                key = (ct["rs_trip_id"], s_dest, ct_origin)
                if key in seen:
                    continue
                seen.add(key)
                dh_min = net.deadhead_minutes(s_dest, ct_origin, t["arrival"], ct_dep, 57.0)
                if dh_min == float('inf'):
                    continue
                entry = net.sp_raw.get(str(s_dest), {}).get(str(ct_origin))
                if entry:
                    deadhead_couple.append({
                        "canceled_trip": ct["rs_trip_id"],
                        "from_station":  s_dest,
                        "to_station":    ct_origin,
                        "dh_meters":     entry["weight"] / 1000,
                    })
    out_dir = os.path.join('IntegratedRescheduling', 'deadhead_couple')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'deadhead_couples.csv')

    with open(out_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['canceled_trip', 'from_station', 'to_station', 'dh_meters'])
        writer.writeheader()
        writer.writerows(deadhead_couple)
    return deadhead_couple

def setup_instance(instance_id: str) -> tuple:
    instance_file      = os.path.join(INSTANCE_DIR,      f"{instance_id}.json")
    crew_schedule_file = os.path.join(CREW_SCHEDULE_DIR, f"Transformed-{instance_id}_sol.txt")
    crew_task_file     = os.path.join(CREW_TASK_DIR,     f"Transformed-{instance_id}.tsv")
    id_mapping_file    = os.path.join(ID_MAPPING_DIR,    f"ID-Mapping-Transformed-{instance_id}.tsv")

    for f in [instance_file, crew_schedule_file, crew_task_file, id_mapping_file]:
        if not os.path.exists(f):
            raise FileNotFoundError(f"Missing: {f}")

    instance, _, _ = load_data(instance_file, NETWORK_FILE, SHORTESTPATHS_FILE)
    disruption_start = epoch_to_minutes(instance['disruption_start'])
    disruption_end   = epoch_to_minutes(instance['disruption_end'])

    net = RailwayNetwork(NETWORK_FILE, SHORTESTPATHS_FILE)
    net.build_for_instance(instance, disruption_start, disruption_end)

    mapper = DriverStatusMapper(crew_schedule_file, crew_task_file,
                                id_mapping_file, instance_file)
    export_status_driver(mapper)
    return instance, mapper, net, disruption_start, disruption_end


def solve_instance(instance, mapper, net, disruption_start, disruption_end,
                   seed: int = 42, forced: dict = None):
    checker_loco = LocoChecker(instance, net)
    checker_crew = TaskFeasibilityChecker(net, mapper, max_duty_length=720)

    rescheduler = IntegratedRescheduler(checker_loco, checker_crew, mapper, net)

    solution, existing_duties, duty_breaks, loco_duties, canceled_tasks, all_candidates, forced_failures = rescheduler.run(
        seed=seed, forced=forced)
    
    check_deadhead(canceled_tasks, existing_duties, net)

    no_slot = [d for d, s in duty_breaks.items() if s is None]
    print(f"[BreakCheck] duties with no feasible break slot: {len(no_slot)}/{len(duty_breaks)} — {no_slot}")

    rs_canceled = count_canceled(solution)
    rs_covered  = len(solution) - rs_canceled
    print(f"[IntegratedRescheduler] trips={len(solution)} covered={rs_covered} "
          f"canceled={rs_canceled} duties={len(existing_duties)}")

    loco_dh_m = sum(
        net.sp_raw.get(str(task['origin']), {}).get(str(task['destination']), {}).get('weight', 0)
        for segs in loco_duties.values()
        for task, _ in segs
        if task.get('type') == 'loco_deadhead'
    )

    crew_dh_m = 0
    for driver_id, tasks in existing_duties.items():
        cur = mapper.driver_status[driver_id]['available_from_station']
        for task in sorted(tasks, key=lambda t: t['departure']):
            if cur != task['origin']:
                crew_dh_m += net.sp_raw.get(str(cur), {}).get(str(task['origin']), {}).get('weight', 0)
            cur = task['destination']

    return SolveResult(
        solution=        solution,
        existing_duties= existing_duties,
        duty_breaks=     duty_breaks,
        loco_duties=     loco_duties,
        canceled_tasks=  canceled_tasks,
        all_candidates=  all_candidates,
        dh_stats={
            'loco_dh_m':            loco_dh_m,
            'crew_dh_m':            crew_dh_m,
            'disruption_start_min': disruption_start,
            'disruption_end_min':   disruption_end,
        },
        forced_failures = forced_failures
    )


def run_instance(instance_id: str, seed: int = 42):
    instance, mapper, net, disruption_start, disruption_end = setup_instance(instance_id)
    return solve_instance(instance, mapper, net, disruption_start, disruption_end, seed)
       


def export_status_driver(mapper: DriverStatusMapper, output_path: str = "IntegratedRescheduling/driver_status_initial.tsv") -> None:
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    fields = ['driver_id', 'available_from_station', 'available_at_time']
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter='\t', extrasaction='ignore')
        writer.writeheader()
        for driver_id, status in sorted(mapper.driver_status.items()):
            writer.writerow({'driver_id':              driver_id,
                             'available_from_station': status.get('available_from_station'),
                             'available_at_time':      status.get('available_at_time')})
    print(f"[DriverStatus] {len(mapper.driver_status)} drivers → {output_path}")


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
    import argparse, time
    from datetime import datetime as _dt

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', nargs='+', metavar='S01', dest='instance_ids',
                        help='Instance IDs to run (default: all S*.json in single_type/)')
    parser.add_argument('--xaxis','-x', choices=['index', 'station', 'time'], default='index',
                        help='X-axis mode: index (default), origin station, or minutes from disruption start')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--canc-per-trip', action='store_true',
                        help='Gantt: one row per canceled trip instead of packed CANC-n rows')
    parser.add_argument('--excel', metavar='FILE.xlsx',
                        help='Visualize an external Excel solution (skips model run)')
    args = parser.parse_args()

    ts = _dt.now().strftime('%Y%m%d_%H%M%S')

    if args.excel:
        from LocoCrewViz import plot_loco_crew_gantt
        iid = args.instance_ids[0] if args.instance_ids else None
        loco_duties, metrics, disruption_start_min = loco_duties_from_excel(args.excel, iid)
        label       = iid or os.path.splitext(os.path.basename(args.excel))[0]
        output_path = os.path.join('IntegratedRescheduling/visualize', f"{label}_ext_{ts}.html")
        plot_loco_crew_gantt(
            loco_duties,
            title=f"External solution — {label}",
            output_html=output_path,
            metrics=metrics,
            xaxis=args.xaxis,
            disruption_start_min=disruption_start_min,
        )
        import sys; sys.exit(0)

    if args.instance_ids:
        instance_ids = args.instance_ids
    else:
        all_files    = sorted(glob.glob(os.path.join(INSTANCE_DIR, "S*.json")))
        instance_ids = [os.path.basename(f).replace('.json', '') for f in all_files
                        if 'network' not in f]

    all_results = []

    for iid in instance_ids:
        print(f"\n=== Instance: {iid} ===")
        try:
            t0 = time.time()
            r = run_instance(iid, seed=args.seed)
            elapsed = time.time() - t0
            all_results.append({
                'instance_id':           iid,
                'total_trip':            len(r.solution),
                'n_cancel':              count_canceled(r.solution),
                'total_deadhead_length [m]': r.dh_stats['loco_dh_m'] + r.dh_stats['crew_dh_m'],
                'computation_time [s]':      round(elapsed, 2),
            })
        except Exception as e:
            all_results.append({'instance_id': iid, 'error': str(e)})
            print(f"{iid}  ERROR: {e}")
            continue
        
        # Gantt only in single-instance mode
        if len(instance_ids) == 1:
            from LocoCrewViz import plot_loco_crew_gantt
            metrics = {
                'total_trips':          len(r.solution),
                'cancellations':        count_canceled(r.solution),
                'loco_dh_m':            r.dh_stats['loco_dh_m'],
                'crew_dh_m':            r.dh_stats['crew_dh_m'],
                'compute_time_sec':     elapsed,
                'disruption_start_min': r.dh_stats['disruption_start_min'],
                'disruption_end_min':   r.dh_stats['disruption_end_min'],
            }
            output_path = os.path.join('IntegratedRescheduling/visualize', f"{iid}_{ts}.html")
            plot_loco_crew_gantt(
                r.loco_duties,
                title=f"Instance {iid}",
                output_html=output_path,
                metrics=metrics,
                xaxis=args.xaxis,
                disruption_start_min=r.dh_stats['disruption_start_min'],
                canceled=r.canceled_tasks,
                canceled_per_trip=args.canc_per_trip,
            )
        

    export_to_csv(all_results, os.path.join('IntegratedRescheduling/results', f'results_{ts}.csv'))

