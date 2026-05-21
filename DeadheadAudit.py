import json
def print_duties(existing_duties):
    print("\n=== DUTIES ===")
    for driver_id, tasks in existing_duties.items():
        task_list = [f"{t['id']}({t['origin']} {t['departure']}-{t['arrival']} {t['destination']})" for t in tasks]
        print(f"  {driver_id}: {task_list}")
    print("=== END ===\n")


def audit_deadhead_solution(existing_duties, sp, crew_speed_kmh=60.0,
                            network=None, disrupted_section_ids=None,
                            disruption_start=None, disruption_end=None):
    """Print deadhead gaps in existing_duties and report missing/tight/disrupted paths.

    DISRUPTED PATH is only flagged when the deadhead timing overlaps with the
    disruption window AND the sp path crosses a disrupted section — meaning
    _get_deadhead_minutes should have used dsp but didn't (or dsp was None).
    Deadheads outside the disruption window using sp through disrupted sections
    are OK (disruption is over, section restored).
    """
    edge_to_section = {}
    if network is not None:
        for sec in network['sections']:
            edge_to_section[(sec['origin'], sec['destination'])] = sec['id']

    def path_crosses_disruption(path):
        if not disrupted_section_ids or not edge_to_section:
            return False, []
        bad = []
        for a, b in zip(path, path[1:]):
            sid = edge_to_section.get((a, b))
            if sid in disrupted_section_ids:
                bad.append(sid)
        return bool(bad), bad

    def overlaps_disruption(dh_start, dh_end):
        if disruption_start is None or disruption_end is None:
            return True  # can't tell → assume worst case
        return dh_start <= disruption_end and dh_end >= disruption_start

    print("\n=== DEADHEAD AUDIT ===")
    missing_paths = 0
    tight_paths = 0
    disrupted_paths = 0

    for driver_id, tasks in existing_duties.items():
        for prev, task in zip(tasks, tasks[1:]):
            gap = task["departure"] - prev["arrival"]
            if gap <= 0:
                continue
            frm, to = str(prev["destination"]), str(task["origin"])
            if frm == to:
                continue
            route = sp.get(frm, {}).get(to)
            if route is None:
                print(f"  PATH MISSING   [{driver_id}] {frm} -> {to}  (gap={gap}min)")
                missing_paths += 1
                continue

            dh_min = (route['weight'] / 1000.0 / crew_speed_kmh) * 60.0
            crosses, bad_secs = path_crosses_disruption(route.get('path', []))
            during_disruption = overlaps_disruption(prev["arrival"], task["departure"])

            if crosses and during_disruption:
                print(f"  DISRUPTED PATH [{driver_id}] {frm} -> {to}  sections={bad_secs}  gap={gap}min  need={dh_min:.1f}min  dh_window=[{prev['arrival']},{task['departure']}]")
                disrupted_paths += 1
            elif gap < dh_min:
                print(f"  TOO TIGHT      [{driver_id}] {frm} -> {to}  need={dh_min:.1f}min gap={gap}min")
                tight_paths += 1
            else:
                label = "OK(post-dis)" if crosses else "OK"
                print(f"  {label:<14} [{driver_id}] {frm} -> {to}  need={dh_min:.1f}min gap={gap}min")

    print(f"Missing: {missing_paths}, Too tight: {tight_paths}, Disrupted path: {disrupted_paths}")
    print("=== END AUDIT ===\n")
    return missing_paths, tight_paths, disrupted_paths

def audit_deadhead_from_to(startstation, endstation, dh_start_time=None, dh_end_time=None,
                           instance_file='single_type/S01.json'):
    """Check if sp path from startstation to endstation crosses disrupted sections.

    dh_start_time / dh_end_time: minutes when the driver performs the deadhead.
    If provided, flags DISRUPTED only when deadhead overlaps the disruption window.
    If omitted, flags any disrupted section regardless of timing.
    """
    print(f"Audit deadhead from {startstation} to {endstation}"
          + (f"  dh_window=[{dh_start_time},{dh_end_time}]" if dh_start_time is not None else ""))
    with open('single_type/network-shortestpaths.json') as f:
        sp = json.load(f)
    with open('single_type/network.json') as f:
        network = json.load(f)
    with open(instance_file) as f:
        instance = json.load(f)

    route = sp.get(str(startstation), {}).get(str(endstation))
    if route is None:
        print(f"No path found in sp from {startstation} to {endstation}")
        return

    path = route['path']
    print(f"Path: {path}  weight={route['weight']}m")

    disrupted_sections = set(instance['disrupted_sections'])
    edge_to_section = {(s['origin'], s['destination']): s['id'] for s in network['sections']}

    from SequentialRescheduling import epoch_to_minutes
    dis_start = epoch_to_minutes(instance['disruption_start'])
    dis_end   = epoch_to_minutes(instance['disruption_end'])
    print(f"Disruption window: [{dis_start}, {dis_end}]")

    if dh_start_time is not None and dh_end_time is not None:
        overlaps = dh_start_time <= dis_end and dh_end_time >= dis_start
    else:
        overlaps = True

    for a, b in zip(path, path[1:]):
        sid = edge_to_section.get((a, b))
        if sid in disrupted_sections:
            if overlaps:
                print(f"  DISRUPTED (during disruption): {a}->{b}  section={sid}")
            else:
                print(f"  ok (post-disruption):          {a}->{b}  section={sid}")
        else:
            print(f"  ok:        {a}->{b}  section={sid}")
