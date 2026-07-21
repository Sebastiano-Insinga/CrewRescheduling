"""
Rolling Stock Rescheduling - Randomized Greedy
Complete Python replication of Roberto's frisch_solution.cc RandomizedGreedy().

Replicates:
  - C++11 std::mt19937 + GCC uniform_int_distribution (for exact RNG match)
  - AssignMaintenanceForLocomotive  (backtracking maintenance placement)
  - ComputeConflicts / ComputeTypeViolations / ComputeUnmaintainedKm
  - CandidateLocomotives  (try-assign + full maintenance + check + restore)
  - Locomotive state initialization at disruption time (ReadInitialSolution)
  - disrupted_shortest_paths: re-routes deadheads that cross the disruption window
"""

import heapq
import json
import os
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# C++11 std::mt19937 + GCC std::uniform_int_distribution replication
# ---------------------------------------------------------------------------

class CppMT19937:
    """
    Replicates C++11 std::mt19937 seeded with g.seed(seed) and
    GCC libstdc++ uniform_int_distribution downscaling rejection algorithm.
    """
    N = 624
    M = 397
    MATRIX_A   = 0x9908B0DF
    UPPER_MASK = 0x80000000
    LOWER_MASK = 0x7FFFFFFF

    def __init__(self, seed: int):
        seed = seed & 0xFFFFFFFF
        self._mt = [0] * self.N
        self._index = self.N
        self._mt[0] = seed
        for i in range(1, self.N):
            self._mt[i] = (
                1812433253 * (self._mt[i - 1] ^ (self._mt[i - 1] >> 30)) + i
            ) & 0xFFFFFFFF

    def _generate_numbers(self):
        mag01 = [0, self.MATRIX_A]
        for i in range(self.N):
            y = (self._mt[i] & self.UPPER_MASK) | (self._mt[(i + 1) % self.N] & self.LOWER_MASK)
            self._mt[i] = self._mt[(i + self.M) % self.N] ^ (y >> 1) ^ mag01[y & 1]
        self._index = 0

    def next32(self) -> int:
        if self._index >= self.N:
            self._generate_numbers()
        y = self._mt[self._index]
        self._index += 1
        y ^= y >> 11
        y ^= (y << 7)  & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= y >> 18
        return y

    def uniform_int(self, a: int, b: int) -> int:
        """Replicates std::uniform_int_distribution<int>(a, b)(g) — GCC downscaling.
        NOTE: GCC always calls g() at least once, even when a==b (u_range==0)."""
        u_range  = b - a
        u_erange = u_range + 1
        urng_range = 0xFFFFFFFF
        scaling = urng_range // u_erange
        past    = u_erange * scaling
        ret = self.next32()
        while ret >= past:
            ret = self.next32()
        return a + ret // scaling


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(instance_file: str, network_file: str, shortestpaths_file: str):
    with open(instance_file) as f:
        instance = json.load(f)
    with open(network_file) as f:
        network = json.load(f)
    with open(shortestpaths_file) as f:
        sp = json.load(f)
    return instance, network, sp


def build_index(instance, network):
    sections     = {s['id']: s   for s in network['sections']}
    loco_classes = {lc['id']: lc for lc in network['locomotive_classes']}
    trips_by_id  = {t['id']: t   for t in instance['train_sections']}
    locos_by_id  = {l['id']: l   for l in instance['locomotives']}

    maint_stations: Dict[int, set] = {}
    for mp in network['maintenance_points']:
        sid = mp['station']
        if sid not in maint_stations:
            maint_stations[sid] = set()
        for lc in mp['maintainable_locomotive_classes']:
            maint_stations[sid].add(lc)

    return sections, loco_classes, maint_stations, trips_by_id, locos_by_id


# ---------------------------------------------------------------------------
# Disrupted shortest paths — replicates TimeRecomputeShortestPaths
# ---------------------------------------------------------------------------

def compute_disrupted_sp(network, sp: Dict, disrupted_section_ids: set) -> Dict:
    """
    Replicates ComputedDisruptedShortestPaths (NDijkstra logic) from
    frisch_input.cc:1092-1173.

    For every (i, j) pair of used stations:
      1. If the original SP path contains no disrupted edge, use it as-is.
      2. Otherwise, scan the path tail for a station k that is in used_station
         and for which dsp[i][k] has already been computed (< inf): build a
         backup path = dsp[i][k] + original_path[k+1..end].
      3. If no backup found, run a fresh Dijkstra(i, j) over the network with
         disrupted sections removed.

    Returns {from_station_id (int): {to_station_id (int): weight_meters (int|inf)}}.
    """
    INT_MAX = 2147483647
    INF = float('inf')

    # (origin, destination) pairs of disrupted sections (= from_to_disrupted)
    from_to_disrupted: set = set()
    edge_dist: Dict[Tuple[int, int], int] = {}
    for sec in network['sections']:
        o, d = sec['origin'], sec['destination']
        dist_m = int(round(sec['distance'] * 1000))
        edge_dist[(o, d)] = dist_m
        if sec['id'] in disrupted_section_ids:
            from_to_disrupted.add((o, d))

    # Adjacency for fallback Dijkstra (disrupted sections removed)
    adj_no_dis: Dict[int, list] = {}
    for sec in network['sections']:
        if sec['id'] in disrupted_section_ids:
            continue
        adj_no_dis.setdefault(sec['origin'], []).append(
            (sec['destination'], int(round(sec['distance'] * 1000)))
        )

    # used_station = source keys of the regular SP file
    used_stations: List[int] = [int(k) for k in sp.keys()]
    used_set = set(used_stations)

    def _fallback_dijkstra(from_station: int, to_station: int) -> Tuple[float, List[int]]:
        if from_station == to_station:
            return 0, [to_station]
        dist: Dict[int, int] = {from_station: 0}
        prev: Dict[int, int] = {}
        heap = [(0, from_station)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist.get(u, INT_MAX):
                continue
            if u == to_station:
                break
            for v, w in adj_no_dis.get(u, []):
                nd = d + w
                if nd < dist.get(v, INT_MAX):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))
        if to_station not in dist:
            return INF, []
        # path excludes source (matches C++ Dijkstra)
        path, cur = [], to_station
        while cur != from_station:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return dist[to_station], path

    # disrupted_shortest_paths[i][j] = {'weight': ..., 'path': [...]}
    dsp_full: Dict[int, Dict[int, dict]] = {
        s: {t: {'weight': INF, 'path': []} for t in used_stations}
        for s in used_stations
    }

    
    
    for i in used_stations:
        i_str = str(i)
        sp_row = sp.get(i_str, {})
        for j in used_stations:
            j_str = str(j)
            entry = sp_row.get(j_str)
            if entry is None:
                # Pair missing from the precomputed SP file (some stations
                # appear only as origins, never as destinations, even though
                # the physical network reaches them) — compute it directly
                # on the disrupted graph.
                w, p = _fallback_dijkstra(i, j)
                dsp_full[i][j] = {'weight': w, 'path': p}
                continue
            if entry['weight'] >= INT_MAX:
                continue  # already inf
            orig_path: List[int] = entry['path']
            orig_w: int = entry['weight']

            # Find LAST disrupted edge in path (scanning from end)
            disrupted_at = -1
            for k in range(len(orig_path) - 2, -1, -1):
                if (orig_path[k], orig_path[k + 1]) in from_to_disrupted:
                    disrupted_at = k
                    break
                    #se la section disrupted è nell'ultima posizione allora esce , fa break 
            if disrupted_at == -1:
                dsp_full[i][j] = {'weight': orig_w, 'path': list(orig_path)}
                continue

            # Try backup: scan k from end down to disrupted_at + 1
            backup_found = False
            for k in range(len(orig_path) - 1, disrupted_at, -1):
                st_k = orig_path[k]
                if st_k not in used_set:
                    continue
                if dsp_full[i][st_k]['weight'] >= INF:
                    continue
                # Backup applies: prepend dsp[i][st_k] then append orig[k+1..end]
                new_path = list(dsp_full[i][st_k]['path'])
                new_w = dsp_full[i][st_k]['weight']
                for l in range(k + 1, len(orig_path)):
                    new_path.append(orig_path[l])
                    # Mirror C++ exactly: GetDistance(path[l], path[l-1])
                    # (note reversed argument order)
                    new_w += edge_dist.get((orig_path[l], orig_path[l - 1]), 0)
                dsp_full[i][j] = {'weight': new_w, 'path': new_path}
                backup_found = True
                break

            if not backup_found:
                w, p = _fallback_dijkstra(i, j)
                dsp_full[i][j] = {'weight': w, 'path': p}

    # Return weight-only matrix (matches existing _dh_info contract)
    dsp: Dict[int, Dict[int, float]] = {
        s: {t: dsp_full[s][t]['weight'] for t in used_stations}
        for s in used_stations
    }
    return dsp


# ---------------------------------------------------------------------------
# Disruption helpers
# ---------------------------------------------------------------------------

def identify_disrupted_trips(instance, sections) -> set:
    disrupted_secs = set(instance['disrupted_sections'])
    dis_start = instance['disruption_start']
    dis_end   = instance['disruption_end']
    disrupted = set()
    for t in instance['train_sections']:
        if t['section'] in disrupted_secs:
            if t['departure_time'] <= dis_end and t['arrival_time'] >= dis_start:
                disrupted.add(t['id'])
    return disrupted


def get_deadhead_info(sp, from_station: int, to_station: int, deadhead_speed: float):
    """Return (time_seconds, dist_km) using the regular SP. Inf if unreachable.

    NOTE: relies on `sp` being already filtered by `filter_sp_to_cpp_matrix` so
    that missing entries correctly reflect cells C++ leaves at INT_MAX.
    """
    entry = sp.get(str(from_station), {}).get(str(to_station))
    if entry is None:
        return float('inf'), float('inf')
    if from_station == to_station:
        return 0.0, 0.0
    distance_km = entry['weight'] / 1000.0
    time_seconds = (distance_km / deadhead_speed) * 3600.0
    return time_seconds, distance_km


def filter_sp_to_cpp_matrix(sp: Dict, instance: Dict, network: Dict) -> Dict:
    """
    Filter the SP file to mirror C++ NDijkstra cell population.
    C++ shortest_paths[i][j] is populated only when
        (is_destination[i] || is_locomotive_starting[i]) && is_origin[j]
    where is_locomotive_starting reflects ORIGINAL loco depots (state at
    NDijkstra call time, before ReadInitialSolution updates).
    Cells removed from sp will return INF on lookup.
    """
    # Step 1: indice sezioni per ID (lookup O(1) invece di scorrere la lista)
    sec_by_id = {s['id']: s for s in network['sections']}

    # Step 2: raccogli stazioni di origine/destinazione dei train_sections.
    # Una loco "arriva" all'origine di un trip e "parte" dalla sua destinazione.
    is_origin: set = set()
    is_destination: set = set()
    for t in instance['train_sections']:
        sec = sec_by_id[t['section']]
        is_origin.add(sec['origin'])
        is_destination.add(sec['destination'])

    # Step 3: depot iniziali delle locomotive.
    # Usa lo stato ORIGINALE (prima di ReadInitialSolution) per matchare il C++:
    # NDijkstra viene chiamato prima che le loco vengano riposizionate.
    is_loc_start_initial: set = {
        loc['initial_departure_station'] for loc in instance['locomotives']
    }

    # Step 4: condizione C++ -> (is_destination[i] || is_loc_start[i]) && is_origin[j].
    # Una loco parte (src) da fine-trip o depot iniziale; arriva (dst) a inizio-trip.
    valid_sources = is_destination | is_loc_start_initial
    valid_targets = is_origin

    # Step 5: filtra la matrice sp tenendo solo le coppie (src, dst) valide.
    # Le chiavi JSON sono stringhe, i set contengono int -> serve int(...) per il confronto.
    # Le celle rimosse faranno restituire INF al lookup nel codice chiamante.
    filtered: Dict = {}
    for src_str, row in sp.items():
        src = int(src_str)
        if src not in valid_sources:
            continue
        new_row = {dst: entry for dst, entry in row.items() if int(dst) in valid_targets}
        if new_row:
            filtered[src_str] = new_row
    return filtered


def _dh_info(sp, dsp: Optional[Dict], from_station: int, to_station: int,
             deadhead_start_time: float, deadhead_end_time: float,
             dis_start: float, dis_end: float,
             deadhead_speed: float):
    """
    Calcola tempo e distanza del deadhead da from_station a to_station.
    Usa il grafo disrupted (dsp) se il deadhead si sovrappone alla finestra di disruption:
      deadhead_start_time <= dis_end  AND  deadhead_end_time >= dis_start
    Altrimenti usa il grafo normale (sp).

    deadhead_start_time: arrival_time del trip precedente (o avail_time della loco)
    deadhead_end_time:   departure_time del trip successivo

    Ritorna: (time_seconds, dist_km) oppure (inf, inf) se irraggiungibile.
    """
    crosses_disruption_window = (dsp is not None and
                                 deadhead_start_time <= dis_end and
                                 deadhead_end_time >= dis_start)

    if crosses_disruption_window:
        if from_station == to_station:
            return 0.0, 0.0
        dist_meters = dsp.get(from_station, {}).get(to_station, float('inf'))
        if dist_meters == float('inf'):
            return float('inf'), float('inf')
        dist_km = dist_meters / 1000.0
        time_s  = (dist_km / deadhead_speed) * 3600.0
        return time_s, dist_km
    else:
        return get_deadhead_info(sp, from_station, to_station, deadhead_speed)


# ---------------------------------------------------------------------------
# Locomotive initial state at disruption time
# Replicates ReadInitialSolution() locomotive state computation from frisch_input.cc
# Note: C++ calls GetDeadhead(..., use_pre_disruption_deadheads=true) here,
# so we always use regular sp (no disrupted paths).
# ---------------------------------------------------------------------------

def _scan_fixed_trips(
    loco_id, loco, all_trips, n_trips, is_fixed_by_idx,
    assignment_by_idx, maint_pos_by_trip,
    sections, sp, deadhead_speed,
    disrupted_section_ids, disruption_start, initial_km,
):
    """
    Scorre i trip fixed (departure_time < disruption_start) nell'ordine C++:
    - while is_fixed_by_idx[j]: accumula km per questa locomotiva
    - poi continua da j per trovare il primo trip non-fixed (next_planned_idx)
    Ritorna: (last_fixed_idx, next_planned_idx, km_accumulated, caught_in_disruption)
    """
    km_accumulated      = initial_km
    last_fixed_idx      = -1
    next_planned_idx    = -1
    caught_in_disruption = False

    j = 0
    while j < n_trips and is_fixed_by_idx[j]:
        if assignment_by_idx[j] == loco_id:
            trip     = all_trips[j]
            maint_pos = maint_pos_by_trip.get(trip['id'], 0)
            origin   = sections[trip['section']]['origin']
            if maint_pos == 1:
                km_accumulated = sections[trip['section']]['distance']
            elif maint_pos == 2:
                km_accumulated = 0
            else:
                if last_fixed_idx == -1:
                    _, dh = get_deadhead_info(sp, loco['initial_departure_station'], origin, deadhead_speed)
                else:
                    prev_dest = sections[all_trips[last_fixed_idx]['section']]['destination']
                    _, dh = get_deadhead_info(sp, prev_dest, origin, deadhead_speed)
                km_accumulated += (dh if dh != float('inf') else 0.0) + sections[trip['section']]['distance']
            if (disrupted_section_ids and
                    trip['arrival_time'] >= disruption_start and
                    trip['section'] in disrupted_section_ids):
                caught_in_disruption = True


            last_fixed_idx = j
        j += 1

    while j < n_trips:
        if assignment_by_idx[j] == loco_id:
            next_planned_idx = j
            break
        j += 1

    return last_fixed_idx, next_planned_idx, km_accumulated, caught_in_disruption


def _determine_loco_position(
    last_fixed_idx, next_planned_idx, km_accumulated, caught_in_disruption,
    all_trips, sections, maint_pos_by_trip,
    sp, deadhead_speed, disruption_start, disruption_end,
):
    """
    Determina station e avail_time della locomotiva alla disruption_start,
    in base all'ultimo trip completato (last_fixed_idx) e al prossimo pianificato (next_planned_idx).
    Ritorna: (station, avail_time, km_accumulated)
    """
    avail_time = disruption_start

    if last_fixed_idx != -1:
        last_trip = all_trips[last_fixed_idx]
        #If the locomotive arrived before the disruption started and if are not any planned trip after the disruption, the locomotive will be at the last station of the last trip
        
        if last_trip['arrival_time'] < disruption_start:
            # Loco già arrivata prima della disruption
            if next_planned_idx == -1:
                station = sections[last_trip['section']]['destination']
                # we compute the km_accumulated until the last trip if the locomotive has not done the maintenance at the destination of the last trip, otherwise we set it to 0
            else:
                next_trip    = all_trips[next_planned_idx]
                next_origin  = sections[next_trip['section']]['origin']
                next_maint   = maint_pos_by_trip.get(next_trip['id'], 0)
                station      = next_origin
                avail_time   = next_trip['departure_time']
                if next_maint == 1:
                    km_accumulated = 0
                else:
                    last_dest = sections[last_trip['section']]['destination']
                    _, dh = get_deadhead_info(sp, last_dest, next_origin, deadhead_speed)
                    km_accumulated += dh if dh != float('inf') else 0.0
        else:
            # Loco is still traveling at the disruption start time: we consider it to be at the destination of the last trip
            # Computation of the available time to do other trips: maximum between the disruption end and the arrival + the time remaining of the dirsuption
            station = sections[last_trip['section']]['destination']
            if caught_in_disruption:
                arr = last_trip['arrival_time']
                avail_time = max(disruption_end, arr + (disruption_end - disruption_start))
            else:
    
                avail_time = last_trip['arrival_time']
    elif next_planned_idx != -1:
        # Nessun trip completato: la loco è già posizionata all'origine del prossimo trip
        next_trip   = all_trips[next_planned_idx]
        next_origin = sections[next_trip['section']]['origin']
        next_maint  = maint_pos_by_trip.get(next_trip['id'], 0)
        station     = next_origin
        if next_maint == 1:
            km_accumulated = 0
    else:
        # Nessun trip: la loco rimane al depot
        station = None  # caller sostituisce con initial_departure_station

    return station, avail_time, km_accumulated


def build_initial_loco_state(
    instance, sections: Dict, loco_classes: Dict, sp: Dict,
    disruption_start: float, disruption_end: float,
    disrupted_trips: set, trip_order: List,
    disrupted_section_ids: set = None,
):
    """
    Computes per-locomotive initial state at the start of rescheduling.
    Exactly replicates ReadInitialSolution() from frisch_input.cc.

    Returns:
        loco_state: dict loco_id -> {'station', 'avail_time', 'km'}
        maint_pos_by_trip: dict trip_id -> 0 / 1 (at dep) / 2 (at arr)
    """
    # C++ sorts train_trips by departure_time before ReadInitialSolution (frisch_input.cc:214)
    all_trips    = sorted(instance['train_sections'], key=lambda t: t['departure_time'])
    n_trips      = len(all_trips)
    locos_by_id  = {l['id']: l for l in instance['locomotives']}
    loco_order   = [l['id'] for l in instance['locomotives']]

    solution_by_trip_id = {e['id_trip']: e for e in instance['solution']}
    assignment_by_idx   = [None] * n_trips
    maint_pos_by_trip: Dict[int, int] = {}

    for i, trip in enumerate(all_trips):
        entry = solution_by_trip_id.get(trip['id'])
        if entry is None:
            continue
        loco_id = entry.get('locomotive')
        assignment_by_idx[i] = loco_id if loco_id != 'canceled' else None
        maint_pos = 0
        if entry.get('maintenance_at_departure') == 'true':
            maint_pos = 1
        elif entry.get('maintenance_at_destination') == 'true':
            maint_pos = 2
        maint_pos_by_trip[trip['id']] = maint_pos

    is_fixed_by_idx = [all_trips[i]['departure_time'] < disruption_start for i in range(n_trips)]

    loco_state: Dict = {}

    for loco_id in loco_order:
        loco         = locos_by_id[loco_id]
        loco_class   = loco_classes[loco['class']]
        deadhead_speed = loco_class['deadhead_speed']

        last_fixed_idx, next_planned_idx, km_accumulated, caught_in_disruption = _scan_fixed_trips(
            loco_id, loco, all_trips, n_trips, is_fixed_by_idx,
            assignment_by_idx, maint_pos_by_trip,
            sections, sp, deadhead_speed,
            disrupted_section_ids, disruption_start,
            loco['kilometers_since_last_maintenance'],
        )

        station, avail_time, km_accumulated = _determine_loco_position(
            last_fixed_idx, next_planned_idx, km_accumulated, caught_in_disruption,
            all_trips, sections, maint_pos_by_trip,
            sp, deadhead_speed, disruption_start, disruption_end,
        )

        if station is None:
            station = loco['initial_departure_station']

        loco_state[loco_id] = {
            'station':    station,
            'avail_time': avail_time,
            'km':         max(0.0, km_accumulated),
        }

    return loco_state, maint_pos_by_trip


# ---------------------------------------------------------------------------
# Global assignment state helpers
# ---------------------------------------------------------------------------

def assign_loco_to_trip(trip_id: int, loco_id: int,
                         loco_trips: Dict, trip_to_loco: Dict,
                         trips_by_id: Dict):
    """Insert trip_id into loco's sorted sequence by departure time."""
    dep = trips_by_id[trip_id]['departure_time']
    seq = loco_trips.setdefault(loco_id, [])
    i = 0
    while i < len(seq) and trips_by_id[seq[i]]['departure_time'] <= dep:
        i += 1
    seq.insert(i, trip_id)
    trip_to_loco[trip_id] = loco_id


def remove_loco_from_trip(trip_id: int,
                           loco_trips: Dict, trip_to_loco: Dict,
                           maintenance: Dict):
    """Remove trip_id from its assigned loco and clear its maintenance."""
    loco_id = trip_to_loco.pop(trip_id, None)
    if loco_id is not None:
        seq = loco_trips.get(loco_id, [])
        if trip_id in seq:
            seq.remove(trip_id)
    maintenance.pop(trip_id, None)


# ---------------------------------------------------------------------------
# Maintenance placement — replicates AssignMaintenanceForLocomotive
# ---------------------------------------------------------------------------

def _maint_feasible_at(
    loco_id: int, trip_idx: int, pos: int,
    trips_seq: List, loco_init: Dict,
    trips_by_id: Dict, locos_by_id: Dict,
    sections: Dict, loco_classes: Dict, maint_stations: Dict,
    sp: Dict, dsp: Optional[Dict], dis_start: float, dis_end: float,
) -> bool:
    """
    Replicates MaintenanceFeasibleAtStation(loc, trip, arrival_or_departure).
    pos: 1 = departure, 2 = arrival.
    Uses disrupted SP for deadheads that cross the disruption window.
    """
    tid   = trips_seq[trip_idx]
    loco  = locos_by_id[loco_id]
    lc    = loco_classes[loco['class']]
    sec   = sections[trips_by_id[tid]['section']]
    maint_dur = lc['maintenance_duration']
    dh_speed  = lc['deadhead_speed']

    station = sec['origin'] if pos == 1 else sec['destination']

    if station not in maint_stations:
        return False
    if loco['class'] not in maint_stations[station]:
        return False

    if pos == 1:
        trip_dep = trips_by_id[tid]['departure_time']
        if trip_idx == 0:
            prev_station = loco_init[loco_id]['station']
            prev_avail   = loco_init[loco_id]['avail_time']
        else:
            prev_tid     = trips_seq[trip_idx - 1]
            prev_avail   = trips_by_id[prev_tid]['arrival_time']
            prev_station = sections[trips_by_id[prev_tid]['section']]['destination']
        dh_time, _ = _dh_info(sp, dsp, prev_station, station,
                               prev_avail, trip_dep,
                               dis_start, dis_end, dh_speed)
        if dh_time == float('inf'):
            return False
        return prev_avail + dh_time + maint_dur <= trip_dep
    else:
        n = len(trips_seq)
        if trip_idx == n - 1:
            return True
        next_tid    = trips_seq[trip_idx + 1]
        this_arr    = trips_by_id[tid]['arrival_time']
        next_dep    = trips_by_id[next_tid]['departure_time']
        next_origin = sections[trips_by_id[next_tid]['section']]['origin']
        dh_time, _  = _dh_info(sp, dsp, station, next_origin,
                                this_arr, next_dep,
                                dis_start, dis_end, dh_speed)
        if dh_time == float('inf'):
            return False
        return this_arr + maint_dur + dh_time <= next_dep


def assign_maintenance_for_loco(
    loco_id: int,
    loco_trips: Dict,
    maintenance: Dict,
    loco_init: Dict,
    initial_maint_pos: Dict,
    trips_by_id: Dict,
    locos_by_id: Dict,
    sections: Dict,
    loco_classes: Dict,
    maint_stations: Dict,
    sp: Dict,
    dsp: Optional[Dict] = None,
    dis_start: float = 0.0,
    dis_end: float = 0.0,
):
    """
    Replicates AssignMaintenanceForLocomotive from frisch_solution.cc.
    Modifies `maintenance` dict in-place.
    Uses disrupted SP when deadheads cross the disruption window.
    """
    trips_seq = loco_trips.get(loco_id, [])
    for tid in trips_seq:
        maintenance.pop(tid, None)
    if not trips_seq:
        return

    lc       = loco_classes[locos_by_id[loco_id]['class']]
    max_km   = lc['max_kilometers_before_maintenance']
    dh_speed = lc['deadhead_speed']
    init     = loco_init[loco_id]

    km             = init['km']
    last_maint_idx = -1
    last_maint_pos = None

    def feasible(idx, pos):
        return _maint_feasible_at(loco_id, idx, pos, trips_seq, loco_init,
                                  trips_by_id, locos_by_id, sections,
                                  loco_classes, maint_stations,
                                  sp, dsp, dis_start, dis_end)

    def assign_maint(idx, pos):
        nonlocal km, last_maint_idx, last_maint_pos
        maintenance[trips_seq[idx]] = pos
        km = 0.0
        last_maint_idx = idx
        last_maint_pos = pos

    def backtrack(from_idx, from_pos):
        # Walk backwards from one step before (from_idx, from_pos)
        bt_idx = from_idx if from_pos == 2 else from_idx - 1
        bt_pos = 1        if from_pos == 2 else 2
        while bt_idx >= 0 and bt_idx != last_maint_idx:
            if feasible(bt_idx, bt_pos):
                assign_maint(bt_idx, bt_pos)
                return
            if bt_pos == 1:
                bt_idx -= 1
                bt_pos  = 2
            else:
                bt_pos = 1

    for i, tid in enumerate(trips_seq):
        trip = trips_by_id[tid]
        sec  = sections[trip['section']]

        # pos=1: deadhead to trip start
        # C++: unreachable deadhead adds INT_MAX → km becomes huge → triggers backtrack
        if i == 0:
            dh_from, dh_dep = init['station'], init['avail_time']
        else:
            prev    = trips_by_id[trips_seq[i - 1]]
            dh_from = sections[prev['section']]['destination']
            dh_dep  = prev['arrival_time']

        _, dh_dist = _dh_info(sp, dsp, dh_from, sec['origin'],
                              dh_dep, trip['departure_time'],
                              dis_start, dis_end, dh_speed)
        km += dh_dist

        if initial_maint_pos.get(tid, 0) == 1 and feasible(i, 1):
            assign_maint(i, 1)
        if km > max_km:
            backtrack(i, 1)

        # pos=2: trip distance
        km += sec['distance']

        if initial_maint_pos.get(tid, 0) == 2 and feasible(i, 2):
            assign_maint(i, 2)
        if km > max_km:
            backtrack(i, 2)


def assign_maintenance_all(
    loco_trips: Dict, maintenance: Dict, loco_init: Dict,
    initial_maint_pos: Dict,
    trips_by_id: Dict, locos_by_id: Dict,
    sections: Dict, loco_classes: Dict, maint_stations: Dict,
    sp: Dict, dsp: Optional[Dict] = None,
    dis_start: float = 0.0, dis_end: float = 0.0,
):
    """Replicates AssignFullMaintenance: run for every used loco."""
    for loco_id in loco_trips:
        if loco_trips[loco_id]:
            assign_maintenance_for_loco(
                loco_id, loco_trips, maintenance, loco_init,
                initial_maint_pos, trips_by_id, locos_by_id,
                sections, loco_classes, maint_stations,
                sp, dsp, dis_start, dis_end,
            )


# ---------------------------------------------------------------------------
# Feasibility checks — replicates ComputeConflicts, ComputeTypeViolations,
# ComputeUnmaintainedKm from frisch_solution.cc
# ---------------------------------------------------------------------------

def _feasible_by_time_start(loco_id: int, trip_id: int, with_maintenance: bool,
                              loco_init: Dict, trips_by_id: Dict, locos_by_id: Dict,
                              sections: Dict, loco_classes: Dict,
                              sp: Dict, dsp: Optional[Dict],
                              dis_start: float, dis_end: float) -> bool:
    """FeasibleByTimeStart: can loco reach trip from its initial position?"""
    loco = locos_by_id[loco_id]
    lc   = loco_classes[loco['class']]
    dh_speed  = lc['deadhead_speed']
    maint_dur = lc['maintenance_duration'] if with_maintenance else 0.0

    trip_origin = sections[trips_by_id[trip_id]['section']]['origin']
    trip_dep    = trips_by_id[trip_id]['departure_time']
    station     = loco_init[loco_id]['station']
    ready_time= loco_init[loco_id]['avail_time']

    dh_time, _ = _dh_info(sp, dsp, station, trip_origin,
                           ready_time, trip_dep,
                           dis_start, dis_end, dh_speed)
    if dh_time == float('inf'):
        return False
    return ready_time + dh_time + maint_dur <= trip_dep


def _feasible_by_time_trips(loco_id: int, trip1_id: int, trip2_id: int,
                              locos_by_id: Dict, trips_by_id: Dict,
                              sections: Dict, loco_classes: Dict,
                              sp: Dict, dsp: Optional[Dict],
                              dis_start: float, dis_end: float) -> bool:
    """FeasibleByTimeTrips: can loco go from trip1 to trip2?"""
    loco_class   = loco_classes[locos_by_id[loco_id]['class']]
    deadhead_speed = loco_class['deadhead_speed']

    trip1_destination = sections[trips_by_id[trip1_id]['section']]['destination']
    trip2_origin      = sections[trips_by_id[trip2_id]['section']]['origin']
    trip1_arrival     = trips_by_id[trip1_id]['arrival_time']
    trip2_departure   = trips_by_id[trip2_id]['departure_time']

    dh_time, _ = _dh_info(sp, dsp, trip1_destination, trip2_origin,
                           trip1_arrival, trip2_departure,
                           dis_start, dis_end, deadhead_speed)
    if dh_time == float('inf'):
        return False
    return trip1_arrival + dh_time <= trip2_departure


def _time_for_maintenance_between(loco_id: int, trip1_id, trip2_id: int,
                                   loco_init: Dict, locos_by_id: Dict, trips_by_id: Dict,
                                   sections: Dict, loco_classes: Dict,
                                   sp: Dict, dsp: Optional[Dict],
                                   dis_start: float, dis_end: float) -> bool:
    """TimeForMaintenanceBetweenTrips: can loco reach trip2 from trip1 with maintenance?"""
    loco = locos_by_id[loco_id]
    lc   = loco_classes[loco['class']]
    dh_speed  = lc['deadhead_speed']
    maint_dur = lc['maintenance_duration']

    if trip1_id is None:
        return _feasible_by_time_start(loco_id, trip2_id, True,
                                        loco_init, trips_by_id, locos_by_id,
                                        sections, loco_classes,
                                        sp, dsp, dis_start, dis_end)

    dest1   = sections[trips_by_id[trip1_id]['section']]['destination']
    origin2 = sections[trips_by_id[trip2_id]['section']]['origin']
    arr1    = trips_by_id[trip1_id]['arrival_time']
    dep2    = trips_by_id[trip2_id]['departure_time']

    dh_time, _ = _dh_info(sp, dsp, dest1, origin2,
                           arr1, dep2,
                           dis_start, dis_end, dh_speed)
    if dh_time == float('inf'):
        return False
    return arr1 + maint_dur + dh_time <= dep2


def compute_conflicts(
    loco_trips: Dict, maintenance: Dict, loco_init: Dict,
    trips_by_id: Dict, locos_by_id: Dict,
    sections: Dict, loco_classes: Dict,
    sp: Dict, dsp: Optional[Dict] = None,
    dis_start: float = 0.0, dis_end: float = 0.0,
) -> int:
    """ComputeConflicts: count temporal conflicts across all locos."""
    conflicts = 0
    for loco_id, seq in loco_trips.items():
        if not seq:
            continue
        first = seq[0]
        maint_first = maintenance.get(first, 0)
        if maint_first == 1:
            if not _time_for_maintenance_between(loco_id, None, first,
                                                  loco_init, locos_by_id, trips_by_id,
                                                  sections, loco_classes,
                                                  sp, dsp, dis_start, dis_end):
                conflicts += 1
        else:
            if not _feasible_by_time_start(loco_id, first, False,
                                            loco_init, trips_by_id, locos_by_id,
                                            sections, loco_classes,
                                            sp, dsp, dis_start, dis_end):
                conflicts += 1
        for i in range(len(seq) - 1):
            t1, t2 = seq[i], seq[i + 1]
            m1 = maintenance.get(t1, 0)
            m2 = maintenance.get(t2, 0)
            if m1 == 2 or m2 == 1:
                if not _time_for_maintenance_between(loco_id, t1, t2,
                                                      loco_init, locos_by_id, trips_by_id,
                                                      sections, loco_classes,
                                                      sp, dsp, dis_start, dis_end):
                    conflicts += 1
            else:
                if not _feasible_by_time_trips(loco_id, t1, t2,
                                                locos_by_id, trips_by_id,
                                                sections, loco_classes,
                                                sp, dsp, dis_start, dis_end):
                    conflicts += 1
    return conflicts


def compute_type_violations(
    loco_trips: Dict, trips_by_id: Dict, locos_by_id: Dict,
) -> int:
    """ComputeTypeViolations: count trips where loco class is not allowed."""
    violations = 0
    for loco_id, seq in loco_trips.items():
        loco = locos_by_id[loco_id]
        for tid in seq:
            if loco['class'] not in trips_by_id[tid]['locomotive_orders']:
                violations += 1
    return violations


def compute_unmaintained_km(
    loco_trips: Dict, maintenance: Dict, loco_init: Dict,
    trips_by_id: Dict, locos_by_id: Dict,
    sections: Dict, loco_classes: Dict,
    sp: Dict, buffer_km: float = 200.0,
    dsp: Optional[Dict] = None,
    dis_start: float = 0.0, dis_end: float = 0.0,
) -> float:
    """
    ComputeUnmaintainedKm(buffer): returns total km exceeding max_km+buffer.
    In RESCHEDULING mode: threshold = max_km + buffer.
    Uses disrupted SP for deadheads crossing the disruption window.
    """
    total_over = 0.0

    for loco_id, seq in loco_trips.items():
        if not seq:
            continue

        lc        = loco_classes[locos_by_id[loco_id]['class']]
        threshold = lc['max_kilometers_before_maintenance'] + buffer_km
        dh_speed  = lc['deadhead_speed']
        init      = loco_init[loco_id]
        km        = init['km']

        for i, tid in enumerate(seq):
            trip = trips_by_id[tid]
            sec  = sections[trip['section']]

            # pos=1: deadhead to trip start
            if i == 0:
                dh_from, dh_dep = init['station'], init['avail_time']
            else:
                prev    = trips_by_id[seq[i - 1]]
                dh_from = sections[prev['section']]['destination']
                dh_dep  = prev['arrival_time']

            _, dh_dist = _dh_info(sp, dsp, dh_from, sec['origin'],
                                  dh_dep, trip['departure_time'],
                                  dis_start, dis_end, dh_speed)
            km += dh_dist

            if maintenance.get(tid, 0) == 1:
                total_over += max(0.0, km - threshold)
                km = 0.0

            # pos=2: trip distance
            km += sec['distance']

            if maintenance.get(tid, 0) == 2:
                total_over += max(0.0, km - threshold)
                km = 0.0

        total_over += max(0.0, km - threshold)

    return total_over


# ---------------------------------------------------------------------------
# CandidateLocomotives — replicates CandidateLocomotives from frisch_solution.cc
# ---------------------------------------------------------------------------

def candidate_locomotives(
    trip_id: int,
    initial_loco_id: int,
    buffer_km: float,
    loco_trips: Dict,
    trip_to_loco: Dict,
    maintenance: Dict,
    loco_init: Dict,
    initial_maint_pos: Dict,
    usable_loco_ids: List,
    trips_by_id: Dict,
    locos_by_id: Dict,
    sections: Dict,
    loco_classes: Dict,
    maint_stations: Dict,
    sp: Dict,
    dsp: Optional[Dict] = None,
    dis_start: float = 0.0,
    dis_end: float = 0.0,
    disrupted_edges: frozenset = frozenset(),
) -> List[int]:
    """
    Replicates CandidateLocomotives from frisch_solution.cc.
    Returns list of feasible loco IDs (in order found).
    State is fully restored on return.
    """
    candidates = []

    def _check():
        c = compute_conflicts(loco_trips, maintenance, loco_init,
                               trips_by_id, locos_by_id, sections, loco_classes,
                               sp, dsp, dis_start, dis_end)
        if c > 0:
            return False
        v = compute_type_violations(loco_trips, trips_by_id, locos_by_id)
        if v > 0:
            return False
        u = compute_unmaintained_km(loco_trips, maintenance, loco_init,
                                     trips_by_id, locos_by_id, sections, loco_classes,
                                     sp, buffer_km, dsp, dis_start, dis_end)
        return u == 0.0
    def _try(loco_id):
        assign_loco_to_trip(trip_id, loco_id, loco_trips, trip_to_loco, trips_by_id)
        assign_maintenance_all(loco_trips, maintenance, loco_init, initial_maint_pos,
                               trips_by_id, locos_by_id, sections, loco_classes, maint_stations,
                               sp, dsp, dis_start, dis_end)
        return _check()

    def _undo():
        remove_loco_from_trip(trip_id, loco_trips, trip_to_loco, maintenance)
        assign_maintenance_all(loco_trips, maintenance, loco_init, initial_maint_pos,
                               trips_by_id, locos_by_id, sections, loco_classes, maint_stations,
                               sp, dsp, dis_start, dis_end)

    for loco_id in usable_loco_ids:
        if _try(loco_id):
            candidates.append(loco_id)
        _undo()
    return candidates


# ---------------------------------------------------------------------------
# Main algorithm — replicates RandomizedGreedy from frisch_solution.cc
# ---------------------------------------------------------------------------

def randomized_greedy(instance, network, sp, seed: int = 42, deterministic: bool = False,
                      crew_check=None) -> List[Dict]:
    """
    Python replication of RandomizedGreedy() from frisch_solution.cc.
    Uses C++ MT19937 + uniform_int_distribution for exact RNG match.
    Computes disrupted_shortest_paths to match C++ path selection.
    """
    rng = CppMT19937(seed)

    sp = filter_sp_to_cpp_matrix(sp, instance, network)

    sections, loco_classes, maint_stations, trips_by_id, locos_by_id = build_index(instance, network)
    disrupted   = identify_disrupted_trips(instance, sections)
    dis_start   = instance['disruption_start']
    dis_end     = instance['disruption_end']

    disrupted_section_ids = set(instance.get('disrupted_sections', []))
    dsp = compute_disrupted_sp(network, sp, disrupted_section_ids)

    # Pre-disruption solution
    initial_sol = {s['id_trip']: s for s in instance['solution']}

    # Fixed trips: C++ uses departure_time < disruption_start (frisch_input.cc:300)
    
    completed_trip_ids = {
        t['id'] for t in instance['train_sections']
        if t['departure_time'] < dis_start
    }

    # C++ sorts train_trips by departure_time before processing (frisch_input.cc:214)
    sorted_sections = sorted(instance['train_sections'], key=lambda t: t['departure_time'])

    # trip_order: non-completed, non-disrupted trips sorted by departure_time
    trip_order = [
        t['id'] for t in sorted_sections
        if t['id'] not in completed_trip_ids
        and t['id'] not in disrupted
    ]

    # usable_loco_ids: locos in initial solution, in locomotive array order
    loco_order = [l['id'] for l in instance['locomotives']]
    locos_in_sol = {
        e['locomotive'] for e in instance['solution']
        if e['locomotive'] != 'canceled'
    }
    usable_loco_ids = [lid for lid in loco_order if lid in locos_in_sol]

    # Build initial loco state (C++ ReadInitialSolution — uses regular sp)
    loco_init, initial_maint_pos = build_initial_loco_state(
        instance, sections, loco_classes, sp,
        dis_start, dis_end, disrupted, trip_order,
        disrupted_section_ids=disrupted_section_ids,
    )

    # Global assignment state
    loco_trips:   Dict[int, List[int]] = {}
    trip_to_loco: Dict[int, int]       = {}
    maintenance:  Dict[int, int]       = {}

    result = []

    for trip_id in trip_order:
        orig_entry = initial_sol.get(trip_id, {})
        orig_loco  = orig_entry.get('locomotive')

        if orig_loco is None or orig_loco == 'canceled':
            result.append({
                'id_trip': trip_id,
                'locomotive': 'canceled',
                'maintenance_at_departure': 'false',
                'maintenance_at_destination': 'false',
            })
            continue

        candidates = candidate_locomotives(
            trip_id, orig_loco, 200.0,
            loco_trips, trip_to_loco, maintenance, loco_init,
            initial_maint_pos, usable_loco_ids,
            trips_by_id, locos_by_id, sections, loco_classes, maint_stations,
            sp, dsp, dis_start, dis_end,
        )
        #print(f"Trip {trip_id}: candidates = {candidates}")
        if candidates:
            if crew_check is not None:
                # Prefer candidates whose assignment generates crew-coverable tasks.
                # A candidate passes if: it is already at trip_origin (no deadhead created)
                # OR the deadhead it would create can be covered by at least one driver.
                # Falls back to all candidates if none pass the crew check.
                crew_feasible = [c for c in candidates
                                 if crew_check(trip_id, c, loco_trips, loco_init)]
                pool = crew_feasible if crew_feasible else candidates
            else:
                pool = candidates
            chosen = pool[rng.uniform_int(0, len(pool) - 1)]
            assign_loco_to_trip(trip_id, chosen, loco_trips, trip_to_loco, trips_by_id)
            assign_maintenance_all(
                loco_trips, maintenance, loco_init, initial_maint_pos,
                trips_by_id, locos_by_id, sections, loco_classes, maint_stations,
                sp, dsp, dis_start, dis_end,
            )
            m = maintenance.get(trip_id, 0)
            result.append({
                'id_trip':  trip_id,
                'locomotive': chosen,
                'maintenance_at_departure':   'true' if m == 1 else 'false',
                'maintenance_at_destination': 'true' if m == 2 else 'false',
            })
        else:
            result.append({
                'id_trip': trip_id,
                'locomotive': 'canceled',
                'maintenance_at_departure': 'false',
                'maintenance_at_destination': 'false',
            })

    return result


# ---------------------------------------------------------------------------
# Score helper
# ---------------------------------------------------------------------------

def count_canceled(solution: List[Dict]) -> int:
    return sum(1 for e in solution if e['locomotive'] == 'canceled')


def compute_loco_score(loco_id, loco_init, locos_by_id, loco_classes, loco_trips, maintenance, sp, dsp, dis_start, dis_end, trips_by_id, sections):
    """
    Km slack score in [0, 1]: vicino a 1 = loco fresca, vicino a 0 = prossima a manutenzione.
    """
    loco_class = loco_classes[locos_by_id[loco_id]['class']]
    max_km     = loco_class['max_kilometers_before_maintenance']
    current_km = update_loco_km(loco_id, loco_trips, trips_by_id, sections, loco_init, maintenance, sp, dsp, dis_start, dis_end, locos_by_id, loco_classes)
    if max_km == 0:
        return 0.0
    return (max_km - current_km) / max_km


def update_loco_km(loco_id, loco_trips, trips_by_id, sections, loco_init, maintenance, sp, dsp, dis_start, dis_end, locos_by_id, loco_classes):
    km   = loco_init[loco_id]['km']
    seq  = loco_trips.get(loco_id, [])
    init = loco_init[loco_id]
    deadhead_speed = loco_classes[locos_by_id[loco_id]['class']]['deadhead_speed']
    for i, trip_id in enumerate(seq):
        trip = trips_by_id[trip_id]
        sec  = sections[trip['section']]
        if i == 0:
            dh_from, dh_dep = init['station'], init['avail_time']
        else:
            prev    = trips_by_id[seq[i - 1]]
            dh_from = sections[prev['section']]['destination']
            dh_dep  = prev['arrival_time']
        _, dh_dist = _dh_info(sp, dsp, dh_from, sec['origin'],
                               dh_dep, trip['departure_time'],
                               dis_start, dis_end, deadhead_speed)
        km += dh_dist
        if maintenance.get(trip_id, 0) == 1:
            km = 0
            km += sec['distance']
        elif maintenance.get(trip_id, 0) == 2:
            km += sec['distance']
            km = 0
        else:
            km += sec['distance']
    return km    

def five_best_scores(candidates: List[int], locos_by_id: Dict, loco_init: Dict, loco_classes: Dict, loco_trips: Dict, maintenance: Dict,
    sp: Dict,
    dsp: Optional[Dict],
    dis_start: float,
    dis_end: float,
    trips_by_id: Dict,
    sections: Dict,
    n: int = 5,
):
    """Return top-n candidate loco IDs sorted by km-slack score descending."""
    scored = sorted(
        candidates,
        key=lambda lid: compute_loco_score(
            lid, loco_init, locos_by_id, loco_classes, loco_trips,
            maintenance, sp, dsp, dis_start, dis_end, trips_by_id, sections,
        ),
        reverse=True,
    )
    return scored[:n]

# ---------------------------------------------------------------------------
# Scored greedy : candidate selection base on km remaining 
#
def scored_greedy(instance, network, sp, seed: int = 42) -> List[Dict]:
    """
    Greedy con km slack scoring.
    Per ogni trip considera tutte le loco compatibili per classe,
    assegna quella con il maggiore km slack tra le feasibili.
    """
    rng = CppMT19937(seed)
    sp = filter_sp_to_cpp_matrix(sp, instance, network)

    sections, loco_classes, maint_stations, trips_by_id, locos_by_id = build_index(instance, network)
    disrupted  = identify_disrupted_trips(instance, sections)
    dis_start  = instance['disruption_start']
    dis_end    = instance['disruption_end']

    disrupted_section_ids = set(instance.get('disrupted_sections', []))
    dsp = compute_disrupted_sp(network, sp, disrupted_section_ids)

    initial_sol = {s['id_trip']: s for s in instance['solution']}

    completed_trip_ids = {
        t['id'] for t in instance['train_sections']
        if t['departure_time'] < dis_start
    }

    sorted_sections = sorted(instance['train_sections'], key=lambda t: t['departure_time'])

    trip_order = [
        t['id'] for t in sorted_sections
        if t['id'] not in completed_trip_ids
        and t['id'] not in disrupted
    ]

    loco_order = [l['id'] for l in instance['locomotives']]
    locos_in_sol = {
        e['locomotive'] for e in instance['solution']
        if e['locomotive'] != 'canceled'
    }
    usable_loco_ids = [lid for lid in loco_order if lid in locos_in_sol]

    loco_init, initial_maint_pos = build_initial_loco_state(
        instance, sections, loco_classes, sp,
        dis_start, dis_end, disrupted, trip_order,
        disrupted_section_ids=disrupted_section_ids,
    )

    loco_trips:   Dict[int, List[int]] = {}
    trip_to_loco: Dict[int, int]       = {}
    maintenance:  Dict[int, int]       = {}

    result = []

    for trip_id in trip_order:
        orig_entry = initial_sol.get(trip_id, {})
        orig_loco  = orig_entry.get('locomotive')

        if orig_loco is None or orig_loco == 'canceled':
            result.append({
                'id_trip': trip_id,
                'locomotive': 'canceled',
                'maintenance_at_departure': 'false',
                'maintenance_at_destination': 'false',
            })
            continue

        candidates = candidate_locomotives(
            trip_id, orig_loco, 200.0,
            loco_trips, trip_to_loco, maintenance, loco_init,
            initial_maint_pos, usable_loco_ids,
            trips_by_id, locos_by_id, sections, loco_classes, maint_stations,
            sp, dsp, dis_start, dis_end,
        )
        
        top5 = five_best_scores(
            candidates, locos_by_id, loco_init, loco_classes, loco_trips,
            maintenance, sp, dsp, dis_start, dis_end, trips_by_id, sections,
        )
        best_loco = top5[rng.uniform_int(0, len(top5) - 1)] if top5 else None

        if best_loco is not None:
            assign_loco_to_trip(trip_id, best_loco, loco_trips, trip_to_loco, trips_by_id)
            assign_maintenance_all(loco_trips, maintenance, loco_init, initial_maint_pos,
                                   trips_by_id, locos_by_id, sections, loco_classes, maint_stations,
                                   sp, dsp, dis_start, dis_end)
            m = maintenance.get(trip_id, 0)
            result.append({
                'id_trip':  trip_id,
                'locomotive': best_loco,
                'maintenance_at_departure':   'true' if m == 1 else 'false',
                'maintenance_at_destination': 'true' if m == 2 else 'false',
            })
        else:
            result.append({
                'id_trip': trip_id,
                'locomotive': 'canceled',
                'maintenance_at_departure': 'false',
                'maintenance_at_destination': 'false',
            })

    return result


# ---------------------------------------------------------------------------
# Counterfactual baseline: original solution filtered to non-disrupted trips
# ---------------------------------------------------------------------------

def original_greedy(instance, network, sp, seed: int = None) -> List[Dict]:
    """
    Counterfactual baseline for Test 1.
    Returns the original locomotive assignments with disrupted and completed
    trips removed — no rescheduling applied.
    Output format is identical to randomized_greedy so it plugs into
    rs_solution_to_open_tasks unchanged.
    """
    sections, _, _, _, _ = build_index(instance, network)
    disrupted   = identify_disrupted_trips(instance, sections)
    dis_start   = instance['disruption_start']

    completed_trip_ids = {
        t['id'] for t in instance['train_sections']
        if t['departure_time'] < dis_start
    }

    original_sol = {s['id_trip']: s for s in instance['solution']}
    sorted_sections = sorted(instance['train_sections'], key=lambda t: t['departure_time'])

    result = []
    for t in sorted_sections:
        tid = t['id']
        if tid in completed_trip_ids:
            continue
        entry = original_sol.get(tid, {})
        loco  = entry.get('locomotive')

        if tid in disrupted or loco is None or loco == 'canceled':
            result.append({
                'id_trip': tid,
                'locomotive': 'canceled',
                'maintenance_at_departure': 'false',
                'maintenance_at_destination': 'false',
            })
        else:
            result.append({
                'id_trip':  tid,
                'locomotive': loco,
                'maintenance_at_departure':   entry.get('maintenance_at_departure', 'false'),
                'maintenance_at_destination': entry.get('maintenance_at_destination', 'false'),
            })

    return result


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys

    INSTANCE_DIR       = 'single_type'
    NETWORK_FILE       = os.path.join(INSTANCE_DIR, 'network.json')
    SHORTESTPATHS_FILE = os.path.join(INSTANCE_DIR, 'network-shortestpaths.json')
    OUTPUT_DIR         = 'output/rs_solution'
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    instance_id = sys.argv[1] if len(sys.argv) > 1 else 'S01'
    mode        = sys.argv[2] if len(sys.argv) > 2 else 'random'
    seed        = int(sys.argv[3]) if len(sys.argv) > 3 else 42

    if mode not in ('random', 'scored'):
        print(f'Error: mode must be "random" or "scored", got "{mode}"')
        sys.exit(1)

    instance_file = os.path.join(INSTANCE_DIR, f'{instance_id}.json')
    print(f'Loading instance : {instance_file}')
    print(f'Mode             : {mode}')
    if mode == 'random':
        print(f'Seed             : {seed}')

    instance, network, sp = load_data(instance_file, NETWORK_FILE, SHORTESTPATHS_FILE)

    dis_start = instance['disruption_start']
    n_trips   = len(instance['train_sections'])
    sections, loco_classes, maint_stations, trips_by_id, locos_by_id = build_index(instance, network)
    disrupted  = identify_disrupted_trips(instance, sections)
    completed  = {t['id'] for t in instance['train_sections'] if t['arrival_time'] < dis_start}

    print(f'\nInstance stats:')
    print(f'  Total trips          : {n_trips}')
    print(f'  Completed (frozen)   : {len(completed)}')
    print(f'  Disrupted (canceled) : {len(disrupted)}')
    print(f'  Locomotives          : {len(instance["locomotives"])}')

    if mode == 'scored':
        print(f'\nRunning ScoredGreedy...')
        solution = scored_greedy(instance, network, sp)
    else:
        print(f'\nRunning RandomizedGreedy...')
        solution = randomized_greedy(instance, network, sp, seed=seed)

    assigned = [e for e in solution if e['locomotive'] != 'canceled']
    canceled = [e for e in solution if e['locomotive'] == 'canceled']

    print(f'\nResults:')
    print(f'  Trips processed  : {len(solution)}')
    print(f'  Assigned         : {len(assigned)}')
    print(f'  Canceled         : {len(canceled)}')

    output_file = os.path.join(OUTPUT_DIR, f'{instance_id}.json')
    with open(output_file, 'w') as f:
        json.dump(solution, f, indent=3)
    print(f'\nSolution saved to: {output_file}')

    # Print JSON to stdout (matches C++ PrintJSON / j_sol.dump(3))
    print(json.dumps(solution, indent=3))
