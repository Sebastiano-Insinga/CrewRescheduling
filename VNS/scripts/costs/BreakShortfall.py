from .CostComponent import CostComponent


class BreakShortfall(CostComponent):

    def __init__(self, weight: float, is_hard: bool = True):
        super().__init__("break_shortfall", weight, is_hard)

    def compute(self, state) -> float:
        return sum(state.duty_break_short)

    def print_violations(self, state, out) -> None:
        for driver in range(len(state.drivers)):
            shortfall = state.duty_break_short[driver]
            if shortfall == 0:
                continue
            required = state.duty_req_break[driver]
            print(f"driver {state.drivers[driver]}: duty of "
                  f"{state.duty_len[driver]:.1f} min requires a {required} min break, "
                  f"the widest idle window holds {required - shortfall:.1f} min "
                  f"— {shortfall:.1f} missing, {len(state.duty_tasks_list[driver])} tasks, "
                  f"last arrival {state.duty_last_arr[driver]:.1f}", file=out)
