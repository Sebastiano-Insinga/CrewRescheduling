from .CostComponent import CostComponent


class DutyExcess(CostComponent):

    def __init__(self, weight: float, is_hard: bool = True):
        super().__init__("duty_excess_minutes", weight, is_hard)

    def compute(self, state) -> float:
        return sum(state.duty_excess)

    def print_violations(self, state, out) -> None:
        for driver in range(len(state.drivers)):
            if state.duty_excess[driver] == 0:
                continue
            driver_id = state.drivers[driver]
            carried   = state.mapper.driver_status[driver_id]["duty_length"]
            before    = f", {carried:.1f} of them before the disruption" if carried > 0 else ""
            print(f"driver {driver_id}: duty of {state.duty_len[driver]:.1f} min exceeds "
                  f"{state.max_duty_length}{before} — "
                  f"{len(state.duty_tasks_list[driver])} tasks, "
                  f"last arrival {state.duty_last_arr[driver]:.1f}", file=out)
