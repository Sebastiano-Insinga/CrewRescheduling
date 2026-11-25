from rescheduling.IntegratedRescheduling import IntegratedRescheduler
from rescheduling.RollingStockGreedy import CppMT19937

MAX_SAMPLE_TRIES = 100


class SwapStrategies:


    @staticmethod
    def swap_first_in_time(all_candidates, trips):
        return SwapStrategies.select_k(all_candidates, trips, 1, CppMT19937(42))

    @staticmethod
    def multiple_swap(all_candidates, trips):
        return SwapStrategies.select_k(all_candidates, trips, 2, CppMT19937(42))
              
    @staticmethod
    # k = number of trips that we want to shake, the first k in departure order
    def select_k(all_candidates, trips, k, rng, exclude=(), min_alternatives=1):
        candidates = SwapStrategies.pool(all_candidates, trips, exclude)
        chosen = candidates[:1] + [c for c in candidates[1:] if len(c[1]) >= min_alternatives][:k - 1]
        if len(chosen) < k:
            return None
        return SwapStrategies.build_forced(chosen, rng)


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
    def select_random_k(all_candidates, trips, k, rng, exclude=(), min_alternatives=1):
        candidates = SwapStrategies.pool(all_candidates, trips, exclude)
        if len(candidates) < k:
            return None
        for _ in range(MAX_SAMPLE_TRIES):
            idx = SwapStrategies.sample_k_indices(len(candidates), k, rng)
            chosen = [candidates[i] for i in idx]
            if all(len(alternatives) >= min_alternatives for _, alternatives in chosen[1:]):
                return SwapStrategies.build_forced(chosen, rng)
        return None

    @staticmethod
    def select_window_k(all_candidates, trips, k, rng, exclude=(), min_alternatives=1,
                        window_hours=4.0):
        candidates = SwapStrategies.pool(all_candidates, trips, exclude)
        if len(candidates) < k:
            return None
        windows = SwapStrategies.valid_windows(candidates, trips, k, min_alternatives, window_hours)
        if not windows:
            return None
        start, end = windows[rng.uniform_int(0, len(windows) - 1)]
        window = candidates[start:end]
        for _ in range(MAX_SAMPLE_TRIES):
            idx = SwapStrategies.sample_k_indices(len(window), k, rng)
            chosen = [window[i] for i in idx]
            if all(len(alternatives) >= min_alternatives for _, alternatives in chosen[1:]):
                return SwapStrategies.build_forced(chosen, rng)
        rich = [c for c in window[1:] if len(c[1]) >= min_alternatives]
        return SwapStrategies.build_forced(window[:1] + rich[:k - 1], rng)

    @staticmethod
    def valid_windows(candidates, trips, k, min_alternatives, window_hours):
        departure = {t['id']: t['departure_time'] // 60 for t in trips}
        deps = [departure[trip_id] for trip_id, _ in candidates]
        rich = [len(alternatives) >= min_alternatives for _, alternatives in candidates]
        span = int(window_hours * 60)
        windows = []
        end = 0
        rich_in_window = 0
        for start in range(len(candidates)):
            while end < len(candidates) and deps[end] <= deps[start] + span:
                rich_in_window += rich[end]
                end += 1
            if end - start >= k and rich_in_window - rich[start] >= k - 1:
                windows.append((start, end))
            rich_in_window -= rich[start]
        return windows

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
    "window" : SwapStrategies.select_window_k,
}
