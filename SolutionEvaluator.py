from dataclasses import dataclass

@dataclass
class ObjectiveValue:
    n_canceled : int
    loco_dh_m : float
    crew_dh_m : float
    back_home : float
    total : float

class SolutionEvaluator:
    def __init__(self, mapper, net, w_canceled = 500, w_loco_dh = 0.2, w_crew_dh = 0.7, w_back_home = 0.5):
        self.mapper = mapper
        self.net = net
        self.w_canceled= w_canceled
        self.w_loco_dh = w_loco_dh
        self.w_crew_dh = w_crew_dh
        self.w_back_home  = w_back_home

    def evaluate_components(self, canceled_tasks, loco_dh_m, crew_dh_m, existing_duties):
        back_home  = self.check_back_home(existing_duties)
        n_canceled = len(canceled_tasks)
        loco_dh_km   = loco_dh_m / 1000
        crew_dh_km   = crew_dh_m / 1000
        back_home_km = back_home / 1000
        total = (self.w_canceled   * n_canceled
                 + self.w_loco_dh  * loco_dh_km
                 + self.w_crew_dh  * crew_dh_km
                 + self.w_back_home * back_home_km)
        return ObjectiveValue(total=total, n_canceled=n_canceled,
                          loco_dh_m=loco_dh_m, crew_dh_m=crew_dh_m,
                          back_home=back_home)


    def evaluate(self, canceled_tasks, loco_dh_m, crew_dh_m, existing_duties):
        return self.evaluate_components(canceled_tasks, loco_dh_m, crew_dh_m, existing_duties).total

    def check_back_home(self, existing_duties: dict) -> float:
        total = 0
        for driver_id, tasks in existing_duties.items():
            if not tasks:
                continue
            orig = self.mapper.original_schedule.get(driver_id, [])
            if not orig:
                continue
            home = orig[0]['origin']
            last = max(tasks, key=lambda t: t['arrival'])
            if last['destination'] != home:
                total += self.net.sp_raw.get(str(last['destination']), {}).get(str(home), {}).get('weight', 0)
        return total