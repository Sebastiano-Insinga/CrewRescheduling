class Move:

    def feasible(self, state) -> bool:
        raise NotImplementedError

    def make_move(self, state) -> "Move":
        raise NotImplementedError

    @classmethod
    def random_move(cls, state, rng) -> "Move":
        raise NotImplementedError


def random_drivers(state, rng, n: int) -> tuple:
    return tuple(rng.uniform_int(0, len(state.drivers) - 1) for _ in range(n))


def valid_drivers(state, drivers: tuple) -> bool:
    return all(0 <= driver < len(state.drivers) for driver in drivers)
