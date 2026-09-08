"""Export dei risultati VNS.

Tre livelli di granularità:
  - `export_vns_csv`        → una riga per istanza (risultato finale)
  - `export_iterations_csv` → una riga per iterazione (traiettoria di ricerca)
  - `export_solution_json`  → la soluzione completa, per il validatore

Convenzione condivisa con il resto del progetto: append, header scritto solo se
il file non esiste, `extrasaction='ignore'` sulle chiavi non dichiarate.
"""
import csv
import os

from validator.Solution import Solution, TRIP, CREW_DEADHEAD

FORCED_ALTERNATIVE_TAG = "FORCED_ALTERNATIVE"

VNS_CSV_COLUMNS = ['instance_id', 'total_trip', 'n_cancel', 'obj_total',
                   'loco_dh_m', 'crew_dh_m', 'back_home', 'computation_time [s]']

ITER_CSV_COLUMNS = ['instance_id', 'iter', 'k', 'outcome',
                    'obj_total', 'n_canceled', 'loco_dh_m', 'crew_dh_m', 'back_home',
                    'incumbent_total', 'best_total',
                    'n_forced', 'forced_trips', 'forced_failures', 'elapsed_s']


def _append_rows(rows, output_path, columns, label):
    if not rows:
        return
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    file_exists = os.path.isfile(output_path)
    with open(output_path, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)
    print(f"[CSV] {len(rows)} {label} → {output_path}")


def export_vns_csv(results: list, output_path: str):
    """Risultato finale per istanza. Le righe con chiave 'error' vengono saltate."""
    ok = [r for r in results if 'error' not in r]
    _append_rows(ok, output_path, VNS_CSV_COLUMNS, 'rows')


def export_iterations_csv(rows: list, output_path: str):
    """Traiettoria di ricerca: una riga per iterazione."""
    _append_rows(rows, output_path, ITER_CSV_COLUMNS, 'iterations')


def iteration_row(instance_id, it, k, outcome, obj, incumbent_val, best_val,
                  forced, failures, elapsed):
    """Costruisce una riga del log per-iterazione.

    `obj` è None quando la candidata non è stata valutata (outcome 'no_shake' o
    'incomplete'): in quel caso le colonne dell'objective restano vuote, mentre
    incumbent/best riflettono comunque lo stato della ricerca.
    """
    return {
        'instance_id':     instance_id,
        'iter':            it,
        'k':               k,
        'outcome':         outcome,
        'obj_total':       round(obj.total, 2) if obj else '',
        'n_canceled':      obj.n_canceled if obj else '',
        'loco_dh_m':       obj.loco_dh_m  if obj else '',
        'crew_dh_m':       obj.crew_dh_m  if obj else '',
        'back_home':       obj.back_home  if obj else '',
        'incumbent_total': round(incumbent_val.total, 2),
        'best_total':      round(best_val.total, 2),
        'n_forced':        len(forced),
        'forced_trips':    ' '.join(str(t) for t in sorted(forced)),
        'forced_failures': ' '.join(str(t) for t in sorted(failures)),
        'elapsed_s':       round(elapsed, 3),
    }


def export_solution_json(result, run_info: dict, output_path: str) -> None:
    """
    Converte un SolveResult in Solution e lo salva.

    Le assignment si costruiscono da `result.loco_duties`, l'unica struttura che
    porta insieme `rs_trip_id` e driver: in `existing_duties` il task arriva con
    un `id` progressivo e senza `rs_trip_id`.
    """
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    # i flag di manutenzione stanno in result.solution, per trip
    maint = {e['id_trip']: e for e in result.solution if e['locomotive'] != 'canceled'}

    assignments = []
    for loco_id, segments in result.loco_duties.items():
        for task, driver_id in segments:
            trip_id = task.get('rs_trip_id')
            a = {
                'type':          task.get('type'),
                'trip_id':       trip_id,
                'origin':        task['origin'],
                'destination':   task['destination'],
                'departure':     task['departure'],
                'arrival':       task['arrival'],
                'locomotive':    loco_id,
                'driver':        driver_id,
            }
            if a['type'] == TRIP:
                e = maint.get(trip_id, {})
                a['maintenance_at_departure']   = e.get('maintenance_at_departure')   == 'true'
                a['maintenance_at_destination'] = e.get('maintenance_at_destination') == 'true'
            assignments.append(a)

    # i deadhead crew non esistono come task: sono impliciti nel gap fra due
    # task consecutivi che non si toccano nello spazio
    for driver_id, tasks in result.existing_duties.items():
        ordered = sorted(tasks, key=lambda t: t['departure'])
        for prev, nxt in zip(ordered, ordered[1:]):
            if prev['destination'] == nxt['origin']:
                continue
            assignments.append({
                'type':          CREW_DEADHEAD,
                'trip_id':       None,
                'origin':        prev['destination'],
                'destination':   nxt['origin'],
                # finestra disponibile, non durata del viaggio: la durata la
                # calcola il validatore, altrimenti il controllo e' tautologico
                'departure':     prev['arrival'],
                'arrival':       nxt['departure'],
                'locomotive':    None,
                'driver':        driver_id,
            })

    run_info = dict(run_info)
    if 'forced' in run_info:
        # FORCED_ALTERNATIVE e' un object() sentinel, non serializzabile:
        # le forzature concrete sono dict, il sentinel no
        run_info['forced'] = {
            str(t): e if isinstance(e, dict) else FORCED_ALTERNATIVE_TAG
            for t, e in run_info['forced'].items()
        }

    Solution(
        assignments= assignments,
        breaks=      {d: s for d, s in result.duty_breaks.items() if s is not None},
        canceled=    [ct['rs_trip_id'] for ct in result.canceled_tasks],
        run_info=    run_info,
        name=        run_info.get('instance_id'),
    ).save(output_path)
