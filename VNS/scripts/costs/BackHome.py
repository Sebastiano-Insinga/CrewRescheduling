from .CostComponent import CostComponent


class BackHome(CostComponent):

    def __init__(self, weight: float, is_hard: bool = False):
        super().__init__("back_home", weight, is_hard)

    def compute(self, state) -> float:
        return state.back_home / 1000

    def print_violations(self, state, out) -> None:
        for driver in range(len(state.drivers)):
            metres = state.duty_back_home[driver]
            if metres == 0:
                continue
            driver_id = state.drivers[driver]
            home = (state.mapper.original_schedule.get(driver_id) or [{}])[0].get("origin")
            print(f"driver {driver_id}: {metres / 1000:.1f} km from "
                  f"{state.duty_last_dest[driver]} back home to {home}, "
                  f"last arrival {state.duty_last_arr[driver]:.1f}", file=out)
