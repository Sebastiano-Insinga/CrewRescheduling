"""Crew repositioning and where a duty begins.

Leaf module: it only needs a duck typed `net` exposing sp_raw, dsp_crew,
disrupted_edges, disruption_start and disruption_end. Solver, validator and
VNS state all read the same primitive, so a duty length is the same number
wherever it is computed.
"""

EPS = 1e-6
CREW_SPEED_KMH = 57.0


def crew_deadhead_minutes(net, from_st, to_st, window_start, window_end) -> float:
    """Travel time of a crew deadhead, in minutes, float('inf') if unreachable.

    Crew travels as a passenger: full unfiltered matrices (sp_raw / dsp_crew)
    at CREW_SPEED_KMH, unlike a loco deadhead which uses the filtered ones.
    The disrupted matrix applies when the window overlaps the disruption and
    the regular shortest path crosses a disrupted section. The stored path
    excludes its source station, so it is prepended before the scan.
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


def crew_deadhead_arrival(net, from_st, to_st, window_start, window_end) -> tuple:
    """Earliest (departure, arrival) inside a free window.

    The window is free time, so the driver may wait for the disruption to clear
    and travel the regular path rather than being charged the detour for the
    whole window.
    """
    minutes = crew_deadhead_minutes(net, from_st, to_st, window_start, window_end)
    best = (window_start, window_start + minutes)

    if window_end > net.disruption_end > window_start:
        start    = net.disruption_end + EPS
        deferred = crew_deadhead_minutes(net, from_st, to_st, start, window_end)
        if start + deferred < best[1]:
            best = (start, start + deferred)
    return best


def initial_travel(net, status, first_origin, first_departure) -> float:
    """Minutes the driver spends travelling to the first task of the chain.

    Zero when the disruption already left them at that station, otherwise the
    duration crew_deadhead_arrival picks inside the window, deferral included.

    An unreachable first task gives zero, not inf: whether the driver can get
    there at all is check_initial_position's business, and the solver already
    rejects the task before reading this. Returning inf here would only turn
    one real violation into a second, unreadable one of infinite duty.
    """
    if int(status['available_from_station']) == int(first_origin):
        return 0.0
    departure, arrival = crew_deadhead_arrival(
        net, status['available_from_station'], first_origin,
        status['available_at_time'], first_departure)
    if arrival == float('inf'):
        return 0.0
    return arrival - departure


def duty_start(net, status, first_origin, first_departure) -> float:
    """The instant the duty starts, in minutes.

    A driver already on duty when the disruption hit never stopped working, so
    the duty is running from available_at_time. For everyone else the duty
    opens when they set off towards the first task: the journey is service, the
    wait before it is not. Hence `first_departure - travel` and not
    `available_at_time + travel` — leaving as late as possible is always at
    least as feasible, and it is the same deferral crew_deadhead_arrival
    already applies.

    Travel is zero at a coincident station, otherwise the wait would be counted
    as service through the back door.
    """
    if status['duty_length'] > 0:
        return status['available_at_time']
    return first_departure - initial_travel(net, status, first_origin, first_departure)


def duty_minutes(net, status, first_origin, first_departure, last_arrival) -> float:
    """Minutes of duty worked, MAX_DUTY_LENGTH being the cap.

    Recomputable from driver_status plus the first task and the last arrival,
    so solver, validator and ScheduleState reach the same number by
    construction rather than by three formulas agreeing.
    """
    start = duty_start(net, status, first_origin, first_departure)
    if status['duty_length'] > 0:
        return last_arrival - start + status['duty_length']
    return last_arrival - start
