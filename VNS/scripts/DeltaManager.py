from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Cost import Cost
from ScheduleManager import ScheduleManager
from deltas import candidate_duties, duty_delta, new_buffers
from deltas.Snap import snapped

DRIFT_TOLERANCE = 1e-6


class DeltaManager(ScheduleManager):

    def __init__(self):
        super().__init__()
        self._cost    = None
        self._buffers = new_buffers()
        self._hard    = ()
        self.by_hand  = 0
        self.by_apply = 0

    def initialize(self, state, weights: list = None) -> Cost:
        self._hard = tuple(component.is_hard for component in self.components)
        self._cost = self.cost_function_components(state, weights)
        return self._cost

    @property
    def cost(self) -> Cost:
        if self._cost is None:
            raise ValueError("accumulatore non inizializzato: chiamare initialize(state)")
        return self._cost

    def evaluate(self, state, move, weights: list = None) -> Cost:
        lists = candidate_duties(state, move)
        if lists is not None:
            self.by_hand += 1
            return duty_delta(state, self.components, lists, self._buffers, weights)
        self.by_apply += 1
        before  = (self._cost if self._cost is not None and weights is None
                   else self.cost_function_components(state, weights))
        inverse = move.make_move(state)
        after   = self.cost_function_components(state, weights)
        inverse.make_move(state)
        return after - before

    def commit(self, state, move, delta: Cost):
        inverse    = move.make_move(state)
        self._cost = snapped(self.cost + delta, self._hard)
        return inverse

    def revert(self, state, inverse, delta: Cost) -> None:
        inverse.make_move(state)
        self._cost = snapped(self.cost - delta, self._hard)

    def realign(self, state, weights: list = None) -> tuple:
        accumulated = self._cost
        self._hard  = tuple(component.is_hard for component in self.components)
        self._cost  = self.cost_function_components(state, weights)
        return accumulated, self._cost

    def drift(self, state, weights: list = None) -> float:
        full = self.cost_function_components(state, weights)
        return max(abs(self.cost.violations - full.violations),
                   abs(self.cost.objective - full.objective))

    def check_consistency(self, state) -> list:
        problems = super().check_consistency(state)
        if self._cost is None:
            return problems
        full = self.cost_function_components(state)
        if (abs(full.violations - self._cost.violations) > DRIFT_TOLERANCE
                or abs(full.objective - self._cost.objective) > DRIFT_TOLERANCE):
            problems.append(f"l'accumulatore dice {self._cost} ma il ricalcolo pieno {full}")
        for index, component in enumerate(self.components):
            if abs(full.all_components[index] - self._cost.all_components[index]) > DRIFT_TOLERANCE:
                problems.append(f"accumulatore su {component.name}: "
                                f"{self._cost.all_components[index]} invece di "
                                f"{full.all_components[index]}")
        return problems
