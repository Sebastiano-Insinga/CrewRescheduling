"""Per-driver duty feasibility.

The rules are re-stated here instead of being imported from VNS_Rescheduling:
a validator that calls the same functions as the solver cannot contradict it.
The measure is not: crew travel times and the instant a duty starts come from
CrewDeadhead, because asking the same graph twice with two readings does not
make the check stricter, it only makes the numbers incomparable.
"""
from rescheduling.CrewDeadhead import (crew_deadhead_arrival, crew_deadhead_minutes,
                          duty_minutes, duty_start, initial_travel)
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
        start, arrival = crew_deadhead_arrival(net, a['origin'], a['destination'],
                                               a['departure'], a['arrival'])
        if arrival == float('inf'):
            violations.append(
                f"driver {driver_id}: unreachable crew_deadhead "
                f"{a['origin']}->{a['destination']} — {describe(a)}")
        elif arrival > a['arrival']:
            violations.append(
                f"driver {driver_id}: crew_deadhead needs {arrival - start:.1f} min "
                f"but the window is {a['arrival'] - start:.1f} min — {describe(a)}")
    return violations


def check_initial_position(driver_id, mapper, net, tasks) -> list:
    """The driver must be able to reach the first task from wherever the
    disruption left them.

    VNSExport only materialises a crew_deadhead between consecutive tasks, so
    this initial repositioning never appears in the file: it is checked against
    driver_status instead. Reachability only — how those minutes land in the
    duty is duty_length's business, and since the journey is service they now
    count for every driver, not just one already on duty.
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
    start, arrival = crew_deadhead_arrival(net, origin, first['origin'],
                                           status['available_at_time'],
                                           first['departure'])
    if arrival == float('inf'):
        return [f"driver {driver_id}: cannot reach the first task, no path "
                f"{origin}->{first['origin']} — {describe(first)}"]
    if arrival > first['departure']:
        return [f"driver {driver_id}: reaching the first task from {origin} needs "
                f"{arrival - start:.1f} min but only {first['departure'] - start:.1f} "
                f"min are available — {describe(first)}"]
    return []


def duty_length(status, net, tasks) -> float:
    """Minutes of duty worked by the driver, MAX_DUTY_LENGTH being the cap.

    A driver already on duty when the disruption hit carries duty_length
    minutes over: the duty started that long before available_at_time, so
    everything after it counts, repositioning included. A driver not on duty
    yet has to travel to the first task, and that journey is service: the duty
    opens when they set off, not when the first task departs. Travelling back
    home afterwards is not service — it only enters the objective.

    The duty ends at the last arrival of the chain, not at the arrival of the
    task departing last: a solution that overlaps two tasks can declare a
    crew_deadhead whose window runs backwards, and reading its arrival would
    close the duty before the driver is done.

    The first task is the first one that is not an initial CREW_DEADHEAD: once
    VNSExport materialises that repositioning, reading tasks[0] would put the
    duty start back at available_at_time and charge the wait as service. A
    materialised file and a legacy one have to give the same number, which is
    why the formula lives in a single primitive.
    """
    last = max(a['arrival'] for a in tasks)
    first = _first_served_task(tasks)
    return duty_minutes(net, status, first['origin'], first['departure'], last)


def _first_served_task(tasks) -> dict:
    """The task the duty is built around: the initial repositioning, when the
    exporter wrote it out, is the journey to it, not the first served task."""
    for a in tasks:
        if a['type'] != CREW_DEADHEAD:
            return a
    return tasks[0]


def check_duty_length(driver_id, mapper, net, tasks) -> list:
    """A duty cannot exceed MAX_DUTY_LENGTH. Exactly at the cap is legal."""
    status = mapper.driver_status.get(driver_id)
    if status is None:
        return []   # already reported by check_initial_position

    duty = duty_length(status, net, tasks)
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
    first, and only what is left over can be spent resting. The travel is the
    one crew_deadhead_arrival measures, deferral included — the same reading
    check_crew_deadhead applies, so a path the disruption blocks at the start
    of the window does not eat the whole window.

      - inside a crew_deadhead: what is left once the driver has arrived
      - a plain gap between two tasks at the same station: the whole width
      - before the first task, for a driver already on duty: the wait minus
        the travel needed to reach it. A driver not on duty yet gets no such
        window: their duty opens when they set off, so the wait before that
        is not service and resting in it is not a break.
      - after the last task: the duty is over as far as this solution goes,
        but the real duty continues, so the break fits as long as it stays
        within MAX_DUTY_LENGTH
    """
    windows = []

    first = _first_served_task(tasks)
    if status['duty_length'] > 0:
        arrival = crew_deadhead_arrival(net, status['available_from_station'],
                                        first['origin'],
                                        status['available_at_time'],
                                        first['departure'])[1]
        windows.append((status['available_at_time'], first['departure'],
                        first['departure'] - arrival))

    for a in tasks:
        if a['type'] == CREW_DEADHEAD:
            arrival = crew_deadhead_arrival(net, a['origin'], a['destination'],
                                            a['departure'], a['arrival'])[1]
            windows.append((a['departure'], a['arrival'], a['arrival'] - arrival))

    for prev, nxt in zip(tasks, tasks[1:]):
        width = nxt['departure'] - prev['arrival']
        if width > 0:
            windows.append((prev['arrival'], nxt['departure'], width))

    last_arrival = max(a['arrival'] for a in tasks)
    tail = MAX_DUTY_LENGTH - duty
    if tail > 0:
        windows.append((last_arrival, last_arrival + tail, tail))

    return sorted(windows)


def check_break(driver_id, mapper, net, sol, tasks) -> list:
    """The declared break must be long enough and fit in idle duty time."""
    status = mapper.driver_status.get(driver_id)
    if status is None:
        return []   # already reported by check_initial_position

    duty     = duty_length(status, net, tasks)
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
        violations += check_duty_length(driver_id, mapper, net, tasks)
        violations += check_break(driver_id, mapper, net, sol, tasks)
    return violations
