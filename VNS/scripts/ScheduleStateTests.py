from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Cost import PenaltyWeights
from ScheduleManager import ScheduleManager
from ScheduleState import NONE, ScheduleState
from moves import ChangeDriver, CoverTrip, cover_search, descend, random_move
from moves.Move import random_drivers


def check_arrays(state: ScheduleState, result) -> list:
    problems = []

    for loco_id, segments in result.loco_duties.items():
        expected = [task["rs_trip_id"] for task, _ in
                    sorted(segments, key=lambda s: (s[0]["departure"], s[0]["arrival"]))
                    if task.get("type") == "trip"]
        got = [state.trip_order[i] for i in state.loco_sequence(state.loco_at[loco_id])]
        if got != expected:
            problems.append(f"loco {loco_id}: sequenza {got} invece di {expected}")

    if state.n_canceled != len(result.canceled_tasks):
        problems.append(f"cancellati dagli array {state.n_canceled} invece di "
                        f"{len(result.canceled_tasks)}")

    if abs(state.loco_dh_m - result.dh_stats["loco_dh_m"]) > 1e-6:
        problems.append(f"loco_dh_m dagli array {state.loco_dh_m} invece di "
                        f"{result.dh_stats['loco_dh_m']}")

    canceled = {ct["rs_trip_id"] for ct in result.canceled_tasks}
    for i, trip_id in enumerate(state.trip_order):
        if (state.trip_loco[i] == NONE) != (trip_id in canceled):
            problems.append(f"trip {trip_id}: trip_loco e i cancellati non concordano")

    for j, loco_id in enumerate(state.locos):
        if state.loco_station[j] == NONE:
            continue
        sequence = state.loco_sequence(j)
        if not sequence:
            continue
        first = sequence[0]
        dh    = first * state.max_dh
        start = state.dh_origin[dh] if state.dh_used[dh] else state.trip_origin[first]
        if start != state.loco_station[j]:
            problems.append(f"loco {loco_id}: la catena parte da {start} ma la loco e' a "
                            f"{state.loco_station[j]}")

    return problems


def check_break_against_validator(state: ScheduleState) -> list:
    from validator.CrewChecks import idle_windows, required_break_length

    problems = []
    for driver in range(len(state.drivers)):
        if not state.duty_tasks_list[driver]:
            continue
        status   = state.mapper.driver_status[state.drivers[driver]]
        chain    = state.duty_tasks(driver)
        length   = state.duty_len[driver]
        required = required_break_length(status, length)
        windows  = idle_windows(status, state.net, chain, length)
        holds    = required == 0 or any(capacity >= required for _, _, capacity in windows)
        if holds != state.break_ok(driver):
            problems.append(f"turno {driver}: break_ok={state.break_ok(driver)} "
                            f"validatore={holds} (richiesti {required} min, "
                            f"capacita' massima {max([c for _, _, c in windows], default=0):.1f})")
    return problems


def check_overlap_against_validator(state: ScheduleState) -> list:
    from validator.LocoChecks import check_loco_chaining

    problems = []
    for loco_index, loco_id in enumerate(state.locos):
        chain = [state.task_as_dict(task) for task in state.loco_chain(loco_index)]
        messages = [m for m in check_loco_chaining(loco_id, chain) if "time overlap" in m]
        pairs = sum(1 for before, after in zip(state.loco_chain(loco_index),
                                               state.loco_chain(loco_index)[1:])
                    if state.task_arr(before) > state.task_dep(after))
        if pairs != len(messages):
            problems.append(f"loco {loco_id}: {pairs} coppie sovrapposte ma il validatore "
                            f"ne segnala {len(messages)}")
        minutes = sum(float(m.split("time overlap of ")[1].split(" min")[0]) for m in messages)
        if abs(minutes - state.loco_overlap(loco_index)) > 1e-6:
            problems.append(f"loco {loco_id}: {state.loco_overlap(loco_index):.1f} min di "
                            f"sovrapposizione ma il validatore ne somma {minutes:.1f}")
    return problems


def check_violations_against_validator(state: ScheduleState) -> list:
    from validator.CrewChecks import check_duty_length, check_initial_position

    from costs.DutyWalk import walk

    problems = []
    for driver in range(len(state.drivers)):
        if not state.duty_tasks_list[driver]:
            continue
        driver_id = state.drivers[driver]
        chain     = state.duty_tasks(driver)

        flagged = bool(check_duty_length(driver_id, state.mapper, state.net, chain))
        if flagged != (state.duty_excess[driver] > 0):
            problems.append(f"turno {driver}: duty_excess={state.duty_excess[driver]:.1f} "
                            f"ma il validatore {'' if flagged else 'non '}segnala il turno")

        first = next(walk(state, driver))
        late  = first[8] is None or first[8] < 0
        if bool(check_initial_position(driver_id, state.mapper, state.net, chain)) != late:
            problems.append(f"turno {driver}: primo link gap={first[8]} ma il validatore dice "
                            f"il contrario")
    return problems


VALIDATOR_FAMILIES = {
    "loco_unreachable_links": ("unreachable loco_deadhead",),
    "maintenance_excess_km": ("km between maintenances",),
    "maintenance_time_minutes": ("maintenance at departure needs",
                                 "maintenance at destination needs",
                                 "not a maintenance station"),
    "loco_overlap_minutes":  ("time overlap", "before being available", "reaching"),
    "duty_excess_minutes":   ("exceeds",),
    "break_shortfall":       ("requires a", "break ["),
    "unreachable_links":     ("no path", "unreachable crew_deadhead"),
    "continuity_minutes":    ("but the driver is free only at", "needs",
                              "but only", "time overlap"),
}

UNMEASURED_FAMILIES = ("spatial gap",)

INF_MAINTENANCE = "inf km between maintenances"


def classify(messages: list) -> dict:
    found = {name: [] for name in VALIDATOR_FAMILIES}
    found["non classificati"] = []
    found[INF_MAINTENANCE]    = []
    for message in messages:
        if any(hint in message for hint in UNMEASURED_FAMILIES):
            continue
        if INF_MAINTENANCE in message:
            found["loco_unreachable_links"].append(message)
            found[INF_MAINTENANCE].append(message)
            continue
        crew = message.startswith("driver")
        for name, hints in VALIDATOR_FAMILIES.items():
            is_crew_family = name in ("duty_excess_minutes", "break_shortfall",
                                      "unreachable_links", "continuity_minutes")
            if crew != is_crew_family:
                continue
            if any(hint in message for hint in hints):
                found[name].append(message)
                break
        else:
            found["non classificati"].append(message)
    return found


def check_components_against_validator(state: ScheduleState, manager: ScheduleManager,
                                       instance, mapper, net) -> list:
    from validator.CrewChecks import compute_crew_violations
    from validator.LocoChecks import compute_loco_violations

    solution = manager.to_solution(state, {"instance_id": "check"})
    messages = (compute_loco_violations(instance, net, solution)
                + compute_crew_violations(mapper, net, solution))
    found    = classify(messages)
    cost     = manager.cost_function_components(state)
    declared = {component.name: cost.all_components[index]
                for index, component in enumerate(manager.components)}

    problems = [f"messaggio che nessuna componente misura: {m}"
                for m in found.pop("non classificati")]
    if found.pop(INF_MAINTENANCE):
        found.pop("maintenance_excess_km")
    for name, family in found.items():
        value = declared[name]
        if bool(family) != (value > 0):
            problems.append(f"{name}={value:.1f} ma il validatore ne segnala "
                            f"{len(family)}: {family[:1]}")
    return problems


def reference_penalties(state: ScheduleState) -> dict:
    return {"continuity_minutes":    sum(state.duty_continuity),
            "unreachable_links":     sum(state.duty_unreachable),
            "duty_excess_minutes":   sum(state.duty_excess),
            "break_shortfall":       sum(state.duty_break_short),
            "maintenance_excess_km": state._maint_excess}


def reference_violations(state: ScheduleState, w: PenaltyWeights = PenaltyWeights()) -> float:
    totals = reference_penalties(state)
    return (w.continuity        * totals["continuity_minutes"]
            + w.unreachable     * totals["unreachable_links"]
            + w.duty_excess     * totals["duty_excess_minutes"]
            + w.break_shortfall * totals["break_shortfall"]
            + w.maintenance_km  * totals["maintenance_excess_km"])


def feasible_random_move(state: ScheduleState, rng, weights: tuple):
    while True:
        move = random_move(state, rng, weights)
        if move is not None and move.feasible(state):
            return move


def stress_moves(state: ScheduleState, manager: ScheduleManager, rng, rounds: int,
                 weights: tuple = None) -> tuple:
    problems = []
    kinds    = {}
    for _ in range(rounds):
        move    = feasible_random_move(state, rng, weights)
        before  = state.snapshot()
        inverse = move.make_move(state)
        kinds[type(move).__name__] = kinds.get(type(move).__name__, 0) + 1
        problems += [f"{move}: check_consistency {p}" for p in manager.check_consistency(state)]
        inverse.make_move(state)
        if state.snapshot() != before:
            problems.append(f"{move}: undo non ha ripristinato lo stato")
        if problems:
            break
    return problems, kinds


def stress_sequence(state: ScheduleState, manager: ScheduleManager, rng,
                    length: int, weights: tuple = None) -> list:
    inverses = []
    for _ in range(length):
        inverses.append(feasible_random_move(state, rng, weights).make_move(state))
    problems = [f"dopo {len(inverses)} mosse: check_consistency {p}"
                for p in manager.check_consistency(state)]
    for inverse in reversed(inverses):
        inverse.make_move(state)
    return problems


def cover_tasks(state: ScheduleState, trip: int, plan: tuple) -> list:
    own, following, after = plan
    return ([-(trip * state.max_dh + k) - 1 for k in range(len(own))] + [trip]
            + [-(following * state.max_dh + k) - 1 for k in range(len(after))])


def cover_cost(state: ScheduleState, manager: ScheduleManager, move: CoverTrip):
    undo = move.make_move(state)
    cost = manager.cost_function_components(state)
    undo.make_move(state)
    return cost


def cascade_by_cost(state: ScheduleState, manager: ScheduleManager, trip: int, loco: int,
                    n: int) -> tuple:
    chosen = ()
    for k in range(n):
        best = None
        for driver in range(len(state.drivers)):
            move = CoverTrip(trip, loco, chosen + (driver,) * (n - k))
            cost = cover_cost(state, manager, move)
            if best is None or cost.beats_best(best[0]):
                best = (cost, driver)
        chosen += (best[1],)
    return chosen, best[0]


def descend_cover_drivers(state: ScheduleState, manager: ScheduleManager, tasks: list) -> tuple:
    current  = manager.cost_function_components(state)
    inverses = []
    improved = True
    while improved:
        improved = False
        for task in tasks:
            for driver in range(len(state.drivers)):
                move = ChangeDriver(task, state.task_driver(task), driver)
                if not move.feasible(state):
                    continue
                inverse   = move.make_move(state)
                candidate = manager.cost_function_components(state)
                if candidate.beats_best(current):
                    current, improved = candidate, True
                    inverses.append(inverse)
                else:
                    inverse.make_move(state)
    return current, inverses


def check_decomposition(state: ScheduleState, manager: ScheduleManager, rng, trips: int) -> list:
    candidates = [i for i in range(len(state.trip_order))
                  if state.trip_loco[i] == NONE and state.trip_plan_loco[i] != NONE
                  and state.cover_plan(i, state.trip_plan_loco[i]) is not None]
    problems  = []
    not_worse = 0
    tried     = 0
    for _ in range(min(trips, len(candidates))):
        tried  += 1
        trip    = candidates.pop(rng.uniform_int(0, len(candidates) - 1))
        loco    = state.trip_plan_loco[trip]
        plan    = state.cover_plan(trip, loco)
        tasks   = cover_tasks(state, trip, plan)
        before  = state.snapshot()
        _, cascade = cascade_by_cost(state, manager, trip, loco, len(tasks))

        undo_cover    = CoverTrip(trip, loco, random_drivers(state, rng, len(tasks))).make_move(state)
        random_cost   = manager.cost_function_components(state)
        final, inverses = descend_cover_drivers(state, manager, tasks)
        for inverse in reversed(inverses):
            inverse.make_move(state)
        undo_cover.make_move(state)
        if state.snapshot() != before:
            problems.append(f"trip {state.trip_order[trip]}: undo non ha ripristinato lo stato")
            break

        worse      = cascade.beats_best(final)
        not_worse += not worse
        print(f"  trip {state.trip_order[trip]} ({len(tasks)} segmenti): a caso {random_cost.total:.1f}"
              f" -> discesa {final.total:.1f} (viol {final.violations:.1f})  cascata per costo "
              f"{cascade.total:.1f} (viol {cascade.violations:.1f})"
              f"{'  PEGGIORE' if worse else ''}")
    print(f"  decomposizione non peggiore della cascata per costo: {not_worse}/{tried}")
    return problems


def compare_with_evaluator(result, mapper, net, instance_id: str, loco_checker=None) -> list:
    from SolutionEvaluator import SolutionEvaluator

    state     = ScheduleState.from_solve_result(result, mapper, net, loco_checker=loco_checker)
    evaluator = SolutionEvaluator(mapper, net)
    manager   = ScheduleManager.default(evaluator)
    expected  = evaluator.evaluate_components(result.canceled_tasks,
                                              result.dh_stats["loco_dh_m"],
                                              result.dh_stats["crew_dh_m"],
                                              result.existing_duties)
    cost  = manager.cost_function_components(state)
    value = {component.name: component.compute(state) for component in manager.components}

    weighted = {component.name: cost.all_components[index]
                for index, component in enumerate(manager.components)}
    overdue  = weighted["maintenance_overdue_km"]
    overlap  = weighted["loco_overlap_minutes"]
    unknown  = weighted["loco_unreachable_links"]
    maint_t  = weighted["maintenance_time_minutes"]

    pairs = [("n_canceled", value["cancellations"],            expected.n_canceled),
             ("loco_dh_m",  value["loco_deadhead_km"] * 1000,  expected.loco_dh_m),
             ("crew_dh_m",  value["crew_deadhead_km"] * 1000,  expected.crew_dh_m),
             ("back_home",  value["back_home"] * 1000,         expected.back_home),
             ("total",      cost.objective - overdue,          expected.total),
             ("violations", cost.violations - overlap - unknown - maint_t,
                                                              reference_violations(state))]

    problems = [f"{name}: manager={value_} riferimento={reference}"
                for name, value_, reference in pairs if abs(value_ - reference) > 1e-6]
    if abs(sum(cost.all_components) - cost.total) > 1e-6:
        problems.append(f"all_components somma {sum(cost.all_components)} "
                        f"invece di {cost.total}")
    problems += [f"check_consistency: {p}" for p in manager.check_consistency(state)]
    problems += [f"overlap: {p}" for p in check_overlap_against_validator(state)]
    problems += [f"break: {p}" for p in check_break_against_validator(state)]
    problems += [f"array: {p}" for p in check_arrays(state, result)]

    with_plan = sum(1 for i in range(len(state.trip_order))
                    if state.trip_loco[i] == NONE and state.trip_plan_loco[i] != NONE)
    print(f"  loco con posizione iniziale nota={sum(1 for x in state.loco_station if x != NONE)}"
          f"/{len(state.locos)}  cancellati con loco di piano={with_plan}")
    print(f"  array: {len(state.trip_order)} trip, {len(state.locos)} loco, "
          f"{len(state.drivers)} driver, MAX_DH={state.max_dh}, "
          f"deadhead in uso={sum(state.dh_used)}, cancellati={state.n_canceled}")
    print(f"[{instance_id}] turni usati={sum(1 for tasks in state.duty_tasks_list if tasks)} "
          f"turni con violazioni={len(state.duties_with_violations())}")
    for name, value_, reference in pairs:
        flag = "OK " if abs(value_ - reference) <= 1e-6 else "DIFF"
        print(f"  {flag} {name:<11} manager={value_:>14.3f}  riferimento={reference:>14.3f}")

    worst = max(abs(value_ - reference) for _, value_, reference in pairs)
    print(f"  differenza massima fra manager e riferimento (senza i termini F2): {worst:.3e}")
    print(f"  termini nuovi di F2: maintenance_overdue_km="
          f"{value['maintenance_overdue_km']:.1f} km -> {overdue:.1f}  "
          f"loco_overlap_minutes={value['loco_overlap_minutes']:.1f} min -> {overlap:.1f}  "
          f"loco_unreachable_links={value['loco_unreachable_links']:.0f} -> {unknown:.1f}")
    print("  componenti: " + "  ".join(
        f"{component.name}={cost.all_components[index]:g}"
        for index, component in enumerate(manager.components)))
    print(f"  cost: {cost}")
    return problems


if __name__ == "__main__":
    import RunConfig
    from rescheduling import IntegratedRescheduling as IR

    parser = argparse.ArgumentParser(
        description="Costruisce lo ScheduleState dalla soluzione greedy e verifica che "
                    "riproduca esattamente i quattro termini di SolutionEvaluator.")
    parser.add_argument("-i", "--instance", nargs="+", required=True)
    parser.add_argument("-seed", type=int, default=42)
    parser.add_argument("--no-maintenance", action="store_true", dest="no_maintenance")
    parser.add_argument("--moves", type=int, default=200, metavar="N",
                        help="mosse casuali da esercitare: ognuna applicata, verificata e disfatta")
    parser.add_argument("--sequence", type=int, default=20, metavar="K",
                        help="lunghezza della sequenza di mosse da applicare in fila prima di "
                             "verificare lo stato e disfarla tutta")
    parser.add_argument("-move-seed", type=int, default=7)
    parser.add_argument("--radius-km", type=float, default=None, dest="radius_km", metavar="KM",
                        help="bias: la mossa pesca un driver la cui posizione prima di quella "
                             "partenza sta entro KM dall'origine del task. Senza candidati vicini "
                             "ripesca fra tutti, quindi il vicinato resta intero")
    parser.add_argument("-move-weights", type=float, nargs=5, default=None, dest="move_weights",
                        metavar=("CD", "SWAP", "COVER", "UNCOVER", "CL"),
                        help="peso di ChangeDriver, SwapTasks, CoverTrip, UncoverTrip, ChangeLoco "
                             "nella pesca casuale; 0 esclude la mossa. Default uniforme")
    parser.add_argument("--sample", type=int, default=200, metavar="N",
                        help="mosse casuali provate prima di dichiarare un minimo locale")
    parser.add_argument("--descend", action="store_true",
                        help="esegue una discesa first-improvement dalla soluzione greedy")
    parser.add_argument("-violations", type=int, default=0, metavar="N",
                        help="sabota lo stato con N mosse casuali, stampa i print_violations di "
                             "ogni componente e confronta le violazioni di turno coi controlli "
                             "del validatore")
    parser.add_argument("-overlap", action="store_true",
                        help="sabota lo stato mettendo una seconda locomotiva su un viaggio che "
                             "si sovrappone al primo, e confronta LocoOverlap col validatore")
    parser.add_argument("-cover-validator", type=int, default=0, metavar="N",
                        dest="cover_validator",
                        help="applica N mosse di copertura casuali, una alla volta, e per ognuna "
                             "confronta le componenti hard coi messaggi del validatore sulla "
                             "soluzione esportata")
    parser.add_argument("--cover", type=int, default=0, metavar="N",
                        help="N iterazioni di shake+discesa: copre un trip cancellato a caso con la "
                             "loco del piano, lascia che la discesa assegni i driver, e tiene il "
                             "risultato solo se il costo migliora")
    parser.add_argument("-decomposition", type=int, default=0, metavar="N",
                        help="su N trip cancellati confronta CoverTrip con driver a caso seguita "
                             "da una discesa di ChangeDriver sui suoi segmenti con la cascata che "
                             "sceglie i driver per costo")
    RunConfig.add_path_args(parser)
    args = parser.parse_args()

    RunConfig.resolve(args, parser).apply_to(IR)

    failed = []
    for instance_id in args.instance:
        instance, mapper, net, dis_start, dis_end = IR.setup_instance(instance_id)
        result = IR.solve_instance(instance, mapper, net, dis_start, dis_end, args.seed,
                                   ignore_maintenance=args.no_maintenance)
        from rescheduling.LocoChecker import LocoChecker
        loco_checker = LocoChecker(instance, net, ignore_maintenance=args.no_maintenance)
        problems = compare_with_evaluator(result, mapper, net, instance_id, loco_checker)

        if args.moves or args.sequence:
            from rescheduling.RollingStockGreedy import CppMT19937
            from SolutionEvaluator import SolutionEvaluator
            state  = ScheduleState.from_solve_result(result, mapper, net,
                                                     loco_checker=loco_checker)
            rng    = CppMT19937(args.move_seed)
            before = state.snapshot()
            t0 = time.time()
            manager       = ScheduleManager.default(SolutionEvaluator(mapper, net))
            move_problems, kinds = stress_moves(state, manager, rng, args.moves,
                                                args.move_weights)
            per_second    = args.moves / max(1e-9, time.time() - t0)
            seq_problems  = stress_sequence(state, manager, rng, args.sequence,
                                            args.move_weights)
            restored = state.snapshot() == before
            print(f"  mosse esercitate={args.moves} ({per_second:.0f}/s, verifica inclusa) "
                  f"per tipo {kinds} sequenza={args.sequence} "
                  f"stato finale {'invariato' if restored else 'DIVERSO dal costruito'}")
            problems += move_problems + seq_problems
            if not restored:
                problems.append("lo stato dopo le mosse non coincide con quello costruito")

        if args.descend:
            from rescheduling.RollingStockGreedy import CppMT19937
            from SolutionEvaluator import SolutionEvaluator
            state     = ScheduleState.from_solve_result(result, mapper, net,
                                                        loco_checker=loco_checker)
            manager   = ScheduleManager.default(SolutionEvaluator(mapper, net))
            start     = manager.cost_function_components(state)
            t0        = time.time()
            final, steps = descend(state, manager, CppMT19937(args.move_seed),
                                   sample=args.sample, radius_km=args.radius_km,
                                   weights=args.move_weights)
            print(f"  discesa: {steps} mosse accettate in {time.time() - t0:.1f}s")
            print(f"    da  {start}")
            print(f"    a   {final}")
            problems += [f"discesa: check_consistency {p}"
                         for p in manager.check_consistency(state)]
            problems += [f"discesa: break {p}" for p in check_break_against_validator(state)]

        if args.violations:
            from rescheduling.RollingStockGreedy import CppMT19937
            from SolutionEvaluator import SolutionEvaluator
            state   = ScheduleState.from_solve_result(result, mapper, net,
                                                      loco_checker=loco_checker)
            manager = ScheduleManager.default(SolutionEvaluator(mapper, net))
            rng     = CppMT19937(args.move_seed)
            for _ in range(args.violations):
                feasible_random_move(state, rng, args.move_weights).make_move(state)
            print(f"\n  stato sabotato con {args.violations} mosse casuali: "
                  f"{manager.cost_function_components(state)}")
            manager.print_violations(state, sys.stdout)
            problems += [f"sabotato: check_consistency {p}"
                         for p in manager.check_consistency(state)]
            problems += [f"sabotato: break {p}" for p in check_break_against_validator(state)]
            problems += [f"sabotato: {p}" for p in check_violations_against_validator(state)]

        if args.overlap:
            from SolutionEvaluator import SolutionEvaluator
            state   = ScheduleState.from_solve_result(result, mapper, net,
                                                      loco_checker=loco_checker)
            manager = ScheduleManager.default(SolutionEvaluator(mapper, net))
            index   = manager.cost_component_index("loco_overlap_minutes")
            before  = manager.cost_function_components(state)
            victim  = None
            for a in range(len(state.trip_order)):
                if state.trip_loco[a] == NONE:
                    continue
                for b in range(len(state.trip_order)):
                    if b == a or state.trip_loco[b] in (NONE, state.trip_loco[a]):
                        continue
                    if (state.trip_dep[b] < state.trip_arr[a]
                            and state.trip_dep[a] < state.trip_arr[b]):
                        victim = (a, b)
                        break
                if victim:
                    break
            if victim is None:
                problems.append("overlap: nessuna coppia di viaggi sovrapposti da sabotare")
            else:
                a, b = victim
                print(f"\n  sabotaggio: trip {state.trip_order[b]} passa dalla loco "
                      f"{state.locos[state.trip_loco[b]]} alla loco "
                      f"{state.locos[state.trip_loco[a]]}, che opera il trip "
                      f"{state.trip_order[a]} nello stesso intervallo")
                state.trip_loco[b] = state.trip_loco[a]
                state._recompute_coverage()
                after = manager.cost_function_components(state)
                print(f"    loco_overlap_minutes {before.all_components[index]:.1f} -> "
                      f"{after.all_components[index]:.1f}")
                manager.get_cost_component(index).print_violations(state, sys.stdout)
                if after.all_components[index] <= before.all_components[index]:
                    problems.append("overlap: il sabotaggio non ha fatto salire LocoOverlap")
                problems += [f"overlap sabotato: {p}"
                             for p in check_overlap_against_validator(state)]

        if args.cover_validator:
            from rescheduling.RollingStockGreedy import CppMT19937
            from SolutionEvaluator import SolutionEvaluator
            state   = ScheduleState.from_solve_result(result, mapper, net,
                                                      loco_checker=loco_checker)
            manager = ScheduleManager.default(SolutionEvaluator(mapper, net))
            rng     = CppMT19937(args.move_seed)
            start   = check_components_against_validator(state, manager, instance, mapper, net)
            problems += [f"partenza: {p}" for p in start]
            print(f"  punto di partenza: componenti e validatore "
                  f"{'concordi' if not start else 'DISCORDI'}")
            agreed = 0
            for _ in range(args.cover_validator):
                move    = feasible_random_move(state, rng, (0, 0, 1, 1, 1))
                before  = state.snapshot()
                inverse = move.make_move(state)
                found   = check_components_against_validator(state, manager, instance,
                                                             mapper, net)
                agreed += not found
                problems += [f"{move}: {p}" for p in found]
                inverse.make_move(state)
                if state.snapshot() != before:
                    problems.append(f"{move}: undo non ha ripristinato lo stato")
                    break
            print(f"  {agreed}/{args.cover_validator} mosse di copertura con componenti e "
                  f"validatore concordi")

        if args.cover:
            from rescheduling.RollingStockGreedy import CppMT19937
            from SolutionEvaluator import SolutionEvaluator
            from rescheduling.LocoChecker import LocoChecker
            state     = ScheduleState.from_solve_result(result, mapper, net,
                                                        loco_checker=loco_checker)
            manager   = ScheduleManager.default(SolutionEvaluator(mapper, net))
            start     = manager.cost_function_components(state)
            canceled  = state.n_canceled
            t0        = time.time()
            final, covered, attempted = cover_search(
                state, manager, CppMT19937(args.move_seed), iterations=args.cover,
                sample=args.sample, radius_km=args.radius_km, weights=args.move_weights)
            print(f"  copertura: {covered} trip recuperati su {attempted} tentativi "
                  f"in {time.time() - t0:.1f}s")
            print(f"    da  cancellati={canceled}  {start}")
            print(f"    a   cancellati={state.n_canceled}  {final}")
            problems += [f"copertura: check_consistency {p}"
                         for p in manager.check_consistency(state)]
            problems += [f"copertura: break {p}" for p in check_break_against_validator(state)]

        if args.decomposition:
            from rescheduling.RollingStockGreedy import CppMT19937
            from SolutionEvaluator import SolutionEvaluator
            state   = ScheduleState.from_solve_result(result, mapper, net,
                                                      loco_checker=loco_checker)
            manager = ScheduleManager.default(SolutionEvaluator(mapper, net))
            problems += check_decomposition(state, manager, CppMT19937(args.move_seed),
                                            args.decomposition)
            problems += [f"decomposizione: check_consistency {p}"
                         for p in manager.check_consistency(state)]

        failed += [f"{instance_id}: {p}" for p in problems]

    if failed:
        print("\nDIFFERENZE:")
        for problem in failed:
            print(f"  {problem}")
        sys.exit(1)
    print("\nTutti i termini coincidono con SolutionEvaluator.")
