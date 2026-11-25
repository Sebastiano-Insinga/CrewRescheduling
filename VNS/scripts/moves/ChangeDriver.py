from dataclasses import dataclass

from ScheduleState import NONE

from .Move import Move


@dataclass(frozen=True)
class ChangeDriver(Move):
    task:   int
    d_from: int
    d_to:   int

    def feasible(self, state) -> bool:
        return (self.d_from != self.d_to
                and self.d_from != NONE
                and 0 <= self.d_to < len(state.drivers)
                and state.task_driver(self.task) == self.d_from)

    def make_move(self, state) -> "ChangeDriver":
        if not self.feasible(state):
            raise ValueError(f"mossa non applicabile: {self}, il task e' di "
                             f"{state.task_driver(self.task)}")
        state.duty_tasks_list[self.d_from].remove(self.task)
        state._duty_insert(self.d_to, self.task)
        state._set_task_driver(self.task, self.d_to)
        state._recompute_duty(self.d_from)
        state._recompute_duty(self.d_to)
        return ChangeDriver(self.task, self.d_to, self.d_from)

    @classmethod
    def random_move(cls, state, rng, radius_km: float = None) -> "ChangeDriver":
        tasks   = state._used
        task    = tasks[rng.uniform_int(0, len(tasks) - 1)]
        current = state.task_driver(task)
        if radius_km is not None:
            near = state.near_drivers(task, radius_km)
            if near:
                return cls(task, current, near[rng.uniform_int(0, len(near) - 1)])
        while True:
            driver = rng.uniform_int(0, len(state.drivers) - 1)
            if driver != current:
                return cls(task, current, driver)

    def __str__(self) -> str:
        kind = f"trip {self.task}" if self.task >= 0 else f"dh {-self.task - 1}"
        return f"{kind}: {self.d_from}->{self.d_to}"
