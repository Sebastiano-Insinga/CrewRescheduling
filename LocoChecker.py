from __future__ import annotations

import math
from datetime import datetime

from RollingStockGreedy import (
    identify_disrupted_trips,
    build_initial_loco_state,
    candidate_locomotives,
    assign_loco_to_trip,
    assign_maintenance_all,
)
from RailwayNetwork import RailwayNetwork

CREW_SPEED_KMH = 57.0
LOCO_DEADHEAD_SPEED_KMH = 57.0  # fixed loco deadhead speed, overrides loco_class['deadhead_speed']
_BASELINE_DAY  = datetime(2018, 9, 10)


def _epoch_to_minutes(epoch_seconds: float) -> int:
    dt   = datetime.fromtimestamp(epoch_seconds)
    diff = dt - _BASELINE_DAY
    return diff.days * 1440 + math.ceil(dt.hour * 60 + dt.minute + dt.second / 60.0)


class LocoChecker:
    """
    Checks locomotive feasibility and deadhead requirements for each trip.

    Wraps build_initial_loco_state, candidate_locomotives,
    assign_loco_to_trip, and assign_maintenance_all, keeping
    all mutable RS state internal.

    buffer_km: km tolerance above max_km_before_maintenance.
    Default 200.0 matches randomized_greedy().

    Responsibilities:
      - candidates(trip_id)             → feasible locos (no state change)
      - deadhead_task(loco_id, trip_id) → loco_deadhead DriverTask or None
      - assign(trip_id, loco_id)        → commit only after crew also confirmed
    """

    def __init__(self, instance: dict, net: RailwayNetwork,
                 buffer_km: float = 200.0,
                 id_mapping: dict | None = None):
        self._net       = net
        self._buffer_km = buffer_km

        dis_start = instance['disruption_start']   # epoch seconds
        dis_end   = instance['disruption_end']     # epoch seconds

        disrupted             = identify_disrupted_trips(instance, net.sections)
        disrupted_section_ids = set(instance.get('disrupted_sections', []))

        completed = {t['id'] for t in instance['train_sections']
                     if t['departure_time'] < dis_start}
        sorted_sections = sorted(instance['train_sections'],
                                 key=lambda t: t['departure_time'])
        self._trip_order: list[int] = [
            t['id'] for t in sorted_sections
            if t['id'] not in completed and t['id'] not in disrupted
        ]

        loco_order   = [l['id'] for l in instance['locomotives']]
        locos_in_sol = {e['locomotive'] for e in instance['solution']
                        if e['locomotive'] != 'canceled'}
        self._usable_loco_ids: list[int] = [lid for lid in loco_order
                                             if lid in locos_in_sol]

        self._loco_init, self._initial_maint_pos = build_initial_loco_state(
            instance, net.sections, net.loco_classes, net.sp,
            dis_start, dis_end, disrupted, self._trip_order,
            disrupted_section_ids=disrupted_section_ids,
        )

        self._initial_sol: dict = {s['id_trip']: s for s in instance['solution']}
        self._dis_start = dis_start
        self._dis_end   = dis_end
        self._disrupted_edges: frozenset = frozenset(
            (net.sections[sid]['origin'], net.sections[sid]['destination'])
            for sid in disrupted_section_ids
            if sid in net.sections
        )

        # Direct section distances: (origin, destination) → km
        self._edge_km: dict[tuple[int, int], float] = {
            (s['origin'], s['destination']): s['distance']
            for s in net.network.get('sections', [])
        }


        # Pre-compute driver task dicts for all trips (origin, dest, times in minutes)
        self._trip_tasks: dict[int, dict] = {
            t_id: {
                'origin':      net.sections[net.trips_by_id[t_id]['section']]['origin'],
                'destination': net.sections[net.trips_by_id[t_id]['section']]['destination'],
                'departure':   _epoch_to_minutes(net.trips_by_id[t_id]['departure_time']),
                'arrival':     _epoch_to_minutes(net.trips_by_id[t_id]['arrival_time']),
                'type':        'trip',
                'id':          None,
            }
            for t_id in self._trip_order
        }

        # Mutable assignment state — modified only via assign()
        self._loco_trips:   dict[int, list[int]] = {}
        self._trip_to_loco: dict[int, int]       = {}
        self._maintenance:  dict[int, int]       = {}

    # ------------------------------------------------------------------
    # Feasibility checks
    # ------------------------------------------------------------------

    def trip_task(self, trip_id: int) -> dict:
        """Pre-computed DriverTask dict for trip_id (type='trip', id=None)."""
        return self._trip_tasks[trip_id]

    @property
    def trip_order(self) -> list[int]:
        """Trips to reschedule, sorted by departure."""
        return self._trip_order
    

    def original_loco(self, trip_id: int) -> int | None:
        """Loco from the pre-disruption solution, or None if not present."""
        return self._initial_sol.get(trip_id, {}).get('locomotive')

    def candidates(self, trip_id: int) -> list[int]:
        """
        Feasible locomotive IDs for trip_id.
        State fully restored after the call (try/undo internally).
        """
        orig = self.original_loco(trip_id)
        if orig is None:
            return []
        net = self._net
        return candidate_locomotives(
            trip_id, orig, self._buffer_km,
            self._loco_trips, self._trip_to_loco, self._maintenance,
            self._loco_init, self._initial_maint_pos, self._usable_loco_ids,
            net.trips_by_id, net.locos_by_id, net.sections, net.loco_classes,
            net.maint_stations, net.sp, net.dsp,
            self._dis_start, self._dis_end,
            self._disrupted_edges,
        )

    def deadhead_duration(self, loco_id: int, trip_id: int,
                          epoch_to_minutes_fn) -> float:
        """
        Total deadhead minutes for loco_id to reach trip_id's origin.
        Returns 0.0 if loco already at trip_origin.

        Call only with loco_id from candidates() — that guarantees the loco
        can reach the trip in time. float('inf') is a defensive fallback only.
        """
        loco_station, loco_avail_ep = self.loco_position(loco_id)
        net         = self._net
        trip        = net.trips_by_id[trip_id]
        trip_origin = net.sections[trip['section']]['origin']

        if loco_station == trip_origin:
            return 0.0

        loco_avail_min = epoch_to_minutes_fn(loco_avail_ep)
        trip_dep_min   = epoch_to_minutes_fn(trip['departure_time'])
        dh_speed_kmh   = LOCO_DEADHEAD_SPEED_KMH

        dh_min = net.deadhead_minutes(
            loco_station, trip_origin, loco_avail_min, trip_dep_min,
            speed_kmh=dh_speed_kmh,
        )
        if dh_min == float('inf') or loco_avail_min + dh_min > trip_dep_min:
            return float('inf')
        return dh_min

    def deadhead_tasks(self, loco_id: int, trip_id: int,
                       epoch_to_minutes_fn,
                       max_duty_length: int = 720) -> list[dict]:
        """
        Returns the list of loco_deadhead DriverTasks needed for loco_id
        to reach trip_id's origin.

        - None: route infeasible (no path or loco arrives too late).
        - Empty list: loco already at trip_origin, no deadhead needed.
        - One element: deadhead fits within max_duty_length.
        - Multiple elements: long deadhead split at intermediate SP stations,
          each segment ≤ max_duty_length minutes.

        All tasks have id=None (assigned at commit by IntegratedRescheduler).
        """
        net         = self._net
        trip        = net.trips_by_id[trip_id]
        trip_origin = net.sections[trip['section']]['origin']

        # Use position of loco immediately before trip_id in the sorted sequence.
        # loco_position() returns position after the last trip by departure_time,
        # which may be a future trip — wrong if trip_id inserts earlier in sequence.
        committed  = self._loco_trips.get(loco_id, [])
        trip_dep   = trip['departure_time']
        prev_trips = [t for t in committed
                      if net.trips_by_id[t]['departure_time'] <= trip_dep]
        if prev_trips:
            prev = max(prev_trips, key=lambda t: net.trips_by_id[t]['departure_time'])
            loco_station  = net.sections[net.trips_by_id[prev]['section']]['destination']
            loco_avail_ep = net.trips_by_id[prev]['arrival_time']
        else:
            loco_station  = self._loco_init[loco_id]['station']
            loco_avail_ep = self._loco_init[loco_id]['avail_time']

        if loco_station == trip_origin:
            return []

        loco_avail_min = epoch_to_minutes_fn(loco_avail_ep)
        trip_dep_min   = epoch_to_minutes_fn(trip['departure_time'])

        dh_speed_kmh = LOCO_DEADHEAD_SPEED_KMH

        # Uses dsp when the deadhead window overlaps disruption AND sp path
        # crosses a disrupted section. Returns inf if no viable route.
        dh_min = net.deadhead_minutes(
            loco_station, trip_origin, loco_avail_min, trip_dep_min,
            speed_kmh=dh_speed_kmh,
        )
        if dh_min == float('inf') or loco_avail_min + dh_min > trip_dep_min:
            return None  # infeasible — caller must reject this loco

        if dh_min <= max_duty_length:
            return [{
                'origin':      loco_station,
                'destination': trip_origin,
                'departure':   loco_avail_min,
                'arrival':     loco_avail_min + dh_min,
                'type':        'loco_deadhead',
                'id':          None,
            }]

        return self._split_deadhead(
            loco_station, trip_origin, loco_avail_min,
            dh_speed_kmh, max_duty_length,
        )

    def commit(self, trip_id: int, loco_id: int) -> dict:
        """
        Commit loco_id to trip_id. Called by IntegratedRescheduler after
        crew assignment is also confirmed.
        Returns {'at_departure': bool, 'at_destination': bool}.
        """
        from RollingStockGreedy import assign_loco_to_trip, assign_maintenance_all
        net = self._net
        assign_loco_to_trip(
            trip_id, loco_id,
            self._loco_trips, self._trip_to_loco, net.trips_by_id,
        )
        assign_maintenance_all(
            self._loco_trips, self._maintenance, self._loco_init,
            self._initial_maint_pos, net.trips_by_id, net.locos_by_id,
            net.sections, net.loco_classes, net.maint_stations,
            net.sp, net.dsp, self._dis_start, self._dis_end,
        )
        m = self._maintenance.get(trip_id, 0)
        return {'at_departure': m == 1, 'at_destination': m == 2}

    def _split_deadhead(self, origin: int, destination: int,
                         departure: float, speed_kmh: float,
                         max_duty_length: int) -> list[dict]:
        """Split a long deadhead into segments along SP path nodes."""
        net   = self._net
        entry = net.sp.get(str(origin), {}).get(str(destination))
        if entry is None:
            return []

        raw_path   = entry.get('path', [])
        path_nodes = [origin] + [int(n) for n in raw_path]

        # Cumulative km along the path:
        # - direct section if the pair is a known network edge
        # - sp_raw otherwise (intermediate nodes implicit between the two)
        cum_km = [0.0]
        for i in range(len(path_nodes) - 1):
            a, b = path_nodes[i], path_nodes[i + 1]
            if (a, b) in self._edge_km:
                km = self._edge_km[(a, b)]
            else:
                sub = net.sp_raw.get(str(a), {}).get(str(b), {}).get('weight')
                if sub is None:
                    raise ValueError(f"No section or sp_raw entry {a} → {b}")
                km = sub/1000
            cum_km.append(cum_km[-1] + km)

        budget_km = speed_kmh * max_duty_length / 60.0
        segments  = []
        cursor    = 0
        t_current = departure

        while cursor < len(path_nodes) - 1:
            # Distance from cursor = sum of adjacent pairs along the path
            feasible = [
                i for i in range(cursor + 1, len(path_nodes))
                if (cum_km[i] - cum_km[cursor]) <= budget_km
            ]
            if not feasible:
                feasible = [cursor + 1]

            split   = feasible[-1]
            seg_km  = cum_km[split] - cum_km[cursor]
            seg_arr = t_current + seg_km / speed_kmh * 60.0
            segments.append({
                'origin':      path_nodes[cursor],
                'destination': path_nodes[split],
                'departure':   t_current,
                'arrival':     seg_arr,
                'type':        'loco_deadhead',
                'id':          None,
            })
            t_current = seg_arr
            cursor    = split

        return segments


    def loco_position(self, loco_id: int) -> tuple[int, float]:
        """(station_id, avail_time_epoch) based on current committed state."""
        net = self._net
        if self._loco_trips.get(loco_id):
            last_trip  = max(self._loco_trips[loco_id],
                             key=lambda t: net.trips_by_id[t]['departure_time'])
            station    = net.sections[net.trips_by_id[last_trip]['section']]['destination']
            avail_time = net.trips_by_id[last_trip]['arrival_time']
        else:
            station    = self._loco_init[loco_id]['station']
            avail_time = self._loco_init[loco_id]['avail_time']
        return station, avail_time

   