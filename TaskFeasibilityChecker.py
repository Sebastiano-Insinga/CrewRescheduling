from __future__ import annotations

from VNS_Rescheduling import (
    _is_task_feasible_with_deadhead,
    _is_break_feasible,
    _required_break_length,
)
from RailwayNetwork import RailwayNetwork
from DriverStatusMapper import DriverStatusMapper

CREW_SPEED_KMH = 57.0


class TaskFeasibilityChecker:
    """
    Checks whether a driver can be assigned a task, accounting for
    deadhead travel and break constraints.

    Wraps _is_task_feasible_with_deadhead and _is_break_feasible.
    Network context and driver data are injected at construction —
    only per-call state (current position, current tasks) is passed
    to is_feasible().

    Usage:
        checker = TaskFeasibilityChecker(net, mapper, max_duty_length=720)
        feasible, dh_min, new_duty = checker.is_feasible(
            task, task_id, driver_id,
            current_origin, current_time, first_departure, current_tasks
        )
    """

    def __init__(self,
                 net:             RailwayNetwork,
                 mapper:          DriverStatusMapper,
                 max_duty_length: int = 720):
        self._net             = net
        self._driver_status   = mapper.driver_status
        self._suitable_tasks  = {d: list(mapper.id_mapping.keys())
                                 for d in mapper.driver_status}
        self._max_duty_length = max_duty_length

    @property
    def max_duty_length(self) -> int:
        return self._max_duty_length

    def is_feasible(
        self,
        task:            dict,
        task_id:         int,
        driver_id:       int,
        current_origin:  int,
        current_time:    int,
        first_departure: int | None,
        current_tasks:   list,
    ) -> bool:
        """
        True if driver_id can be assigned task.

        task           : {id, origin, destination, departure, arrival}
        task_id        : ID used for suitable_tasks qualification check
        driver_id      : duty_id of the candidate driver
        current_origin : station where the driver currently is
        current_time   : minute at which the driver is available
        first_departure: departure of first task in duty (None if no tasks yet)
        current_tasks  : tasks already assigned to this driver in current duty
        """
        feasible, _, _ = self.evaluate(
            task, task_id, driver_id,
            current_origin, current_time, first_departure, current_tasks,
        )
        return feasible

    def evaluate(
        self,
        task:            dict,
        task_id:         int,
        driver_id:       int,
        current_origin:  int,
        current_time:    int,
        first_departure: int | None,
        current_tasks:   list,
        next_gap_minutes: float | None = None,
    ) -> tuple[bool, float, int]:
        """
        Returns (feasible, deadhead_minutes, new_duty_length).
        Use when deadhead_minutes or new_duty_length are needed at commit time.

        next_gap_minutes: idle time between this task's arrival and the
        driver's next assigned task in the chain (if known to the caller).
        Counts as a break slot alongside the pre-gap, since the driver may
        rest there instead of before the task.
        """
        net         = self._net
        driver_duty = self._driver_status[driver_id]
        # Use a known-valid task_id when the caller passes None (loco_deadhead)
        # or a trip_id that is not in the suitable_tasks domain (integrated loop).
        # A12: all drivers qualify for all tasks, so this check always passes anyway.
        valid_ids = self._suitable_tasks.get(driver_id, [])
        if task_id is not None and task_id in valid_ids:
            effective_task_id = task_id
        else:
            effective_task_id = valid_ids[0] if valid_ids else task_id

        feasible, dh_min, new_duty, _ = _is_task_feasible_with_deadhead(
            task, effective_task_id, current_origin, current_time, first_departure,
            driver_duty, self._max_duty_length, self._suitable_tasks, driver_id,
            net.sp_raw, net.dsp_crew,
            net.disruption_start, net.disruption_end,
            CREW_SPEED_KMH,
            disrupted_edges=net.disrupted_edges,
        )
        if not feasible:
            return False, 0.0, 0

        tasks_with_new = current_tasks + [task]
        if not _is_break_feasible(tasks_with_new, new_duty, driver_duty):
            # Gap before the first task in the duty also qualifies as a break slot.
            # _has_break_slot only checks inter-task gaps, missing this idle window.
            b30 = driver_duty["break30done"]
            b45 = driver_duty["break45done"]
            base_req = _required_break_length(new_duty)
            if b45 or (b30 and new_duty <= 480):
                req_break = 0
            elif b30:
                req_break = max(0, base_req - 30)
            else:
                req_break = base_req
            pre_gap = tasks_with_new[0]["departure"] - current_time
            next_gap_ok = (next_gap_minutes is not None
                           and next_gap_minutes >= req_break)
            if not (req_break == 0 or pre_gap >= req_break or next_gap_ok):
                return False, 0.0, 0

        return True, dh_min, new_duty
