from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rescheduling.CrewDeadhead import crew_deadhead_arrival, duty_minutes
from rescheduling.crew_greedy import _required_break_length
from Cost import PenaltyWeights

MAX_DUTY_LENGTH         = 720
MAX_TIME_WITHOUT_BREAK  = 360
LOCO_DEADHEAD_SPEED_KMH = 57.0
MAINT_BUFFER_KM         = 200.0
NONE                    = -1

SC_FIRST_DEP   = 0
SC_LAST_ARR    = 1
SC_LAST_DEST   = 2
SC_DH_M        = 3
SC_LEN         = 4
SC_REQ_BREAK   = 5
SC_BACK_HOME   = 6
SC_CONTINUITY  = 7
SC_UNREACHABLE = 8
SC_EXCESS      = 9
SC_BREAK_SHORT = 10
SC_SLOTS       = 11


def max_deadheads_per_trip(net, threshold: int = MAX_TIME_WITHOUT_BREAK) -> int:
    worst = 0
    for row in net.sp_raw.values():
        for entry in row.values():
            weight = entry.get("weight", 0) if isinstance(entry, dict) else 0
            if weight > worst:
                worst = weight
    minutes = (worst / 1000.0) / LOCO_DEADHEAD_SPEED_KMH * 60
    return max(1, math.ceil(minutes / threshold))


def required_break(driver_status: dict, duty_length: float) -> int:
    base = _required_break_length(duty_length)
    if driver_status["break45done"] or (driver_status["break30done"] and duty_length <= 480):
        return 0
    if driver_status["break30done"]:
        return max(0, base - 30)
    return base


class ScheduleState:

    def __init__(self, mapper, net, trips: dict, trip_order: list,
                 max_duty_length: int = MAX_DUTY_LENGTH,
                 penalty_weights: PenaltyWeights = PenaltyWeights(),
                 loco_info: dict = None, loco_checker=None):
        self.mapper          = mapper
        self.net             = net
        self.loco_checker    = loco_checker
        self.max_duty_length = max_duty_length
        self.penalty_weights = penalty_weights

        in_use          = {e["loco"] for e in trips.values() if e["loco"] is not None}
        self.trip_order = trip_order
        self.trip_at    = {trip_id: i for i, trip_id in enumerate(trip_order)}
        self.locos      = sorted(set(loco_info["usable"]) | in_use if loco_info else in_use)
        self.loco_at    = {loco: j for j, loco in enumerate(self.locos)}

        self.loco_station    = [NONE] * len(self.locos)
        self.loco_ready      = [0.0] * len(self.locos)
        self.loco_km         = [0.0] * len(self.locos)
        self.loco_limit      = [float("inf")] * len(self.locos)
        self.loco_soft_limit = [float("inf")] * len(self.locos)
        self.loco_maint_min  = [0.0] * len(self.locos)
        self.trip_plan_loco = [NONE] * len(trip_order)
        if loco_info:
            for loco, (station, ready, km) in loco_info["start"].items():
                j = self.loco_at[loco]
                self.loco_station[j] = station
                self.loco_ready[j]   = ready
                self.loco_km[j]      = km
            for loco, limit in loco_info.get("limit", {}).items():
                self.loco_limit[self.loco_at[loco]] = limit
            for loco, limit in loco_info.get("soft_limit", {}).items():
                self.loco_soft_limit[self.loco_at[loco]] = limit
            for loco, minutes in loco_info.get("maint_minutes", {}).items():
                self.loco_maint_min[self.loco_at[loco]] = minutes
            for trip_id, loco in loco_info["plan"].items():
                if loco is not None and trip_id in self.trip_at:
                    self.trip_plan_loco[self.trip_at[trip_id]] = self.loco_at[loco]
        self.placed_locos = [j for j in range(len(self.locos)) if self.loco_station[j] != NONE]
        self.drivers    = sorted(mapper.driver_status)
        self.driver_at  = {driver: j for j, driver in enumerate(self.drivers)}
        self.max_dh     = max_deadheads_per_trip(net)

        n = len(trip_order)
        self.trip_loco   = [NONE] * n
        self.trip_driver = [NONE] * n
        self.trip_origin = [NONE] * n
        self.trip_dest   = [NONE] * n
        self.trip_dep    = [0.0] * n
        self.trip_arr    = [0.0] * n
        self.trip_km     = [0.0] * n
        self.trip_maint  = [0] * n

        width = n * self.max_dh
        self.dh_used   = [0] * width
        self.dh_driver = [NONE] * width
        self.dh_origin = [NONE] * width
        self.dh_dest   = [NONE] * width
        self.dh_dep    = [0.0] * width
        self.dh_arr    = [0.0] * width
        self.dh_km     = [0.0] * width
        self.dh_unknown = [0] * width

        for trip_id, entry in trips.items():
            i    = self.trip_at[trip_id]
            task = entry["trip"]
            self.trip_origin[i] = task["origin"]
            self.trip_dest[i]   = task["destination"]
            self.trip_dep[i]    = task["departure"]
            self.trip_arr[i]    = task["arrival"]
            self.trip_km[i]     = entry.get("km", 0.0)
            self.trip_maint[i]  = entry.get("maint", 0)
            if entry["loco"] is None:
                continue
            self.trip_loco[i]   = self.loco_at[entry["loco"]]
            self.trip_driver[i] = self.driver_at[entry["driver"]]
            if len(entry["dh"]) > self.max_dh:
                raise ValueError(f"trip {trip_id}: {len(entry['dh'])} deadhead, "
                                 f"il limite calcolato dalla rete e' {self.max_dh}")
            for k, (dh_task, dh_driver) in enumerate(entry["dh"]):
                j = i * self.max_dh + k
                self.dh_used[j]   = 1
                self.dh_driver[j] = self.driver_at[dh_driver]
                self.dh_origin[j] = dh_task["origin"]
                self.dh_dest[j]   = dh_task["destination"]
                self.dh_dep[j]    = dh_task["departure"]
                self.dh_arr[j]    = dh_task["arrival"]
                self._dh_measure(j)

        d = len(self.drivers)
        self.duty_tasks_list  = [[] for _ in range(d)]
        self.duty_first_dep   = [None] * d
        self.duty_last_arr    = [None] * d
        self.duty_last_dest   = [None] * d
        self.duty_dh_m        = [0.0] * d
        self.duty_len         = [0.0] * d
        self.duty_req_break   = [0] * d
        self.duty_back_home   = [0.0] * d
        self.duty_continuity  = [0.0] * d
        self.duty_unreachable = [0] * d
        self.duty_excess      = [0.0] * d
        self.duty_break_short = [0.0] * d

        self._scratch = [0.0] * SC_SLOTS

        for task in self.used_tasks():
            driver = self.task_driver(task)
            if driver != NONE:
                self._duty_insert(driver, task)
        for driver in range(d):
            self._recompute_duty(driver)

        self._recompute_coverage()

    def _duty_insert(self, driver: int, task: int) -> None:
        tasks = self.duty_tasks_list[driver]
        key   = (self.task_dep(task), task)
        lo, hi = 0, len(tasks)
        while lo < hi:
            mid = (lo + hi) // 2
            if (self.task_dep(tasks[mid]), tasks[mid]) < key:
                lo = mid + 1
            else:
                hi = mid
        tasks.insert(lo, task)

    def _recompute_coverage(self) -> None:
        self._used       = self.used_tasks()
        self._n_canceled = sum(1 for i in range(len(self.trip_order))
                               if not self.trip_is_operated(i))
        self._loco_dh_m  = sum(self._sp_metres(self.dh_origin[j], self.dh_dest[j])
                               for j in range(len(self.dh_used)) if self.dh_used[j])
        self._maint_excess    = sum(self.maintenance_excess(j) for j in range(len(self.locos)))
        self._maint_overdue   = sum(self.maintenance_excess(j, self.loco_soft_limit)
                                    for j in range(len(self.locos)))
        self._loco_overlap    = sum(self.loco_overlap(j) for j in range(len(self.locos)))
        self._loco_unknown    = len(self.unknown_segments())
        self._maint_time      = sum(self.maintenance_time(j) for j in range(len(self.locos)))

    @staticmethod
    def loco_info_from_checker(checker, trip_ids) -> dict:
        from rescheduling.LocoChecker import _epoch_to_minutes

        net    = checker._net
        usable = list(checker._usable_loco_ids)
        start  = {loco: (state["station"], _epoch_to_minutes(state["avail_time"]), state["km"])
                  for loco, state in checker._loco_init.items() if loco in usable}
        plan   = {trip_id: checker.original_loco(trip_id) for trip_id in trip_ids}
        plain  = {loco: net.loco_classes[net.locos_by_id[loco]["class"]]
                                        ["max_kilometers_before_maintenance"]
                  for loco in usable}
        limit  = {loco: km + MAINT_BUFFER_KM for loco, km in plain.items()}
        maint  = {loco: net.loco_classes[net.locos_by_id[loco]["class"]]
                                        ["maintenance_duration"] / 60.0
                  for loco in usable}
        return {"usable": usable, "start": start, "plan": plan, "limit": limit,
                "soft_limit": plain, "maint_minutes": maint}

    @classmethod
    def from_solve_result(cls, result, mapper, net,
                          max_duty_length: int = MAX_DUTY_LENGTH,
                          penalty_weights: PenaltyWeights = PenaltyWeights(),
                          loco_checker = None) -> "ScheduleState":
        trips = {}
        for loco, segments in result.loco_duties.items():
            pending = []
            for task, driver in sorted(segments,
                                       key=lambda s: (s[0]["departure"], s[0]["arrival"])):
                if task.get("type") == "loco_deadhead":
                    pending.append((task, driver))
                    continue
                trips[task["rs_trip_id"]] = {"loco": loco, "trip": task,
                                             "driver": driver, "dh": pending}
                pending = []
            if pending:
                raise ValueError(f"loco {loco}: {len(pending)} deadhead senza un trip che li segue")

        for ct in result.canceled_tasks:
            trips[ct["rs_trip_id"]] = {"loco": None, "trip": ct, "driver": None, "dh": []}

        for entry in result.solution:
            trip = trips.get(entry["id_trip"])
            if trip is None:
                continue
            if entry.get("maintenance_at_departure") == "true":
                trip["maint"] = 1
            elif entry.get("maintenance_at_destination") == "true":
                trip["maint"] = 2
        for trip_id, entry in trips.items():
            section = net.trips_by_id[trip_id]["section"]
            entry["km"] = net.sections[section]["distance"]

        trip_order = sorted(trips, key=lambda t: (trips[t]["trip"]["departure"], t))
        loco_info  = (cls.loco_info_from_checker(loco_checker, trip_order)
                      if loco_checker is not None else None)
        return cls(mapper, net, trips, trip_order, max_duty_length, penalty_weights, loco_info,
                   loco_checker)

    def _sp_metres(self, from_station: int, to_station: int) -> float:
        if from_station == to_station:
            return 0
        return (self.net.sp_raw.get(str(from_station), {})
                             .get(str(to_station), {})
                             .get("weight", 0))

    def crew_arrival(self, origin: int, ready: float, destination: int,
                     departure: float) -> tuple:
        return crew_deadhead_arrival(self.net, origin, destination, ready, departure)

    def task_driver(self, task: int) -> int:
        return self.trip_driver[task] if task >= 0 else self.dh_driver[-task - 1]

    def _set_task_driver(self, task: int, driver: int) -> None:
        if task >= 0:
            self.trip_driver[task] = driver
        else:
            self.dh_driver[-task - 1] = driver

    def task_origin(self, task: int) -> int:
        return self.trip_origin[task] if task >= 0 else self.dh_origin[-task - 1]

    def task_dest(self, task: int) -> int:
        return self.trip_dest[task] if task >= 0 else self.dh_dest[-task - 1]

    def task_dep(self, task: int) -> float:
        return self.trip_dep[task] if task >= 0 else self.dh_dep[-task - 1]

    def task_arr(self, task: int) -> float:
        return self.trip_arr[task] if task >= 0 else self.dh_arr[-task - 1]

    def task_as_dict(self, task: int) -> dict:
        return {"type":        "trip" if task >= 0 else "loco_deadhead",
                "origin":      self.task_origin(task),
                "destination": self.task_dest(task),
                "departure":   self.task_dep(task),
                "arrival":     self.task_arr(task)}

    def used_tasks(self) -> list:
        tasks = []
        for i in range(len(self.trip_order)):
            if self.trip_loco[i] != NONE:
                tasks.append(i)
            base = i * self.max_dh
            for k in range(self.max_dh):
                if self.dh_used[base + k]:
                    tasks.append(-(base + k) - 1)
        return tasks

    def duty_tasks(self, driver: int) -> list:
        return [self.task_as_dict(task) for task in self.duty_tasks_list[driver]]

    def break_ok(self, driver: int) -> bool:
        return self.duty_break_short[driver] == 0

    def _duty_metrics(self, driver: int, tasks: list, out: list) -> None:
        status = self.mapper.driver_status[self.drivers[driver]]

        if not tasks:
            out[SC_FIRST_DEP]   = None
            out[SC_LAST_ARR]    = None
            out[SC_LAST_DEST]   = None
            out[SC_DH_M]        = 0
            out[SC_LEN]         = 0
            out[SC_REQ_BREAK]   = 0
            out[SC_BACK_HOME]   = 0
            out[SC_CONTINUITY]  = 0
            out[SC_UNREACHABLE] = 0
            out[SC_EXCESS]      = 0
            out[SC_BREAK_SHORT] = 0
            return

        last = max(tasks, key=lambda t: self.task_arr(t))

        dh_metres          = 0
        continuity_minutes = 0
        unreachable_links  = 0
        max_gap            = None
        position = status["available_from_station"]
        ready    = status["available_at_time"]
        for index, task in enumerate(tasks):
            origin    = self.task_origin(task)
            departure = self.task_dep(task)
            if position == origin:
                arrival = ready
            else:
                dh_metres += self._sp_metres(position, origin)
                arrival    = self.crew_arrival(position, ready, origin, departure)[1]
            if arrival == float("inf"):
                unreachable_links += 1
                if departure < ready:
                    continuity_minutes += ready - departure
            else:
                gap = departure - arrival
                if gap < 0:
                    continuity_minutes += -gap
                elif (index > 0 or status["duty_length"] > 0) and (max_gap is None or gap > max_gap):
                    max_gap = gap
            position = self.task_dest(task)
            ready    = self.task_arr(task)

        last_arrival     = self.task_arr(last)
        last_destination = self.task_dest(last)
        duty_length = duty_minutes(self.net, status,
                                   self.task_origin(tasks[0]), self.task_dep(tasks[0]),
                                   last_arrival)

        home = (self.mapper.original_schedule.get(self.drivers[driver]) or [{}])[0].get("origin")
        if home is None or last_destination == home:
            back_home = 0
        else:
            back_home = self._sp_metres(last_destination, home)

        needed_break    = required_break(status, duty_length)
        tail            = max(0, self.max_duty_length - duty_length)
        best_gap        = max(tail, 0 if max_gap is None else max_gap)
        break_shortfall = max(0, needed_break - best_gap) if needed_break else 0

        out[SC_FIRST_DEP]   = self.task_dep(tasks[0])
        out[SC_LAST_ARR]    = last_arrival
        out[SC_LAST_DEST]   = last_destination
        out[SC_DH_M]        = dh_metres
        out[SC_LEN]         = duty_length
        out[SC_REQ_BREAK]   = needed_break
        out[SC_BACK_HOME]   = back_home
        out[SC_CONTINUITY]  = continuity_minutes
        out[SC_UNREACHABLE] = unreachable_links
        out[SC_EXCESS]      = max(0, duty_length - self.max_duty_length)
        out[SC_BREAK_SHORT] = break_shortfall

    def _recompute_duty(self, driver: int) -> None:
        out = self._scratch
        self._duty_metrics(driver, self.duty_tasks_list[driver], out)
        self.duty_first_dep[driver]   = out[SC_FIRST_DEP]
        self.duty_last_arr[driver]    = out[SC_LAST_ARR]
        self.duty_last_dest[driver]   = out[SC_LAST_DEST]
        self.duty_dh_m[driver]        = out[SC_DH_M]
        self.duty_len[driver]         = out[SC_LEN]
        self.duty_req_break[driver]   = out[SC_REQ_BREAK]
        self.duty_back_home[driver]   = out[SC_BACK_HOME]
        self.duty_continuity[driver]  = out[SC_CONTINUITY]
        self.duty_unreachable[driver] = out[SC_UNREACHABLE]
        self.duty_excess[driver]      = out[SC_EXCESS]
        self.duty_break_short[driver] = out[SC_BREAK_SHORT]

    def maintenance_stretches(self, loco_index: int, limits: list = None):
        limit = (self.loco_limit if limits is None else limits)[loco_index]
        if limit == float("inf"):
            return
        run = self.loco_km[loco_index]
        for task in self.loco_chain(loco_index):
            if task < 0:
                run += self.dh_km[-task - 1]
                continue
            if self.trip_maint[task] == 1:
                yield run, limit, task
                run = 0.0
            run += self.trip_km[task]
            if self.trip_maint[task] == 2:
                yield run, limit, task
                run = 0.0
        yield run, limit, None

    def maintenance_excess(self, loco_index: int, limits: list = None) -> float:
        return sum(max(0.0, run - limit)
                   for run, limit, _ in self.maintenance_stretches(loco_index, limits))

    def maintenance_windows(self, loco_index: int):
        required = self.loco_maint_min[loco_index]
        if required <= 0:
            return
        chain = self.loco_chain(loco_index)
        for position, task in enumerate(chain):
            if task < 0 or self.trip_maint[task] == 0:
                continue
            if self.trip_maint[task] == 1:
                free = self.task_dep(task) - (self.task_arr(chain[position - 1])
                                              if position else self.loco_ready[loco_index])
                yield task, required, free, NONE
                continue
            following = next((p for p in range(position + 1, len(chain))
                              if chain[p] >= 0), None)
            if following is None:
                continue
            start = self.task_arr(task)
            end   = self.task_dep(chain[following])
            busy  = 0.0
            edge  = start
            for p in range(position + 1, following):
                low  = max(self.task_dep(chain[p]), edge)
                high = min(self.task_arr(chain[p]), end)
                if high > low:
                    busy += high - low
                    edge  = high
            yield task, required, end - start - busy, chain[following]

    def maintenance_time(self, loco_index: int) -> float:
        return sum(max(0.0, required - free)
                   for _, required, free, _ in self.maintenance_windows(loco_index))

    def loco_chain(self, loco_index: int) -> list:
        chain = []
        for i in self.loco_sequence(loco_index):
            base = i * self.max_dh
            for k in range(self.max_dh):
                if self.dh_used[base + k]:
                    chain.append(-(base + k) - 1)
            chain.append(i)
        chain.sort(key=lambda task: (self.task_dep(task), self.task_arr(task)))
        return chain

    def loco_overlap(self, loco_index: int) -> float:
        chain = self.loco_chain(loco_index)
        if not chain:
            return 0.0
        head = (0.0 if self.loco_station[loco_index] == NONE
                else max(0.0, self.loco_ready[loco_index] - self.task_dep(chain[0])))
        return head + sum(max(0.0, self.task_arr(before) - self.task_dep(after))
                          for before, after in zip(chain, chain[1:]))

    def loco_sequence(self, loco_index: int) -> list:
        return [i for i in range(len(self.trip_order)) if self.trip_loco[i] == loco_index]

    def trip_is_operated(self, i: int) -> bool:
        if self.trip_loco[i] == NONE or self.trip_driver[i] == NONE:
            return False
        base = i * self.max_dh
        return all(self.dh_driver[base + k] != NONE
                   for k in range(self.max_dh) if self.dh_used[base + k])

    def _route(self, origin: int, ready: float, destination: int, departure: float) -> list:
        _, segments = self.loco_checker.deadhead_route(origin, ready, destination, departure,
                                                       MAX_TIME_WITHOUT_BREAK)
        if segments is None or len(segments) > self.max_dh:
            return None
        return [(s["origin"], s["destination"], s["departure"], s["arrival"]) for s in segments]

    def cover_plan(self, trip: int, loco_index: int) -> tuple:
        if self.loco_station[loco_index] == NONE:
            return None
        station, ready = self._loco_arrival_before(loco_index, trip)
        own = self._route(station, ready, self.trip_origin[trip], self.trip_dep[trip])
        following = self._next_in_sequence(loco_index, trip)
        after = [] if following == NONE else self._route(
            self.trip_dest[trip], self.trip_arr[trip],
            self.trip_origin[following], self.trip_dep[following])
        if own is None or after is None:
            return None
        return own, following, after

    def uncover_plan(self, trip: int) -> tuple:
        loco_index = self.trip_loco[trip]
        following  = self._next_in_sequence(loco_index, trip)
        if following == NONE:
            return following, []
        station, ready = self._loco_arrival_before(loco_index, trip)
        after = self._route(station, ready, self.trip_origin[following],
                            self.trip_dep[following])
        if after is None:
            return None
        return following, after

    def record(self, trip: int, affected: tuple) -> dict:
        return {"trip": trip, "loco": self.trip_loco[trip], "driver": self.trip_driver[trip],
                "dh": {i: self._dh_snapshot(i) for i in affected if i != NONE}}

    def _set_trip_driver(self, trip: int, driver: int, touched: set) -> None:
        if self.trip_driver[trip] != NONE:
            self.duty_tasks_list[self.trip_driver[trip]].remove(trip)
            touched.add(self.trip_driver[trip])
        self.trip_driver[trip] = driver
        if driver != NONE:
            self._duty_insert(driver, trip)
            touched.add(driver)

    def _finish(self, touched: set) -> None:
        for driver in touched:
            self._recompute_duty(driver)
        self._recompute_coverage()

    def _loco_arrival_before(self, loco_index: int, trip: int) -> tuple:
        previous = NONE
        for i in self.loco_sequence(loco_index):
            if i == trip or self.trip_dep[i] >= self.trip_dep[trip]:
                break
            previous = i
        if previous == NONE:
            return self.loco_station[loco_index], self.loco_ready[loco_index]
        return self.trip_dest[previous], self.trip_arr[previous]

    def _next_in_sequence(self, loco_index: int, trip: int) -> int:
        for i in self.loco_sequence(loco_index):
            if i != trip and self.trip_dep[i] > self.trip_dep[trip]:
                return i
        return NONE

    def _dh_measure(self, j: int) -> None:
        from validator.LocoChecks import deadhead_km

        self.dh_km[j] = ((self.dh_arr[j] - self.dh_dep[j])
                         * LOCO_DEADHEAD_SPEED_KMH / 60.0)
        matrix = deadhead_km(self.net, self.dh_origin[j], self.dh_dest[j],
                             self.dh_dep[j], self.dh_arr[j])
        self.dh_unknown[j] = 1 if matrix == float("inf") else 0

    def unknown_segments(self):
        return [j for j in range(len(self.dh_used))
                if self.dh_used[j] and self.dh_unknown[j]]

    def _dh_snapshot(self, trip: int) -> tuple:
        base = trip * self.max_dh
        return tuple((self.dh_used[base + k], self.dh_driver[base + k],
                      self.dh_origin[base + k], self.dh_dest[base + k],
                      self.dh_dep[base + k], self.dh_arr[base + k],
                      self.dh_km[base + k], self.dh_unknown[base + k])
                     for k in range(self.max_dh))

    def _dh_clear(self, trip: int, touched: set) -> None:
        base = trip * self.max_dh
        for k in range(self.max_dh):
            j = base + k
            if self.dh_used[j] and self.dh_driver[j] != NONE:
                driver = self.dh_driver[j]
                self.duty_tasks_list[driver].remove(-j - 1)
                touched.add(driver)
            self.dh_used[j]   = 0
            self.dh_driver[j] = NONE
            self.dh_origin[j] = NONE
            self.dh_dest[j]   = NONE
            self.dh_dep[j]    = 0.0
            self.dh_arr[j]    = 0.0
            self.dh_km[j]     = 0.0
            self.dh_unknown[j] = 0

    def _dh_write(self, trip: int, segments: list, drivers: tuple, touched: set) -> None:
        base = trip * self.max_dh
        for k, (origin, destination, departure, arrival) in enumerate(segments):
            j = base + k
            self.dh_used[j]   = 1
            self.dh_driver[j] = drivers[k]
            self.dh_origin[j] = origin
            self.dh_dest[j]   = destination
            self.dh_dep[j]    = departure
            self.dh_arr[j]    = arrival
            self._dh_measure(j)
            self._duty_insert(drivers[k], -j - 1)
            touched.add(drivers[k])

    def _dh_restore(self, trip: int, snapshot: tuple, touched: set) -> None:
        base = trip * self.max_dh
        for k, (used, driver, origin, destination, departure, arrival,
                km, unknown) in enumerate(snapshot):
            j = base + k
            self.dh_used[j]   = used
            self.dh_driver[j] = driver
            self.dh_origin[j] = origin
            self.dh_dest[j]   = destination
            self.dh_dep[j]    = departure
            self.dh_arr[j]    = arrival
            self.dh_km[j]     = km
            self.dh_unknown[j] = unknown
            if used and driver != NONE:
                self._duty_insert(driver, -j - 1)
                touched.add(driver)

    def restore(self, record: dict) -> None:
        trip    = record["trip"]
        touched = set()
        if self.trip_driver[trip] != NONE:
            self.duty_tasks_list[self.trip_driver[trip]].remove(trip)
            touched.add(self.trip_driver[trip])
        for affected in record["dh"]:
            self._dh_clear(affected, touched)
        self.trip_loco[trip]   = record["loco"]
        self.trip_driver[trip] = record["driver"]
        if record["driver"] != NONE:
            self._duty_insert(record["driver"], trip)
            touched.add(record["driver"])
        for affected, snapshot in record["dh"].items():
            self._dh_restore(affected, snapshot, touched)
        for driver in touched:
            self._recompute_duty(driver)
        self._recompute_coverage()

    def position_before(self, driver: int, departure: float) -> int:
        status   = self.mapper.driver_status[self.drivers[driver]]
        position = status["available_from_station"]
        for task in self.duty_tasks_list[driver]:
            if self.task_dep(task) >= departure:
                break
            position = self.task_dest(task)
        return position

    def near_drivers(self, task: int, radius_km: float) -> list:
        departure = self.task_dep(task)
        origin    = self.task_origin(task)
        current   = self.task_driver(task)
        limit     = radius_km * 1000
        return [driver for driver in range(len(self.drivers))
                if driver != current
                and self._sp_metres(self.position_before(driver, departure), origin) <= limit]

    def duty_metrics_arrays(self) -> list:
        return [self.duty_first_dep, self.duty_last_arr, self.duty_last_dest,
                self.duty_dh_m, self.duty_len, self.duty_req_break, self.duty_back_home,
                self.duty_continuity, self.duty_unreachable, self.duty_excess,
                self.duty_break_short]

    def snapshot(self) -> dict:
        return {"n_canceled":  self.n_canceled,
                "loco_dh_m":   self.loco_dh_m,
                "trip_loco":   list(self.trip_loco),
                "trip_driver": list(self.trip_driver),
                "dh_used":     list(self.dh_used),
                "dh_driver":   list(self.dh_driver),
                "dh_origin":   list(self.dh_origin),
                "dh_dest":     list(self.dh_dest),
                "dh_dep":      list(self.dh_dep),
                "dh_arr":      list(self.dh_arr),
                "duty_tasks":  [list(tasks) for tasks in self.duty_tasks_list],
                "duty_metrics": [list(array) for array in self.duty_metrics_arrays()]}

    @property
    def n_canceled(self) -> int:
        return self._n_canceled

    @property
    def loco_dh_m(self) -> float:
        return self._loco_dh_m

    @property
    def crew_dh_m(self) -> float:
        return sum(self.duty_dh_m)

    @property
    def back_home(self) -> float:
        return sum(self.duty_back_home)

    def duties_with_violations(self) -> list:
        return [driver for driver in range(len(self.drivers))
                if self.duty_tasks_list[driver]
                and (not self.break_ok(driver)
                     or self.duty_len[driver] >= self.max_duty_length)]
