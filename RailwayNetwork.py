from __future__ import annotations

import heapq
import json

from RollingStockGreedy import (
    build_index,
    filter_sp_to_cpp_matrix,
    compute_disrupted_sp,
)
from VNS_Rescheduling import _get_deadhead_minutes

CREW_SPEED_KMH = 57.0


class RailwayNetwork:
    """
    Wraps the static railway graph (network.json + network-shortestpaths.json)
    and per-instance derived state (filtered SP, disrupted SP, index structures).

    Usage:
        net = RailwayNetwork(NETWORK_FILE, SP_FILE)
        net.build_for_instance(instance)   # instance = json loaded from S*.json
    """

    def __init__(self, network_file: str, sp_file: str):
        with open(network_file) as f:
            self._network_raw: dict = json.load(f)
        with open(sp_file) as f:
            self._sp_raw: dict = json.load(f)

        self._sp_augmented = False

        # Per-instance state — populated by build_for_instance()
        self._sp:               dict | None = None
        self._dsp:              dict | None = None
        self._sections:         dict | None = None
        self._loco_classes:     dict | None = None
        self._maint_stations:   dict | None = None
        self._trips_by_id:      dict | None = None
        self._locos_by_id:      dict | None = None
        self._disrupted_edges:  set  | None = None
        self._disruption_start: int  | None = None   # minutes from baseline
        self._disruption_end:   int  | None = None   # minutes from baseline

    def build_for_instance(self, instance: dict, disruption_start: int, disruption_end: int) -> None:
        """
        Configure per-instance derived state.

        disruption_start / disruption_end: minutes from baseline (already converted
        by the caller via epoch_to_minutes before being passed here).
        """
        disrupted_section_ids = set(instance.get('disrupted_sections', []))

        # The precomputed SP file is asymmetric: some stations appear as
        # origins (rows) but never as destinations in any row, even though
        # the physical network has sections into them. Fill the missing
        # pairs once, before any derived structure is built from sp_raw.
        self._augment_sp_with_dijkstra()

        # RS: filtered SP (loco depots/destinations → trip origins only)
        self._sp  = filter_sp_to_cpp_matrix(self._sp_raw, instance, self._network_raw)
        self._dsp = compute_disrupted_sp(self._network_raw, self._sp, disrupted_section_ids)

        # Crew: full unfiltered SP (any station → any station)
        self._dsp_crew = compute_disrupted_sp(self._network_raw, self._sp_raw, disrupted_section_ids)

        (self._sections,
         self._loco_classes,
         self._maint_stations,
         self._trips_by_id,
         self._locos_by_id) = build_index(instance, self._network_raw)

        self._disrupted_edges = {
            (s['origin'], s['destination'])
            for s in self._network_raw.get('sections', [])
            if s['id'] in disrupted_section_ids
        }
        self._disruption_start = disruption_start
        self._disruption_end   = disruption_end

    def _augment_sp_with_dijkstra(self) -> None:
        """
        Complete sp_raw with Dijkstra-computed entries for missing (i, j)
        pairs where both i and j are SP stations (rows of the file).

        The shortest-paths file only lists 96 of its 100 stations as
        destinations; locos parked at the other 14 are unreachable for the
        crew (sp[X][st] is None for every X → dh = inf → no driver chain).
        These full-graph entries cover deadheads outside the disruption
        window; inside the window, compute_disrupted_sp re-routes them like
        any other pair (and additionally Dijkstra-computes pairs that are
        still missing when it runs).

        Added entries match the file format: {'weight': meters (int),
        'path': [...]} with the path excluding the source and including the
        destination (the convention _get_deadhead_minutes expects).
        Existing entries are never modified. Idempotent.
        """
        if self._sp_augmented:
            return
        self._sp_augmented = True

        sp = self._sp_raw
        station_ids = [int(k) for k in sp]
        targets_str = set(sp.keys())

        # Adjacency over the full physical graph (regular SP, no disruption)
        adj: dict[int, list[tuple[int, int]]] = {}
        for sec in self._network_raw.get('sections', []):
            adj.setdefault(sec['origin'], []).append(
                (sec['destination'], int(round(sec['distance'] * 1000)))
            )

        added = 0
        rows_touched = 0
        for src in station_ids:
            row = sp[str(src)]
            missing = targets_str - set(row.keys()) - {str(src)}
            if not missing:
                continue
            dist: dict[int, int] = {src: 0}
            prev: dict[int, int] = {}
            heap = [(0, src)]
            while heap:
                d, u = heapq.heappop(heap)
                if d > dist.get(u, float('inf')):
                    continue
                for v, w in adj.get(u, []):
                    nd = d + w
                    if nd < dist.get(v, float('inf')):
                        dist[v] = nd
                        prev[v] = u
                        heapq.heappush(heap, (nd, v))
            rows_touched += 1
            for j_str in missing:
                j = int(j_str)
                if j not in dist:
                    continue  # genuinely unreachable — stays inf
                path, cur = [], j
                while cur != src:
                    path.append(cur)
                    cur = prev[cur]
                path.reverse()
                row[j_str] = {'weight': dist[j], 'path': path}
                added += 1
        if added:
            print(f"[RailwayNetwork] SP augmented: {added} missing entries "
                  f"added via Dijkstra across {rows_touched} rows")

    # ------------------------------------------------------------------
    # Graph query
    # ------------------------------------------------------------------

    def shortest_path_entry(self, from_st: int, to_st: int) -> dict | None:
        """Raw SP entry {weight, path} or None if unreachable."""
        if self._sp is None:
            raise RuntimeError("build_for_instance() not called")
        return self._sp.get(str(from_st), {}).get(str(to_st))

    def deadhead_minutes(self, from_st: int, to_st: int,
                         current_time: int, task_departure: int,
                         speed_kmh: float = CREW_SPEED_KMH) -> float:
        """
        Deadhead travel time in minutes from from_st to to_st.
        Uses disrupted SP when the deadhead window overlaps the disruption.
        Returns float('inf') if unreachable.

        speed_kmh: travel speed in km/h.
          - CREW_SPEED_KMH (57.0, default) for passenger deadhead.
          - loco_class['deadhead_speed'] for loco deadhead (driver driving empty loco).
        """
        self._require_instance()
        # Loco deadhead uses filtered sp/dsp; crew deadhead uses full sp_raw/dsp_crew
        use_sp  = self._sp     if speed_kmh != CREW_SPEED_KMH else self._sp_raw
        use_dsp = self._dsp    if speed_kmh != CREW_SPEED_KMH else self._dsp_crew
        dh_min, _ = _get_deadhead_minutes(
            from_st, to_st, current_time, task_departure,
            use_sp, use_dsp,
            self._disruption_start, self._disruption_end,
            speed_kmh,
            disrupted_edges=self._disrupted_edges,
        )
        return dh_min

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def network(self) -> dict:
        return self._network_raw

    @property
    def sp(self) -> dict:
        """Filtered SP — RS use only (loco depots/destinations → trip origins)."""
        self._require_instance()
        return self._sp

    @property
    def sp_raw(self) -> dict:
        """Full unfiltered SP — crew deadhead use (any station → any station)."""
        return self._sp_raw

    @property
    def dsp(self) -> dict:
        """Disrupted SP derived from filtered SP — RS use only."""
        self._require_instance()
        return self._dsp

    @property
    def dsp_crew(self) -> dict:
        """Disrupted SP derived from full SP — crew deadhead use."""
        self._require_instance()
        return self._dsp_crew

    @property
    def sections(self) -> dict:
        self._require_instance()
        return self._sections

    @property
    def loco_classes(self) -> dict:
        self._require_instance()
        return self._loco_classes

    @property
    def maint_stations(self) -> dict:
        self._require_instance()
        return self._maint_stations

    @property
    def trips_by_id(self) -> dict:
        self._require_instance()
        return self._trips_by_id

    @property
    def locos_by_id(self) -> dict:
        self._require_instance()
        return self._locos_by_id

    @property
    def disrupted_edges(self) -> set:
        self._require_instance()
        return self._disrupted_edges

    @property
    def disruption_start(self) -> int:
        self._require_instance()
        return self._disruption_start

    @property
    def disruption_end(self) -> int:
        self._require_instance()
        return self._disruption_end

    # ------------------------------------------------------------------

    def _require_instance(self):
        if self._sp is None:
            raise RuntimeError("build_for_instance() not called")
