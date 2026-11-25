from dataclasses import dataclass

from ScheduleState import NONE

from .Move import Move, random_drivers, valid_drivers
from .Restore import Restore


@dataclass(frozen=True)
class UncoverTrip(Move):
    trip:    int
    drivers: tuple

    def feasible(self, state) -> bool:
        if state.trip_loco[self.trip] == NONE:
            return False
        plan = state.uncover_plan(self.trip)
        if plan is None:
            return False
        return len(self.drivers) == len(plan[1]) and valid_drivers(state, self.drivers)

    def make_move(self, state) -> Restore:
        if not self.feasible(state):
            raise ValueError(f"mossa non applicabile: {self}")
        following, after = state.uncover_plan(self.trip)
        record  = state.record(self.trip, (self.trip, following))
        touched = set()
        state._set_trip_driver(self.trip, NONE, touched)
        state._dh_clear(self.trip, touched)
        state.trip_loco[self.trip] = NONE
        if following != NONE:
            state._dh_clear(following, touched)
            state._dh_write(following, after, self.drivers, touched)
        state._finish(touched)
        return Restore(record)

    @classmethod
    def random_move(cls, state, rng) -> "UncoverTrip":
        operated = [i for i in range(len(state.trip_order)) if state.trip_loco[i] != NONE]
        if not operated:
            return None
        trip = operated[rng.uniform_int(0, len(operated) - 1)]
        plan = state.uncover_plan(trip)
        n    = 0 if plan is None else len(plan[1])
        return cls(trip, random_drivers(state, rng, n))

    def __str__(self) -> str:
        return f"uncover trip {self.trip} drivers {list(self.drivers)}"
