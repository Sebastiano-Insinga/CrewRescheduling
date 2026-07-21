from __future__ import annotations


class CrewState:
    """
    Mutable crew state for the integrated rescheduling loop.

    Tracks each driver's current position, availability, and assigned tasks
    as locos and drivers are assigned trip by trip.

    Initialized from driver_status (post-disruption initial state).
    """

    def __init__(self, driver_status: dict):
        self._state: dict = {
            duty_id: {
                "station":               d["available_from_station"],
                "available_at":          d["available_at_time"],
                "original_available_at": d["available_at_time"],   # fixed
                "duty_length_base":      d["duty_length"],          # fixed
                "first_departure":       None,
                "tasks":                 [],
                "closed":                False,
            }
            for duty_id, d in driver_status.items()
        }

    # ------------------------------------------------------------------
    # Read access
    # ------------------------------------------------------------------

    def station(self, driver_id: int) -> int:
        return self._state[driver_id]["station"]

    def available_at(self, driver_id: int) -> float:
        return self._state[driver_id]["available_at"]

    def first_departure(self, driver_id: int) -> float | None:
        return self._state[driver_id]["first_departure"]

    def duty_length_base(self, driver_id: int) -> float:
        return self._state[driver_id]["duty_length_base"]

    def original_available_at(self, driver_id: int) -> float:
        return self._state[driver_id]["original_available_at"]

    def tasks(self, driver_id: int) -> list:
        return self._state[driver_id]["tasks"]

    def new_duty_length(self, driver_id: int, task: dict) -> float:
        """
        Projected total duty length if task is assigned to driver_id.
        Mirrors the formula used by TaskFeasibilityChecker / VNS.
        """
        d = self._state[driver_id]
        if d["duty_length_base"] > 0:
            return d["duty_length_base"] + (task["arrival"] - d["original_available_at"])
        first = d["first_departure"] if d["first_departure"] is not None else task["departure"]
        return task["arrival"] - first

    def driver_ids(self):
        return self._state.keys()

    def is_closed(self, driver_id: int) -> bool:
        return self._state[driver_id]["closed"]

    def close_duty(self, driver_id: int) -> None:
        """Mark the duty as closed — driver accepts no further tasks (home mode)."""
        self._state[driver_id]["closed"] = True

    # ------------------------------------------------------------------
    # State update
    # ------------------------------------------------------------------

    def apply_task(self, driver_id: int, task: dict) -> None:
        """Commit task to driver_id — updates station, availability, task list."""
        d = self._state[driver_id]
        if d["first_departure"] is None:
            d["first_departure"] = task["departure"]
        d["station"]      = task["destination"]
        d["available_at"] = task["arrival"]
        d["tasks"].append(task)

    # ------------------------------------------------------------------
    # Snapshot / restore for rollback
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """Full deep copy of all driver states."""
        return {
            did: {
                "station":               s["station"],
                "available_at":          s["available_at"],
                "original_available_at": s["original_available_at"],
                "duty_length_base":      s["duty_length_base"],
                "first_departure":       s["first_departure"],
                "tasks":                 list(s["tasks"]),
                "closed":                s["closed"],
            }
            for did, s in self._state.items()
        }

    def restore(self, snapshot: dict) -> None:
        """Restore all driver states from snapshot."""
        for did, snap in snapshot.items():
            s = self._state[did]
            s["station"]               = snap["station"]
            s["available_at"]          = snap["available_at"]
            s["original_available_at"] = snap["original_available_at"]
            s["duty_length_base"]      = snap["duty_length_base"]
            s["first_departure"]       = snap["first_departure"]
            s["tasks"]                 = list(snap["tasks"])
            s["closed"]                = snap["closed"]

    def snapshot_driver(self, driver_id: int) -> dict:
        """Snapshot of a single driver — used for per-task rollback in _find_driver_chain."""
        s = self._state[driver_id]
        return {
            "station":        s["station"],
            "available_at":   s["available_at"],
            "first_departure": s["first_departure"],
            "tasks":          list(s["tasks"]),
            "closed":         s["closed"],
        }

    def restore_driver(self, driver_id: int, snap: dict) -> None:
        """Restore a single driver from snapshot."""
        s = self._state[driver_id]
        s["station"]        = snap["station"]
        s["available_at"]   = snap["available_at"]
        s["first_departure"] = snap["first_departure"]
        s["tasks"]          = list(snap["tasks"])
        s["closed"]         = snap["closed"]
