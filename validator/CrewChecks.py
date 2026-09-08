"""Per-driver duty feasibility.

The rules are re-stated here instead of being imported from VNS_Rescheduling:
a validator that calls the same functions as the solver cannot contradict it.
"""
from validator.Helper import EPS, check_chaining, describe, group_by_driver
from validator.Solution import CREW_DEADHEAD

MAX_DUTY_LENGTH = 720    # minutes
BREAK_THRESHOLD = 360    # duty length above which a break is required
BREAK_LENGTH    = 45     # minutes
CREW_SPEED_KMH  = 57.0


def check_driver_chaining(driver_id, tasks) -> list:
    """No overlap in time, no jump in space along the driver's chain.

    The crew_deadhead is itself an assignment closing the gap, so there is no
    legal jump: any mismatch means a missing repositioning.
    """
    return check_chaining('driver', driver_id, tasks, gap_hint=" (no crew_deadhead)")


def crew_deadhead_minutes(net, from_st, to_st, window_start, window_end) -> float:
    """Travel time of a crew deadhead, in minutes, float('inf') if unreachable.

    Crew travels as a passenger: full unfiltered matrices (sp_raw / dsp_crew)
    at CREW_SPEED_KMH, unlike a loco deadhead which uses the filtered ones.
    The disrupted matrix applies when the window overlaps the disruption and
    the regular shortest path crosses a disrupted section.
    """
    if from_st == to_st:
        return 0.0

    entry = net.sp_raw.get(str(from_st), {}).get(str(to_st))
    disruption_active = (window_start <= net.disruption_end and
                         window_end   >= net.disruption_start)

    path_blocked = False
    if disruption_active and entry is not None:
        path = [int(from_st)] + [int(n) for n in entry.get('path', [])]
        path_blocked = any((u, v) in net.disrupted_edges
                           for u, v in zip(path, path[1:]))

    if path_blocked or entry is None:
        dist_meters = net.dsp_crew.get(int(from_st), {}).get(int(to_st), float('inf'))
    else:
        dist_meters = entry['weight']

    if dist_meters == float('inf') or dist_meters >= 2147483647:
        return float('inf')
    return (dist_meters / 1000.0 / CREW_SPEED_KMH) * 60.0


def check_crew_deadhead(driver_id, net, tasks) -> list:
    """The crew_deadhead window must fit the actual travel time.

    departure/arrival on a crew_deadhead are the bounds of the free window,
    not the duration of the trip: the duration is what we compute here.
    """
    violations = []
    for a in tasks:
        if a['type'] != CREW_DEADHEAD:
            continue
        if a['locomotive'] is not None:
            violations.append(
                f"driver {driver_id}: crew_deadhead carries locomotive "
                f"{a['locomotive']} — {describe(a)}")
        minutes = crew_deadhead_minutes(net, a['origin'], a['destination'],
                                        a['departure'], a['arrival'])
        if minutes == float('inf'):
            violations.append(
                f"driver {driver_id}: unreachable crew_deadhead "
                f"{a['origin']}->{a['destination']} — {describe(a)}")
        elif a['departure'] + minutes > a['arrival']:
            window = a['arrival'] - a['departure']
            violations.append(
                f"driver {driver_id}: crew_deadhead needs {minutes:.1f} min but the "
                f"window is {window:.1f} min — {describe(a)}")
    return violations


def check_initial_position(driver_id, mapper, net, tasks) -> list:
    """The driver must be able to reach the first task from wherever the
    disruption left them.

    VNSExport only materialises a crew_deadhead between consecutive tasks, so
    this initial repositioning never appears in the file: it is checked against
    driver_status instead. Reachability only — those minutes count towards the
    duty just for a driver already on duty, and that is check_duty_length.
    """
    status = mapper.driver_status.get(driver_id)
    if status is None:
        return [f"driver {driver_id}: not in driver_status"]

    first = tasks[0]
    if first['departure'] < status['available_at_time'] - EPS:
        return [f"driver {driver_id}: first task departs at {first['departure']:.1f} "
                f"but the driver is free only at {status['available_at_time']:.1f} "
                f"— {describe(first)}"]

    origin = status['available_from_station']
    minutes = crew_deadhead_minutes(net, origin, first['origin'],
                                    status['available_at_time'], first['departure'])
    if minutes == float('inf'):
        return [f"driver {driver_id}: cannot reach the first task, no path "
                f"{origin}->{first['origin']} — {describe(first)}"]
    if status['available_at_time'] + minutes > first['departure']:
        window = first['departure'] - status['available_at_time']
        return [f"driver {driver_id}: reaching the first task from {origin} needs "
                f"{minutes:.1f} min but only {window:.1f} min are available "
                f"— {describe(first)}"]
    return []


def duty_length(status, tasks) -> float:
    """Minutes of duty worked by the driver, MAX_DUTY_LENGTH being the cap.

    A driver already on duty when the disruption hit carries duty_length
    minutes over: the duty started that long before available_at_time, so
    everything after it counts, repositioning included. A driver not on duty
    yet starts working at the first task: reaching it is commuting, not
    service. Travelling back home afterwards is not service either — it only
    enters the objective, never the duty.
    """
    if status['duty_length'] > 0:
        return tasks[-1]['arrival'] - status['available_at_time'] + status['duty_length']
    return tasks[-1]['arrival'] - tasks[0]['departure']


def check_duty_length(driver_id, mapper, tasks) -> list:
    """A duty cannot exceed MAX_DUTY_LENGTH. Exactly at the cap is legal."""
    status = mapper.driver_status.get(driver_id)
    if status is None:
        return []   # already reported by check_initial_position

    duty = duty_length(status, tasks)
    if duty > MAX_DUTY_LENGTH + EPS:
        carried = f", {status['duty_length']:.1f} of them before the disruption" \
                  if status['duty_length'] > 0 else ""
        return [f"driver {driver_id}: duty of {duty:.1f} min exceeds "
                f"{MAX_DUTY_LENGTH}{carried} — {len(tasks)} tasks, "
                f"last arrival {tasks[-1]['arrival']:.1f}"]
    return []


def required_break_length(status, duty) -> int:
    """Break the driver still owes, given what was already taken before the
    disruption. At most BREAK_THRESHOLD of duty needs no break at all."""
    base = 0 if duty <= BREAK_THRESHOLD else BREAK_LENGTH
    if status['break45done'] or (status['break30done'] and duty <= 480):
        return 0
    if status['break30done']:
        return max(0, base - 30)
    return base


def idle_windows(status, net, tasks, duty) -> list:
    """Windows where a break fits, as (start, end, capacity) in minutes.

    Capacity is below the window width whenever part of it is already sold to
    travel: a crew_deadhead window has to carry the driver to the next task
    first, and only what is left over can be spent resting.

      - inside a crew_deadhead: width minus travel time
      - a plain gap between two tasks at the same station: the whole width
      - before the first task, for a driver already on duty: the wait minus
        the travel needed to reach it
      - after the last task: the duty is over as far as this solution goes,
        but the real duty continues, so the break fits as long as it stays
        within MAX_DUTY_LENGTH
    """
    windows = []

    if status['duty_length'] > 0:
        travel = crew_deadhead_minutes(net, status['available_from_station'],
                                       tasks[0]['origin'],
                                       status['available_at_time'], tasks[0]['departure'])
        width = tasks[0]['departure'] - status['available_at_time']
        windows.append((status['available_at_time'], tasks[0]['departure'], width - travel))

    for a in tasks:
        if a['type'] == CREW_DEADHEAD:
            travel = crew_deadhead_minutes(net, a['origin'], a['destination'],
                                           a['departure'], a['arrival'])
            width = a['arrival'] - a['departure']
            windows.append((a['departure'], a['arrival'], width - travel))

    for prev, nxt in zip(tasks, tasks[1:]):
        width = nxt['departure'] - prev['arrival']
        if width > 0:
            windows.append((prev['arrival'], nxt['departure'], width))

    last_arrival = tasks[-1]['arrival']
    tail = MAX_DUTY_LENGTH - duty
    if tail > 0:
        windows.append((last_arrival, last_arrival + tail, tail))

    return sorted(windows)


def check_break(driver_id, mapper, net, sol, tasks) -> list:
    """The declared break must be long enough and fit in idle duty time."""
    status = mapper.driver_status.get(driver_id)
    if status is None:
        return []   # already reported by check_initial_position

    duty     = duty_length(status, tasks)
    required = required_break_length(status, duty)
    if required == 0:
        return []   # the exporter still writes a (-45, 0) sentinel: ignore it

    window = sol.breaks.get(driver_id)
    if window is None:
        return [f"driver {driver_id}: duty of {duty:.1f} min requires a "
                f"{required} min break, none declared"]

    start, end = window
    if end - start < required - EPS:
        return [f"driver {driver_id}: break [{start:.1f}, {end:.1f}] lasts "
                f"{end - start:.1f} min, {required} required"]

    windows = idle_windows(status, net, tasks, duty)
    holding = [w for w in windows if start >= w[0] - EPS and end <= w[1] + EPS]
    if not holding:
        return [f"driver {driver_id}: break [{start:.1f}, {end:.1f}] falls outside "
                f"every idle window {[(round(s, 1), round(e, 1)) for s, e, _ in windows]}"]
    if all(cap < required - EPS for _, _, cap in holding):
        s, e, cap = holding[0]
        return [f"driver {driver_id}: break [{start:.1f}, {end:.1f}] sits in the window "
                f"[{s:.1f}, {e:.1f}] which is {e - s:.1f} min wide but leaves only "
                f"{cap:.1f} min once travel is paid, {required} required"]
    return []


def compute_crew_violations(mapper, net, sol):
    """TODO: trip in the driver's suitable_tasks — vacuous today, every driver
    qualifies for every task."""
    violations = []
    for driver_id, tasks in group_by_driver(sol).items():
        violations += check_driver_chaining(driver_id, tasks)
        violations += check_crew_deadhead(driver_id, net, tasks)
        violations += check_initial_position(driver_id, mapper, net, tasks)
        violations += check_duty_length(driver_id, mapper, tasks)
        violations += check_break(driver_id, mapper, net, sol, tasks)
    return violations
