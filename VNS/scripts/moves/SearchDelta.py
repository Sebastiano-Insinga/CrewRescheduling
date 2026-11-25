from Moves import commit, select_best, select_first
from ScheduleState import NONE

from .CoverTrip import CoverTrip
from .Move import random_drivers


def _rollback(state, manager, journal: list, down_to: int) -> None:
    while len(journal) > down_to:
        inverse, delta = journal.pop()
        manager.revert(state, inverse, delta)


def descend_delta(state, manager, rng, max_steps: int = 100000, sample: int = 200,
                  radius_km: float = None, journal: list = None, weights: tuple = None,
                  steepest: bool = False) -> tuple:
    applied = journal if journal is not None else []
    select  = select_best if steepest else select_first
    best    = manager.cost
    best_at = len(applied)
    steps   = 0
    while steps < max_steps:
        evaluated = select(state, manager, rng, sample, weights, radius_km)
        if evaluated is None:
            break
        applied.append((commit(state, manager, evaluated), evaluated.delta))
        steps += 1
        if manager.cost.beats_best(best):
            best, best_at = manager.cost, len(applied)
    _rollback(state, manager, applied, best_at)
    return best, steps


def cover_search_delta(state, manager, rng, iterations: int = 50, sample: int = 200,
                       radius_km: float = None, weights: tuple = None,
                       steepest: bool = False) -> tuple:
    best      = manager.cost
    covered   = 0
    attempted = 0
    for _ in range(iterations):
        candidates = [i for i in range(len(state.trip_order))
                      if state.trip_loco[i] == NONE and state.trip_plan_loco[i] != NONE
                      and state.cover_plan(i, state.trip_plan_loco[i]) is not None]
        if not candidates:
            break
        trip          = candidates[rng.uniform_int(0, len(candidates) - 1)]
        loco          = state.trip_plan_loco[trip]
        own, _, after = state.cover_plan(trip, loco)
        move          = CoverTrip(trip, loco,
                                  random_drivers(state, rng, len(own) + 1 + len(after)))
        cover_delta   = manager.evaluate(state, move)
        undo_cover    = manager.commit(state, move, cover_delta)
        attempted    += 1
        journal       = []
        descend_delta(state, manager, rng, sample=sample, radius_km=radius_km,
                      journal=journal, weights=weights, steepest=steepest)
        if manager.cost.beats_best(best):
            best     = manager.cost
            covered += 1
        else:
            _rollback(state, manager, journal, 0)
            manager.revert(state, undo_cover, cover_delta)
    return best, covered, attempted
