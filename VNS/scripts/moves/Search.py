from ScheduleState import NONE

from .CoverTrip import CoverTrip
from .Move import random_drivers
from .Neighborhood import random_move


def descend(state, manager, rng, max_steps: int = 100000, sample: int = 200,
            radius_km: float = None, journal: list = None, weights: tuple = None) -> tuple:
    applied = journal if journal is not None else []
    current = manager.cost_function_components(state)
    best    = current
    best_at = len(applied)
    steps   = 0
    while steps < max_steps:
        for _ in range(sample):
            move = random_move(state, rng, weights, radius_km)
            if move is None or not move.feasible(state):
                continue
            inverse   = move.make_move(state)
            candidate = manager.cost_function_components(state)
            if candidate < current:
                current = candidate
                steps  += 1
                applied.append(inverse)
                if candidate.beats_best(best):
                    best, best_at = candidate, len(applied)
                break
            inverse.make_move(state)
        else:
            break
    while len(applied) > best_at:
        applied.pop().make_move(state)
    return best, steps


def cover_search(state, manager, rng, iterations: int = 50, sample: int = 200,
                 radius_km: float = None, weights: tuple = None) -> tuple:
    best      = manager.cost_function_components(state)
    covered   = 0
    attempted = 0
    for _ in range(iterations):
        candidates = [i for i in range(len(state.trip_order))
                      if state.trip_loco[i] == NONE and state.trip_plan_loco[i] != NONE
                      and state.cover_plan(i, state.trip_plan_loco[i]) is not None]
        if not candidates:
            break
        trip            = candidates[rng.uniform_int(0, len(candidates) - 1)]
        loco            = state.trip_plan_loco[trip]
        own, _, after   = state.cover_plan(trip, loco)
        move            = CoverTrip(trip, loco,
                                    random_drivers(state, rng, len(own) + 1 + len(after)))
        undo_cover      = move.make_move(state)
        attempted      += 1
        journal         = []
        descend(state, manager, rng, sample=sample, radius_km=radius_km, journal=journal,
                weights=weights)
        current = manager.cost_function_components(state)
        if current.beats_best(best):
            best     = current
            covered += 1
        else:
            for inverse in reversed(journal):
                inverse.make_move(state)
            undo_cover.make_move(state)
    return best, covered, attempted
