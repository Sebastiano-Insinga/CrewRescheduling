import random
from IntegratedRescheduling import IntegratedRescheduler

class SwapStrategies:


    @staticmethod
    def swap_first_in_time(all_candidates, trips):
        sorted_trips = sorted(trips, key=lambda t: t['departure_time'])
        for t in sorted_trips:
            alternatives = all_candidates.get(t['id'], [])[1:]
            if alternatives:
                forced_pair = random.choice(alternatives)
                return {t['id']: forced_pair}
        return None

    @staticmethod
    def multiple_swap(all_candidates, trips):
        sorted_trips = sorted (trips, key=lambda t: t['departure_time'] )
        found=[]
        for t in sorted_trips:
            alternatives = all_candidates.get(t['id'], [])[1:]
            if alternatives:
                found.append((t['id'], alternatives))
                if len(found)==2:
                    break
        if len(found)==0:
            return None
        if len(found)==1:
            trip_id= found[0][0]
            alternatives = found[0][1]
            forced_pair = random.choice(alternatives)
            return {trip_id: forced_pair}
        if len(found)==2:
            trip1_id= found[0][0]
            alternatives = found[0][1]
            forced_pair1 = random.choice(alternatives)
            trip2_id = found[1][0]
            return {trip1_id: forced_pair1, trip2_id: IntegratedRescheduler.FORCED_ALTERNATIVE}
              

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
