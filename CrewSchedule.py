from CrewDuty import CrewDuty
from Dashboards import *
import copy

class CrewSchedule:
    def __init__(self, all_tasks, crew_duties, duty_breaks, uncovered_tasks, shortest_path_matrix, id_mapping, locomotives):
        self.all_tasks = all_tasks
        self.set_of_all_tasks = set(self.all_tasks)
        self.shortest_path_matrix = shortest_path_matrix
        self.id_mapping = id_mapping
        self.locomotives = locomotives
        self.crew_duties = {}
        for duty_id, duty in crew_duties.items():
            self.crew_duties[duty_id] = CrewDuty(duty_id, duty, duty_breaks[duty_id], shortest_path_matrix)
            #print(f"Duty {duty_id} is feasible: {self.crew_duties[duty_id].check_feasibility()}")
        self.uncovered_tasks = []
        for task in uncovered_tasks:
            self.uncovered_tasks.append(copy.deepcopy(task))
        self.spared_duties = []

    def analyze_schedule(self):
        nr_duties = len(self.crew_duties)
        print(f"In the schedule there are currently {nr_duties} duties.")
        total_duty_length = 0
        min_duty_length = float("inf")
        max_duty_length = 0
        for duty_id, duty in self.crew_duties.items():
            length = duty.tasks[-1]["arrival"] - duty.tasks[0]["departure"]
            total_duty_length += length
            if length > max_duty_length:
                max_duty_length = length
            if length < min_duty_length:
                min_duty_length = length
        avg_duty_length = float(total_duty_length) / float(nr_duties)

        print(f"The average duty length is {avg_duty_length} minutes ({avg_duty_length/60} hours)")
        print(f"The minimum duty length is {min_duty_length} minutes ({min_duty_length / 60} hours)")
        print(f"The maximum duty length is {max_duty_length} minutes ({max_duty_length / 60} hours)")

    def visualizeSchedule(self, figures):
        display_duties = {}

        for duty_id, duty in self.crew_duties.items():
            display_duties[duty_id] = copy.deepcopy(duty.tasks)

        return createPlotlyFigure(figures, display_duties, self.id_mapping, self.locomotives)

    def display_schedule(self):
        for crew_duty in self.crew_duties.values():
            crew_duty.display_duty()

    def evaluteScheduleObjective(self):
        #one part of the objective is the number of uncovered tasks
        nr_uncovered_tasks = len(self.uncovered_tasks)
        nr_spared_drivers = len(self.spared_duties)
        #the second part is the cost for taxi deadheading
        #this will increase with the number of applied window-reschedulings
        #but hopefully this will decrease the number of uncovered tasks
        deadheading_costs = 0
        nr_deadheads = 0
        nr_breaks_violated = 0
        for duty_id, duty in self.crew_duties.items():
            duty_duration = duty.tasks[-1]["arrival"] - duty.tasks[0]["departure"]
            #we only need a break for duties that are longer than 6 hours
            if duty.duty_break == None and duty_duration > 360:
                nr_breaks_violated += 1
            for i in range(len(duty.tasks) - 1):
                if duty.tasks[i]["destination"] != duty.tasks[i + 1]["origin"]:
                    deadheading_costs += self.shortest_path_matrix[duty.tasks[i]["destination"]][duty.tasks[i + 1]["origin"]]
                    #deadheading_costs += 999 #TODO: replace by line above
                    nr_deadheads += 1
            #now also penalize the "going home" deadhead
            if len(duty.tasks) > 0:
                if duty.tasks[-1]["destination"] != duty.tasks[0]["origin"]:
                    deadheading_costs += self.shortest_path_matrix[duty.tasks[-1]["destination"]][duty.tasks[0]["origin"]]
                    #deadheading_costs += 999  # TODO: replace by line above
                    nr_deadheads += 1

        return (nr_deadheads, deadheading_costs, nr_uncovered_tasks, nr_breaks_violated, nr_spared_drivers)

    def updateScheduleFromWindow(self, window_solution, time_window, graph_nodes):
        #for duty_id in window_solution.keys():
        #    self.crew_duties[duty_id].display_duty()

        for duty_id in window_solution.keys():
            path = window_solution[duty_id]
            #print(f"Before updating duty {duty_id} it has the following tasks:")
            #self.crew_duties[duty_id].display_duty()
            self.crew_duties[duty_id].updateDutyFromWindow(path, time_window, graph_nodes)
            #print(f"After updating duty {duty_id} it has the following tasks:")
            #self.crew_duties[duty_id].display_duty()

        #new covered tasks
        self.covered_tasks = set()
        for duty_id, duty in self.crew_duties.items():
            #identify spared drivers
            if len(duty.tasks) == 0:
                self.spared_duties.append(duty_id)
            for task in duty.tasks:
                self.covered_tasks.add(task['id'])
        #claculate the set difference between all tasks and the covered tasks
        uncovered_task_ids = list(self.set_of_all_tasks - self.covered_tasks)
        self.uncovered_tasks = []
        for task_id in uncovered_task_ids:
            self.uncovered_tasks.append(copy.deepcopy(self.all_tasks[task_id]))

        #we delete this duty from the schedule
        for duty_id in self.spared_duties:
            self.crew_duties.pop(duty_id, None)

    #this function should be called at the end of the optimization run
    #it might potentially lead to uncovering certain tasks but avoids break-infeasible duties
    def makeScheduleBreakFeasible(self):
        for duty_id, duty in self.crew_duties.items():
            duty.makeDutyBreakFeasible()

        # update the number of covered tasks
        self.covered_tasks = set()
        for duty_id, duty in self.crew_duties.items():
            # identify spared drivers
            if len(duty.tasks) == 0:
                self.spared_duties.append(duty_id)
            for task in duty.tasks:
                self.covered_tasks.add(task['id'])
        # claculate the set difference between all tasks and the covered tasks
        uncovered_task_ids = list(self.set_of_all_tasks - self.covered_tasks)
        self.uncovered_tasks = []
        for task_id in uncovered_task_ids:
            self.uncovered_tasks.append(copy.deepcopy(self.all_tasks[task_id]))

        # we delete this duty from the schedule
        for duty_id in self.spared_duties:
            self.crew_duties.pop(duty_id, None)

