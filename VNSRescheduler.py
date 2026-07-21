import argparse
import csv
import glob
import os
import time
from datetime import datetime as _dt
from IntegratedRescheduling import setup_instance, solve_instance, IntegratedRescheduler, INSTANCE_DIR
from SolutionEvaluator import SolutionEvaluator
from LocoCrewViz import plot_loco_crew_gantt
from VNS.scripts.SwapStrategies import SwapStrategies

VNS_CSV_COLUMNS = ['instance_id', 'total_trip', 'n_cancel', 'computation_time [s]']


def export_vns_csv(results: list, output_path: str):
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    file_exists = os.path.isfile(output_path)
    with open(output_path, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=VNS_CSV_COLUMNS, extrasaction='ignore')
        if not file_exists:
            writer.writeheader()
        for r in results:
            if 'error' not in r:
                writer.writerow(r)
    print(f"[CSV] appended {len([r for r in results if 'error' not in r])} rows → {output_path}")


class VNSRescheduler:
    def __init__(self, instance_id, seed: int = 42):
        self.instance_id = instance_id
        self.instance, self.mapper, self.net, self.dis_start, self.dis_end = setup_instance(instance_id)
        self.evaluator = SolutionEvaluator(self.mapper, self.net)
        self.seed = seed
        self.current_forced = {}
        self.current_result = None
        self.current_obj = None
        self.history: list[tuple[dict, float]] = []

    def _evaluate(self, result) -> float:
        return self.evaluator.evaluate(
            result.canceled_tasks,
            result.dh_stats["loco_dh_m"],
            result.dh_stats["crew_dh_m"],
            result.existing_duties,
        )

    def _export_gantt(self, result, obj: float, label: str):
        ts = _dt.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs('IntegratedRescheduling/visualize', exist_ok=True)
        output_path = os.path.join('IntegratedRescheduling/visualize', f"{self.instance_id}_vns_{ts}.html")
        metrics = {
            'total_trips':          len(result.solution),
            'cancellations':        len(result.canceled_tasks),
            'loco_dh_m':            result.dh_stats['loco_dh_m'],
            'crew_dh_m':            result.dh_stats['crew_dh_m'],
            'disruption_start_min': self.dis_start,
            'disruption_end_min':   self.dis_end,
            'obj_value': obj,
        }
        plot_loco_crew_gantt(
            result.loco_duties,
            title=f"VNS — {label} [{self.instance_id}]",
            output_html=output_path,
            metrics=metrics,
            xaxis='time',
            disruption_start_min=self.dis_start,
            canceled=result.canceled_tasks,
        )
        print(f"Gantt → {output_path}")

    def run_once(self, strategy_fn, export_gantt: bool = True):
        rescheduling_results = solve_instance(self.instance, self.mapper, self.net, self.dis_start, self.dis_end, self.seed)
        obj_0 = self._evaluate(rescheduling_results)
        self.current_forced = {}
        self.current_result = rescheduling_results
        self.current_obj    = obj_0
        self.history = [({}, obj_0)]

        candidates = rescheduling_results.all_candidates
        forced = strategy_fn(candidates, self.instance['train_sections'])
        print(f"Forced trip from swap={forced}")
        if forced is None:
            print("No trip with alternatives found — nothing to swap.")
            return rescheduling_results

        r_new = solve_instance(self.instance, self.mapper, self.net,
                   self.dis_start, self.dis_end, self.seed,
                   forced=forced)
        obj = self._evaluate(r_new)
        delta = obj - obj_0
        print(f"[VNS run_once] baseline_obj={obj_0} new_obj={obj} delta={delta} "
              f"({'improved' if delta < 0 else 'no improvement'})")
        if export_gantt:
            self._export_gantt(r_new, obj, strategy_fn.__name__)
        return r_new

    def run_loop(self, strategies: list, max_iter: int = 50, max_no_improve: int = 10,
                 export_gantt: bool = True):
        """RVNS: shake with strategies[k-1] at neighborhood k, accept on improvement
        (reset k=1), otherwise widen (k+=1). Stops on max_iter or max_no_improve."""
        r0 = solve_instance(self.instance, self.mapper, self.net, self.dis_start, self.dis_end, self.seed)
        obj0 = self._evaluate(r0)
        self.current_forced = {}
        self.current_result = r0
        self.current_obj    = obj0
        self.history = [({}, obj0)]

        kmax = len(strategies)
        no_improve_count = 0
        iter_count = 0
        while iter_count < max_iter and no_improve_count < max_no_improve:
            k = 1
            improved_this_iter = False
            while k <= kmax:
                strategy_fn = strategies[k - 1]
                candidates = self.current_result.all_candidates
                forced_delta = strategy_fn(candidates, self.instance['train_sections'])
                if forced_delta is None:
                    k += 1
                    continue

                candidate_forced = dict(self.current_forced)
                candidate_forced.update(forced_delta)
                r_candidate = solve_instance(self.instance, self.mapper, self.net,
                                              self.dis_start, self.dis_end, self.seed,
                                              forced=candidate_forced)
                obj_candidate = self._evaluate(r_candidate)

                if obj_candidate < self.current_obj:
                    for trip_id, pair in forced_delta.items():
                        baseline = candidates.get(trip_id, [{}])[0]
                        if pair is IntegratedRescheduler.FORCED_ALTERNATIVE:
                            print(f"    swap trip={trip_id}: baseline loco={baseline.get('loco')} "
                                  f"drivers={baseline.get('drivers')} → FORCED_ALTERNATIVE (resolved on-the-fly)")
                        else:
                            print(f"    swap trip={trip_id}: baseline loco={baseline.get('loco')} "
                                  f"drivers={baseline.get('drivers')} → loco={pair['loco']} drivers={pair['drivers']}")
                    self.current_forced = candidate_forced
                    self.current_result = r_candidate
                    self.current_obj    = obj_candidate
                    self.history.append((candidate_forced, obj_candidate))
                    no_improve_count = 0
                    improved_this_iter = True
                    k = 1
                else:
                    k += 1
            iter_count += 1
            if not improved_this_iter:
                no_improve_count += 1

        delta = self.current_obj - obj0
        print(f"[VNS loop] iterations={iter_count} history_len={len(self.history)} "
              f"baseline_obj={obj0} final_obj={self.current_obj} delta={delta} "
              f"({'improved' if delta < 0 else 'no improvement'})")
        if export_gantt:
            self._export_gantt(self.current_result, self.current_obj,
                                label=f"loop_{'+'.join(s.__name__ for s in strategies)}")
        return self.current_result







if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run VNS rescheduling with a chosen swap strategy.")
    parser.add_argument('-i', '--instance', nargs='+', default=None,
                         help="Instance id(s) (default: all S*.json in single_type/)")
    parser.add_argument('--seed', type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument('-s', '--strategy', nargs='+', default=['first_in_time', 'multiple_swap'],
                         help="Swap strategy names, in k-order (k=1,2,...). "
                              "Options: first_in_time, multiple_swap. "
                              "With --loop pass one per neighborhood level; "
                              "without --loop only the first is used.")
    parser.add_argument('--loop', action='store_true',
                         help="Run the full RVNS loop (run_loop) instead of a single shake (run_once)")
    parser.add_argument('--max-iter', type=int, default=50,
                         help="Loop mode: max outer iterations (default: 50)")
    parser.add_argument('--max-no-improve', type=int, default=10,
                         help="Loop mode: stop after this many consecutive iterations without improvement (default: 10)")
    parser.add_argument('-csv', metavar='FILE.csv', default=None,
                         help="Append per-instance results (instance_id, total_trip, n_cancel, "
                              "computation_time [s]) to this CSV. "
                              "Default: VNS/results/vns_results_<timestamp>.csv")
    args = parser.parse_args()

    if args.csv:
        csv_path = args.csv
    else:
        ts_csv = _dt.now().strftime('%Y%m%d_%H%M%S')
        csv_path = os.path.join('VNS', 'results', f'vns_results_{ts_csv}.csv')

    strategies = [SwapStrategies.get_swap_strategy(name) for name in args.strategy]

    if args.instance:
        instance_ids = args.instance
    else:
        all_files    = sorted(glob.glob(os.path.join(INSTANCE_DIR, "S*.json")))
        instance_ids = [os.path.basename(f).replace('.json', '') for f in all_files
                        if 'network' not in f]

    export_gantt = len(instance_ids) == 1  # Gantt only in single-instance mode, as in IntegratedRescheduling.py

    csv_results = []
    for iid in instance_ids:
        print(f"\n=== Instance: {iid} ===")
        try:
            t0 = time.time()
            vns = VNSRescheduler(iid, seed=args.seed)
            if args.loop:
                best = vns.run_loop(strategies, max_iter=args.max_iter, max_no_improve=args.max_no_improve,
                                     export_gantt=export_gantt)
            else:
                best = vns.run_once(strategies[0], export_gantt=export_gantt)
            elapsed = time.time() - t0
            csv_results.append({
                'Instance':            iid,
                'total_trip':             len(best.solution),
                'n_cancel':               len(best.canceled_tasks),
                'computation_time [s]':   round(elapsed, 2),
            })
        except Exception as e:
            csv_results.append({'instance_id': iid, 'error': str(e)})
            print(f"{iid}  ERROR: {e}")

    export_vns_csv(csv_results, csv_path)
