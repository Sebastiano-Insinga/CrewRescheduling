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
                "duty_start":            None,
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

    def duty_start(self, driver_id: int) -> float | None:
        """When the duty opened: the first task's departure minus the journey
        to reach it, since that journey is service. None until the first task
        is applied."""
        return self._state[driver_id]["duty_start"]

    def duty_length_base(self, driver_id: int) -> float:
        return self._state[driver_id]["duty_length_base"]

    def original_available_at(self, driver_id: int) -> float:
        return self._state[driver_id]["original_available_at"]

    def tasks(self, driver_id: int) -> list:
        return self._state[driver_id]["tasks"]

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

    def apply_task(self, driver_id: int, task: dict, dh_minutes: float = 0.0) -> None:
        """Commit task to driver_id — updates station, availability, task list.

        dh_minutes is the journey the driver makes to reach this task. It only
        matters on the first one, where it opens the duty: the duty starts when
        the driver sets off, not when the task departs.
        """
        d = self._state[driver_id]
        if d["duty_start"] is None:
            d["duty_start"] = task["departure"] - dh_minutes
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
                "duty_start":            s["duty_start"],
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
            s["duty_start"]            = snap["duty_start"]
            s["tasks"]                 = list(snap["tasks"])
            s["closed"]                = snap["closed"]

    def snapshot_driver(self, driver_id: int) -> dict:
        """Snapshot of a single driver — used for per-task rollback in _find_driver_chain."""
        s = self._state[driver_id]
        return {
            "station":        s["station"],
            "available_at":   s["available_at"],
            "duty_start":     s["duty_start"],
            "tasks":          list(s["tasks"]),
            "closed":         s["closed"],
        }

    def restore_driver(self, driver_id: int, snap: dict) -> None:
        """Restore a single driver from snapshot."""
        s = self._state[driver_id]
        s["station"]        = snap["station"]
        s["available_at"]   = snap["available_at"]
        s["duty_start"]     = snap["duty_start"]
        s["tasks"]          = list(snap["tasks"])
        s["closed"]         = snap["closed"]
