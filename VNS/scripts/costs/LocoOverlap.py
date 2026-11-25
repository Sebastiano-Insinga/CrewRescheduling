from .CostComponent import CostComponent, describe


class LocoOverlap(CostComponent):

    def __init__(self, weight: float, is_hard: bool = True):
        super().__init__("loco_overlap_minutes", weight, is_hard)

    def compute(self, state) -> float:
        return state._loco_overlap

    def print_violations(self, state, out) -> None:
        for loco_index in range(len(state.locos)):
            chain = state.loco_chain(loco_index)
            if chain and state.loco_station[loco_index] != -1:
                late = state.loco_ready[loco_index] - state.task_dep(chain[0])
                if late > 0:
                    print(f"loco {state.locos[loco_index]}: starts {late:.1f} min before "
                          f"being available at {state.loco_station[loco_index]} "
                          f"— {describe(state, chain[0])}", file=out)
            for before, after in zip(chain, chain[1:]):
                overlap = state.task_arr(before) - state.task_dep(after)
                if overlap <= 0:
                    continue
                print(f"loco {state.locos[loco_index]}: time overlap of {overlap:.1f} min "
                      f"between {describe(state, before)} and {describe(state, after)}",
                      file=out)
