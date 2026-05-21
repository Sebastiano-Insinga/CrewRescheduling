# Deadhead-Aware Initial Solution

## Overview

`calculateInitialSolution_deadhead` builds a greedy feasible crew schedule after a disruption. Unlike the basic greedy method, it allows drivers to **deadhead** (travel as a passenger) to reach tasks at stations they are not currently at.

---

## 1. `calculateInitialSolution_deadhead`

### Input
| Parameter | Description |
|---|---|
| `original_schedule` | Pre-disruption duty assignments |
| `driver_status` | Each driver's state at disruption time: station, time available, duty length accumulated, breaks done |
| `input_open_tasks` | Tasks that need to be covered after the disruption |
| `sp` | Shortest path matrix on the normal network |
| `dsp` | Shortest path matrix on the disrupted network (`None` if no network disruption) |
| `crew_speed_kmh` | Speed used to convert distance to travel time |

### Algorithm

The function iterates over all drivers and greedily assigns tasks one at a time.

For each driver:
1. Determine current position (`current_origin`) and time availability (`current_time`) from either `driver_status` (first task) or the last assigned task.
2. For every open task, call `_is_task_feasible_with_deadhead` to check if the driver can physically reach and execute it.
3. If feasible, also check `_is_break_feasible` to ensure the resulting duty sequence has a valid rest slot.
4. From all feasible tasks, select using priority:
   - Originally assigned task, no deadhead needed
   - Originally assigned task, deadhead needed
   - Any task: minimise `(deadhead_minutes, departure_time)`
5. Append the selected task to the driver's duty. Accumulate deadhead distance in km.
6. Repeat until no more feasible tasks exist for that driver.

Tasks not assigned to any driver end up in `uncovered_tasks`.

After construction, the function scans each completed duty to find and record a valid break slot (`duty_breaks`).

### Feasibility checks

**`_is_task_feasible_with_deadhead`** checks:
- The driver can reach `task.origin` from `current_origin` within the available time window (deadhead travel time ≤ time before task departure).
- The resulting `new_duty_length` stays below `max_duty_length`.
- The task is in the driver's `suitable_tasks` set.

**`_is_break_feasible`** checks:
- Given breaks already done before the disruption (`break30done`, `break45done`), compute remaining required rest.
- Verify that at least one gap between consecutive tasks in `current_tasks + [new_task]` is long enough to fit the rest.

### Deadhead time vs. network

The function `_get_deadhead_minutes` selects which shortest path matrix to use:
- If the deadhead window `[current_time, task_departure]` overlaps `[disruption_start, disruption_end]` **and** `dsp` is not `None` → use `dsp` (disrupted network).
- Otherwise → use `sp` (normal network).

---

## 2. Disrupted Shortest Paths (`compute_disrupted_sp`)

`dsp` is a weight-only matrix `{from_station: {to_station: distance_meters}}` built by `compute_disrupted_sp` before the crew rescheduling starts.

### Steps

**Step 1 — Build disrupted adjacency graph**

Remove all sections whose ID is in `disrupted_section_ids` from the network. The result is `adj_no_dis`: the network crews can actually use during the disruption.

**Step 2 — Initialise `dsp_full`**

Create an `N × N` matrix (N = number of used stations) with all weights set to `∞` and empty paths.

**Step 3 — Fill `dsp_full` for every `(i, j)` pair**

For each pair `(i, j)` reachable in the normal SP matrix:

1. **No disrupted edge in original path** → copy path and weight directly into `dsp_full[i][j]`.

2. **Disrupted edge found** → scan the original path from the end backwards to find the last node `k` that is a disrupted edge's source. Then try to find a **re-entry node**: scan from the path end down to `k+1`, looking for a node `st_k` such that `dsp_full[i][st_k]` is already known (< ∞). If found, combine:
   ```
   new_path = dsp_full[i][st_k].path + orig_path[k+1 .. end]
   new_weight = dsp_full[i][st_k].weight + edge distances for the tail
   ```

3. **No re-entry node available** → run a fresh Dijkstra on `adj_no_dis` from `i` to `j`.

**Step 4 — Return weight-only matrix**

Strip the path data and return only the distance values (used by `_get_deadhead_minutes`).

---

## 3. Dijkstra and Path Reconstruction (`_fallback_dijkstra`)

Standard Dijkstra over `adj_no_dis` (network without disrupted sections).

### Algorithm

```
dist = {from_station: 0}         # known shortest distances
prev = {}                         # predecessor map for path reconstruction
heap = [(0, from_station)]        # min-heap: (cost, node)

while heap not empty:
    pop (d, u) with minimum cost
    if d > dist[u]: skip          # stale heap entry
    if u == to_station: break     # optimal path to destination found
    for each neighbour (v, w) of u:
        nd = d + w
        if nd < dist[v]:
            dist[v] = nd
            prev[v] = u
            push (nd, v) to heap
```

Early exit when `to_station` is popped: since the heap is ordered by cost, the first extraction of the destination is guaranteed to be optimal.

### Path reconstruction

```
path = []
cur = to_station
while cur != from_station:
    path.append(cur)
    cur = prev[cur]
path.reverse()
```

The source node is **excluded** from the returned path to match the convention used in the C++ implementation this replicates.

Returns `(total_distance_meters, path)`, or `(inf, [])` if `to_station` is unreachable.
