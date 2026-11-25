from .CostComponent import CostComponent, describe
from .DutyWalk import walk


class Unreachable(CostComponent):

    def __init__(self, weight: float, is_hard: bool = True):
        super().__init__("unreachable_links", weight, is_hard)

    def compute(self, state) -> float:
        return sum(state.duty_unreachable)

    def print_violations(self, state, out) -> None:
        for driver in range(len(state.drivers)):
            for _, task, position, _, origin, _, dh_minutes, _, _ in walk(state, driver):
                if dh_minutes != float("inf"):
                    continue
                print(f"driver {state.drivers[driver]}: no path {position}->{origin} "
                      f"— {describe(state, task)}", file=out)
