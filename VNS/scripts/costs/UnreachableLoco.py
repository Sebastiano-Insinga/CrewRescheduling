from .CostComponent import CostComponent


class UnreachableLoco(CostComponent):

    def __init__(self, weight: float, is_hard: bool = True):
        super().__init__("loco_unreachable_links", weight, is_hard)

    def compute(self, state) -> float:
        return state._loco_unknown

    def print_violations(self, state, out) -> None:
        for j in state.unknown_segments():
            loco = state.locos[state.trip_loco[j // state.max_dh]]
            print(f"loco {loco}: unreachable loco_deadhead "
                  f"{state.dh_origin[j]}->{state.dh_dest[j]} "
                  f"[{state.dh_dep[j]:.1f}, {state.dh_arr[j]:.1f}], "
                  f"{state.dh_km[j]:.1f} km written", file=out)
