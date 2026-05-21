# ARCHITECTURE — RollingStockGreedy.py

Python replication of `RandomizedGreedy()` from `frisch_solution.cc` (C++).

---

## Legend

| Symbol | Meaning |
|--------|---------|
| `[inner]` | function defined inside another function (closure), accesses variables from outer scope |
| `→` | calls the same function already shown above (avoids repetition) |

---

## Main data structures

| Name | Type | Content |
|------|------|---------|
| `loco_trips` | `Dict[int, List[int]]` | per loco: list of trip_ids sorted by departure_time |
| `trip_to_loco` | `Dict[int, int]` | per trip: assigned loco |
| `maintenance` | `Dict[int, int]` | per trip: 0=none, 1=at departure, 2=at arrival |
| `loco_init` | `Dict[int, dict]` | per loco: `{station, avail_time, km}` at start of rescheduling |
| `initial_maint_pos` | `Dict[int, int]` | original maintenance plan (pre-disruption) |
| `sp` | `Dict` | shortest paths matrix between stations (normal graph) |
| `dsp` | `Dict` | shortest paths matrix with disrupted sections removed |

---

## Function hierarchy

### randomized_greedy()

Main entry point. Calls in order:

- `CppMT19937`
- `filter_sp_to_cpp_matrix()`
- `build_index()`
- `identify_disrupted_trips()`
- `compute_disrupted_sp()`
- `build_initial_loco_state()`
- `candidate_locomotives()` — once per trip
- `assign_loco_to_trip()`
- `assign_maintenance_all()`
- `count_canceled()`

---

### CppMT19937

Random number generator. Replicates C++11 `std::mt19937` + GCC `uniform_int_distribution`.

```
CppMT19937
├── __init__()
├── _generate_numbers()
├── next32()
└── uniform_int()
```

---

### filter_sp_to_cpp_matrix()

Filters shortest paths matrix to match C++ cell population logic. No sub-calls.

---

### build_index()

Builds lookup dictionaries from instance and network JSON. No sub-calls.

---

### identify_disrupted_trips()

Finds trip IDs cancelled by the disruption window. No sub-calls.

---

### compute_disrupted_sp()

Recomputes shortest paths with disrupted sections removed.

```
compute_disrupted_sp()
└── _fallback_dijkstra()    # [inner] Dijkstra on reduced graph
```

---

### build_initial_loco_state()

Computes each loco's station, availability time, and km at the start of rescheduling.

```
build_initial_loco_state()
├── _scan_fixed_trips()         # iterates trips completed before the disruption
│   └── get_deadhead_info()
└── _determine_loco_position()  # computes station and availability time of each loco
    └── get_deadhead_info()
```

---

### candidate_locomotives()

For each trip, finds the list of feasible locos. Tries, checks, then undoes each candidate.

#### _try()

[inner] Assigns a loco to the trip and checks full feasibility.

```
_try()
├── assign_loco_to_trip()
├── assign_maintenance_all()
│   └── assign_maintenance_for_loco()   # see below
└── _check()                            # see below
```

#### assign_maintenance_for_loco()

Places maintenance points along a loco's trip sequence. Backtracks if km limit exceeded.

```
assign_maintenance_for_loco()
├── feasible()              # [inner] → _maint_feasible_at() → _dh_info() → get_deadhead_info()
├── assign_maint()          # [inner] sets maintenance entry and resets km counter
├── backtrack()             # [inner] walks backwards to find a feasible maintenance slot
│   ├── feasible()  →  _maint_feasible_at()  →  _dh_info()
│   └── assign_maint()
└── _dh_info()
    └── get_deadhead_info()
```

#### _maint_feasible_at()

Checks whether maintenance is feasible at a given trip position (departure or arrival).

```
_maint_feasible_at()
└── _dh_info()
    └── get_deadhead_info()
```

#### _dh_info()

Returns deadhead time and distance. Uses disrupted SP if deadhead crosses the disruption window, regular SP otherwise.

```
_dh_info()
└── get_deadhead_info()
```

#### _check()

[inner] Verifies full solution feasibility: no conflicts, no type violations, no unmaintained km over threshold.

```
_check()
├── compute_conflicts()
│   ├── _feasible_by_time_start()   → _dh_info()
│   ├── _feasible_by_time_trips()   → _dh_info()
│   └── _time_for_maintenance_between()
│       ├── _feasible_by_time_start()
│       └── _dh_info()
├── compute_type_violations()
└── compute_unmaintained_km()       → _dh_info()
```

#### _undo()

[inner] Removes the assignment and restores maintenance state.

```
_undo()
├── remove_loco_from_trip()
└── assign_maintenance_all()
    └── assign_maintenance_for_loco()  →  (see above)
```

---

### assign_loco_to_trip()

Inserts a trip into a loco's sequence, maintaining departure time order. No sub-calls.

---

### assign_maintenance_all()

Runs `assign_maintenance_for_loco()` for every loco with at least one trip assigned.

```
assign_maintenance_all()
└── assign_maintenance_for_loco()  →  (see above)
```

---

### count_canceled()

Counts trips with `locomotive == 'canceled'` in the final solution. No sub-calls.
