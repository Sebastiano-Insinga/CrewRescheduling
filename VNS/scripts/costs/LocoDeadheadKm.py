from .CostComponent import CostComponent


class LocoDeadheadKm(CostComponent):

    def __init__(self, weight: float, is_hard: bool = False):
        super().__init__("loco_deadhead_km", weight, is_hard)

    def compute(self, state) -> float:
        return state.loco_dh_m / 1000

    def print_violations(self, state, out) -> None:
        for i in range(len(state.trip_order)):
            base = i * state.max_dh
            for k in range(state.max_dh):
                j = base + k
                if not state.dh_used[j]:
                    continue
                metres = state._sp_metres(state.dh_origin[j], state.dh_dest[j])
                print(f"loco {state.locos[state.trip_loco[i]]}: "
                      f"{metres / 1000:.1f} km of loco_deadhead "
                      f"{state.dh_origin[j]}->{state.dh_dest[j]} "
                      f"[{state.dh_dep[j]:.1f}, {state.dh_arr[j]:.1f}] "
                      f"before trip {state.trip_order[i]}", file=out)
