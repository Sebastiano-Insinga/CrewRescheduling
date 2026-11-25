from .CostComponent import CostComponent, trip_label


class MaintenanceExcess(CostComponent):

    def __init__(self, weight: float, is_hard: bool = True):
        name = "maintenance_excess_km" if is_hard else "maintenance_overdue_km"
        super().__init__(name, weight, is_hard)

    def _limits(self, state) -> list:
        return state.loco_limit if self.is_hard else state.loco_soft_limit

    def compute(self, state) -> float:
        return state._maint_excess if self.is_hard else state._maint_overdue

    def print_violations(self, state, out) -> None:
        kind   = "unmaintained" if self.is_hard else "overdue"
        limits = self._limits(state)
        for loco_index in range(len(state.locos)):
            for run, limit, closing in state.maintenance_stretches(loco_index, limits):
                if run <= limit:
                    continue
                where = (f"closed by {trip_label(state, closing)}" if closing is not None
                         else "still open at the end of the chain")
                print(f"loco {state.locos[loco_index]}: {run:.1f} km between maintenances, "
                      f"{run - limit:.1f} {kind} over the limit {limit:.0f} "
                      f"— stretch {where}", file=out)
