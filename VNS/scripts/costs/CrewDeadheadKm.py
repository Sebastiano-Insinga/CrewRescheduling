from .CostComponent import CostComponent, describe
from .DutyWalk import walk


class CrewDeadheadKm(CostComponent):

    def __init__(self, weight: float, is_hard: bool = False):
        super().__init__("crew_deadhead_km", weight, is_hard)

    def compute(self, state) -> float:
        return state.crew_dh_m / 1000

    def print_violations(self, state, out) -> None:
        for driver in range(len(state.drivers)):
            for _, task, position, _, origin, _, _, dh_metres, _ in walk(state, driver):
                if dh_metres == 0:
                    continue
                print(f"driver {state.drivers[driver]}: {dh_metres / 1000:.1f} km of "
                      f"crew_deadhead {position}->{origin} before {describe(state, task)}",
                      file=out)
