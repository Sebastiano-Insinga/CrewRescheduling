import copy
import math
import time
import random
import heapq
from collections import defaultdict
from rescheduling.CrewDeadhead import EPS
from readers.TimeFormat import *

RANDOM_SEED = 42

def _required_break_length(duty_length):
    if duty_length <= 360:
        return 0
    else:
        return 45

def _has_break_slot(tasks, required_break_length, deadhead_minutes=None):
    """Whether an idle gap between two tasks can hold the required break.

    deadhead_minutes: (from_station, to_station, current_time, task_departure)
    -> minutes. When given, the repositioning the driver has to make inside a
    gap is subtracted from it: resting and travelling cannot happen at once.
    Callers whose chains never move the driver leave it None and get the gross
    gap, which is the same thing when the stations match.
    """
    if required_break_length == 0:
        return True
    for i in range(len(tasks) - 1):
        gap = tasks[i + 1]["departure"] - tasks[i]["arrival"]
        if deadhead_minutes is not None:
            gap -= deadhead_minutes(tasks[i]["destination"], tasks[i + 1]["origin"],
                                    tasks[i]["arrival"], tasks[i + 1]["departure"])
        if gap >= required_break_length:
            return True
    return False

def _is_task_feasible(task, task_id, current_origin, current_time, first_departure, driver_duty, max_duty_length, suitable_tasks, driver_id):
    if driver_duty["duty_length"] > 0:
        new_duty_length = task["arrival"] - driver_duty["available_at_time"] + driver_duty["duty_length"]
    else:
        new_duty_length = task["arrival"] - first_departure
    return (
        task["origin"] == current_origin
        and task["departure"] >= current_time
        and new_duty_length < max_duty_length
        and task_id in suitable_tasks[driver_id]
    )

def calculateInitialSolution(original_schedule, driver_status, input_open_tasks, disruption_start, disruption_end, max_duty_length, id_mapping, suitable_tasks):
    open_tasks = copy.deepcopy(input_open_tasks)
    #in Twans solution there are tasks that are part of more than one duty so we introduce the available_tasks
    available_tasks = copy.deepcopy(input_open_tasks)
    #define some greedy function here to generate a first feasible schedule to recover from the disruption
    existing_duties = {}

    print("******************************************************************")
    print(f"There are {len(open_tasks)} many open tasks at the beginning of calculating the initial solution")
    #for duty_id, st in suitable_tasks.items():
    #    print(f"Duty {duty_id} could potentially cover {len(set(st)&set(open_tasks))} tasks")

    #for duty_id, st in suitable_tasks.items():
    #    print(f"Duty {duty_id} cannot cover the following tasks {set(open_tasks)-set(st)}")
    #for duty_id, st in suitable_tasks.items():
    #    print(f"Duty {duty_id} cannot cover {len(set(open_tasks) - set(st))} tasks")

    for driver_id, driver_duty in driver_status.items():
        original_task_ids = {t["id"] for t in original_schedule[driver_id]}
        feasible_task_found = True
        while feasible_task_found:
            feasible_tasks = {}
            if driver_id not in existing_duties:
                current_origin = driver_duty["available_from_station"]
                current_time = driver_duty["available_at_time"]
                fixed_first_departure = None
                current_tasks = []
            else:
                current_origin = existing_duties[driver_id][-1]["destination"]
                current_time = existing_duties[driver_id][-1]["arrival"]
                fixed_first_departure = existing_duties[driver_id][0]["departure"]
                current_tasks = existing_duties[driver_id]
            for task_id, task in available_tasks.items():
                first_departure = task["departure"] if fixed_first_departure is None else fixed_first_departure
                if _is_task_feasible_break(task, task_id, current_origin, current_time, first_departure, driver_duty, max_duty_length, suitable_tasks, driver_id, current_tasks):
                    feasible_tasks[task_id] = copy.deepcopy(task)
            if feasible_tasks:
                previously_assigned_tasks = {ta_id: ta for ta_id, ta in feasible_tasks.items() if ta_id in original_task_ids}
                if previously_assigned_tasks:
                    min_departure_id = min(previously_assigned_tasks, key=lambda k: previously_assigned_tasks[k]["departure"])
                else:
                    min_departure_id = min(feasible_tasks, key=lambda k: feasible_tasks[k]["departure"])

                if driver_id not in existing_duties:
                    existing_duties[driver_id] = [copy.deepcopy(available_tasks[min_departure_id])]
                else:
                    existing_duties[driver_id].append(copy.deepcopy(available_tasks[min_departure_id]))
                
                if min_departure_id in open_tasks:
                    open_tasks.pop(min_departure_id)
                available_tasks.pop(min_departure_id, None)
            else:
                feasible_task_found = False


    ################################################################
    spare_duty_id_list = []
    #experiment
    #try here to duplicate a fixed ratio of the duties to create spare drivers
    #this would for example duplicate 10% of the duties randomly
    spare_driver_fraction = 0.0
    max_duty_id = max(existing_duties.keys()) + 1

    spare_duty_ids = max_duty_id
    extracted_duties = list(existing_duties.values())
    k = int(len(extracted_duties) * spare_driver_fraction)

    duplicated_duties = random.sample(extracted_duties, k)

    for i in range(len(duplicated_duties)):
        existing_duties[spare_duty_ids] = copy.deepcopy(duplicated_duties[i])
        #here we assume that spare drivers can drive all tasks
        suitable_tasks[spare_duty_ids] = copy.deepcopy(input_open_tasks)
        spare_duty_id_list.append(spare_duty_ids)
        spare_duty_ids += 1

    ################################################################

    duty_breaks = {}
    for duty_id, duty in existing_duties.items():
        duty_length = duty[-1]["arrival"] - duty[0]["departure"]
        if duty_id < max_duty_id:
            break_30_done = driver_status[duty_id]["break30done"]
            break_45_done = driver_status[duty_id]["break45done"]
        else:
            break_30_done = break_45_done = False

        if break_45_done or (break_30_done and duty_length <= 480):
            required_break_length = 0
        elif break_30_done:  # duty_length > 480
            required_break_length = 15
        else:
            required_break_length = 45 if duty_length > 480 else 30

        if required_break_length == 0:
            duty_breaks[duty_id] = (-45, 0)
            continue

        pairs = list(zip(duty, duty[1:]))
        slot = next(
            ((a["arrival"], a["arrival"] + required_break_length)
             for a, b in pairs
             if b["departure"] - a["arrival"] >= required_break_length),
            None
        )
        duty_breaks[duty_id] = slot

    #print(duty_breaks)

    uncovered_tasks = []
    for task in open_tasks.values():
        uncovered_tasks.append(task)

    #this part is removed
    #instead of creating new duties we simply assume that all tasks that cannot be assigned to an existing driver are uncovered
    '''   
    duty_index = max(driver_status.keys()) + 1  # generate a new duty index for new crew members
    new_duties = {}
    if len(open_tasks.keys()) > 0:
        initial_task_key = min(open_tasks, key=lambda k: open_tasks[k]["departure"])
        new_duties[duty_index] = [copy.deepcopy(open_tasks[initial_task_key])]
        open_tasks.pop(initial_task_key)

    while len(open_tasks.keys()) > 0:
        feasible_tasks = {}
        for task_id, task in open_tasks.items():
            if task["origin"] == new_duties[duty_index][-1]["destination"] and task["departure"] >= new_duties[duty_index][-1][
                "arrival"] and (task["arrival"] - new_duties[duty_index][0]["departure"]) < max_duty_length:
                feasible_tasks[task_id] = copy.deepcopy(task)
        if len(feasible_tasks.keys()) > 0:
            min_departure_id = min(feasible_tasks, key=lambda k: feasible_tasks[k]["departure"])
            duty_task_list = copy.deepcopy(new_duties[duty_index])
            duty_task_list.append(copy.deepcopy(open_tasks[min_departure_id]))
            new_duties[duty_index] = duty_task_list
            open_tasks.pop(min_departure_id)
        # no more feasible task was found for the current duty -> start a new duty
        else:
            duty_index += 1
            # initial_task_key = min(open_tasks.keys())
            initial_task_key = min(open_tasks, key=lambda k: open_tasks[k]["departure"])
            new_duties[duty_index] = [copy.deepcopy(open_tasks[initial_task_key])]
            open_tasks.pop(initial_task_key)
    '''
    #print("The existing duties are the following:")
    #for driver_id, duty in existing_duties.items():
    #    print(f"Driver {driver_id}: {duty}")
    #print("")
    '''
    print("The new duties are the following:")
    for driver_id, duty in new_duties.items():
        print(f"Driver {driver_id}: {duty}")
    '''
    #here I want to see the new schedule
    #this should help to analyze what is happening
    locomotives = {task['locomotive'] for task in id_mapping.values()}
    sorted_rescheduled = dict(sorted(existing_duties.items(), key=lambda item: item[1][0]["departure"]))
    return existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, spare_duty_id_list

def _compute_driver_slack(driver_id, existing_duties, max_duty_length):
    if driver_id not in existing_duties or not existing_duties[driver_id]:
        return 1.0
    current_duty_length = existing_duties[driver_id][-1]["arrival"] - existing_duties[driver_id][0]["departure"]
    return (max_duty_length - current_duty_length) / max_duty_length


def _count_feasible_tasks_for_driver(driver_id, driver_status, existing_duties, available_tasks, max_duty_length, suitable_tasks):
    driver_duty = driver_status[driver_id]
    if driver_id not in existing_duties:
        current_origin = driver_duty["available_from_station"]
        current_time = driver_duty["available_at_time"]
        fixed_first_departure = None
    else:
        current_origin = existing_duties[driver_id][-1]["destination"]
        current_time = existing_duties[driver_id][-1]["arrival"]
        fixed_first_departure = existing_duties[driver_id][0]["departure"]
    count = 0
    for task_id, task in available_tasks.items():
        first_departure = task["departure"] if fixed_first_departure is None else fixed_first_departure
        if _is_task_feasible(task, task_id, current_origin, current_time, first_departure, driver_duty, max_duty_length, suitable_tasks, driver_id):
            count += 1
    return count


def _count_eligible_drivers_for_task(task, task_id, driver_status, existing_duties, max_duty_length, suitable_tasks):
    count = 0
    for driver_id, driver_duty in driver_status.items():
        if driver_id not in existing_duties:
            current_origin = driver_duty["available_from_station"]
            current_time = driver_duty["available_at_time"]
            fixed_first_departure = None
        else:
            current_origin = existing_duties[driver_id][-1]["destination"]
            current_time = existing_duties[driver_id][-1]["arrival"]
            fixed_first_departure = existing_duties[driver_id][0]["departure"]
        first_departure = task["departure"] if fixed_first_departure is None else fixed_first_departure
        if _is_task_feasible(task, task_id, current_origin, current_time, first_departure, driver_duty, max_duty_length, suitable_tasks, driver_id):
            count += 1
    return count


def _count_reachable_from(destination, arrival_time, available_tasks, driver_id, suitable_tasks):
    return sum(
        1 for tid, t in available_tasks.items()
        if t["origin"] == destination
        and t["departure"] >= arrival_time
        and tid in suitable_tasks[driver_id]
    )


def calculateInitialSolution_driverMRV(original_schedule, driver_status, input_open_tasks, disruption_start, disruption_end, max_duty_length, id_mapping, suitable_tasks):
    """Driver-MRV greedy initial solution.

    Same round-based structure as calculateInitialSolution_slack but drivers
    are sorted by number of currently feasible tasks (ascending) instead of
    slack. The most constrained driver builds its chain first, preventing
    other drivers from consuming the few tasks it can cover.
    Effective only when suitable_tasks is heterogeneous (drivers have different
    qualifications). With uniform suitable_tasks produces identical results to
    calculateInitialSolution.
    """
    open_tasks = copy.deepcopy(input_open_tasks)
    available_tasks = copy.deepcopy(input_open_tasks)
    existing_duties = {}

    print("******************************************************************")
    print(f"[driverMRV] There are {len(open_tasks)} open tasks at the beginning of calculating the initial solution")

    progress = True
    while progress:
        progress = False
        sorted_drivers = sorted(
            driver_status.keys(),
            key=lambda d: _count_feasible_tasks_for_driver(d, driver_status, existing_duties, available_tasks, max_duty_length, suitable_tasks)
        )
        for driver_id in sorted_drivers:
            driver_duty = driver_status[driver_id]
            original_task_ids = {t["id"] for t in original_schedule[driver_id]}

            if driver_id not in existing_duties:
                current_origin = driver_duty["available_from_station"]
                current_time = driver_duty["available_at_time"]
                fixed_first_departure = None
                current_tasks = []
            else:
                current_origin = existing_duties[driver_id][-1]["destination"]
                current_time = existing_duties[driver_id][-1]["arrival"]
                fixed_first_departure = existing_duties[driver_id][0]["departure"]
                current_tasks = existing_duties[driver_id]

            feasible_tasks = {}
            for task_id, task in available_tasks.items():
                first_departure = task["departure"] if fixed_first_departure is None else fixed_first_departure
                if _is_task_feasible_break(task, task_id, current_origin, current_time, first_departure, driver_duty, max_duty_length, suitable_tasks, driver_id, current_tasks):
                    feasible_tasks[task_id] = copy.deepcopy(task)

            if feasible_tasks:
                previously_assigned_tasks = {ta_id: ta for ta_id, ta in feasible_tasks.items() if ta_id in original_task_ids}
                if previously_assigned_tasks:
                    selected_id = min(previously_assigned_tasks, key=lambda k: previously_assigned_tasks[k]["departure"])
                else:
                    selected_id = min(feasible_tasks, key=lambda k: feasible_tasks[k]["departure"])

                if driver_id not in existing_duties:
                    existing_duties[driver_id] = [copy.deepcopy(available_tasks[selected_id])]
                else:
                    existing_duties[driver_id].append(copy.deepcopy(available_tasks[selected_id]))

                if selected_id in open_tasks:
                    open_tasks.pop(selected_id)
                available_tasks.pop(selected_id, None)
                progress = True

    ################################################################
    spare_duty_id_list = []
    spare_driver_fraction = 0.0
    max_duty_id = max(existing_duties.keys()) + 1
    spare_duty_ids = max_duty_id
    extracted_duties = list(existing_duties.values())
    k = int(len(extracted_duties) * spare_driver_fraction)
    duplicated_duties = random.sample(extracted_duties, k)
    for i in range(len(duplicated_duties)):
        existing_duties[spare_duty_ids] = copy.deepcopy(duplicated_duties[i])
        suitable_tasks[spare_duty_ids] = copy.deepcopy(input_open_tasks)
        spare_duty_id_list.append(spare_duty_ids)
        spare_duty_ids += 1
    ################################################################

    duty_breaks = {}
    for duty_id, duty in existing_duties.items():
        duty_length = duty[-1]["arrival"] - duty[0]["departure"]
        if duty_id < max_duty_id:
            b30 = driver_status[duty_id]["break30done"]
            b45 = driver_status[duty_id]["break45done"]
        else:
            b30 = b45 = False
        base_req = _required_break_length(duty_length)
        if b45 or (b30 and duty_length <= 480):
            required_break_length = 0
        elif b30:
            required_break_length = max(0, base_req - 30)
        else:
            required_break_length = base_req
        if required_break_length == 0:
            duty_breaks[duty_id] = (-45, 0)
            continue
        pairs = list(zip(duty, duty[1:]))
        slot = next(
            ((a["arrival"], a["arrival"] + required_break_length)
             for a, b in pairs
             if b["departure"] - a["arrival"] >= required_break_length),
            None
        )
        duty_breaks[duty_id] = slot

    uncovered_tasks = list(open_tasks.values())
    locomotives = {task['locomotive'] for task in id_mapping.values()}
    sorted_rescheduled = dict(sorted(existing_duties.items(), key=lambda item: item[1][0]["departure"]))
    return existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, spare_duty_id_list


def calculateInitialSolution_taskScarcity(original_schedule, driver_status, input_open_tasks, disruption_start, disruption_end, max_duty_length, id_mapping, suitable_tasks):
    """Task-scarcity greedy initial solution.

    Same driver-first chain structure as calculateInitialSolution but changes
    the task selection criterion: instead of min departure, each driver picks
    the feasible task with fewest eligible drivers globally (most scarce task).
    Originally-assigned tasks still take priority over non-original ones.
    Preserves chain building — avoids the temporal fragmentation of global task-MRV.
    """
    open_tasks = copy.deepcopy(input_open_tasks)
    available_tasks = copy.deepcopy(input_open_tasks)
    existing_duties = {}

    print("******************************************************************")
    print(f"[taskScarcity] There are {len(open_tasks)} open tasks at the beginning of calculating the initial solution")

    eligible_counts = {
        task_id: _count_eligible_drivers_for_task(task, task_id, driver_status, {}, max_duty_length, suitable_tasks)
        for task_id, task in open_tasks.items()
    }
    contested = sum(1 for c in eligible_counts.values() if c >= 2)
    zero = sum(1 for c in eligible_counts.values() if c == 0)
    print(f"[taskScarcity] Task con 0 driver eligible: {zero}/{len(open_tasks)} ({100*zero/len(open_tasks):.1f}%)")
    print(f"[taskScarcity] Task con >=2 driver eligible: {contested}/{len(open_tasks)} ({100*contested/len(open_tasks):.1f}%)")

    # Breakdown: why are tasks with 0 eligible drivers uncoverable?
    wrong_station = too_late = duty_full = break_fail = 0
    zero_tasks = {tid: t for tid, t in open_tasks.items() if eligible_counts[tid] == 0}
    for task_id, task in zero_tasks.items():
        reasons = set()
        for driver_id, driver_duty in driver_status.items():
            current_origin = driver_duty["available_from_station"]
            current_time   = driver_duty["available_at_time"]
            first_dep      = task["departure"]
            if driver_duty["duty_length"] > 0:
                new_duty_length = task["arrival"] - driver_duty["available_at_time"] + driver_duty["duty_length"]
            else:
                new_duty_length = task["arrival"] - first_dep
            if task["origin"] != current_origin:
                reasons.add("wrong_station")
            elif task["departure"] < current_time:
                reasons.add("too_late")
            elif new_duty_length >= max_duty_length:
                reasons.add("duty_full")
            else:
                b30 = driver_duty["break30done"]
                b45 = driver_duty["break45done"]
                base_req = _required_break_length(new_duty_length)
                if b45 or (b30 and new_duty_length <= 480):
                    req = 0
                elif b30:
                    req = max(0, base_req - 30)
                else:
                    req = base_req
                if req > 0 and not _has_break_slot([task], req):
                    reasons.add("break_fail")
        if "wrong_station" in reasons: wrong_station += 1
        if "too_late"      in reasons: too_late      += 1
        if "duty_full"     in reasons: duty_full      += 1
        if "break_fail"    in reasons: break_fail     += 1
    print(f"[taskScarcity] Breakdown task con 0 eligible (un task può avere più cause):")
    print(f"  wrong_station: {wrong_station}  too_late: {too_late}  duty_full: {duty_full}  break_fail: {break_fail}")

    from collections import Counter
    driver_stations = Counter(d["available_from_station"] for d in driver_status.values())
    task_origins    = Counter(t["origin"] for t in open_tasks.values())
    driver_station_set = set(driver_stations.keys())
    task_origin_set    = set(task_origins.keys())
    print(f"[taskScarcity] Stazioni con almeno 1 driver: {len(driver_station_set)}")
    print(f"[taskScarcity] Stazioni origine task: {len(task_origin_set)}")
    print(f"[taskScarcity] Stazioni task senza driver: {len(task_origin_set - driver_station_set)}")
    print(f"[taskScarcity] Top stazioni driver: {dict(driver_stations.most_common(5))}")
    print(f"[taskScarcity] Top stazioni task origin: {dict(task_origins.most_common(5))}")

    for driver_id, driver_duty in driver_status.items():
        original_task_ids = {t["id"] for t in original_schedule[driver_id]}
        feasible_task_found = True
        while feasible_task_found:
            feasible_tasks = {}
            if driver_id not in existing_duties:
                current_origin = driver_duty["available_from_station"]
                current_time = driver_duty["available_at_time"]
                fixed_first_departure = None
                current_tasks = []
            else:
                current_origin = existing_duties[driver_id][-1]["destination"]
                current_time = existing_duties[driver_id][-1]["arrival"]
                fixed_first_departure = existing_duties[driver_id][0]["departure"]
                current_tasks = existing_duties[driver_id]

            for task_id, task in available_tasks.items():
                first_departure = task["departure"] if fixed_first_departure is None else fixed_first_departure
                if _is_task_feasible_break(task, task_id, current_origin, current_time, first_departure, driver_duty, max_duty_length, suitable_tasks, driver_id, current_tasks):
                    feasible_tasks[task_id] = copy.deepcopy(task)

            if feasible_tasks:
                previously_assigned_tasks = {ta_id: ta for ta_id, ta in feasible_tasks.items() if ta_id in original_task_ids}
                pool = previously_assigned_tasks if previously_assigned_tasks else feasible_tasks
                selected_id = min(
                    pool,
                    key=lambda k: _count_eligible_drivers_for_task(
                        pool[k], k, driver_status, existing_duties, max_duty_length, suitable_tasks
                    )
                )

                if driver_id not in existing_duties:
                    existing_duties[driver_id] = [copy.deepcopy(available_tasks[selected_id])]
                else:
                    existing_duties[driver_id].append(copy.deepcopy(available_tasks[selected_id]))

                if selected_id in open_tasks:
                    open_tasks.pop(selected_id)
                available_tasks.pop(selected_id, None)
            else:
                feasible_task_found = False

    ################################################################
    spare_duty_id_list = []
    spare_driver_fraction = 0.0
    max_duty_id = max(existing_duties.keys()) + 1
    spare_duty_ids = max_duty_id
    extracted_duties = list(existing_duties.values())
    k = int(len(extracted_duties) * spare_driver_fraction)
    duplicated_duties = random.sample(extracted_duties, k)
    for i in range(len(duplicated_duties)):
        existing_duties[spare_duty_ids] = copy.deepcopy(duplicated_duties[i])
        suitable_tasks[spare_duty_ids] = copy.deepcopy(input_open_tasks)
        spare_duty_id_list.append(spare_duty_ids)
        spare_duty_ids += 1
    ################################################################

    duty_breaks = {}
    for duty_id, duty in existing_duties.items():
        duty_length = duty[-1]["arrival"] - duty[0]["departure"]
        if duty_id < max_duty_id:
            b30 = driver_status[duty_id]["break30done"]
            b45 = driver_status[duty_id]["break45done"]
        else:
            b30 = b45 = False
        base_req = _required_break_length(duty_length)
        if b45 or (b30 and duty_length <= 480):
            required_break_length = 0
        elif b30:
            required_break_length = max(0, base_req - 30)
        else:
            required_break_length = base_req
        if required_break_length == 0:
            duty_breaks[duty_id] = (-45, 0)
            continue
        pairs = list(zip(duty, duty[1:]))
        slot = next(
            ((a["arrival"], a["arrival"] + required_break_length)
             for a, b in pairs
             if b["departure"] - a["arrival"] >= required_break_length),
            None
        )
        duty_breaks[duty_id] = slot

    uncovered_tasks = list(open_tasks.values())
    locomotives = {task['locomotive'] for task in id_mapping.values()}
    sorted_rescheduled = dict(sorted(existing_duties.items(), key=lambda item: item[1][0]["departure"]))
    return existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, spare_duty_id_list


def calculateInitialSolution_connectivity(original_schedule, driver_status, input_open_tasks, disruption_start, disruption_end, max_duty_length, id_mapping, suitable_tasks):
    """Destination-connectivity greedy initial solution.

    Same driver-first chain structure as calculateInitialSolution but selects
    the task that maximizes follow-up reachability: picks the feasible task
    whose destination has the most subsequent tasks reachable (origin match +
    time feasibility). Originally-assigned tasks still take priority.
    Tiebreaker: min departure.
    """
    open_tasks = copy.deepcopy(input_open_tasks)
    available_tasks = copy.deepcopy(input_open_tasks)
    existing_duties = {}

    print("******************************************************************")
    print(f"[connectivity] There are {len(open_tasks)} open tasks at the beginning of calculating the initial solution")

    for driver_id, driver_duty in driver_status.items():
        original_task_ids = {t["id"] for t in original_schedule[driver_id]}
        feasible_task_found = True
        while feasible_task_found:
            feasible_tasks = {}
            if driver_id not in existing_duties:
                current_origin = driver_duty["available_from_station"]
                current_time = driver_duty["available_at_time"]
                fixed_first_departure = None
                current_tasks = []
            else:
                current_origin = existing_duties[driver_id][-1]["destination"]
                current_time = existing_duties[driver_id][-1]["arrival"]
                fixed_first_departure = existing_duties[driver_id][0]["departure"]
                current_tasks = existing_duties[driver_id]

            for task_id, task in available_tasks.items():
                first_departure = task["departure"] if fixed_first_departure is None else fixed_first_departure
                if _is_task_feasible_break(task, task_id, current_origin, current_time, first_departure, driver_duty, max_duty_length, suitable_tasks, driver_id, current_tasks):
                    feasible_tasks[task_id] = copy.deepcopy(task)

            if feasible_tasks:
                previously_assigned_tasks = {ta_id: ta for ta_id, ta in feasible_tasks.items() if ta_id in original_task_ids}
                pool = previously_assigned_tasks if previously_assigned_tasks else feasible_tasks
                selected_id = min(
                    pool,
                    key=lambda k: (
                        -_count_reachable_from(pool[k]["destination"], pool[k]["arrival"], available_tasks, driver_id, suitable_tasks),
                        pool[k]["departure"]
                    )
                )

                if driver_id not in existing_duties:
                    existing_duties[driver_id] = [copy.deepcopy(available_tasks[selected_id])]
                else:
                    existing_duties[driver_id].append(copy.deepcopy(available_tasks[selected_id]))

                if selected_id in open_tasks:
                    open_tasks.pop(selected_id)
                available_tasks.pop(selected_id, None)
            else:
                feasible_task_found = False

    ################################################################
    spare_duty_id_list = []
    spare_driver_fraction = 0.0
    max_duty_id = max(existing_duties.keys()) + 1
    spare_duty_ids = max_duty_id
    extracted_duties = list(existing_duties.values())
    k = int(len(extracted_duties) * spare_driver_fraction)
    duplicated_duties = random.sample(extracted_duties, k)
    for i in range(len(duplicated_duties)):
        existing_duties[spare_duty_ids] = copy.deepcopy(duplicated_duties[i])
        suitable_tasks[spare_duty_ids] = copy.deepcopy(input_open_tasks)
        spare_duty_id_list.append(spare_duty_ids)
        spare_duty_ids += 1
    ################################################################

    duty_breaks = {}
    for duty_id, duty in existing_duties.items():
        duty_length = duty[-1]["arrival"] - duty[0]["departure"]
        if duty_id < max_duty_id:
            b30 = driver_status[duty_id]["break30done"]
            b45 = driver_status[duty_id]["break45done"]
        else:
            b30 = b45 = False
        base_req = _required_break_length(duty_length)
        if b45 or (b30 and duty_length <= 480):
            required_break_length = 0
        elif b30:
            required_break_length = max(0, base_req - 30)
        else:
            required_break_length = base_req
        if required_break_length == 0:
            duty_breaks[duty_id] = (-45, 0)
            continue
        pairs = list(zip(duty, duty[1:]))
        slot = next(
            ((a["arrival"], a["arrival"] + required_break_length)
             for a, b in pairs
             if b["departure"] - a["arrival"] >= required_break_length),
            None
        )
        duty_breaks[duty_id] = slot

    uncovered_tasks = list(open_tasks.values())
    locomotives = {task['locomotive'] for task in id_mapping.values()}
    sorted_rescheduled = dict(sorted(existing_duties.items(), key=lambda item: item[1][0]["departure"]))
    return existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, spare_duty_id_list


def calculateInitialSolution_slack(original_schedule, driver_status, input_open_tasks, disruption_start, disruption_end, max_duty_length, id_mapping, suitable_tasks):
    """Slack-based greedy initial solution.

    Drivers are sorted by slack (most available first) each round.
    slack = (max_duty_length - current_duty_length) / max_duty_length
    Each round assigns one task per driver; rounds repeat until no progress.
    Original calculateInitialSolution (min-departure greedy) is preserved unchanged.
    """
    open_tasks = copy.deepcopy(input_open_tasks)
    available_tasks = copy.deepcopy(input_open_tasks)
    existing_duties = {}

    print("******************************************************************")
    print(f"[SLACK] There are {len(open_tasks)} open tasks at the beginning of calculating the initial solution")

    progress = True
    while progress:
        progress = False
        sorted_drivers = sorted(
            driver_status.keys(),
            key=lambda d: _compute_driver_slack(d, existing_duties, max_duty_length),
            reverse=True
        )
        for driver_id in sorted_drivers:
            driver_duty = driver_status[driver_id]
            original_task_ids = {t["id"] for t in original_schedule[driver_id]}

            if driver_id not in existing_duties:
                current_origin = driver_duty["available_from_station"]
                current_time = driver_duty["available_at_time"]
                fixed_first_departure = None
                current_tasks = []
            else:
                current_origin = existing_duties[driver_id][-1]["destination"]
                current_time = existing_duties[driver_id][-1]["arrival"]
                fixed_first_departure = existing_duties[driver_id][0]["departure"]
                current_tasks = existing_duties[driver_id]

            feasible_tasks = {}
            for task_id, task in available_tasks.items():
                first_departure = task["departure"] if fixed_first_departure is None else fixed_first_departure
                if _is_task_feasible_break(task, task_id, current_origin, current_time, first_departure, driver_duty, max_duty_length, suitable_tasks, driver_id, current_tasks):
                    feasible_tasks[task_id] = copy.deepcopy(task)

            if feasible_tasks:
                previously_assigned_tasks = {ta_id: ta for ta_id, ta in feasible_tasks.items() if ta_id in original_task_ids}
                if previously_assigned_tasks:
                    selected_id = min(previously_assigned_tasks, key=lambda k: previously_assigned_tasks[k]["departure"])
                else:
                    selected_id = min(feasible_tasks, key=lambda k: feasible_tasks[k]["departure"])

                if driver_id not in existing_duties:
                    existing_duties[driver_id] = [copy.deepcopy(available_tasks[selected_id])]
                else:
                    existing_duties[driver_id].append(copy.deepcopy(available_tasks[selected_id]))

                if selected_id in open_tasks:
                    open_tasks.pop(selected_id)
                available_tasks.pop(selected_id, None)
                progress = True

    ################################################################
    spare_duty_id_list = []
    spare_driver_fraction = 0.0
    max_duty_id = max(existing_duties.keys()) + 1

    spare_duty_ids = max_duty_id
    extracted_duties = list(existing_duties.values())
    k = int(len(extracted_duties) * spare_driver_fraction)

    duplicated_duties = random.sample(extracted_duties, k)

    for i in range(len(duplicated_duties)):
        existing_duties[spare_duty_ids] = copy.deepcopy(duplicated_duties[i])
        suitable_tasks[spare_duty_ids] = copy.deepcopy(input_open_tasks)
        spare_duty_id_list.append(spare_duty_ids)
        spare_duty_ids += 1

    ################################################################

    duty_breaks = {}
    for duty_id, duty in existing_duties.items():
        duty_length = duty[-1]["arrival"] - duty[0]["departure"]
        if duty_id < max_duty_id:
            break_30_done = driver_status[duty_id]["break30done"]
            break_45_done = driver_status[duty_id]["break45done"]
        else:
            break_30_done = break_45_done = False

        if break_45_done or (break_30_done and duty_length <= 480):
            required_break_length = 0
        elif break_30_done:  # duty_length > 480
            required_break_length = 15
        else:
            required_break_length = 45 if duty_length > 480 else 30

        if required_break_length == 0:
            duty_breaks[duty_id] = (-45, 0)
            continue

        pairs = list(zip(duty, duty[1:]))
        slot = next(
            ((a["arrival"], a["arrival"] + required_break_length)
             for a, b in pairs
             if b["departure"] - a["arrival"] >= required_break_length),
            None
        )
        duty_breaks[duty_id] = slot

    uncovered_tasks = list(open_tasks.values())

    locomotives = {task['locomotive'] for task in id_mapping.values()}
    sorted_rescheduled = dict(sorted(existing_duties.items(), key=lambda item: item[1][0]["departure"]))
    return existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, spare_duty_id_list


def _is_task_feasible_break(task, task_id, current_origin, current_time, first_departure,
                            driver_duty, max_duty_length, suitable_tasks, driver_id, current_tasks):
    if driver_duty["duty_length"] > 0:
        new_duty_length = task["arrival"] - driver_duty["available_at_time"] + driver_duty["duty_length"]
    else:
        new_duty_length = task["arrival"] - first_departure
    if not (
        task["origin"] == current_origin
        and task["departure"] >= current_time
        and new_duty_length < max_duty_length
        and task_id in suitable_tasks[driver_id]
    ):
        return False
    req_break = _required_break_length(new_duty_length)
    if req_break > 0:
        if not _has_break_slot(current_tasks + [task], req_break):
            return False
    return True


def calculateInitialSolutionBreak(original_schedule, driver_status, input_open_tasks, disruption_start, disruption_end, max_duty_length, id_mapping, suitable_tasks):
    """Break-aware greedy initial solution.

    Same logic as calculateInitialSolution but rejects a task assignment
    whenever adding that task would make the duty exceed 360 min without
    a feasible break slot in the resulting task sequence.
    """
    open_tasks = copy.deepcopy(input_open_tasks)
    available_tasks = copy.deepcopy(input_open_tasks)
    existing_duties = {}

    print("******************************************************************")
    print(f"[BREAK] There are {len(open_tasks)} open tasks at the beginning of calculating the initial solution")

    for driver_id, driver_duty in driver_status.items():
        original_task_ids = {t["id"] for t in original_schedule[driver_id]}
        feasible_task_found = True
        while feasible_task_found:
            feasible_tasks = {}
            if driver_id not in existing_duties:
                current_origin = driver_duty["available_from_station"]
                current_time = driver_duty["available_at_time"]
                fixed_first_departure = None
                current_tasks = []
            else:
                current_origin = existing_duties[driver_id][-1]["destination"]
                current_time = existing_duties[driver_id][-1]["arrival"]
                fixed_first_departure = existing_duties[driver_id][0]["departure"]
                current_tasks = existing_duties[driver_id]
            for task_id, task in available_tasks.items():
                first_departure = task["departure"] if fixed_first_departure is None else fixed_first_departure
                if _is_task_feasible_break(task, task_id, current_origin, current_time, first_departure,
                                           driver_duty, max_duty_length, suitable_tasks, driver_id, current_tasks):
                    feasible_tasks[task_id] = copy.deepcopy(task)
            if feasible_tasks:
                previously_assigned_tasks = {ta_id: ta for ta_id, ta in feasible_tasks.items() if ta_id in original_task_ids}
                if previously_assigned_tasks:
                    min_departure_id = min(previously_assigned_tasks, key=lambda k: previously_assigned_tasks[k]["departure"])
                else:
                    min_departure_id = min(feasible_tasks, key=lambda k: feasible_tasks[k]["departure"])

                if driver_id not in existing_duties:
                    existing_duties[driver_id] = [copy.deepcopy(available_tasks[min_departure_id])]
                else:
                    existing_duties[driver_id].append(copy.deepcopy(available_tasks[min_departure_id]))

                if min_departure_id in open_tasks:
                    open_tasks.pop(min_departure_id)
                available_tasks.pop(min_departure_id, None)
            else:
                feasible_task_found = False

    ################################################################
    spare_duty_id_list = []
    spare_driver_fraction = 0.0
    max_duty_id = max(existing_duties.keys()) + 1

    spare_duty_ids = max_duty_id
    extracted_duties = list(existing_duties.values())
    k = int(len(extracted_duties) * spare_driver_fraction)
    duplicated_duties = random.sample(extracted_duties, k)

    for i in range(len(duplicated_duties)):
        existing_duties[spare_duty_ids] = copy.deepcopy(duplicated_duties[i])
        suitable_tasks[spare_duty_ids] = copy.deepcopy(input_open_tasks)
        spare_duty_id_list.append(spare_duty_ids)
        spare_duty_ids += 1
    ################################################################

    duty_breaks = {}
    for duty_id, duty in existing_duties.items():
        duty_length = duty[-1]["arrival"] - duty[0]["departure"]
        if duty_id < max_duty_id:
            break_30_done = driver_status[duty_id]["break30done"]
            break_45_done = driver_status[duty_id]["break45done"]
        else:
            break_30_done = break_45_done = False

        if break_45_done or (break_30_done and duty_length <= 480):
            required_break_length = 0
        elif break_30_done:
            required_break_length = 15
        else:
            required_break_length = 45 if duty_length > 480 else 30

        if required_break_length == 0:
            duty_breaks[duty_id] = (-45, 0)
            continue

        pairs = list(zip(duty, duty[1:]))
        slot = next(
            ((a["arrival"], a["arrival"] + required_break_length)
             for a, b in pairs
             if b["departure"] - a["arrival"] >= required_break_length),
            None
        )
        duty_breaks[duty_id] = slot

    uncovered_tasks = list(open_tasks.values())

    locomotives = {task['locomotive'] for task in id_mapping.values()}
    sorted_rescheduled = dict(sorted(existing_duties.items(), key=lambda item: item[1][0]["departure"]))
    return existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, spare_duty_id_list


def _get_deadhead_minutes(from_station, to_station, current_time, task_departure,
                          sp, dsp, disruption_start, disruption_end, crew_speed_kmh,
                          disrupted_edges=None):
    if from_station == to_station:
        return 0.0, False
    entry = sp.get(str(from_station), {}).get(str(to_station))
    # Check if deadhead window overlaps disruption and SP path crosses a disrupted section
    disruption_active = (dsp is not None and
                         disrupted_edges is not None and
                         current_time <= disruption_end and
                         task_departure >= disruption_start)
    sp_path_blocked = False
    if disruption_active and entry is not None:
        path = entry.get('path', [])
        full_path = [int(from_station)] + [int(n) for n in path]
        for i in range(len(full_path) - 1):
            if (full_path[i], full_path[i + 1]) in disrupted_edges:
                sp_path_blocked = True
                break
    if sp_path_blocked or (entry is None and dsp is not None):
        # entry is None: pair missing from the precomputed SP file — dsp now
        # carries a Dijkstra-computed value for it (compute_disrupted_sp).
        dist_meters = dsp.get(int(from_station), {}).get(int(to_station), float('inf'))
        used_dsp = True
    else:
        dist_meters = entry['weight'] if entry is not None else float('inf')
        used_dsp = False
    if dist_meters == float('inf') or dist_meters >= 2147483647:
        return float('inf'), used_dsp
    return (dist_meters / 1000.0 / crew_speed_kmh) * 60.0, used_dsp


def _is_break_feasible(tasks_with_new, new_duty_length, driver_duty, deadhead_minutes=None):
    b30 = driver_duty["break30done"]
    b45 = driver_duty["break45done"]
    base_req = _required_break_length(new_duty_length)
    if b45 or (b30 and new_duty_length <= 480):
        req_break = 0
    elif b30:
        req_break = max(0, base_req - 30)
    else:
        req_break = base_req
    return req_break == 0 or _has_break_slot(tasks_with_new, req_break, deadhead_minutes)


def _chain_duty_start(duty_tasks, driver_duty, sp, dsp, disruption_start, disruption_end,
                      crew_speed_kmh, disrupted_edges=None):
    """When the duty of a non empty chain opened.

    Same rule as _is_task_feasible_with_deadhead applies to the first task of
    the chain: the driver set off from where the disruption left them, and that
    journey is service. The carryover case never reads this value, so the plain
    departure is returned there.
    """
    first = duty_tasks[0]
    if driver_duty["duty_length"] > 0:
        return first["departure"]
    travel, _ = _get_deadhead_minutes(
        driver_duty["available_from_station"], first["origin"],
        driver_duty["available_at_time"], first["departure"],
        sp, dsp, disruption_start, disruption_end, crew_speed_kmh,
        disrupted_edges=disrupted_edges)
    if travel == float('inf'):
        return first["departure"]
    return first["departure"] - travel


def _is_task_feasible_with_deadhead(task, task_id, current_origin, current_time, first_departure,
                                     driver_duty, max_duty_length, suitable_tasks, driver_id,
                                     sp, dsp, disruption_start, disruption_end, crew_speed_kmh,
                                     disrupted_edges=None):
    dh_minutes, used_dsp = _get_deadhead_minutes(
        current_origin, task["origin"], current_time, task["departure"],
        sp, dsp, disruption_start, disruption_end, crew_speed_kmh,
        disrupted_edges=disrupted_edges
    )
    if dh_minutes == float('inf'):
        return False, 0.0, 0, False
    if current_time + dh_minutes > task["departure"]:
        return False, 0.0, 0, False
    if driver_duty["duty_length"] > 0:
        new_duty_length = task["arrival"] - driver_duty["available_at_time"] + driver_duty["duty_length"]
    else:
        # The journey to the first task is service, so the duty opens when the
        # driver sets off: as late as the task allows, which is the departure
        # minus the travel. Waiting before that is not service.
        fp = task["departure"] - dh_minutes if first_departure is None else first_departure
        new_duty_length = task["arrival"] - fp
    if new_duty_length > max_duty_length + EPS:
        return False, 0.0, 0, False
    if task_id not in suitable_tasks[driver_id]:
        return False, 0.0, 0, False
    return True, dh_minutes, new_duty_length, used_dsp


def calculateInitialSolution_deadhead(original_schedule, driver_status, input_open_tasks,
                                       disruption_start, disruption_end, max_duty_length,
                                       id_mapping, suitable_tasks,
                                       sp=None, dsp=None, crew_speed_kmh=57.0,
                                       disrupted_edges=None):
    """Deadhead-aware greedy initial solution.

    Same driver-first chain structure as calculateInitialSolution but relaxes
    the station constraint: a driver can reach a task by deadheading (travelling
    as passenger) if the shortest-path travel time fits before task departure.
    Uses disrupted SP (dsp) when the deadhead window overlaps the disruption.
    Task selection priority:
      1. originally-assigned task, no deadhead needed
      2. originally-assigned task, deadhead needed
      3. any task: minimize (deadhead_minutes, departure)
    Deadhead entries are NOT added to existing_duties to keep the data structure
    compatible with downstream VNS; deadhead time is captured implicitly via
    the timing gap between consecutive tasks.
    """
    open_tasks = copy.deepcopy(input_open_tasks)
    existing_duties = {}

    #print("******************************************************************")
    #print(f"[DEADHEAD] There are {len(open_tasks)} open tasks at the beginning of calculating the initial solution")

    total_dh_km = 0.0
    #for driver_id, driver_duty in driver_status.items():
    #    if driver_duty["available_at_time"] <= disruption_end:
    #       print(f"[CANDIDATE DSP] Driver {driver_id}: available_at={driver_duty['available_at_time']} station={driver_duty['available_from_station']} disruption=[{disruption_start},{disruption_end}]")
    for driver_id, driver_duty in driver_status.items():
        original_task_ids = {t["id"] for t in original_schedule[driver_id]}
        feasible_task_found = True
        while feasible_task_found:
            feasible_tasks = {}
            if driver_id not in existing_duties:
                current_origin = driver_duty["available_from_station"]
                current_time = driver_duty["available_at_time"]
                fixed_first_departure = None
                current_tasks = []
            else:
                current_origin = existing_duties[driver_id][-1]["destination"]
                current_time = existing_duties[driver_id][-1]["arrival"]
                fixed_first_departure = _chain_duty_start(
                    existing_duties[driver_id], driver_duty,
                    sp, dsp, disruption_start, disruption_end, crew_speed_kmh,
                    disrupted_edges=disrupted_edges)
                current_tasks = existing_duties[driver_id]

            for task_id, task in open_tasks.items():
                first_departure = fixed_first_departure
                feasible, dh, new_duty_length, used_dsp = _is_task_feasible_with_deadhead(
                    task, task_id, current_origin, current_time, first_departure,
                    driver_duty, max_duty_length, suitable_tasks, driver_id,
                    sp, dsp, disruption_start, disruption_end, crew_speed_kmh,
                    disrupted_edges=disrupted_edges
                )
                if feasible and not _is_break_feasible(current_tasks + [task], new_duty_length, driver_duty):
                    feasible = False
                if feasible:
                    feasible_tasks[task_id] = (copy.deepcopy(task), dh)

            if feasible_tasks:
                original = {tid: v for tid, v in feasible_tasks.items() if tid in original_task_ids}
                pool = (
                    {tid: v for tid, v in original.items() if v[1] == 0}  # originally assigned, no dh
                    or original                                             # originally assigned, with dh
                    or feasible_tasks                                       # any task
                )
                selected_id = min(pool, key=lambda k: (pool[k][1], pool[k][0]["departure"]))
                selected_dh = pool[selected_id][1]
                #'''' Check on deadhead distance and print if >0 '''
                #if selected_dh > 0:
                #        from_st=str(current_origin)
                #        to_st=str(open_tasks[selected_id]['origin'])
                #        if used_dsp:
                #            dist_meters = dsp.get(int(from_st), {}).get(int(open_tasks[selected_id]['origin']), None)
                #            path_info="N/A (dsp weight-only)"
                #        else:
                #            matrix_label="SP"
                #            entry=sp.get(from_st, {}).get(to_st)
                #            dist=entry.get("weight")
                #            path_info=entry.get("path",[])
                #            print(f"[DH] Driver {driver_id}: {current_origin} → {open_tasks[selected_id]['origin']}")
                #            print(f"     matrix={matrix_label} | dist={dist}m | {selected_dh:.1f} min")
                #            print(f"     path={path_info}")
                total_dh_km += selected_dh * crew_speed_kmh / 60.0

                if driver_id not in existing_duties:
                    existing_duties[driver_id] = [copy.deepcopy(open_tasks[selected_id])]
                else:
                    existing_duties[driver_id].append(copy.deepcopy(open_tasks[selected_id]))

                open_tasks.pop(selected_id)
            else:
                feasible_task_found = False

    #print(f"[DEADHEAD] Total deadhead distance in initial solution: {total_dh_km:.1f} km")

    duty_breaks = {}
    for duty_id, duty in existing_duties.items():
        # come in _is_task_feasible_with_deadhead: chi era gia' in servizio alla
        # disruption porta con se' i minuti lavorati prima, altrimenti un turno
        # lungo davvero risulta sotto soglia e non riceve la pausa dovuta
        if driver_status[duty_id]["duty_length"] > 0:
            duty_length = (duty[-1]["arrival"] - driver_status[duty_id]["available_at_time"]
                           + driver_status[duty_id]["duty_length"])
        else:
            duty_length = duty[-1]["arrival"] - _chain_duty_start(
                duty, driver_status[duty_id],
                sp, dsp, disruption_start, disruption_end, crew_speed_kmh,
                disrupted_edges=disrupted_edges)
        b30 = driver_status[duty_id]["break30done"]
        b45 = driver_status[duty_id]["break45done"]

        base_req = _required_break_length(duty_length)
        if b45 or (b30 and duty_length <= 480):
            required_break_length = 0
        elif b30:
            required_break_length = max(0, base_req - 30)
        else:
            required_break_length = base_req

        if required_break_length == 0:
            duty_breaks[duty_id] = (-45, 0)
            continue

        pairs = list(zip(duty, duty[1:]))
        slot = next(
            ((a["arrival"], a["arrival"] + required_break_length)
             for a, b in pairs
             if b["departure"] - a["arrival"] >= required_break_length),
            None
        )
        duty_breaks[duty_id] = slot

    uncovered_tasks = list(open_tasks.values())

    locomotives = {task['locomotive'] for task in id_mapping.values()}
    sorted_rescheduled = dict(sorted(existing_duties.items(), key=lambda item: item[1][0]["departure"]))
    return existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, [], total_dh_km


def calcDifferenceToOriginalSchedule_ScheduleClass(original_schedule, new_schedule,  open_tasks):
    different_task_penalty = 0
    penalty_per_duty = {}
    for driver_id, driver_duty in original_schedule.items():
        if driver_id in new_schedule.crew_duties.keys():
            for task_id, task in open_tasks.items():
                if (task["id"] in [t["id"] for t in original_schedule[driver_id]] and task["id"] not in [t["id"] for t in new_schedule.crew_duties[driver_id].tasks]) or (task["id"] not in [t["id"] for t in original_schedule[driver_id]] and task["id"] in [t["id"] for t in new_schedule.crew_duties[driver_id].tasks]):
                    different_task_penalty += 1
                    if driver_id in penalty_per_duty.keys():
                        penalty_per_duty[driver_id] = penalty_per_duty[driver_id] + 1
                    else:
                        penalty_per_duty[driver_id] = 1
                    #print(f"The task {task_id} was changed from driver {driver_id}")

    return different_task_penalty, penalty_per_duty

def dijkstra(graph, start):
    """
    Run Dijkstra from a single source.
    graph: dict[node] -> list of (neighbor, weight)
    start: starting node
    Returns: dict[node] = distance from start
    """
    dist = defaultdict(lambda: float("inf"))
    dist[start] = 0
    pq = [(0, start)]  # (distance, node)

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in graph[u]:
            if dist[v] > d + w:
                dist[v] = d + w
                heapq.heappush(pq, (dist[v], v))

    return dist

def compute_shortest_path_matrix_dijkstra(stations, sections, station_list, directed=False):
    # Build adjacency list
    graph = defaultdict(list)
    for sec in sections.values():
        o, d, w = sec["origin"], sec["destination"], sec["distance"]
        graph[o].append((d, w))
        if not directed:
            graph[d].append((o, w))

    # Compute all-pairs shortest paths using Dijkstra
    shortest_path = {dest: {} for dest in station_list}

    for origin in station_list:
        dist = dijkstra(graph, origin)
        for dest in station_list:
            #we want it in meters
            shortest_path[dest][origin] = int(round(dist[dest]*1000,0))

    return shortest_path

def check_model_solution(model_node_paths, graph, duty_categories):
    flag = True
    for k, path in model_node_paths.items():
        #print(f"These are the nodes of the current paths for duty {k}")
        #for node in path:
            #print(f"node_id: {graph.graph_nodes[node].node_id} | node_type: {graph.graph_nodes[node].node_type}")
        if len(path) > 0:
            first_task_departure = graph.graph_nodes[path[0]].node_task["departure"]
            last_task_arrival = graph.graph_nodes[path[-1]].node_task["arrival"]
            if last_task_arrival-first_task_departure > 720:
                print(f"Duty {k} is of type {duty_categories[k]}")
                print(f"Duty {k} is infeasible becuase its duration is {last_task_arrival-first_task_departure}")
                flag = False

    return step_results, schedule_figures, final_metrics