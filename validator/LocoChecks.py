
from collections import namedtuple

from IntegratedRescheduling import epoch_to_minutes
from validator.Helper import EPS, check_chaining, describe, group_by_loco
from validator.Solution import TRIP, LOCO_DEADHEAD

# km tolerance above max_kilometers_before_maintenance, mirrors
# LocoChecker(buffer_km=200.0)
MAINT_BUFFER_KM = 200.0

# a pre-disruption trip together with where its maintenance happened, if any:
# the flags are what resets the kilometre count
PreTrip = namedtuple('PreTrip', 'trip maint_dep maint_dest')

# where the rescheduling finds a loco.
LocoState = namedtuple('LocoState', 'station avail_time km')


def check_loco_chaining(loco_id, tasks) -> list:
    """No overlap in time, no jump in space along the loco's chain.

    Waits are legal and common: unlike a driver, a loco standing still at a
    station costs nothing. Only overlap and teleporting are violations.
    """
    return check_chaining('loco', loco_id, tasks)


def loco_deadhead_minutes(net, loco_class, from_st, to_st,
                          window_start, window_end) -> float:

    if from_st == to_st:
        return 0.0

    speed = loco_class['deadhead_speed']
    entry = net.sp.get(str(from_st), {}).get(str(to_st))
    disruption_active = (window_start <= net.disruption_end and
                         window_end   >= net.disruption_start)

    path_blocked = False
    if disruption_active and entry is not None:
        path = [int(from_st)] + [int(n) for n in entry.get('path', [])]
        path_blocked = any((u, v) in net.disrupted_edges
                           for u, v in zip(path, path[1:]))

    if path_blocked or entry is None:
        dist_meters = net.dsp.get(int(from_st), {}).get(int(to_st), float('inf'))
    else:
        dist_meters = entry['weight']

    if dist_meters == float('inf') or dist_meters >= 2147483647:
        return float('inf')

    return (dist_meters / 1000.0 / speed) * 60.0

def initial_loco_state(instance, net):
    """loco_id -> (station, avail_time_min) where rescheduling finds the loco.

    Physical reading: the loco stands where its last pre-disruption trip left
    it. The solver instead places it at the origin of its next planned trip and
    takes the repositioning in between for granted — it charges the kilometres
    but never checks they fit in time. Sticking to the physical position is
    what makes check_initial_position able to test that assumption instead of
    restating it.

    A loco with no earlier trip waits at its depot, available from the start of
    the rescheduling: what happened before the disruption is none of our
    business.

    TODO: a loco still travelling when the disruption hits is available later
    than its arrival — max(disruption_end, arrival + disruption length), see
    RollingStockGreedy._determine_loco_position. Ignoring that makes this
    reading more permissive than the solver, which is the wrong direction for
    a validator.
    """
    pre_state = {}
    for e in instance['solution']:
        loco = e['locomotive']
        if loco == 'canceled':
            continue
        trip = net.trips_by_id[e['id_trip']]
        if epoch_to_minutes(trip['departure_time']) < net.disruption_start:
            # the instance stores the flags as strings, the solution file as bools
            pre_state.setdefault(loco, []).append(PreTrip(
                trip,
                e['maintenance_at_departure']   == 'true',
                e['maintenance_at_destination'] == 'true'))

    state = {}
    for loco_id in net.locos_by_id:
        if loco_id in pre_state:
            trips   = sorted(pre_state[loco_id], key=lambda p: p.trip['departure_time'])
            last    = trips[-1].trip
            station = net.sections[last['section']]['destination']
            time    = epoch_to_minutes(last['arrival_time'])
            km = net.locos_by_id[loco_id]['kilometers_since_last_maintenance']
            prev_arrival = None
            prev_dest = net.locos_by_id[loco_id]['initial_departure_station']

            for p in trips:
                sec = net.sections[p.trip['section']]
                we = epoch_to_minutes(p.trip['departure_time'])
                ws = epoch_to_minutes(prev_arrival) if prev_arrival is not None else we
                km += deadhead_km(net, prev_dest, sec['origin'],ws, we)  
                if p.maint_dep:
                    km= 0.0
                km +=sec['distance']
                if p.maint_dest:
                    km= 0.0
                prev_dest = sec['destination']
                prev_arrival = p.trip['arrival_time']
        else:
            station = net.locos_by_id[loco_id]['initial_departure_station']
            time    = net.disruption_start
            km = net.locos_by_id[loco_id]['kilometers_since_last_maintenance']
        state[loco_id] = LocoState(station, time, km)
    return state

def deadhead_km(net,from_station, to_station, window_start, window_end):
    if from_station == to_station:
        return 0.0
    entry = net.sp.get(str(from_station), {}).get(str(to_station))
    disruption_active = (window_start <= net.disruption_end and
                     window_end   >= net.disruption_start)
    path_blocked = False
    if disruption_active and entry is not None:
        path = [int(from_station)] + [int(n) for n in entry.get('path', [])]
        path_blocked = any((u, v) in net.disrupted_edges
                   for u, v in zip(path, path[1:]))

    if path_blocked or entry is None:
        dist_meters = net.dsp.get(int(from_station), {}).get(int(to_station), float('inf'))
    else:
        dist_meters=entry['weight']

    if dist_meters == float('inf') or dist_meters >= 2147483647:
        return float('inf')
    return dist_meters/1000.0

def check_loco_deadhead(loco_id, net, tasks) -> list:
    violations = []
    lc = net.loco_classes[net.locos_by_id[loco_id]['class']]
    for a in tasks:
        if a['type'] == LOCO_DEADHEAD:
            minutes = loco_deadhead_minutes(net,lc,a['origin'], a['destination'],
                                            a['departure'], a['arrival'])
            if minutes == float('inf'):
                violations.append(f"loco {loco_id}: unreachable loco_deadhead "
                                  f"{a['origin']}->{a['destination']} — {describe(a)}")
            elif a['departure'] + minutes > a['arrival'] + EPS:
                declared = a['arrival'] - a['departure']
                violations.append(
                    f"loco {loco_id}: loco_deadhead needs {minutes:.1f} min but is "
                    f"declared as {declared:.1f} min — {describe(a)}")
    return violations


def check_initial_position(loco_id, net, tasks, state) -> list:
    violations = []
    loco_class = net.loco_classes[net.locos_by_id[loco_id]['class']]
    if tasks[0]['departure'] + EPS < state.avail_time :
        violations.append(f"loco :{loco_id} before being available")
    if state.avail_time + loco_deadhead_minutes(net, loco_class, state.station, tasks[0]['origin'],state.avail_time ,tasks[0]['departure'] )  > tasks[0]['departure'] + EPS:
        violations.append(f"loco: {loco_id} is arriving too late for {tasks[0]['origin']}")
    return violations


def check_loco_class(loco_id, net, tasks) -> list:
    """TODO: loco['class'] must be in the trip's locomotive_orders.

    Vacuous on the current instances — a single class, LC_XX, accepted
    everywhere — like suitable_tasks on the crew side.
    """
    return []


def trip_section(net, a) -> dict:
    """The stretch of track a trip assignment runs over.

    Two hops because the assignment only carries the trip id, the trip only
    carries the section id, and distance belongs to the section: several trips
    share the same stretch and its length is written once.
    """
    return net.sections[net.trips_by_id[a['trip_id']]['section']]


def trip_km(net, a) -> float:
    """Kilometres of the section a trip assignment runs over."""
    return trip_section(net, a)['distance']


def check_maintenance_km(loco_id, net, tasks, state) -> list:
    """Kilometres run between two maintenances must stay under the cap.

    The chain splits into stretches, one per maintenance: the counter starts
    from what the loco carried into the rescheduling and goes back to zero
    every time it is serviced. Each stretch is checked on its own — a loco
    that runs 19000 km, gets maintained, then runs 19000 km again is fine.

    Order matters inside a trip: maintenance at departure happens before the
    trip is run, maintenance at destination after, so the trip's kilometres
    land in different stretches depending on which flag is set.
    """
    km       = state.km
    segments = []          # (km of the stretch, task that closed it or None)

    for a in tasks:
        if a['type'] == LOCO_DEADHEAD:
            km += deadhead_km(net, a['origin'], a['destination'],
                              a['departure'], a['arrival'])
        elif a['type'] == TRIP:
            if a.get('maintenance_at_departure'):
                segments.append((km, a))
                km = 0.0
            km += trip_km(net, a)
            if a.get('maintenance_at_destination'):
                segments.append((km, a))
                km = 0.0

    segments.append((km, None))   # the stretch left open at the end of the chain

    loco_class = net.loco_classes[net.locos_by_id[loco_id]['class']]
    limit      = loco_class['max_kilometers_before_maintenance'] + MAINT_BUFFER_KM

    violations = []
    for run_km, closing in segments:
        if run_km > limit:
            where = f"closed by {describe(closing)}" if closing else "still open at the end of the chain"
            violations.append(
                f"loco {loco_id}: {run_km:.1f} km between maintenances, "
                f"limit {limit:.0f} — stretch {where}")
    return violations


def check_maintenance_feasibility(loco_id, net, tasks, state) -> list:
    """TODO: every declared maintenance must be possible where and when it is.

    The maintenance_at_departure / maintenance_at_destination flags ride on
    trip assignments only. For each one:
      - the station must be a maintenance point accepting this loco class
        (net.maint_stations: {station: {class, ...}})
      - it must fit in time, maintenance_duration included. Watch the unit:
        the network stores 10800 as seconds, i.e. 180 minutes, while the
        solution file is in minutes throughout.
    """
    loco_class = net.loco_classes[net.locos_by_id[loco_id]['class']]
    maint_min  = loco_class['maintenance_duration'] / 60.0

    violations = []
    for i, a in enumerate(tasks):
        if a['type'] != TRIP:
            continue

        if a.get('maintenance_at_departure'):
            libero   = tasks[i-1]['arrival']     if i > 0 else state.avail_time
            partenza = tasks[i-1]['destination'] if i > 0 else state.station
            if a['origin'] not in net.maint_stations:
                violations.append(
                    f"loco {loco_id}: maintenance declared at {a['origin']}, which is "
                    f"not a maintenance station — {describe(a)}")
            else:
                travel = loco_deadhead_minutes(net, loco_class, partenza, a['origin'],
                                               libero, a['departure'])
                if libero + travel + maint_min > a['departure']:
                    window = a['departure'] - libero
                    violations.append(
                        f"loco {loco_id}: maintenance at departure needs {maint_min:.0f} min "
                        f"plus {travel:.1f} min of travel, but only {window:.1f} min are "
                        f"free before the trip — {describe(a)}")

        if a.get('maintenance_at_destination'):
            # the window runs to the next TRIP, not to the next task: the task
            # right after is usually a deadhead leaving at this very arrival
            next_t = next((t for t in tasks[i+1:] if t['type'] == TRIP), None)
            if a['destination'] not in net.maint_stations:
                violations.append(
                    f"loco {loco_id}: maintenance declared at {a['destination']}, which is "
                    f"not a maintenance station — {describe(a)}")
            elif next_t is not None:
                travel = loco_deadhead_minutes(net, loco_class, a['destination'],
                                               next_t['origin'],
                                               a['arrival'], next_t['departure'])
                if a['arrival'] + maint_min + travel > next_t['departure']:
                    window = next_t['departure'] - a['arrival']
                    violations.append(
                        f"loco {loco_id}: maintenance at destination needs {maint_min:.0f} min "
                        f"plus {travel:.1f} min of travel, but only {window:.1f} min are "
                        f"free before {describe(next_t)} — {describe(a)}")
            # next_t is None: last trip of the chain, nothing constrains the end

    return violations


def compute_loco_violations(instance, net, sol):
    # walked once for every loco, not once per check: it replays the whole
    # pre-disruption plan
    state = initial_loco_state(instance, net)

    violations = []
    for loco_id, tasks in group_by_loco(sol).items():
        violations += check_loco_chaining(loco_id, tasks)
        violations += check_loco_deadhead(loco_id, net, tasks)
        violations += check_initial_position(loco_id, net, tasks,state[loco_id])
        violations += check_loco_class(loco_id, net, tasks)
        violations += check_maintenance_km(loco_id, net, tasks, state[loco_id])
        violations += check_maintenance_feasibility(loco_id, net, tasks, state[loco_id])
    return violations
