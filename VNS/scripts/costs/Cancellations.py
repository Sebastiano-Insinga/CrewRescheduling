from .CostComponent import CostComponent, trip_label


class Cancellations(CostComponent):

    def __init__(self, weight: float, is_hard: bool = False):
        super().__init__("cancellations", weight, is_hard)

    def compute(self, state) -> float:
        return state.n_canceled

    def print_violations(self, state, out) -> None:
        for i in range(len(state.trip_order)):
            if not state.trip_is_operated(i):
                print(f"canceled {trip_label(state, i)}", file=out)
