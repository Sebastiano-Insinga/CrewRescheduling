import json


TRIP          = 'trip'
LOCO_DEADHEAD = 'loco_deadhead'
CREW_DEADHEAD = 'crew_deadhead'


class Solution:
    """
    Integrated rescheduling solution: a flat list of assignments.

    assignment = {type, trip_id, origin, destination, departure, arrival,
                  locomotive, driver,
                  maintenance_at_departure, maintenance_at_destination}

    type is trip / loco_deadhead / crew_deadhead. 'locomotive' is None on
    crew_deadhead: the driver travels as a passenger. Grouping by locomotive
    or by driver is left to the reader — every assignment carries both.
    """

    def __init__(self, assignments=None, breaks=None, canceled=None,
                 run_info=None, name: str = None):
        self.assignments: list = assignments if assignments is not None else []
        self.breaks:      dict = breaks   if breaks   is not None else {}   # driver_id -> (start, end)
        self.canceled:    list = canceled if canceled is not None else []   # rs_trip_id
        self.run_info:    dict = run_info if run_info is not None else {}
        self.name = name

    def save(self, path: str) -> None:
        payload = {
            "run_info":    self.run_info,
            "assignments": self.assignments,
            "breaks":      {str(d): list(s) for d, s in self.breaks.items()},
            "canceled":    self.canceled,
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)

    def from_file(self, path: str) -> None:
        with open(path, "r") as f:
            payload = json.load(f)
        self.run_info    = payload["run_info"]
        self.assignments = payload["assignments"]
        # JSON object keys are always strings; driver_id is an int everywhere
        # else, so lookups against driver_status would silently miss
        self.breaks      = {int(d): tuple(s) for d, s in payload["breaks"].items()}
        self.canceled    = payload["canceled"]
        self.name = self.name or self.run_info.get("instance_id") or path
