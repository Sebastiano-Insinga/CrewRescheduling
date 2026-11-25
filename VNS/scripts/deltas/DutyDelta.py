from Cost import Cost
from ScheduleState import NONE, SC_SLOTS

from .DutySlots import classify


def _inserted(state, tasks: list, task: int) -> list:
    key    = (state.task_dep(task), task)
    out    = list(tasks)
    lo, hi = 0, len(out)
    while lo < hi:
        mid = (lo + hi) // 2
        if (state.task_dep(out[mid]), out[mid]) < key:
            lo = mid + 1
        else:
            hi = mid
    out.insert(lo, task)
    return out


def _without(tasks: list, task: int) -> list:
    out = list(tasks)
    out.remove(task)
    return out


def candidate_duties(state, move) -> dict:
    name = type(move).__name__
    if name == "ChangeDriver":
        if move.d_from == NONE or move.d_to == NONE:
            return None
        return {move.d_from: _without(state.duty_tasks_list[move.d_from], move.task),
                move.d_to:   _inserted(state, state.duty_tasks_list[move.d_to], move.task)}
    if name == "SwapTasks":
        d_a = state.task_driver(move.task_a)
        d_b = state.task_driver(move.task_b)
        if d_a == NONE or d_b == NONE or d_a == d_b:
            return None
        return {d_a: _inserted(state, _without(state.duty_tasks_list[d_a], move.task_a),
                               move.task_b),
                d_b: _inserted(state, _without(state.duty_tasks_list[d_b], move.task_b),
                               move.task_a)}
    return None


def new_buffers(n: int = 2) -> list:
    return [[0.0] * SC_SLOTS for _ in range(n)]


def duty_delta(state, components: list, lists: dict, buffers: list,
               weights: list = None) -> Cost:
    while len(buffers) < len(lists):
        buffers.append([0.0] * SC_SLOTS)
    arrays = state.duty_metrics_arrays()
    after  = []
    for position, (driver, tasks) in enumerate(lists.items()):
        state._duty_metrics(driver, tasks, buffers[position])
        after.append((driver, buffers[position]))

    hard   = 0.0
    soft   = 0.0
    values = []
    for index, component in enumerate(components):
        mapping = classify(component.name)
        if mapping is None:
            values.append(0.0)
            continue
        slot, scale = mapping
        weight = component.weight if weights is None else weights[index]
        raw    = sum(buffer[slot] - arrays[slot][driver] for driver, buffer in after)
        value  = weight * scale * raw
        values.append(value)
        if component.is_hard:
            hard += value
        else:
            soft += value
    return Cost(violations=hard, objective=soft, all_components=tuple(values))
