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
    # k = number of trips that we want to shake
    def select_k(all_candidates, trips, k, rng):
        sorted_trips = sorted(trips, key= lambda p:p["departure_time"])
        found = []
        for t in sorted_trips:
            alternatives = all_candidates.get(t['id'], [])[1:]
            if alternatives:
                found.append((t['id'], alternatives))
                if len(found)==k:
                    break
        if len(found)<k:
            return None
        else:
                forced_pair = {}
                for (i, (trip_id, alternatives)) in enumerate(found):        
                    if i==0:
                        forced_pair[trip_id]=alternatives[rng.uniform_int(0, len(alternatives)-1)]
                    else:
                        forced_pair[trip_id]= IntegratedRescheduler.FORCED_ALTERNATIVE
                return forced_pair
                    


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
