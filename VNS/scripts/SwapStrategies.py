from IntegratedRescheduling import IntegratedRescheduler
from RollingStockGreedy import CppMT19937

class SwapStrategies:


    @staticmethod
    def swap_first_in_time(all_candidates, trips):
        return SwapStrategies.select_k(all_candidates, trips, 1, CppMT19937(42))

    @staticmethod
    def multiple_swap(all_candidates, trips):
        return SwapStrategies.select_k(all_candidates, trips, 2, CppMT19937(42))
              
    @staticmethod
    # k = number of trips that we want to shake, the first k in departure order
    def select_k(all_candidates, trips, k, rng, exclude=()):
        candidates = SwapStrategies.pool(all_candidates, trips, exclude)
        if len(candidates) < k:
            return None
        return SwapStrategies.build_forced(candidates[:k], rng)


    @staticmethod
    def pool(all_candidates, trips, exclude=()): 
        sorted_trips = sorted(trips, key= lambda p:p["departure_time"])
        found = []
        for t in sorted_trips:
            if t['id'] in exclude:
                continue
            alternatives = all_candidates.get(t['id'], [])[1:]
            if alternatives:
                found.append((t['id'], alternatives))
        return found


    @staticmethod
    # k distinct indices out of 0..n-1, sorted (partial Fisher-Yates)
    def sample_k_indices(n, k, rng):
        idx = list(range(n))
        for i in range(k):
            j = i + rng.uniform_int(0, n - 1 - i)
            idx[i], idx[j] = idx[j], idx[i]
        return sorted(idx[:k])

    @staticmethod
    # found must be sorted by departure_time: concrete pair on the first, sentinel on the rest
    def build_forced(found, rng):
        forced_pair = {}
        for (i, (trip_id, alternatives)) in enumerate(found):
            if i == 0:
                forced_pair[trip_id] = alternatives[rng.uniform_int(0, len(alternatives) - 1)]
            else:
                forced_pair[trip_id] = IntegratedRescheduler.FORCED_ALTERNATIVE
        return forced_pair

    @staticmethod
    # k = number of trips that we want to shake, picked at random instead of first-in-time
    def select_random_k(all_candidates, trips, k, rng, exclude=()):
        candidates = SwapStrategies.pool(all_candidates, trips, exclude)
        if len(candidates) < k:
            return None
        idx = SwapStrategies.sample_k_indices(len(candidates), k, rng)
        return SwapStrategies.build_forced([candidates[i] for i in idx], rng)


    @staticmethod
    def get_swap_strategy(name):
        try:
            return SWAP_STRATEGIES[name]
        except KeyError:
            valid = ', '.join(sorted(SWAP_STRATEGIES))
            raise ValueError(f"Unknown swap strategy '{name}'. Valid options: {valid}")


SWAP_STRATEGIES = {
    "first_in_time": SwapStrategies.swap_first_in_time,
    "multiple_swap" : SwapStrategies.multiple_swap,
}

# strategie di shaking per run_loop: firma (all_candidates, trips, k, rng, exclude).
# Registro separato da SWAP_STRATEGIES, che ha firma a 2 argomenti (DD-1).
SHAKE_STRATEGIES = {
    "ordered": SwapStrategies.select_k,
    "random" : SwapStrategies.select_random_k,
}
