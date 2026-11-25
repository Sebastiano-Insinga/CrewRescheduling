from .CostComponent import CostComponent, trip_label


class MaintenanceTime(CostComponent):

    def __init__(self, weight: float, is_hard: bool = True):
        super().__init__("maintenance_time_minutes", weight, is_hard)

    def compute(self, state) -> float:
        return state._maint_time

    def print_violations(self, state, out) -> None:
        for loco_index in range(len(state.locos)):
            for task, required, free, following in state.maintenance_windows(loco_index):
                if free >= required:
                    continue
                where = "at departure" if state.trip_maint[task] == 1 else "at destination"
                before = ("" if following < 0
                          else f" before {trip_label(state, following)}")
                print(f"loco {state.locos[loco_index]}: maintenance {where} needs "
                      f"{required:.0f} min but only {free:.1f} min are free{before} "
                      f"— {trip_label(state, task)}", file=out)
