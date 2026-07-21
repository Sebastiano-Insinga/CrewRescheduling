
class SolutionEvaluator:
    def __init__(self, mapper, net):
        self.mapper = mapper
        self.net = net

    def evaluate(self, canceled_tasks, loco_dh_m, crew_dh_m, existing_duties) -> float:
        W_1, W_2, W_3, W_4 = 0.1, 0.2, 0.7, 0.5
        back_home = self.check_back_home(existing_duties)
        obj = (W_1 * len(canceled_tasks)
               + W_2 * loco_dh_m
               + W_3 * crew_dh_m
               + W_4 * back_home)
        return obj

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