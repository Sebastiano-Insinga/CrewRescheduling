from .CostComponent import CostComponent, describe
from .DutyWalk import walk


class ResourceLate(CostComponent):

    def __init__(self, weight: float, is_hard: bool = True):
        super().__init__("continuity_minutes", weight, is_hard)

    def compute(self, state) -> float:
        return sum(state.duty_continuity)

    def print_violations(self, state, out) -> None:
        for driver in range(len(state.drivers)):
            for _, task, position, ready, origin, departure, dh_minutes, _, gap in \
                    walk(state, driver):
                if gap is None or gap >= 0:
                    continue
                print(f"driver {state.drivers[driver]}: reaching {origin} from {position} "
                      f"needs {dh_minutes:.1f} min from {ready:.1f} but departure is "
                      f"{departure:.1f}, late by {-gap:.1f} min "
                      f"— {describe(state, task)}", file=out)
