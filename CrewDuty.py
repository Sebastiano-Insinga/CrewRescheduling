import copy
import math
from operator import truediv

crew_deadhead_speed = 100

class CrewDuty:
    def __init__(self, duty_id, tasks, duty_break, shortest_path_matrix):
        self.duty_id = duty_id
        self.tasks = []
        for task in tasks:
            if len(self.tasks) == 0:
                self.tasks.append(copy.deepcopy(task))
            elif task["arrival"] - self.tasks[0]["departure"] <= 720:
                self.tasks.append(copy.deepcopy(task))
        self.duty_break = copy.deepcopy(duty_break)
        self.shortest_path_matrix = shortest_path_matrix

    def insert_task(self, task):
        self.tasks.append(task)
        self.tasks.sort(key=lambda x: x['departure'])

    def remove_task(self, task):
        self.tasks.remove(task)

    def check_feasibility(self):
        copied_tasks = copy.deepcopy(self.tasks)
        # Step 1: Sort tasks based on departure time
        copied_tasks.sort(key=lambda x: x['departure'])

        # Step 2: Check for overlaps
        for i in range(1, len(copied_tasks)):
            # If the current object's departure time is before the previous object's arrival time, there is an overlap
            if copied_tasks[i]['departure'] < copied_tasks[i - 1]['arrival'] or copied_tasks[i]['origin'] < copied_tasks[i - 1]['destination']:
                return False

        return True

    def check_max_duty_length_feasibility(self, task):
        #only check this, if at least one task is already scheduled
        if len(self.tasks) > 0:
            start_time = min(task["departure"], min(t["departure"] for t in self.tasks))
            end_time = max(task["arrival"], max(t["arrival"] for t in self.tasks))

            if end_time - start_time <= 720:
                return True
            else:
                return False
        else:
            #if we have a task that is longer than 12 hours it will fit into no duty
            if task["arrival"] - task["departure"] <= 720:
                return True
            else:
                return False

    def check_insert_feasibility(self, task):
        copied_tasks = copy.deepcopy(self.tasks)
        copied_task = copy.deepcopy(task)
        new_tasks = copied_tasks.append(copied_task)
        # Step 1: Sort tasks based on departure time
        new_tasks.sort(key=lambda x: x['departure'])

        # Step 2: Check for overlaps
        for i in range(1, len(new_tasks)):
            # If the current object's departure time is before the previous object's arrival time, there is an overlap
            if new_tasks[i]['departure'] < new_tasks[i - 1]['arrival'] or new_tasks[i]['origin'] < new_tasks[i - 1]['destination']:
                return True

        return False

    def display_duty(self):
        self.tasks.sort(key=lambda x: x['departure'])
        print(f"Duty {self.duty_id}: {self.tasks}")

    def updateDutyFromWindow(self, path, time_window, nodes):
        updated_tasks_inside_window = []
        for node_id in path:
            if nodes[node_id].node_type == 1:
                task = nodes[node_id].node_task
                updated_tasks_inside_window.append(copy.deepcopy(task))

        window_start = time_window[0]
        window_end = time_window[1]
        #remove old tasks inside window
        to_be_removed = []
        for task in self.tasks:
            #this are all tasks of type for the respective window
            if (task["arrival"] >= window_start and task["arrival"] <= window_end) or (task["departure"] >= window_start and task["departure"] <= window_end):
                to_be_removed.append(copy.deepcopy(task))
        #do this outside the loop to not modify the loop while iterating over it!
        for task in to_be_removed:
            self.remove_task(copy.deepcopy(task))
        #insert new tasks inside window
        for task in updated_tasks_inside_window:
            #this if condition is new, should we only allow feasible duties here??
            if self.check_max_duty_length_feasibility(task):
                self.insert_task(task)
            else:
                print(f"This is crew duty {self.duty_id}")
                print(f"The time window is {time_window}")
                print("The current tasks are:")
                for t in self.tasks:
                    print(t)
                print("These are the tasks that were removed")
                for r in to_be_removed:
                    print(r)
                print(f"The new task would be {task} but cannot be added!")
                print("HEEERE")
            '''
            if len(self.tasks) == 0:
                self.insert_task(task)
            else:
                print(f"The task to be inserted is {task}")
                print(f"The first task of the duty is {self.tasks[0]}")
                if task["arrival"] - self.tasks[0]["departure"] <= 720:
                    self.insert_task(task)
                else:
                    print(task["arrival"] - self.tasks[0]["departure"])
                    print("HEREEEEE")
            '''

        if len(self.tasks) > 0:
            #this shoudl hopefully improve the number of scheduled breaks
            #handle breaks: indicate potential breaks in the self.duty_break field
            start_time = min(t["departure"] for t in self.tasks)
            end_time = max(t["arrival"] for t in self.tasks)
            duty_length = end_time - start_time

            if duty_length <= 360:
                required_break_length = 0
            elif duty_length <= 480:
                required_break_length = 30
            else:
                required_break_length = 45

            if self.duty_break != None:
                #this means there is a break within the time window and we need to make sure that it is again feasible and possibly correct it or also indicate that now no break is posssible
                if self.duty_break[0] <= time_window[1] and self.duty_break[1] >= time_window[0]:
                    for i in range(len(self.tasks) - 1):
                        task_A = self.tasks[i]
                        task_B = self.tasks[i + 1]

                        if task_A["arrival"] >= math.floor(duty_length / 4) and task_B["departure"] - task_A[
                            "arrival"] >= required_break_length:
                            self.duty_break = (task_A["arrival"], task_A["arrival"] + required_break_length)
                            break

            #this means there was no break before and now we need to check if we can insert a break
            else:
                for i in range(len(self.tasks) - 1):
                    task_A = self.tasks[i]
                    task_B = self.tasks[i + 1]

                    if task_A["arrival"] >= math.floor(duty_length / 4) and task_B["departure"] - task_A[
                        "arrival"] >= required_break_length:
                        self.duty_break = (task_A["arrival"], task_A["arrival"] + required_break_length)
                        break


    #this function should only be called after the optimization run
    #the logic might remove a covered task, but makes the duty break-feasible
    def makeDutyBreakFeasible(self):
        #we need to fix the duty because there is no break after the optimization step
        if self.duty_break == None:
            #if there are no tasks we also need no break
            if len(self.tasks) > 0:

                start_time = min(t["departure"] for t in self.tasks)
                end_time = max(t["arrival"] for t in self.tasks)
                duty_length = end_time - start_time

                #for duties with less than 6 hours we do not need a break
                if duty_length > 360:
                    break_added = False

                    if duty_length <= 480:
                        required_break_length = 30
                    else:
                        required_break_length = 45

                    #check again if we can fit the break somewhere
                    for i in range(len(self.tasks) - 1):
                        task_A = self.tasks[i]
                        task_B = self.tasks[i + 1]

                        if task_B["departure"] - task_A["arrival"] >= required_break_length:
                            self.duty_break = (task_A["arrival"], task_A["arrival"] + required_break_length)
                            break_added = True
                            break

                    #if still no break is possible we start to remove tasks to make a break
                    # we then need a gap that is long enough to perform the break and do a potential deadhead
                    #check once if loop should be entered
                    if break_added != True:
                        for i in range(len(self.tasks) - 2):
                            #check again in case a task was removed within the loop
                            if break_added != True:
                                task_A = self.tasks[i]
                                task_B = self.tasks[i + 1]
                                task_C = self.tasks[i + 2]

                                station_before_break = task_A["destination"]
                                station_after_break = task_C["origin"]
                                deadhead_duration = (((self.shortest_path_matrix[station_before_break][station_after_break]) / 1000.0) / crew_deadhead_speed) * 60

                                if task_C["departure"] - task_A["arrival"] >= deadhead_duration + required_break_length:
                                    self.duty_break = (task_A["arrival"], task_A["arrival"] + required_break_length)
                                    self.remove_task(task_B)
                                    print(
                                        f"Task {task_B} was removed from the duty.")
                                    break_added = True
                            else:
                                break

                    print(f"Finally also this duty {self.tasks} has a break: {break_added}: {self.duty_break}.")