from .CostComponent import CostComponent, describe


class UncoveredTasks(CostComponent):

    def __init__(self, weight: float, is_hard: bool = True):
        super().__init__("uncovered_tasks", weight, is_hard)

    def compute(self, state) -> float:
        return state._uncovered

    def print_violations(self, state, out) -> None:
        for task in state._uncovered_tasks:
            print(f"no driver on {describe(state, task)}", file=out)
