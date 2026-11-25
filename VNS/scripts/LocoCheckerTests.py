from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rescheduling.LocoChecker import LOCO_DEADHEAD_SPEED_KMH, LocoChecker, _epoch_to_minutes


def loco_before_trip(checker: LocoChecker, loco_id: int, trip_id: int) -> tuple:
    net        = checker._net
    trip_dep   = net.trips_by_id[trip_id]['departure_time']
    committed  = checker._loco_trips.get(loco_id, [])
    prev_trips = [t for t in committed if net.trips_by_id[t]['departure_time'] <= trip_dep]
    if not prev_trips:
        return (checker._loco_init[loco_id]['station'],
                _epoch_to_minutes(checker._loco_init[loco_id]['avail_time']))
    prev = max(prev_trips, key=lambda t: net.trips_by_id[t]['departure_time'])
    return (net.sections[net.trips_by_id[prev]['section']]['destination'],
            _epoch_to_minutes(net.trips_by_id[prev]['arrival_time']))


def every_pair(checker: LocoChecker):
    net = checker._net
    for loco_id in checker._usable_loco_ids:
        for trip_id in checker.trip_order:
            trip      = net.trips_by_id[trip_id]
            origin    = net.sections[trip['section']]['origin']
            departure = _epoch_to_minutes(trip['departure_time'])
            station, ready = loco_before_trip(checker, loco_id, trip_id)
            yield loco_id, trip_id, station, ready, origin, departure


def check_segments(checker: LocoChecker, max_duty_length: int) -> tuple:
    net      = checker._net
    problems = []
    counts   = {"stessa stazione": 0, "senza percorso": 0, "un segmento": 0,
                "spezzate": 0, "deviate": 0, "in ritardo, scritte": 0,
                "piu' lunghi del peso": 0}

    for loco_id, trip_id, station, ready, origin, departure in every_pair(checker):
        minutes, segments = checker.deadhead_route(station, ready, origin, departure,
                                                   max_duty_length)
        where = f"loco {loco_id} trip {trip_id} {station}->{origin}"

        if station == origin:
            counts["stessa stazione"] += 1
            if (minutes, segments) != (0.0, []):
                problems.append(f"{where}: stessa stazione ma {minutes}, {segments}")
            continue
        if minutes == float("inf"):
            counts["senza percorso"] += 1
            if segments is not None:
                problems.append(f"{where}: nessun percorso ma {segments}")
            continue

        detour = net.deadhead_detour(station, origin, ready, departure,
                                     speed_kmh=LOCO_DEADHEAD_SPEED_KMH)[1]
        if detour is not None:
            counts["deviate"] += 1
        counts["spezzate" if len(segments) > 1 else "un segmento"] += 1
        if segments[-1]["arrival"] > departure:
            counts["in ritardo, scritte"] += 1

        if segments[0]["origin"] != station or segments[-1]["destination"] != origin:
            problems.append(f"{where}: i segmenti vanno da {segments[0]['origin']} a "
                            f"{segments[-1]['destination']}")
        if abs(segments[0]["departure"] - ready) > 1e-6:
            problems.append(f"{where}: il primo segmento parte a "
                            f"{segments[0]['departure']} invece di {ready}")
        for before, after in zip(segments, segments[1:]):
            if before["destination"] != after["origin"]:
                problems.append(f"{where}: salto fra {before['destination']} e "
                                f"{after['origin']}")
            if abs(before["arrival"] - after["departure"]) > 1e-6:
                problems.append(f"{where}: buco di tempo fra {before['arrival']} e "
                                f"{after['departure']}")
        travelled = segments[-1]["arrival"] - segments[0]["departure"]
        # i segmenti non possono durare meno del percorso; durare di piu' e'
        # ammesso, perche' i loro km vengono dalle sezioni mentre dh_min viene
        # dal peso della matrice, che sul percorso di riserva non coincide
        if travelled < minutes - 1.0:
            problems.append(f"{where}: i segmenti durano {travelled:.3f} min ma il "
                            f"percorso ne chiede {minutes:.3f}")
        counts["piu' lunghi del peso"] += travelled > minutes + 1.0
        if len(segments) > 1:
            longest = max(s["arrival"] - s["departure"] for s in segments)
            if longest > max_duty_length + 1e-6 and len(segments) < len(net.sections):
                problems.append(f"{where}: segmento di {longest:.1f} min oltre "
                                f"{max_duty_length}, spezzato in {len(segments)}")
    return problems, counts


def check_tasks_against_route(checker: LocoChecker, max_duty_length: int) -> list:
    problems = []
    for loco_id, trip_id, station, ready, origin, departure in every_pair(checker):
        minutes, segments = checker.deadhead_route(station, ready, origin, departure,
                                                   max_duty_length)
        expected = (None if minutes == float("inf")
                    or (station != origin and segments[-1]["arrival"] > departure)
                    else segments)
        got = checker.deadhead_tasks(loco_id, trip_id, _epoch_to_minutes, max_duty_length)
        if got != expected:
            problems.append(f"loco {loco_id} trip {trip_id}: deadhead_tasks {got} "
                            f"invece di {expected}")
    return problems


if __name__ == "__main__":
    import RunConfig
    from rescheduling import IntegratedRescheduling as IR

    parser = argparse.ArgumentParser(
        description="Verifica i segmenti di deadhead_route su ogni coppia (loco, trip): catena "
                    "continua nello spazio e nel tempo, durata non inferiore al percorso, "
                    "spezzatura sotto la soglia. E che deadhead_tasks sia deadhead_route piu' "
                    "il rifiuto del ritardo.")
    parser.add_argument("-i", "--instance", nargs="+", required=True)
    parser.add_argument("-max-duty", type=int, default=360, dest="max_duty")
    RunConfig.add_path_args(parser)
    args = parser.parse_args()
    RunConfig.resolve(args, parser).apply_to(IR)

    failed = []
    for instance_id in args.instance:
        instance, mapper, net, dis_start, dis_end = IR.setup_instance(instance_id)
        checker = LocoChecker(instance, net)
        problems, counts = check_segments(checker, args.max_duty)
        problems += check_tasks_against_route(checker, args.max_duty)
        pairs = len(checker._usable_loco_ids) * len(checker.trip_order)
        print(f"[{instance_id}] coppie={pairs}  " +
              "  ".join(f"{name}={value}" for name, value in counts.items()))
        for p in problems[:10]:
            print(f"  PROBLEMA: {p}")
        if problems:
            failed.append(instance_id)

    if failed:
        print(f"FALLITO su {failed}")
        sys.exit(1)
    print("i segmenti sono coerenti su tutte le coppie")
