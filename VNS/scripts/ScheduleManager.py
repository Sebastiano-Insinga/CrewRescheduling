from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Cost import Cost, PenaltyWeights
from ScheduleState import LOCO_DEADHEAD_SPEED_KMH, NONE, SC_SLOTS
from costs import (BackHome, BreakShortfall, Cancellations, CrewDeadheadKm, DutyExcess,
                   LocoDeadheadKm, LocoOverlap, MaintenanceExcess, MaintenanceTime,
                   ResourceLate, Unreachable, UnreachableLoco)

FORCED_ALTERNATIVE_TAG = "FORCED_ALTERNATIVE"


class ScheduleManager:

    def __init__(self):
        self.components = []
        self._index     = {}

    @classmethod
    def default(cls, evaluator, penalty_weights: PenaltyWeights = PenaltyWeights()
                ) -> "ScheduleManager":
        manager = cls()
        for component in (MaintenanceExcess(penalty_weights.maintenance_km),
                          MaintenanceExcess(penalty_weights.maintenance_km, is_hard=False),
                          MaintenanceTime(penalty_weights.continuity),
                          LocoOverlap(penalty_weights.continuity),
                          ResourceLate(penalty_weights.continuity),
                          Unreachable(penalty_weights.unreachable),
                          UnreachableLoco(penalty_weights.unreachable),
                          BreakShortfall(penalty_weights.break_shortfall),
                          DutyExcess(penalty_weights.duty_excess),
                          Cancellations(evaluator.w_canceled),
                          LocoDeadheadKm(evaluator.w_loco_dh),
                          CrewDeadheadKm(evaluator.w_crew_dh),
                          BackHome(evaluator.w_back_home)):
            manager.add_cost_component(component)
        return manager

    def add_cost_component(self, component) -> int:
        if component.name in self._index:
            raise ValueError(f"componente duplicata: {component.name}")
        self._index[component.name] = len(self.components)
        self.components.append(component)
        return self._index[component.name]

    def get_cost_component(self, index: int):
        return self.components[index]

    def cost_component_index(self, name: str) -> int:
        return self._index[name]

    def set_cost_component_weight(self, index: int, weight: float) -> None:
        self.components[index].weight = weight

    def cost_function_components(self, state, weights: list = None) -> Cost:
        hard_cost = 0.0
        soft_cost = 0.0
        values    = []
        for index, component in enumerate(self.components):
            weight = component.weight if weights is None else weights[index]
            value  = weight * component.compute(state)
            values.append(value)
            if component.is_hard:
                hard_cost += value
            else:
                soft_cost += value
        return Cost(violations=hard_cost, objective=soft_cost,
                    all_components=tuple(values))

    def print_violations(self, state, out=sys.stdout) -> None:
        for component in self.components:
            print(f"{component}: {component.compute(state):g} "
                  f"-> {component.cost(state):.3f}", file=out)
            component.print_violations(state, out)

    def to_solution(self, state, run_info: dict):
        from validator.CrewChecks import idle_windows, required_break_length
        from validator.Solution import CREW_DEADHEAD, LOCO_DEADHEAD, Solution, TRIP

        assignments = []
        for i in range(len(state.trip_order)):
            if not state.trip_is_operated(i):
                continue
            loco_id = state.locos[state.trip_loco[i]]
            assignments.append({
                "type":                       TRIP,
                "trip_id":                    state.trip_order[i],
                "origin":                     state.trip_origin[i],
                "destination":                state.trip_dest[i],
                "departure":                  state.trip_dep[i],
                "arrival":                    state.trip_arr[i],
                "locomotive":                 loco_id,
                "driver":                     state.drivers[state.trip_driver[i]],
                "maintenance_at_departure":   state.trip_maint[i] == 1,
                "maintenance_at_destination": state.trip_maint[i] == 2,
            })
            base = i * state.max_dh
            for k in range(state.max_dh):
                j = base + k
                if not state.dh_used[j]:
                    continue
                assignments.append({
                    "type":        LOCO_DEADHEAD,
                    "trip_id":     None,
                    "origin":      state.dh_origin[j],
                    "destination": state.dh_dest[j],
                    "departure":   state.dh_dep[j],
                    "arrival":     state.dh_arr[j],
                    "locomotive":  loco_id,
                    "driver":      state.drivers[state.dh_driver[j]],
                })

        breaks = {}
        for driver in range(len(state.drivers)):
            tasks = state.duty_tasks_list[driver]
            if not tasks:
                continue
            chain = []
            for task in tasks:
                d = state.task_as_dict(task)
                if chain and chain[-1]["destination"] != d["origin"]:
                    chain.append({
                        "type":        CREW_DEADHEAD,
                        "origin":      chain[-1]["destination"],
                        "destination": d["origin"],
                        "departure":   chain[-1]["arrival"],
                        "arrival":     d["departure"],
                    })
                chain.append(d)
            assignments.extend({**a, "trip_id": None, "locomotive": None,
                                "driver": state.drivers[driver]}
                               for a in chain if a["type"] == CREW_DEADHEAD)

            status   = state.mapper.driver_status[state.drivers[driver]]
            required = required_break_length(status, state.duty_len[driver])
            if required == 0:
                continue
            for start, end, capacity in idle_windows(status, state.net, chain,
                                                      state.duty_len[driver]):
                if capacity >= required:
                    breaks[state.drivers[driver]] = (end - required, end)
                    break

        canceled = [state.trip_order[i] for i in range(len(state.trip_order))
                   if not state.trip_is_operated(i)]

        run_info = dict(run_info)
        if "forced" in run_info:
            run_info["forced"] = {
                str(t): e if isinstance(e, dict) else FORCED_ALTERNATIVE_TAG
                for t, e in run_info["forced"].items()
            }

        return Solution(assignments=assignments, breaks=breaks, canceled=canceled,
                        run_info=run_info, name=run_info.get("instance_id"))

    def check_consistency(self, state) -> list:
        problems = []
        arrays = state.duty_metrics_arrays()
        probe  = [0.0] * SC_SLOTS
        for driver in range(len(state.drivers)):
            tasks = state.duty_tasks_list[driver]
            for position in range(1, len(tasks)):
                before, after = tasks[position - 1], tasks[position]
                if (state.task_dep(before), before) > (state.task_dep(after), after):
                    problems.append(f"turno {driver}: i task non sono in ordine di partenza "
                                    f"fra le posizioni {position - 1} e {position}")
                    break

            state._duty_metrics(driver, tasks, probe)
            stale = [slot for slot, array in enumerate(arrays) if array[driver] != probe[slot]]
            if stale:
                problems.append(f"turno {driver}: metriche vecchie negli slot {stale}")

        cached = (list(state._used), state._n_canceled, state._loco_dh_m,
                  state._maint_excess, state._maint_overdue, state._maint_time,
                  state._loco_overlap, state._loco_unknown)
        state._recompute_coverage()
        if cached != (state._used, state._n_canceled, state._loco_dh_m,
                      state._maint_excess, state._maint_overdue, state._maint_time,
                      state._loco_overlap, state._loco_unknown):
            problems.append("le cache della copertura sono vecchie")

        for i in range(len(state.trip_order)):
            if (state.trip_loco[i] == NONE) != (state.trip_driver[i] == NONE):
                problems.append(f"trip {state.trip_order[i]}: loco={state.trip_loco[i]} "
                                f"driver={state.trip_driver[i]}, coperto a meta'")
            for k in range(state.max_dh):
                j = i * state.max_dh + k
                if state.dh_used[j] and (state.trip_loco[i] == NONE
                                         or state.dh_driver[j] == NONE):
                    problems.append(f"trip {state.trip_order[i]}: deadhead {k} in uso "
                                    f"senza loco o senza driver")
                if state.dh_used[j]:
                    written = ((state.dh_arr[j] - state.dh_dep[j])
                               * LOCO_DEADHEAD_SPEED_KMH / 60.0)
                    if abs(state.dh_km[j] - written) > 1e-6:
                        problems.append(f"trip {state.trip_order[i]}: deadhead {k} "
                                        f"dichiara {state.dh_km[j]:.3f} km ma gli orari "
                                        f"ne scrivono {written:.3f}")
                if not state.dh_used[j] and state.dh_driver[j] != NONE:
                    problems.append(f"trip {state.trip_order[i]}: deadhead {k} libero "
                                    f"ma con driver {state.dh_driver[j]}")

        placed = sorted(task for tasks in state.duty_tasks_list for task in tasks)
        if placed != sorted(state._used):
            problems.append("i task nei turni non coincidono con quelli in uso negli array")
        for index, tasks in enumerate(state.duty_tasks_list):
            for task in tasks:
                if state.task_driver(task) != index:
                    problems.append(f"task {task} nel turno {index} ma assegnato a "
                                    f"{state.task_driver(task)}")
        return problems
