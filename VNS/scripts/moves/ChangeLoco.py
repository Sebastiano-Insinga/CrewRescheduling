from dataclasses import dataclass

from ScheduleState import NONE

from .Move import Move, random_drivers, valid_drivers
from .Restore import Restore


@dataclass(frozen=True)
class ChangeLoco(Move):
    trip:     int
    old_loco: int
    new_loco: int
    drivers:  tuple

    def plans(self, state) -> tuple:
        old  = state.uncover_plan(self.trip)
        new  = state.cover_plan(self.trip, self.new_loco)
        if old is None or new is None:
            return None
        return old, new

    def feasible(self, state) -> bool:
        if (state.trip_loco[self.trip] != self.old_loco or self.old_loco == NONE
                or self.new_loco == self.old_loco
                or not 0 <= self.new_loco < len(state.locos)):
            return False
        plans = self.plans(state)
        if plans is None:
            return False
        (_, old_after), (own, _, new_after) = plans
        return (len(self.drivers) == len(own) + len(old_after) + len(new_after)
                and valid_drivers(state, self.drivers))

    def make_move(self, state) -> Restore:
        if not self.feasible(state):
            raise ValueError(f"mossa non applicabile: {self}")
        (old_following, old_after), (own, new_following, new_after) = self.plans(state)
        record  = state.record(self.trip, (self.trip, old_following, new_following))
        touched = set()
        state._dh_clear(self.trip, touched)
        state._dh_write(self.trip, own, self.drivers[:len(own)], touched)
        state.trip_loco[self.trip] = self.new_loco
        k = len(own)
        if old_following != NONE:
            state._dh_clear(old_following, touched)
            state._dh_write(old_following, old_after, self.drivers[k:k + len(old_after)],
                            touched)
        k += len(old_after)
        if new_following != NONE:
            state._dh_clear(new_following, touched)
            state._dh_write(new_following, new_after, self.drivers[k:], touched)
        state._finish(touched)
        return Restore(record)

    @classmethod
    def random_move(cls, state, rng) -> "ChangeLoco":
        operated = [i for i in range(len(state.trip_order)) if state.trip_loco[i] != NONE]
        if not operated or len(state.placed_locos) < 2:
            return None
        trip = operated[rng.uniform_int(0, len(operated) - 1)]
        old  = state.trip_loco[trip]
        while True:
            new = state.placed_locos[rng.uniform_int(0, len(state.placed_locos) - 1)]
            if new != old:
                break
        move  = cls(trip, old, new, ())
        plans = move.plans(state)
        if plans is None:
            return move
        (_, old_after), (own, _, new_after) = plans
        return cls(trip, old, new,
                   random_drivers(state, rng, len(own) + len(old_after) + len(new_after)))

    def __str__(self) -> str:
        return (f"change loco trip {self.trip}: {self.old_loco}->{self.new_loco} "
                f"drivers {list(self.drivers)}")
