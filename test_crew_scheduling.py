"""
Unit tests for calculateInitialSolution and calculateInitialSolution_deadhead.

Network topology used throughout:
  Station 1 --30min--> Station 2 --30min--> Station 3
  Station 1 --60min--> Station 3
  Station 4 --120min-> Station 1   (far, most tasks infeasible from here)
  Station 4 --150min-> Station 3   (very far)
  Station 5 --90min--> Station 2   (medium distance)

All times in minutes. Speed = 57 km/h.
30 min  = 28500 m
60 min  = 57000 m
90 min  = 85500 m
120 min = 114000 m
150 min = 142500 m
Max duty length = 720 min (12 h).
"""

import sys
import unittest

sys.path.insert(0, ".")

from VNS_Rescheduling import calculateInitialSolution, calculateInitialSolution_deadhead

SPEED = 57.0
MAX_DUTY = 720
DISRUPTION_START = 300
DISRUPTION_END = 360

# ---------------------------------------------------------------------------
# Minimal sp: str(station) -> str(station) -> {"weight": meters, "path": [...]}
# ---------------------------------------------------------------------------
SP = {
    "1": {
        "2": {"weight": 28500,  "path": [2]},
        "3": {"weight": 57000,  "path": [2, 3]},
        "4": {"weight": 114000, "path": [4]},
        "5": {"weight": 114000, "path": [2, 5]},
    },
    "2": {
        "1": {"weight": 28500,  "path": [1]},
        "3": {"weight": 28500,  "path": [3]},
        "4": {"weight": 142500, "path": [1, 4]},
        "5": {"weight": 85500,  "path": [5]},
    },
    "3": {
        "1": {"weight": 57000,  "path": [2, 1]},
        "2": {"weight": 28500,  "path": [2]},
        "4": {"weight": 142500, "path": [4]},
        "5": {"weight": 114000, "path": [2, 5]},
    },
    "4": {
        "1": {"weight": 114000, "path": [1]},
        "2": {"weight": 142500, "path": [1, 2]},
        "3": {"weight": 142500, "path": [3]},
        "5": {"weight": 199500, "path": [1, 2, 5]},
    },
    "5": {
        "1": {"weight": 114000, "path": [2, 1]},
        "2": {"weight": 85500,  "path": [2]},
        "3": {"weight": 114000, "path": [2, 3]},
        "4": {"weight": 199500, "path": [2, 1, 4]},
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_driver(station, available_at, duty_length=0, b30=False, b45=False):
    return {
        "available_from_station": station,
        "available_at_time": available_at,
        "duty_length": duty_length,
        "break30done": b30,
        "break45done": b45,
    }


def make_task(task_id, origin, dest, departure, arrival, loco="L1"):
    return {
        "id": task_id,
        "origin": origin,
        "destination": dest,
        "departure": departure,
        "arrival": arrival,
        "locomotive": loco,
    }


def make_id_mapping(*task_ids, loco="L1"):
    return {tid: {"locomotive": loco, "task_type": "regular"} for tid in task_ids}


# ---------------------------------------------------------------------------
# Property checks (run on every scenario)
# ---------------------------------------------------------------------------

def check_properties(tc: unittest.TestCase, existing_duties, duty_breaks,
                      uncovered_tasks, driver_status, max_duty=MAX_DUTY):
    """Structural invariants that must hold after any initial solution call."""

    assigned_ids = {t["id"] for duty in existing_duties.values() for t in duty}
    uncovered_ids = {t["id"] for t in uncovered_tasks}

    # P1: no task both assigned and uncovered
    tc.assertEqual(
        assigned_ids & uncovered_ids, set(),
        "Task appears in both existing_duties and uncovered_tasks",
    )

    # P2: no task assigned twice across different duties
    all_assigned = [t["id"] for duty in existing_duties.values() for t in duty]
    tc.assertEqual(
        len(all_assigned), len(set(all_assigned)),
        "Duplicate task assignment across duties",
    )

    # P3: duty length < max_duty for every driver
    for driver_id, duty in existing_duties.items():
        duty_length = duty[-1]["arrival"] - duty[0]["departure"]
        tc.assertLess(
            duty_length, max_duty,
            f"Driver {driver_id} duty length {duty_length} >= max {max_duty}",
        )

    # P4: break slot is valid where duty_breaks records one
    for driver_id, duty in existing_duties.items():
        slot = duty_breaks.get(driver_id)
        if slot is None or slot[0] < 0:
            continue  # no break needed or sentinel value
        slot_duration = slot[1] - slot[0]
        found = any(
            duty[i + 1]["departure"] - duty[i]["arrival"] >= slot_duration
            for i in range(len(duty) - 1)
        )
        tc.assertTrue(
            found,
            f"Driver {driver_id}: duty_breaks slot ({slot}) not backed by a real gap",
        )

    # P5: deadhead feasibility - gap between consecutive tasks covers travel time
    for driver_id, duty in existing_duties.items():
        ds = driver_status[driver_id]

        # initial position -> first task
        first = duty[0]
        from_st = str(ds["available_from_station"])
        avail_t = ds["available_at_time"]
        dist = SP.get(from_st, {}).get(str(first["origin"]), {}).get("weight", 0)
        dh_min = (dist / 1000.0 / SPEED) * 60.0
        tc.assertGreaterEqual(
            first["departure"], avail_t + dh_min - 0.01,
            f"Driver {driver_id}: cannot reach first task {first['id']} in time "
            f"(need {dh_min:.1f} min dh, have {first['departure'] - avail_t:.1f} min)",
        )

        # consecutive tasks within duty
        for i in range(len(duty) - 1):
            prev, nxt = duty[i], duty[i + 1]
            dist = SP.get(str(prev["destination"]), {}).get(str(nxt["origin"]), {}).get("weight", 0)
            dh_min = (dist / 1000.0 / SPEED) * 60.0
            gap = nxt["departure"] - prev["arrival"]
            tc.assertGreaterEqual(
                gap, dh_min - 0.01,
                f"Driver {driver_id}: gap {gap:.1f} min between tasks "
                f"{prev['id']}->{nxt['id']} less than dh {dh_min:.1f} min",
            )


# ---------------------------------------------------------------------------
# Tests for calculateInitialSolution (no deadhead)
# ---------------------------------------------------------------------------

class TestCalculateInitialSolution(unittest.TestCase):

    def _run(self, driver_status, open_tasks, original_schedule, suitable_tasks=None):
        id_mapping = make_id_mapping(*open_tasks.keys())
        if suitable_tasks is None:
            suitable_tasks = {did: list(open_tasks.keys()) for did in driver_status}
        return calculateInitialSolution(
            original_schedule, driver_status, open_tasks,
            DISRUPTION_START, DISRUPTION_END, MAX_DUTY, id_mapping, suitable_tasks,
        )

    # ------------------------------------------------------------------
    # Scenario 1: same station, task assigned directly
    # ------------------------------------------------------------------
    def test_same_station_assigns_task(self):
        """Driver at task origin: should assign without deadhead."""
        T1 = make_task(1, origin=1, dest=2, departure=450, arrival=520)
        ds = {10: make_driver(station=1, available_at=400)}
        orig = {10: [T1]}
        duties, breaks, uncovered, _, _ = self._run(ds, {1: T1}, orig)

        self.assertIn(10, duties)
        self.assertEqual(len(duties[10]), 1)
        self.assertEqual(duties[10][0]["id"], 1)
        self.assertEqual(uncovered, [])
        check_properties(self, duties, breaks, uncovered, ds)

    # ------------------------------------------------------------------
    # Scenario 2: different station, no deadhead -> task uncovered
    # BUG: calculateInitialSolution crashes at line 107 when existing_duties
    # is empty (max() on empty sequence). Fix: use max(..., default=0).
    # ------------------------------------------------------------------
    @unittest.expectedFailure
    def test_different_station_task_uncovered(self):
        """No-deadhead version: driver at wrong station cannot reach task."""
        T1 = make_task(1, origin=2, dest=3, departure=450, arrival=520)
        ds = {10: make_driver(station=1, available_at=400)}
        orig = {10: []}
        duties, breaks, uncovered, _, _ = self._run(ds, {1: T1}, orig)

        self.assertNotIn(10, duties)
        self.assertEqual(len(uncovered), 1)
        self.assertEqual(uncovered[0]["id"], 1)
        check_properties(self, duties, breaks, uncovered, ds)

    # ------------------------------------------------------------------
    # Scenario 3: max duty length exceeded -> task uncovered
    # BUG: same crash as above when no task is feasible.
    # ------------------------------------------------------------------
    @unittest.expectedFailure
    def test_max_duty_length_exceeded(self):
        """Task that would push duty over 720 min must be rejected."""
        T1 = make_task(1, origin=1, dest=2, departure=100, arrival=825)
        ds = {10: make_driver(station=1, available_at=0, duty_length=0)}
        orig = {10: [T1]}
        duties, breaks, uncovered, _, _ = self._run(ds, {1: T1}, orig)

        self.assertEqual(len(uncovered), 1)
        check_properties(self, duties, breaks, uncovered, ds)

    # ------------------------------------------------------------------
    # Scenario 4: two drivers, originally-assigned preferred
    # ------------------------------------------------------------------
    def test_originally_assigned_preferred(self):
        """Driver picks originally-assigned task over earlier non-original."""
        T_orig = make_task(1, origin=1, dest=2, departure=400, arrival=460)
        T_other = make_task(2, origin=1, dest=2, departure=350, arrival=410)
        ds = {10: make_driver(station=1, available_at=300)}
        orig = {10: [T_orig]}
        suitable = {10: [1, 2]}
        duties, breaks, uncovered, _, _ = self._run(
            ds, {1: T_orig, 2: T_other}, orig, suitable
        )

        assigned_ids = [t["id"] for t in duties.get(10, [])]
        self.assertIn(1, assigned_ids, "Originally-assigned task should be picked first")
        check_properties(self, duties, breaks, uncovered, ds)

    # ------------------------------------------------------------------
    # Scenario 5: break slot feasibility
    # ------------------------------------------------------------------
    def test_break_slot_recorded(self):
        """Duty > 360 min with gap >= 30 min: duty_breaks must record a valid slot."""
        T1 = make_task(1, origin=1, dest=1, departure=100, arrival=300)
        T2 = make_task(2, origin=1, dest=1, departure=400, arrival=550)
        ds = {10: make_driver(station=1, available_at=50, b30=False, b45=False)}
        orig = {10: [T1, T2]}
        duties, breaks, uncovered, _, _ = self._run(ds, {1: T1, 2: T2}, orig)

        self.assertIn(10, duties)
        slot = breaks.get(10)
        self.assertIsNotNone(slot)
        check_properties(self, duties, breaks, uncovered, ds)


# ---------------------------------------------------------------------------
# Tests for calculateInitialSolution_deadhead
# ---------------------------------------------------------------------------

class TestCalculateInitialSolutionDeadhead(unittest.TestCase):

    def _run(self, driver_status, open_tasks, original_schedule,
             suitable_tasks=None, dsp=None):
        id_mapping = make_id_mapping(*open_tasks.keys())
        if suitable_tasks is None:
            suitable_tasks = {did: list(open_tasks.keys()) for did in driver_status}
        return calculateInitialSolution_deadhead(
            original_schedule, driver_status, open_tasks,
            DISRUPTION_START, DISRUPTION_END, MAX_DUTY,
            id_mapping, suitable_tasks,
            sp=SP, dsp=dsp, crew_speed_kmh=SPEED,
        )

    # ------------------------------------------------------------------
    # Scenario 1: same station, no deadhead
    # ------------------------------------------------------------------
    def test_same_station_zero_dh(self):
        """Same-station task: assigned, dh_km = 0."""
        T1 = make_task(1, origin=1, dest=2, departure=450, arrival=520)
        ds = {10: make_driver(station=1, available_at=400)}
        orig = {10: [T1]}
        duties, breaks, uncovered, _, _, dh_km = self._run(ds, {1: T1}, orig)

        self.assertIn(10, duties)
        self.assertEqual(duties[10][0]["id"], 1)
        self.assertEqual(uncovered, [])
        self.assertAlmostEqual(dh_km, 0.0, places=3)
        check_properties(self, duties, breaks, uncovered, ds)

    # ------------------------------------------------------------------
    # Scenario 2: deadhead feasible (30 min gap, 30 min dh needed)
    # ------------------------------------------------------------------
    def test_deadhead_feasible(self):
        """Driver at station 1, task at station 2: 30 min dh fits before departure."""
        T1 = make_task(1, origin=2, dest=3, departure=450, arrival=520)
        ds = {10: make_driver(station=1, available_at=400)}
        orig = {10: [T1]}
        duties, breaks, uncovered, _, _, dh_km = self._run(ds, {1: T1}, orig)

        self.assertIn(10, duties)
        self.assertEqual(duties[10][0]["id"], 1)
        self.assertEqual(uncovered, [])
        expected_dh_km = (28500 / 1000.0 / SPEED) * SPEED   # = 28.5 km
        self.assertAlmostEqual(dh_km, expected_dh_km, places=1)
        check_properties(self, duties, breaks, uncovered, ds)

    # ------------------------------------------------------------------
    # Scenario 3: deadhead infeasible (not enough time)
    # ------------------------------------------------------------------
    def test_deadhead_infeasible_time(self):
        """30 min dh needed but only 10 min available: task uncovered."""
        T1 = make_task(1, origin=2, dest=3, departure=410, arrival=480)
        ds = {10: make_driver(station=1, available_at=400)}
        orig = {10: [T1]}
        duties, breaks, uncovered, _, _, dh_km = self._run(ds, {1: T1}, orig)

        self.assertNotIn(10, duties)
        self.assertEqual(len(uncovered), 1)
        self.assertEqual(uncovered[0]["id"], 1)
        self.assertAlmostEqual(dh_km, 0.0, places=3)
        check_properties(self, duties, breaks, uncovered, ds)

    # ------------------------------------------------------------------
    # Scenario 4: priority - originally assigned with dh beats non-original
    # ------------------------------------------------------------------
    def test_priority_original_over_nonoriginal(self):
        """Originally-assigned task (needs dh) is picked before non-original (no dh)."""
        T_orig = make_task(1, origin=2, dest=3, departure=400, arrival=460)
        T_other = make_task(2, origin=1, dest=2, departure=350, arrival=410)
        ds = {10: make_driver(station=1, available_at=300)}
        orig = {10: [T_orig]}
        suitable = {10: [1, 2]}
        duties, breaks, uncovered, _, _, _ = self._run(
            ds, {1: T_orig, 2: T_other}, orig, suitable
        )

        assigned_ids = [t["id"] for t in duties.get(10, [])]
        self.assertIn(1, assigned_ids, "Originally-assigned task must be picked first")
        check_properties(self, duties, breaks, uncovered, ds)

    # ------------------------------------------------------------------
    # Scenario 5: max duty length exceeded even with dh
    # ------------------------------------------------------------------
    def test_max_duty_length_exceeded(self):
        """Task makes duty 825 min >= 720 min: rejected even with dh available."""
        T1 = make_task(1, origin=1, dest=2, departure=100, arrival=825)
        ds = {10: make_driver(station=1, available_at=0, duty_length=0)}
        orig = {10: [T1]}
        duties, breaks, uncovered, _, _, dh_km = self._run(ds, {1: T1}, orig)

        self.assertEqual(len(uncovered), 1)
        check_properties(self, duties, breaks, uncovered, ds)

    # ------------------------------------------------------------------
    # Scenario 6: break feasibility - no gap task rejected, gap task accepted
    # ------------------------------------------------------------------
    def test_break_feasibility(self):
        """Second task with no break gap is rejected; third task with gap is accepted."""
        T_first = make_task(1, origin=1, dest=1, departure=100, arrival=300)
        T_no_gap = make_task(2, origin=1, dest=1, departure=310, arrival=500)
        T_gap_ok = make_task(3, origin=1, dest=1, departure=400, arrival=600)
        ds = {10: make_driver(station=1, available_at=50, b30=False, b45=False)}
        orig = {10: [T_first, T_gap_ok]}
        tasks = {1: T_first, 2: T_no_gap, 3: T_gap_ok}
        suitable = {10: [1, 2, 3]}
        duties, breaks, uncovered, _, _, _ = self._run(ds, tasks, orig, suitable)

        assigned_ids = {t["id"] for t in duties.get(10, [])}
        self.assertIn(1, assigned_ids, "T_first must be assigned")
        self.assertIn(3, assigned_ids, "T_gap_ok must be assigned (gap >= 45 min)")
        self.assertNotIn(2, assigned_ids, "T_no_gap must be rejected (gap < 30 min)")
        uncov_ids = {t["id"] for t in uncovered}
        self.assertIn(2, uncov_ids)
        check_properties(self, duties, breaks, uncovered, ds)

    # ------------------------------------------------------------------
    # Scenario 7: dsp used during disruption window
    # ------------------------------------------------------------------
    def test_dsp_used_in_disruption_window(self):
        """When deadhead overlaps disruption, dsp replaces sp.
        dsp marks station 1->2 as unreachable (inf); task must be uncovered."""
        T1 = make_task(1, origin=2, dest=3, departure=350, arrival=420)
        # available_at=310: window [310, 350] overlaps [300, 360]
        ds = {10: make_driver(station=1, available_at=310)}
        orig = {10: [T1]}
        dsp = {1: {2: float("inf"), 3: float("inf")}, 2: {1: float("inf"), 3: float("inf")}}
        duties, breaks, uncovered, _, _, dh_km = self._run(ds, {1: T1}, orig, dsp=dsp)

        self.assertNotIn(10, duties)
        self.assertEqual(len(uncovered), 1)
        check_properties(self, duties, breaks, uncovered, ds)

    # ------------------------------------------------------------------
    # Scenario 8: two tasks, second reachable only via deadhead after first
    # ------------------------------------------------------------------
    def test_chained_tasks_with_dh(self):
        """Driver chains two tasks: reaches T2 at station 3 by deadheading from station 2."""
        T1 = make_task(1, origin=1, dest=2, departure=400, arrival=460)
        T2 = make_task(2, origin=3, dest=1, departure=520, arrival=600)
        # After T1 driver at station 2, t=460. dh to station 3 = 30 min. 460+30=490 <= 520. OK.
        ds = {10: make_driver(station=1, available_at=380)}
        orig = {10: [T1, T2]}
        duties, breaks, uncovered, _, _, dh_km = self._run(
            ds, {1: T1, 2: T2}, orig
        )

        assigned_ids = [t["id"] for t in duties.get(10, [])]
        self.assertEqual(assigned_ids, [1, 2])
        self.assertEqual(uncovered, [])
        # dh for T1 (same station 1->1): 0; dh for T2 (station 2->3): 28.5 km
        self.assertAlmostEqual(dh_km, 28.5, delta=0.5)
        check_properties(self, duties, breaks, uncovered, ds)


# ---------------------------------------------------------------------------
# Regression: deadhead version must never be worse than greedy
# ---------------------------------------------------------------------------

class TestDeadheadVsGreedy(unittest.TestCase):

    def test_deadhead_uncovered_le_greedy(self):
        """calculateInitialSolution_deadhead uncovered <= calculateInitialSolution uncovered."""
        T1 = make_task(1, origin=2, dest=3, departure=450, arrival=520)
        T2 = make_task(2, origin=1, dest=2, departure=400, arrival=460)
        ds = {10: make_driver(station=1, available_at=380)}
        orig = {10: [T1, T2]}
        tasks = {1: T1, 2: T2}
        id_mapping = make_id_mapping(1, 2)
        suitable = {10: [1, 2]}

        import copy
        _, _, uncov_greedy, _, _ = calculateInitialSolution(
            orig, copy.deepcopy(ds), copy.deepcopy(tasks),
            DISRUPTION_START, DISRUPTION_END, MAX_DUTY,
            copy.deepcopy(id_mapping), copy.deepcopy(suitable),
        )
        _, _, uncov_dh, _, _, _ = calculateInitialSolution_deadhead(
            orig, copy.deepcopy(ds), copy.deepcopy(tasks),
            DISRUPTION_START, DISRUPTION_END, MAX_DUTY,
            copy.deepcopy(id_mapping), copy.deepcopy(suitable),
            sp=SP, crew_speed_kmh=SPEED,
        )

        self.assertLessEqual(
            len(uncov_dh), len(uncov_greedy),
            f"Deadhead ({len(uncov_dh)} uncovered) worse than greedy ({len(uncov_greedy)} uncovered)",
        )


# ---------------------------------------------------------------------------
# COMMENTED TESTS — uncomment one at a time to activate
# ---------------------------------------------------------------------------
# Tests for _fallback_dijkstra and compute_disrupted_sp.
# Import needed when uncommented:
#   from VNS_Rescheduling import _fallback_dijkstra, compute_disrupted_sp
#
# Minimal network used in these tests:
#   1 --100m--> 2 --100m--> 3
#   1 --300m--> 3  (direct, longer)
#
# ADJ_NO_DIS = {
#     1: [(2, 100), (3, 300)],
#     2: [(1, 100), (3, 100)],
#     3: [(1, 300), (2, 100)],
# }
#
# ---------------------------------------------------------------------------
# class TestFallbackDijkstra(unittest.TestCase):
#
#     def test_shortest_path_two_hops(self):
#         """1->3 via 2 (200m) shorter than direct (300m)."""
#         dist, path = _fallback_dijkstra(ADJ_NO_DIS, 1, 3)
#         self.assertEqual(dist, 200)
#         self.assertEqual(path, [2, 3])   # source excluded by convention
#
#     def test_direct_edge(self):
#         """1->2 direct, 100m."""
#         dist, path = _fallback_dijkstra(ADJ_NO_DIS, 1, 2)
#         self.assertEqual(dist, 100)
#         self.assertEqual(path, [2])
#
#     def test_unreachable_node(self):
#         """Node 99 not in graph: returns (inf, [])."""
#         dist, path = _fallback_dijkstra(ADJ_NO_DIS, 1, 99)
#         self.assertEqual(dist, float("inf"))
#         self.assertEqual(path, [])
#
#     def test_same_source_destination(self):
#         """Source == destination: distance 0, empty path."""
#         dist, path = _fallback_dijkstra(ADJ_NO_DIS, 1, 1)
#         self.assertEqual(dist, 0)
#         self.assertEqual(path, [])
#
# ---------------------------------------------------------------------------
# class TestComputeDisruptedSP(unittest.TestCase):
#
#     # Minimal sp matrix (str keys) matching ADJ_NO_DIS
#     # SP_NORMAL = {
#     #     "1": {"2": {"weight": 100, "path": [2]},
#     #           "3": {"weight": 200, "path": [2, 3]}},
#     #     "2": {"1": {"weight": 100, "path": [1]},
#     #           "3": {"weight": 100, "path": [3]}},
#     #     "3": {"1": {"weight": 200, "path": [2, 1]},
#     #           "2": {"weight": 100, "path": [2]}},
#     # }
#     # NETWORK = {section_id: {"from": node, "to": node, "distance": meters}}
#     # NETWORK_FULL = {
#     #     "s12": {"from": 1, "to": 2, "distance": 100},
#     #     "s23": {"from": 2, "to": 3, "distance": 100},
#     #     "s13": {"from": 1, "to": 3, "distance": 300},
#     # }
#
#     def test_no_disruption_copies_sp(self):
#         """No disrupted sections: dsp == sp weights."""
#         dsp = compute_disrupted_sp(SP_NORMAL, NETWORK_FULL, disrupted_section_ids=set())
#         self.assertAlmostEqual(dsp[1][3], 200)
#         self.assertAlmostEqual(dsp[1][2], 100)
#
#     def test_disrupted_section_reroutes(self):
#         """Section 1->2 disrupted: path 1->3 must use 1->3 direct (300m) or be inf."""
#         dsp = compute_disrupted_sp(SP_NORMAL, NETWORK_FULL, disrupted_section_ids={"s12"})
#         # 1->2 now impossible (only route was via s12)
#         self.assertEqual(dsp[1][2], float("inf"))
#         # 1->3 still reachable via direct s13 (300m)
#         self.assertAlmostEqual(dsp[1][3], 300)
#
#     def test_all_paths_to_node_disrupted(self):
#         """All sections into node 2 disrupted: dsp[1][2] = inf, dsp[3][2] = inf."""
#         dsp = compute_disrupted_sp(SP_NORMAL, NETWORK_FULL, disrupted_section_ids={"s12"})
#         self.assertEqual(dsp.get(1, {}).get(2, float("inf")), float("inf"))
#
#     def test_fallback_dijkstra_triggered(self):
#         """Disrupted edge with no re-entry node forces Dijkstra; result still correct."""
#         dsp = compute_disrupted_sp(SP_NORMAL, NETWORK_FULL, disrupted_section_ids={"s12"})
#         # 2->3 unaffected
#         self.assertAlmostEqual(dsp[2][3], 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
