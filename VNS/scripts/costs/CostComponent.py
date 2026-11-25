class CostComponent:

    def __init__(self, name: str, weight: float, is_hard: bool):
        self.name    = name
        self.weight  = weight
        self.is_hard = is_hard

    @property
    def is_soft(self) -> bool:
        return not self.is_hard

    def compute(self, state) -> float:
        raise NotImplementedError

    def cost(self, state) -> float:
        return self.weight * self.compute(state)

    def print_violations(self, state, out) -> None:
        raise NotImplementedError

    def __str__(self) -> str:
        kind = "hard" if self.is_hard else "soft"
        return f"{self.name} ({kind}, weight {self.weight:g})"


def describe(state, task: int) -> str:
    kind = "trip" if task >= 0 else "loco_deadhead"
    return (f"{kind} {state.task_origin(task)}->{state.task_dest(task)} "
            f"[{state.task_dep(task):.1f}, {state.task_arr(task):.1f}]")


def trip_label(state, i: int) -> str:
    return (f"trip {state.trip_order[i]} {state.trip_origin[i]}->{state.trip_dest[i]} "
            f"[{state.trip_dep[i]:.1f}, {state.trip_arr[i]:.1f}]")
