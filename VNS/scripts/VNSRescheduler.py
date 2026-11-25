import argparse
import contextlib
import functools
import glob
import io
import os
import sys
import time
from datetime import datetime as _dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from rescheduling import IntegratedRescheduling as IR
from rescheduling.IntegratedRescheduling import setup_instance, solve_instance, IntegratedRescheduler
import RunConfig
from SolutionEvaluator import SolutionEvaluator
from viz.LocoCrewViz import plot_loco_crew_gantt
from VNS.scripts.SwapStrategies import SwapStrategies, SHAKE_STRATEGIES
from VNS.scripts.utilities.ForcedInspection import export_forced_locos, write_forced_locos_json
from VNS.scripts.VNSExport import (export_vns_csv, export_iterations_csv, iteration_row,
                                    export_solution_json, to_solution)
from validator.Validator import validator
from rescheduling.RollingStockGreedy import CppMT19937

SOLUTION_DIR = os.path.join('VNS', 'solutions')

class VNSRescheduler:
    def __init__(self, instance_id, seed: int = 42, vns_seed: int = 42,
                 ignore_maintenance: bool = False, rescue_pass: bool = False):
        self.instance_id = instance_id
        self.instance, self.mapper, self.net, self.dis_start, self.dis_end = setup_instance(instance_id)
        self.evaluator = SolutionEvaluator(self.mapper, self.net)
        self.seed = seed
        self.ignore_maintenance = ignore_maintenance
        self.rescue_pass = rescue_pass
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
        rescheduling_results = solve_instance(self.instance, self.mapper, self.net, self.dis_start, self.dis_end, self.seed,
                                             ignore_maintenance=self.ignore_maintenance,
                                             rescue_pass=self.rescue_pass)
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
                   forced=forced, ignore_maintenance=self.ignore_maintenance,
                   rescue_pass=self.rescue_pass)
        obj = self._evaluate(r_new)
        delta = obj - obj_0
        print(f"[VNS run_once] baseline_obj={obj_0} new_obj={obj} delta={delta} "
              f"({'improved' if delta < 0 else 'no improvement'})")
        self.solve_time = time.time() - t_start   # solo ricerca, Gantt escluso
        if export_gantt:
            self._export_gantt(r_new, obj, strategy_fn.__name__)
        return r_new

    def _violations(self, result):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            validator(self.instance, self.mapper, self.net,
                      to_solution(result, {'instance_id': self.instance_id}),
                      self.dis_start, self.dis_end)
        return [l for l in buf.getvalue().splitlines() if l.startswith('[')]

    def _verify_replay(self, replayed, forced, soft_forced, early_exit):
        full = solve_instance(self.instance, self.mapper, self.net, self.dis_start, self.dis_end, self.seed,
                              forced=forced, ignore_maintenance=self.ignore_maintenance,
                              abort_on_forced_failure=early_exit, soft_forced=soft_forced,
                              rescue_pass=self.rescue_pass)
        diff = [f for f in ('solution', 'existing_duties', 'duty_breaks', 'loco_duties',
                            'all_candidates', 'forced_failures', 'dh_stats')
                if getattr(full, f) != getattr(replayed, f)]
        if ([c['rs_trip_id'] for c in full.canceled_tasks]
                != [c['rs_trip_id'] for c in replayed.canceled_tasks]):
            diff.append('canceled_tasks')
        if diff:
            raise RuntimeError(f"replay diverged from the full rebuild on {diff}")
        if not replayed.forced_failures and self._violations(replayed) != self._violations(full):
            raise RuntimeError("replay and full rebuild have different validator violations")
        print("[verify] replay identical to the full rebuild")

    def run_loop(self, k_max = 3, max_iter = 50, max_no_improve= 10,export_gantt = True,
                 shake = SwapStrategies.select_k, accept_delta = 0.0, time_limit = None,
                 early_exit = False, min_alternatives = 1, soft_inherited = False,
                 replay = False, rng_checkpoint_every = 25, verify_every = 0):

        t_start = time.time()
        checkpoint_every = rng_checkpoint_every if replay else 0
        s0 = solve_instance(self.instance, self.mapper, self.net, self.dis_start, self.dis_end, self.seed,
                            ignore_maintenance=self.ignore_maintenance,
                            rng_checkpoint_every=checkpoint_every,
                            rescue_pass=self.rescue_pass)
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

        while (it < max_iter and no_improve < max_no_improve
               and (time_limit is None or time.time() - t_start < time_limit)):
            # exclude: i trip gia' forzati nell'incumbent non aggiungono distanza (DD-3),
            # ripescarli sovrascriverebbe il loro pair concreto con il sentinel
            shakes = shake(incumbent.all_candidates, self.instance["train_sections"], k, self.vns_rng,
                           exclude = incumbent_forced.keys(), min_alternatives = min_alternatives)

            accepted = False
            new_best = False
            obj1 = None
            cand_forced = {}
            failures = []
            if shakes is None:
                outcome = 'no_shake'          # meno di k trip con alternative
                print(f"Failed shake k={k}")
            else:
                cand_forced = {**incumbent_forced, **shakes}
                soft_forced = None
                if soft_inherited:
                    soft_forced = {t: (incumbent.all_candidates.get(t) or [None])[0]
                                   for t in incumbent_forced if t not in shakes}
                loco_conflicts = export_forced_locos(cand_forced, incumbent.all_candidates)
                write_forced_locos_json(loco_conflicts, self.instance_id, it + 1)
                replay_from = None
                if replay:
                    position = {t: i for i, (t, _, _) in enumerate(incumbent.decision_log)}
                    replay_from = (incumbent.decision_log, incumbent.rng_checkpoints,
                                   min(position[t] for t in shakes))
                s1 = solve_instance(self.instance, self.mapper, self.net, self.dis_start, self.dis_end, self.seed, forced = cand_forced,
                                    ignore_maintenance=self.ignore_maintenance,
                                    abort_on_forced_failure=early_exit,
                                    soft_forced=soft_forced,
                                    replay=replay_from,
                                    rng_checkpoint_every=checkpoint_every,
                                    rescue_pass=self.rescue_pass)
                if replay and verify_every and (it + 1) % verify_every == 0:
                    self._verify_replay(s1, cand_forced, soft_forced, early_exit)

                if s1.forced_failures:
                    outcome = 'incomplete'    # shake non realizzabile: vicinato indeterminato
                    failures = s1.forced_failures
                    print(f"[k={k}] incompleted shake, failed trips: {s1.forced_failures}")
                else:
                    obj1 = self.evaluator.evaluate_components(s1.canceled_tasks, s1.dh_stats["loco_dh_m"], s1.dh_stats["crew_dh_m"], s1.existing_duties)
                    improved = obj1.total < incumbent_val.total
                    accepted = obj1.total < best_val.total + accept_delta
                    new_best = obj1.total < best_val.total
                    if improved:
                        outcome = 'accepted'
                    elif accepted:
                        outcome = 'accepted_worse'
                    else:
                        outcome = 'worse'

            k_used = k
            if accepted:
                incumbent, incumbent_forced, incumbent_val = s1, cand_forced, obj1
                k = 1
            else:
                k = k + 1 if k < k_max else 1
            if new_best:
                best, best_forced, best_val = s1, cand_forced, obj1
                no_improve = 0
            else:
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
                         help="Instance id(s) (default: all S*.json in Instances/single_type/)")
    parser.add_argument('-seed', type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument('--no-maintenance', action='store_true', dest='no_maintenance',
                        help="Disattiva la manutenzione: nessun vincolo sui km, nessuna "
                             "manutenzione pianificata, flag del piano originale ignorati. "
                             "Finisce nel run_info della soluzione esportata.")
    parser.add_argument('-s', '--strategy', nargs='+', default=['first_in_time'],
                         help="Swap strategy name. Options: first_in_time, multiple_swap. "
                              "Only used WITHOUT --loop: in loop mode the neighborhood is built by "
                              "--shake, so this is not used.")
    parser.add_argument('--shake', choices=sorted(SHAKE_STRATEGIES), default='ordered',
                         help="Loop mode: how the k trips of the shake are picked. "
                              "'ordered' = first k in departure order (deterministic set); "
                              "'random' = k sampled at random from all trips with alternatives; "
                              "'window' = k sampled at random inside a time window of --window-hours "
                              "placed at random (default: ordered)")
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
    parser.add_argument('--accept-delta', type=float, default=0.0,
                         help="Loop mode: record-to-record acceptance, accept a shake if "
                              "obj < best + DELTA. 0 = strict improvement only (default: 0). "
                              "An extra cancellation costs 500 (w_canceled): with DELTA < 500 it is "
                              "accepted only if offset by at least 500 - DELTA of deadhead savings")
    parser.add_argument('--early-exit', action='store_true',
                         help="Loop mode: stop the rebuild as soon as a forced trip finds no "
                              "alternative. The iteration is 'incomplete' either way; only the "
                              "first failed trip is logged")
    parser.add_argument('--replay', action='store_true',
                         help="Loop mode: rebuild a shaken schedule by replaying the incumbent's "
                              "decisions up to the earliest shaken trip and running the greedy from "
                              "there. Same result as a full rebuild, less time")
    parser.add_argument('--rng-checkpoint-every', type=int, default=25, metavar='N',
                         help="Loop mode with --replay: save the greedy RNG state every N trips; the "
                              "replay resumes from the last checkpoint before the shake (default: 25)")
    parser.add_argument('--verify-every', type=int, default=0, metavar='M',
                         help="Loop mode with --replay: every M iterations also run the full rebuild "
                              "and stop with an error if the replayed schedule differs (default: off)")
    parser.add_argument('--soft-inherited', action='store_true',
                         help="Loop mode: a trip forced in the incumbent first tries its incumbent "
                              "pair, then another alternative, then the plain greedy choice "
                              "(or cancellation). Only newly shaken trips can make an iteration incomplete")
    parser.add_argument('--window-hours', type=float, default=4.0, metavar='H',
                         help="Loop mode with --shake window: width in hours of the time window "
                              "the shaken trips are drawn from (default: 4)")
    parser.add_argument('--min-alternatives', type=int, default=1, metavar='N',
                         help="Loop mode: every shaken trip except the earliest must have at least "
                              "N alternative pairs in the incumbent. Trips with a single alternative "
                              "fail far more often when forced after another trip (default: 1, no filter)")
    parser.add_argument('--time-limit', type=float, default=None, metavar='SECONDS',
                         help="Loop mode: no new iteration starts after SECONDS from the start of "
                              "the search (baseline solve included). The iteration in progress "
                              "finishes, so the run can exceed the limit by one solve "
                              "(default: no limit)")
    parser.add_argument('-vns-seed', type=int, default=42,
                         help="Seed for the shaking RNG, independent from --seed")
    parser.add_argument('--export-solution', nargs='?', metavar='DIR', const=SOLUTION_DIR,
                         default=None,
                         help="Dump each solution as JSON for SolutionValidator. "
                              f"DIR is a directory, one file per instance (default: {SOLUTION_DIR})")
    parser.add_argument('--rescue-pass', action='store_true', dest='rescue_pass',
                         help="Riattiva la passata di recupero dei trip cancellati dentro il greedy. "
                              "Spenta per default: recupera 1 trip su 2.263 cancellazioni e costa il "
                              "10-13%% del tempo nella ricerca dei candidati. Serve a riprodurre le "
                              "batch fino al 14/10")
    parser.add_argument('--no-gantt', action='store_true',
                         help="Skip the Gantt HTML export. Thought for batch runs (e.g. one "
                              "SLURM array task per instance), where every task counts as "
                              "single-instance and would write a multi-MB plotly file nobody opens")
    RunConfig.add_path_args(parser)
    args = parser.parse_args()

    # setup_instance() legge i path dalle globali di IntegratedRescheduling,
    # quindi vanno impostate li'. Nota il IR.INSTANCE_DIR piu' sotto: un
    # "from IntegratedRescheduling import INSTANCE_DIR" ne fotograferebbe il
    # valore all'import, cioe' None, e apply_to() non potrebbe raggiungerlo.
    run_paths = RunConfig.resolve(args, parser)
    run_paths.apply_to(IR)
    print(f"[RunConfig] chain={run_paths.chain_name} instances={run_paths.instance_dir}")

    if args.csv:
        csv_path = args.csv
    else:
        ts_csv = _dt.now().strftime('%Y%m%d_%H%M%S')
        csv_path = os.path.join('VNS', 'results', f'vns_results_{ts_csv}.csv')

    strategies = [SwapStrategies.get_swap_strategy(name) for name in args.strategy]
    shake_fn = SHAKE_STRATEGIES[args.shake]
    if args.shake == 'window':
        shake_fn = functools.partial(shake_fn, window_hours=args.window_hours)

    if args.instance:
        instance_ids = args.instance
    else:
        all_files    = sorted(glob.glob(os.path.join(IR.INSTANCE_DIR, "S*.json")))
        instance_ids = [os.path.basename(f).replace('.json', '') for f in all_files
                        if 'network' not in f]

    _problems = RunConfig.validate_chain(run_paths, instance_ids)
    if _problems:
        parser.error("catena crew incoerente:\n  " + "\n  ".join(_problems))

    # Gantt only in single-instance mode, as in IntegratedRescheduling.py; --no-gantt
    # spegne l'export anche li', per le batch dove ogni task e' single-instance
    export_gantt = len(instance_ids) == 1 and not args.no_gantt

    iter_csv_path = csv_path.replace('.csv', '_iterations.csv')

    # identifica la run nel nome del file soluzione: due run diverse sulla stessa
    # istanza non si sovrascrivono. k_max entra nel tag perche' e' il parametro
    # che distingue le batch fra loro: senza, k5 e k10 producono nomi identici e
    # restano distinguibili solo dalla cartella che li contiene.
    run_tag = (f"k{args.k_max}_{args.shake}_seed{args.seed}_vns{args.vns_seed}" if args.loop
               else f"{args.strategy[0]}_seed{args.seed}")
    if args.loop and args.accept_delta:
        run_tag += f"_d{args.accept_delta:g}"
    if args.loop and args.shake == 'window':
        run_tag += f"_w{args.window_hours:g}"

    csv_results = []
    iter_rows   = []
    for iid in instance_ids:
        print(f"\n=== Instance: {iid} ===")
        try:
            vns = VNSRescheduler(iid, seed=args.seed, vns_seed=args.vns_seed,
                                 ignore_maintenance=args.no_maintenance,
                                 rescue_pass=args.rescue_pass)
            if args.loop:
                best = vns.run_loop(k_max=args.k_max, max_iter=args.max_iter, max_no_improve=args.max_no_improve,
                                     export_gantt=export_gantt, shake=shake_fn,
                                     accept_delta=args.accept_delta, time_limit=args.time_limit,
                                     early_exit=args.early_exit, min_alternatives=args.min_alternatives,
                                     soft_inherited=args.soft_inherited, replay=args.replay,
                                     rng_checkpoint_every=args.rng_checkpoint_every,
                                     verify_every=args.verify_every)
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
                # i parametri del loop stanno nel run_info, non solo nel nome del
                # file: una soluzione spostata o rinominata deve restare
                # ricollegabile alla configurazione che l'ha prodotta. In modalita'
                # 'once' non hanno significato e restano None.
                export_solution_json(best, {
                    'instance_id':    iid,
                    'seed':           args.seed,
                    'no_maintenance': args.no_maintenance,
                    'rescue_pass':    args.rescue_pass,
                    'vns_seed':       args.vns_seed,
                    'mode':           'loop' if args.loop else 'once',
                    'shake':          args.shake if args.loop else args.strategy[0],
                    'k_max':          args.k_max          if args.loop else None,
                    'max_iter':       args.max_iter       if args.loop else None,
                    'max_no_improve': args.max_no_improve if args.loop else None,
                    'accept_delta':   args.accept_delta   if args.loop else None,
                    'time_limit':     args.time_limit     if args.loop else None,
                    'early_exit':     args.early_exit     if args.loop else None,
                    'min_alternatives': args.min_alternatives if args.loop else None,
                    'window_hours':   args.window_hours if args.loop and args.shake == 'window' else None,
                    'soft_inherited': args.soft_inherited if args.loop else None,
                    'replay':         args.replay         if args.loop else None,
                    'objective':      round(obj.total, 2) if obj else None,
                    'solve_time':     round(vns.solve_time, 2),
                    # Stessa logica dei parametri del loop, applicata ai path:
                    # una soluzione deve dire da quali directory e' nata.
                    **run_paths.as_run_info(),
                    'forced':         vns.current_forced,
                }, sol_path)
                print(f"[Solution] → {sol_path}")
        except Exception as e:
            csv_results.append({'instance_id': iid, 'error': str(e)})
            print(f"{iid}  ERROR: {e}")

    export_vns_csv(csv_results, csv_path)
    export_iterations_csv(iter_rows, iter_csv_path)
