from dataclasses import dataclass


@dataclass(frozen=True)
class PenaltyWeights:
    continuity:      float = 1000.0
    unreachable:     float = 5000.0
    duty_excess:     float = 1000.0
    break_shortfall: float = 1000.0
    maintenance_km:  float = 10.0


@dataclass(frozen=True)
class Cost:
    violations:     float
    objective:      float
    all_components: tuple = ()

    @property
    def total(self) -> float:
        return self.violations + self.objective

    @property
    def feasible(self) -> bool:
        return self.violations == 0

    def __lt__(self, other: "Cost") -> bool:
        return self.total < other.total

    def __add__(self, other: "Cost") -> "Cost":
        return Cost(violations=self.violations + other.violations,
                    objective=self.objective + other.objective,
                    all_components=_zip(self.all_components, other.all_components, 1.0))

    def __sub__(self, other: "Cost") -> "Cost":
        return Cost(violations=self.violations - other.violations,
                    objective=self.objective - other.objective,
                    all_components=_zip(self.all_components, other.all_components, -1.0))

    def beats_best(self, best: "Cost") -> bool:
        if self.violations != best.violations:
            return self.violations < best.violations
        return self.total < best.total

    def __str__(self) -> str:
        return (f"total={self.total:.1f} violations={self.violations:.1f} "
                f"objective={self.objective:.1f} feasible={self.feasible}")


def _zip(left: tuple, right: tuple, sign: float) -> tuple:
    if not left:
        return tuple(sign * value for value in right)
    if not right:
        return left
    if len(left) != len(right):
        raise ValueError(f"componenti incompatibili: {len(left)} contro {len(right)}")
    return tuple(a + sign * b for a, b in zip(left, right))
