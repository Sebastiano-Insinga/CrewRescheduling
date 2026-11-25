from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from DeltaManager import DeltaManager
from Moves import EvaluatedMove, commit
from ScheduleManager import ScheduleManager
from ScheduleState import ScheduleState
from ScheduleStateTests import feasible_random_move
from deltas import candidate_duties
from moves import descend
from moves.SearchDelta import descend_delta

TOLERANCE = 1e-6


def check_deltas(state, manager: DeltaManager, rng, rounds: int, weights: tuple = None) -> tuple:
    problems = []
    kinds    = {}
    by_hand  = 0
    for _ in range(rounds):
        move  = feasible_random_move(state, rng, weights)
        name  = type(move).__name__
        hand  = candidate_duties(state, move) is not None
        by_hand += hand
        kinds[name] = kinds.get(name, 0) + 1

        delta   = manager.evaluate(state, move)
        before  = manager.cost_function_components(state)
        inverse = move.make_move(state)
        after   = manager.cost_function_components(state)
        inverse.make_move(state)
        full    = after - before

        if (abs(full.violations - delta.violations) > TOLERANCE
                or abs(full.objective - delta.objective) > TOLERANCE):
            problems.append(f"{name} {move}: delta {delta} invece di {full}")
        for index, component in enumerate(manager.components):
            if abs(full.all_components[index] - delta.all_components[index]) > TOLERANCE:
                problems.append(f"{name} {move}: delta su {component.name} "
                                f"{delta.all_components[index]} invece di "
                                f"{full.all_components[index]}")
        if problems:
            break
    return problems, kinds, by_hand


def check_accumulator(state, manager: DeltaManager, rng, rounds: int, verify_every: int,
                      weights: tuple = None) -> list:
    problems = []
    journal  = []
    for step in range(1, rounds + 1):
        move      = feasible_random_move(state, rng, weights)
        evaluated = EvaluatedMove(move, manager.evaluate(state, move))
        journal.append((commit(state, manager, evaluated), evaluated.delta))
        if verify_every and step % verify_every == 0:
            drift = manager.drift(state)
            if drift > TOLERANCE:
                problems.append(f"dopo {step} mosse l'accumulatore deriva di {drift:.3e}")
                break
    problems += [f"accumulatore: {p}" for p in manager.check_consistency(state)]
    for inverse, delta in reversed(journal):
        manager.revert(state, inverse, delta)
    return problems


def timings(state, manager: DeltaManager, rng, rounds: int, weights: tuple = None) -> None:
    moves = []
    while len(moves) < rounds:
        move = feasible_random_move(state, rng, weights)
        if candidate_duties(state, move) is not None:
            moves.append(move)

    t0 = time.time()
    for move in moves:
        manager.evaluate(state, move)
    delta_sec = time.time() - t0

    t0 = time.time()
    for move in moves:
        inverse = move.make_move(state)
        manager.cost_function_components(state)
        inverse.make_move(state)
    full_sec = time.time() - t0

    print(f"  {rounds} mosse a delta: {rounds / max(1e-9, delta_sec):.0f}/s  "
          f"a ricalcolo pieno: {rounds / max(1e-9, full_sec):.0f}/s  "
          f"guadagno {full_sec / max(1e-9, delta_sec):.1f}x")


if __name__ == "__main__":
    import RunConfig
    from rescheduling import IntegratedRescheduling as IR

    parser = argparse.ArgumentParser(
        description="Verifica che evaluate(move) coincida col ricalcolo pieno, che "
                    "l'accumulatore non derivi, e che la discesa a delta dia lo stesso "
                    "risultato di quella a ricalcolo pieno.")
    parser.add_argument("-i", "--instance", nargs="+", required=True)
    parser.add_argument("-seed", type=int, default=42)
    parser.add_argument("-move-seed", type=int, default=7, dest="move_seed")
    parser.add_argument("--no-maintenance", action="store_true", dest="no_maintenance")
    parser.add_argument("-moves", type=int, default=500, metavar="N",
                        help="mosse su cui confrontare evaluate col ricalcolo pieno")
    parser.add_argument("-accumulate", type=int, default=200, metavar="N",
                        help="mosse applicate in fila col costo accumulato, poi disfatte")
    parser.add_argument("-verify-every", type=int, default=50, metavar="M",
                        dest="verify_every",
                        help="ogni M mosse accettate confronta l'accumulatore col ricalcolo pieno")
    parser.add_argument("-timings", type=int, default=500, metavar="N",
                        help="mosse cronometrate a delta e a ricalcolo pieno")
    parser.add_argument("-move-weights", type=float, nargs=5, default=None, dest="move_weights",
                        metavar=("CD", "SWAP", "COVER", "UNCOVER", "CL"))
    parser.add_argument("-descend", action="store_true",
                        help="confronta la discesa a delta con quella a ricalcolo pieno, "
                             "stesso seme")
    parser.add_argument("-steepest", action="store_true",
                        help="la discesa a delta usa select_best invece di select_first")
    parser.add_argument("--sample", type=int, default=200, metavar="N")
    parser.add_argument("-sabotage", choices=("slot", "scale"), default=None,
                        help="falsa la mappa dei delta e verifica che il confronto se ne accorga")
    RunConfig.add_path_args(parser)
    args = parser.parse_args()

    RunConfig.resolve(args, parser).apply_to(IR)

    if args.sabotage:
        from ScheduleState import SC_EXCESS
        from deltas import DutySlots
        if args.sabotage == "slot":
            DutySlots.DUTY_SLOT["continuity_minutes"] = (SC_EXCESS, 1.0)
        else:
            DutySlots.DUTY_SLOT["crew_deadhead_km"] = (DutySlots.DUTY_SLOT["crew_deadhead_km"][0],
                                                       0.0011)
        print(f"  sabotaggio attivo ({args.sabotage}): il confronto deve fallire")

    failed = []
    for instance_id in args.instance:
        from rescheduling.LocoChecker import LocoChecker
        from rescheduling.RollingStockGreedy import CppMT19937
        from SolutionEvaluator import SolutionEvaluator

        instance, mapper, net, dis_start, dis_end = IR.setup_instance(instance_id)
        result = IR.solve_instance(instance, mapper, net, dis_start, dis_end, args.seed,
                                   ignore_maintenance=args.no_maintenance)
        loco_checker = LocoChecker(instance, net, ignore_maintenance=args.no_maintenance)

        state     = ScheduleState.from_solve_result(result, mapper, net,
                                                    loco_checker=loco_checker)
        evaluator = SolutionEvaluator(mapper, net)
        manager   = DeltaManager.default(evaluator)
        start     = manager.initialize(state)
        print(f"[{instance_id}] costo di partenza {start}")

        problems = []
        if args.moves:
            rng = CppMT19937(args.move_seed)
            before = state.snapshot()
            delta_problems, kinds, by_hand = check_deltas(state, manager, rng, args.moves,
                                                          args.move_weights)
            print(f"  delta confrontati su {args.moves} mosse {kinds}: "
                  f"{by_hand} a mano sui turni toccati, {args.moves - by_hand} "
                  f"con apply/undo")
            if state.snapshot() != before:
                problems.append("il confronto dei delta ha lasciato lo stato diverso")
            problems += delta_problems

        if args.accumulate:
            rng = CppMT19937(args.move_seed + 1)
            before = state.snapshot()
            problems += check_accumulator(state, manager, rng, args.accumulate,
                                          args.verify_every, args.move_weights)
            if state.snapshot() != before:
                problems.append("l'accumulatore ha lasciato lo stato diverso")
            print(f"  accumulatore su {args.accumulate} mosse, verifica ogni "
                  f"{args.verify_every}: costo tornato a {manager.cost}")

        if args.timings:
            timings(state, manager, CppMT19937(args.move_seed + 2), args.timings,
                    args.move_weights)

        if args.descend:
            slow_state   = ScheduleState.from_solve_result(result, mapper, net,
                                                           loco_checker=loco_checker)
            slow_manager = ScheduleManager.default(evaluator)
            t0 = time.time()
            slow_best, slow_steps = descend(slow_state, slow_manager,
                                            CppMT19937(args.move_seed),
                                            sample=args.sample, weights=args.move_weights)
            slow_sec = time.time() - t0

            fast_state   = ScheduleState.from_solve_result(result, mapper, net,
                                                           loco_checker=loco_checker)
            fast_manager = DeltaManager.default(evaluator)
            fast_manager.initialize(fast_state)
            t0 = time.time()
            fast_best, fast_steps = descend_delta(fast_state, fast_manager,
                                                  CppMT19937(args.move_seed),
                                                  sample=args.sample,
                                                  weights=args.move_weights,
                                                  steepest=args.steepest)
            fast_sec = time.time() - t0

            print(f"  discesa a ricalcolo pieno: {slow_steps} mosse in {slow_sec:.1f}s "
                  f"-> {slow_best}")
            print(f"  discesa a delta:           {fast_steps} mosse in {fast_sec:.1f}s "
                  f"-> {fast_best}")
            problems += [f"discesa a delta: check_consistency {p}"
                         for p in fast_manager.check_consistency(fast_state)]
            if not args.steepest and abs(slow_best.total - fast_best.total) > 1e-6:
                problems.append(f"le due discese divergono: {slow_best.total} contro "
                                f"{fast_best.total}")

        if problems:
            failed.append(instance_id)
            print(f"  PROBLEMI su {instance_id}:")
            for problem in problems[:20]:
                print(f"    - {problem}")
        else:
            print(f"  {instance_id}: tutto verde")

    if args.sabotage:
        print("\nsabotaggio: " + ("il confronto ha fallito come deve" if failed
                                  else "NON SCATTATO, il controllo non ha denti"))
        sys.exit(0 if failed else 1)
    sys.exit(1 if failed else 0)
