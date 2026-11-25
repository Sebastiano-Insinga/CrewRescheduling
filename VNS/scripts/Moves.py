from __future__ import annotations

import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Cost import Cost
from moves import random_move

EPS = 1e-9


@dataclass(frozen=True)
class EvaluatedMove:
    move:  object
    delta: Cost

    def __str__(self) -> str:
        return f"{self.move}  delta total={self.delta.total:+.3f} " \
               f"violations={self.delta.violations:+.3f}"


def improves(evaluated: EvaluatedMove) -> bool:
    return evaluated.delta.total < -EPS


def not_worse(evaluated: EvaluatedMove) -> bool:
    return evaluated.delta.total <= EPS


def sampled_moves(state, rng, sample: int, weights: tuple = None, radius_km: float = None):
    for _ in range(sample):
        move = random_move(state, rng, weights, radius_km)
        if move is not None and move.feasible(state):
            yield move


def select_first(state, manager, rng, sample: int = 200, weights: tuple = None,
                 radius_km: float = None, accept=improves) -> EvaluatedMove:
    for move in sampled_moves(state, rng, sample, weights, radius_km):
        evaluated = EvaluatedMove(move, manager.evaluate(state, move))
        if accept(evaluated):
            return evaluated
    return None


def select_best(state, manager, rng, sample: int = 200, weights: tuple = None,
                radius_km: float = None, accept=improves) -> EvaluatedMove:
    best     = None
    n_bests  = 0
    for move in sampled_moves(state, rng, sample, weights, radius_km):
        evaluated = EvaluatedMove(move, manager.evaluate(state, move))
        if not accept(evaluated):
            continue
        if best is None or evaluated.delta.total < best.delta.total - EPS:
            best, n_bests = evaluated, 1
            continue
        if abs(evaluated.delta.total - best.delta.total) <= EPS:
            if rng.uniform_int(0, n_bests) == 0:
                best = evaluated
            n_bests += 1
    return best


def commit(state, manager, evaluated: EvaluatedMove):
    return manager.commit(state, evaluated.move, evaluated.delta)
