import argparse
import glob
import os
import time
from datetime import datetime as _dt
from IntegratedRescheduling import setup_instance, solve_instance, IntegratedRescheduler, INSTANCE_DIR
from SolutionEvaluator import SolutionEvaluator
from LocoCrewViz import plot_loco_crew_gantt
from VNS.scripts.SwapStrategies import SwapStrategies, SHAKE_STRATEGIES
from VNS.scripts.VNSExport import (export_vns_csv, export_iterations_csv, iteration_row,
                                    export_solution_json)
from RollingStockGreedy import CppMT19937

SOLUTION_DIR = os.path.join('VNS', 'solutions')

class VNSRescheduler:
    def __init__(self, instance_id, seed: int = 42, vns_seed: int = 42):
        self.instance_id = instance_id
        self.instance, self.mapper, self.net, self.dis_start, self.dis_end = setup_instance(instance_id)
        self.evaluator = SolutionEvaluator(self.mapper, self.net)
        self.seed = seed
        self.current_forced = {}
        self.current_result = None
        self.current_obj = None
        self.history: list[tuple[dict, float]] = []
        self.iteration_log: list[dict] = []
        self.solve_time = 0.0
        # un solo stream per l'intera run: avanza a ogni select_k, cosi' le
        # iterazioni differiscono fra loro ma la run resta riproducibile da vns_seed
        self.vns_rng = CppMT19937(vns_seed)

    def _evaluate(self, result) -> float:
        return self.evaluator.evaluate(
            result.canceled_tasks,
            result.dh_stats["loco_dh_m"],
            result.dh_stats["crew_dh_m"],
            result.existing_duties,
        )

    def _log_row(self, *args):
        """Riga del log per-iterazione (formattazione in VNS.scripts.VNSExport)."""
        return iteration_row(self.instance_id, *args)

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
        t_start = time.time()
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
            self.solve_time = time.time() - t_start
            return rescheduling_results

        r_new = solve_instance(self.instance, self.mapper, self.net,
                   self.dis_start, self.dis_end, self.seed,
                   forced=forced)
        obj = self._evaluate(r_new)
        delta = obj - obj_0
        print(f"[VNS run_once] baseline_obj={obj_0} new_obj={obj} delta={delta} "
              f"({'improved' if delta < 0 else 'no improvement'})")
        self.solve_time = time.time() - t_start   # solo ricerca, Gantt escluso
        if export_gantt:
            self._export_gantt(r_new, obj, strategy_fn.__name__)
        return r_new

    def run_loop(self, k_max = 3, max_iter = 50, max_no_improve= 10,export_gantt = True,
                 shake = SwapStrategies.select_k):

        t_start = time.time()
        s0 = solve_instance(self.instance, self.mapper, self.net, self.dis_start, self.dis_end, self.seed)
        obj0 = self.evaluator.evaluate_components(s0.canceled_tasks, s0.dh_stats["loco_dh_m"], s0.dh_stats["crew_dh_m"], s0.existing_duties)
        best = incumbent = s0
        best_forced = {}
        incumbent_forced = {}
        best_val = incumbent_val = obj0

        k=1
        it=0
        no_improve=0

        # traiettoria di ricerca: una riga per iterazione (iter 0 = baseline greedy)
        self.iteration_log = [self._log_row(0, 0, 'baseline', obj0, obj0, obj0,
                                            {}, [], time.time() - t_start)]

        while it < max_iter and no_improve < max_no_improve:
            # exclude: i trip gia' forzati nell'incumbent non aggiungono distanza (DD-3),
            # ripescarli sovrascriverebbe il loro pair concreto con il sentinel
            shakes = shake(incumbent.all_candidates, self.instance["train_sections"], k, self.vns_rng,
                           exclude = incumbent_forced.keys())

            accepted = False
            obj1 = None
            cand_forced = {}
            failures = []
            if shakes is  None:
                outcome = 'no_shake'          # meno di k trip con alternative
                print(f"Failed shake k={k}")
            else:
                cand_forced = {**incumbent_forced, **shakes}
                s1 = solve_instance(self.instance, self.mapper, self.net, self.dis_start, self.dis_end, self.seed, forced = cand_forced)

                if s1.forced_failures:
                    outcome = 'incomplete'    # shake non realizzabile: vicinato indeterminato
                    failures = s1.forced_failures
                    print(f"[k={k}] incompleted shake, failed trips: {s1.forced_failures}")
                else:
                    obj1 = self.evaluator.evaluate_components(s1.canceled_tasks, s1.dh_stats["loco_dh_m"], s1.dh_stats["crew_dh_m"], s1.existing_duties)
                    accepted = obj1.total < incumbent_val.total
                    outcome = 'accepted' if accepted else 'worse'

            k_used = k
            if accepted:
                incumbent, incumbent_forced, incumbent_val = s1, cand_forced, obj1
                if obj1.total < best_val.total:
                    best, best_forced, best_val = s1, cand_forced, obj1
                k = 1
                no_improve = 0
            else:
                k = k + 1 if k < k_max else 1
                no_improve += 1
            it += 1

            self.iteration_log.append(
                self._log_row(it, k_used, outcome, obj1, incumbent_val, best_val,
                              cand_forced, failures, time.time() - t_start))

        self.solve_time = time.time() - t_start   # solo ricerca, Gantt escluso

        # esposti al chiamante (CLI/CSV): il loop restituisce solo la soluzione
        self.current_result = best
        self.current_forced = best_forced
        self.current_obj    = best_val

        print(f"[VNS loop] iterations={it} baseline_obj={obj0.total:.1f} "
              f"final_obj={best_val.total:.1f} delta={best_val.total - obj0.total:.1f} "
              f"forced_trips={len(best_forced)}")
        if export_gantt:
            self._export_gantt(best, best_val.total, label=f"loop_k{k_max}")
        return best


        






if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run VNS rescheduling with a chosen swap strategy.")
    parser.add_argument('-i', '--instance', nargs='+', default=None,
                         help="Instance id(s) (default: all S*.json in single_type/)")
    parser.add_argument('-seed', type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument('-s', '--strategy', nargs='+', default=['first_in_time'],
                         help="Swap strategy name. Options: first_in_time, multiple_swap. "
                              "Only used WITHOUT --loop: in loop mode the neighborhood is built by "
                              "--shake, so this is not used.")
    parser.add_argument('--shake', choices=sorted(SHAKE_STRATEGIES), default='ordered',
                         help="Loop mode: how the k trips of the shake are picked. "
                              "'ordered' = first k in departure order (deterministic set); "
                              "'random' = k sampled at random from all trips with alternatives "
                              "(default: ordered)")
    parser.add_argument('-loop', action='store_true',
                         help="Run the full BVNS loop (run_loop) instead of a single shake (run_once)")
    parser.add_argument('-max-iter', type=int, default=50,
                         help="Loop mode: max outer iterations (default: 50)")
    parser.add_argument('--max-no-improve', type=int, default=10,
                         help="Loop mode: stop after this many consecutive iterations without improvement (default: 10)")
    parser.add_argument('-csv', metavar='FILE.csv', default=None,
                         help="Append per-instance results (instance_id, total_trip, n_cancel, "
                              "computation_time [s]) to this CSV. "
                              "Default: VNS/results/vns_results_<timestamp>.csv")
    parser.add_argument('-k-max', type=int, default=3,
                         help="Loop mode: max neighborhood size (number of forced trips)")
    parser.add_argument('-vns-seed', type=int, default=42,
                         help="Seed for the shaking RNG, independent from --seed")
    parser.add_argument('--export-solution', nargs='?', metavar='DIR', const=SOLUTION_DIR,
                         default=None,
                         help="Dump each solution as JSON for SolutionValidator. "
                              f"DIR is a directory, one file per instance (default: {SOLUTION_DIR})")
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

    iter_csv_path = csv_path.replace('.csv', '_iterations.csv')

    # identifica la run nel nome del file soluzione: due run diverse sulla stessa
    # istanza non si sovrascrivono
    run_tag = (f"{args.shake}_seed{args.seed}_vns{args.vns_seed}" if args.loop
               else f"{args.strategy[0]}_seed{args.seed}")

    csv_results = []
    iter_rows   = []
    for iid in instance_ids:
        print(f"\n=== Instance: {iid} ===")
        try:
            vns = VNSRescheduler(iid, seed=args.seed, vns_seed=args.vns_seed)
            if args.loop:
                best = vns.run_loop(k_max=args.k_max, max_iter=args.max_iter, max_no_improve=args.max_no_improve,
                                     export_gantt=export_gantt, shake=SHAKE_STRATEGIES[args.shake])
            else:
                best = vns.run_once(strategies[0], export_gantt=export_gantt)
            obj = vns.current_obj
            csv_results.append({
                'instance_id':            iid,
                'total_trip':             len(best.solution),
                'n_cancel':               len(best.canceled_tasks),
                'obj_total':              round(obj.total, 2) if obj else '',
                'loco_dh_m':              obj.loco_dh_m if obj else '',
                'crew_dh_m':              obj.crew_dh_m if obj else '',
                'back_home':              obj.back_home if obj else '',
                'computation_time [s]':   round(vns.solve_time, 2),
            })
            iter_rows.extend(vns.iteration_log)

            if args.export_solution:
                sol_path = os.path.join(args.export_solution, f"{iid}_{run_tag}.json")
                export_solution_json(best, {
                    'instance_id': iid,
                    'seed':        args.seed,
                    'vns_seed':    args.vns_seed,
                    'mode':        'loop' if args.loop else 'once',
                    'shake':       args.shake if args.loop else args.strategy[0],
                    'objective':   round(obj.total, 2) if obj else None,
                    'solve_time':  round(vns.solve_time, 2),
                    'forced':      vns.current_forced,
                }, sol_path)
                print(f"[Solution] → {sol_path}")
        except Exception as e:
            csv_results.append({'instance_id': iid, 'error': str(e)})
            print(f"{iid}  ERROR: {e}")

    export_vns_csv(csv_results, csv_path)
    export_iterations_csv(iter_rows, iter_csv_path)
