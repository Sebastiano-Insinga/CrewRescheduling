from dataclasses import dataclass

from ScheduleState import NONE

from .Move import Move


@dataclass(frozen=True)
class SwapTasks(Move):
    task_a: int
    task_b: int

    def feasible(self, state) -> bool:
        if self.task_a == self.task_b:
            return False
        d_a = state.task_driver(self.task_a)
        d_b = state.task_driver(self.task_b)
        return d_a != NONE and d_b != NONE and d_a != d_b

    def make_move(self, state) -> "SwapTasks":
        if not self.feasible(state):
            raise ValueError(f"scambio non applicabile: {self}")
        d_a = state.task_driver(self.task_a)
        d_b = state.task_driver(self.task_b)
        state.duty_tasks_list[d_a].remove(self.task_a)
        state.duty_tasks_list[d_b].remove(self.task_b)
        state._duty_insert(d_a, self.task_b)
        state._duty_insert(d_b, self.task_a)
        state._set_task_driver(self.task_a, d_b)
        state._set_task_driver(self.task_b, d_a)
        state._recompute_duty(d_a)
        state._recompute_duty(d_b)
        return self

    @classmethod
    def random_move(cls, state, rng) -> "SwapTasks":
        tasks = state._used
        return cls(tasks[rng.uniform_int(0, len(tasks) - 1)],
                   tasks[rng.uniform_int(0, len(tasks) - 1)])

    def __str__(self) -> str:
        return f"swap {self.task_a} <-> {self.task_b}"
