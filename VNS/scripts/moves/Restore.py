from dataclasses import dataclass

from .Move import Move


@dataclass(frozen=True, eq=False)
class Restore(Move):
    record: dict

    def feasible(self, state) -> bool:
        return True

    def make_move(self, state) -> "Restore":
        inverse = Restore(state.record(self.record["trip"], tuple(self.record["dh"])))
        state.restore(self.record)
        return inverse

    def __str__(self) -> str:
        return f"restore trip {self.record['trip']}"
