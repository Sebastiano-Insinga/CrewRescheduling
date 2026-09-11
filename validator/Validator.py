
import argparse

import os

import IntegratedRescheduling as IR
import RunConfig
from IntegratedRescheduling import setup_instance
from validator.Helper import describe
from validator.Solution import Solution, TRIP, LOCO_DEADHEAD, CREW_DEADHEAD
from validator.CrewChecks import compute_crew_violations
from validator.LocoChecks import compute_loco_violations


def open_trips(instance):
    dis_start = instance['disruption_start']
    dis_end   = instance['disruption_end']
    disrupted_sections = set(instance.get('disrupted_sections', []))

    every     = {t['id'] for t in instance['train_sections']}
    completed = {t['id'] for t in instance['train_sections']
                 if t['departure_time'] < dis_start}
    disrupted = {t['id'] for t in instance['train_sections']
                 if t['section'] in disrupted_sections
                 and t['departure_time'] <= dis_end
                 and t['arrival_time']   >= dis_start}

    return every - completed - disrupted


def compute_structure_violations(instance, sol):

    violations = []

    assigned  = [a['trip_id'] for a in sol.assignments if a['type'] == TRIP]
    canceled  = set(sol.canceled)
    to_cover  = open_trips(instance)

    # --- coverage: every open trip lands in exactly one of the two places
    missing = to_cover - set(assigned) - canceled
    if missing:
        violations.append(f"{len(missing)} open trips are neither assigned nor "
                          f"canceled: {sorted(missing)}")

    extra = set(assigned) - to_cover
    if extra:
        violations.append(f"{len(extra)} assigned trips were not open for "
                          f"rescheduling: {sorted(extra)}")

    both = set(assigned) & canceled
    if both:
        violations.append(f"{len(both)} trips are assigned and canceled at the "
                          f"same time: {sorted(both)}")

    # a set would hide this: the same trip pulled by two locomotives
    seen = set()
    for trip_id in assigned:
        if trip_id in seen:
            locos = [a['locomotive'] for a in sol.assignments
                     if a['type'] == TRIP and a['trip_id'] == trip_id]
            violations.append(f"trip {trip_id} is assigned {len(locos)} times, "
                              f"to locomotives {locos}")
        seen.add(trip_id)

    # --- field consistency, one pass over every assignment
    for a in sol.assignments:
        kind = a['type']
        if kind not in (TRIP, LOCO_DEADHEAD, CREW_DEADHEAD):
            violations.append(f"unknown assignment type {kind!r} — {describe(a)}")
            continue
        if a['arrival'] < a['departure']:
            violations.append(f"arrival before departure — {describe(a)}")
        if (a['trip_id'] is None) == (kind == TRIP):
            violations.append(f"trip_id is {a['trip_id']!r} on a {kind} — {describe(a)}")
        if (a['locomotive'] is None) != (kind == CREW_DEADHEAD):
            violations.append(f"locomotive is {a['locomotive']!r} on a {kind} "
                              f"— {describe(a)}")

    return violations


def compute_cross_violations(instance, sol):
    """TODO: every trip and loco_deadhead has a driver; a driver riding a loco
    shares its times. Loco and crew are validated by two separate checkers,
    their coupling by neither.
    """
    return []


def compute_disruption_violations(instance, net, sol, dis_start, dis_end):
    """TODO: no trip on a disrupted section inside the disruption window;
    disrupted trips are canceled or absent; deadheads crossing the window use
    the disrupted shortest paths.
    """
    return []


def validator(instance, mapper, net, sol, dis_start, dis_end):
    """Prints every violation found and returns True when none is found."""
    checks = [
        ("structure",  compute_structure_violations(instance, sol)),
        ("crew",       compute_crew_violations(mapper, net, sol)),
        ("loco",       compute_loco_violations(instance, net, sol)),
        ("cross",      compute_cross_violations(instance, sol)),
        ("disruption", compute_disruption_violations(instance, net, sol, dis_start, dis_end)),
    ]

    feasible = True
    for label, violations in checks:
        for msg in violations:
            feasible = False
            print(f"[{label}] {msg}")

    feasibility = "FEASIBLE" if feasible else "INFEASIBLE"
    print(f"Instance: {sol.run_info.get('instance_id')}, Solution: {sol.name}, "
          f"Solution is {feasibility}, Obj={sol.run_info.get('objective')}, "
          f"canceled={len(sol.canceled)}")
    return feasible


def main():
    parser = argparse.ArgumentParser(description="Validate an integrated rescheduling solution")
    parser.add_argument("-solution", "-s", type=str, required=True,
                        help="Path to the solution JSON file, e.g. "
                             "VNS/solutions/S01_k10_random_seed42_vns42.json")
    parser.add_argument("-instance", "-i", type=str, default=None,
                        help="Instance id, e.g. S01. Only needed when run_info "
                             "does not carry instance_id")
    RunConfig.add_path_args(parser)
    args = parser.parse_args()

    sol = Solution()
    sol.from_file(args.solution)

    instance_id = args.instance or sol.run_info.get('instance_id')
    if instance_id is None:
        parser.error(f"no instance_id in {args.solution}, pass it with -i")

    # Una soluzione prodotta dopo l'introduzione di RunConfig porta con se' le
    # directory da cui e' nata: validarla contro altre directory confronta due
    # cose diverse senza dirlo. Se il run_info le ha e la CLI tace, si usano
    # quelle; se la CLI le passa e divergono, lo si segnala.
    recorded = {k: sol.run_info.get(k) for k in
                ('instance_dir', 'crew_schedule_dir', 'crew_task_dir', 'id_mapping_dir')}
    for attr, value in recorded.items():
        if value and getattr(args, attr, None) is None and not args.chain:
            setattr(args, attr, value)
    if recorded.get('instance_dir') and args.instance_dir != recorded['instance_dir']:
        print(f"[attenzione] la soluzione dice instance_dir={recorded['instance_dir']!r}, "
              f"la stai validando con {args.instance_dir!r}")

    # setup_instance rilegge queste globali dal proprio modulo: riassegnare il
    # nome importato qui sopra non basterebbe, "from ... import" ne crea una
    # copia locale scollegata dal modulo di origine.
    run_paths = RunConfig.resolve(args, parser)
    run_paths.apply_to(IR)

    problems = RunConfig.validate_chain(run_paths, [instance_id])
    if problems:
        parser.error("catena crew incoerente:\n  " + "\n  ".join(problems))

    instance, mapper, net, dis_start, dis_end = setup_instance(instance_id)

    return validator(instance, mapper, net, sol, dis_start, dis_end)


if __name__ == "__main__":
    main()
