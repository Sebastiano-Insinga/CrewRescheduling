from .ChangeDriver import ChangeDriver
from .ChangeLoco import ChangeLoco
from .CoverTrip import CoverTrip
from .SwapTasks import SwapTasks
from .UncoverTrip import UncoverTrip

MOVES = (ChangeDriver, SwapTasks, CoverTrip, UncoverTrip, ChangeLoco)


def random_move(state, rng, weights: tuple = None, radius_km: float = None):
    active = [(kind, weight) for kind, weight in zip(MOVES, weights or (1.0,) * len(MOVES))
              if weight > 0]
    while active:
        if len(active) == 1:
            index = 0
        else:
            draw  = rng.uniform_int(0, 999_999) / 1_000_000 * sum(w for _, w in active)
            index = 0
            while index < len(active) - 1 and draw >= active[index][1]:
                draw  -= active[index][1]
                index += 1
        kind = active[index][0]
        move = (kind.random_move(state, rng, radius_km) if kind is ChangeDriver
                else kind.random_move(state, rng))
        if move is not None:
            return move
        active.pop(index)
    return None
