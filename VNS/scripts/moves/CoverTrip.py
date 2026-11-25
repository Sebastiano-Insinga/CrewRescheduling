from dataclasses import dataclass

from ScheduleState import NONE

from .Move import Move, random_drivers, valid_drivers
from .Restore import Restore


@dataclass(frozen=True)
class CoverTrip(Move):
    trip:    int
    loco:    int
    drivers: tuple

    def feasible(self, state) -> bool:
        if state.trip_loco[self.trip] != NONE or not 0 <= self.loco < len(state.locos):
            return False
        plan = state.cover_plan(self.trip, self.loco)
        if plan is None:
            return False
        own, _, after = plan
        return len(self.drivers) == len(own) + 1 + len(after) and valid_drivers(state,
                                                                                self.drivers)

    def make_move(self, state) -> Restore:
        if not self.feasible(state):
            raise ValueError(f"mossa non applicabile: {self}")
        own, following, after = state.cover_plan(self.trip, self.loco)
        record  = state.record(self.trip, (self.trip, following))
        touched = set()
        state._dh_clear(self.trip, touched)
        state._dh_write(self.trip, own, self.drivers[:len(own)], touched)
        state.trip_loco[self.trip] = self.loco
        state._set_trip_driver(self.trip, self.drivers[len(own)], touched)
        if following != NONE:
            state._dh_clear(following, touched)
            state._dh_write(following, after, self.drivers[len(own) + 1:], touched)
        state._finish(touched)
        return Restore(record)

    @classmethod
    def random_move(cls, state, rng) -> "CoverTrip":
        canceled = [i for i in range(len(state.trip_order)) if state.trip_loco[i] == NONE]
        if not canceled:
            return None
        trip = canceled[rng.uniform_int(0, len(canceled) - 1)]
        loco = state.placed_locos[rng.uniform_int(0, len(state.placed_locos) - 1)]
        plan = state.cover_plan(trip, loco)
        n    = 0 if plan is None else len(plan[0]) + 1 + len(plan[2])
        return cls(trip, loco, random_drivers(state, rng, n))

    def __str__(self) -> str:
        return f"cover trip {self.trip} loco {self.loco} drivers {list(self.drivers)}"
