
import csv
import copy
import matplotlib.pyplot as plt

def performGreedyCrewScheduling(crew_scheduling_instance, max_duty_length):
    duties = {} # this will represent the greedy solution
    open_tasks = {}
    with open(crew_scheduling_instance, "r") as file:
        reader = csv.reader(file, delimiter="\t")
        for row in reader:
            task_id = int(row[0])  # First column as ID
            open_tasks[task_id] = {
                "id": task_id,
                "origin": int(row[1]),
                "destination": int(row[2]),
                "departure": int(row[3]),
                "arrival": int(row[4])
            }

    duty_index = 0
    #start first duty with the first task in the input
    #initial_task_key = min(open_tasks.keys())
    initial_task_key = min(open_tasks, key=lambda k: open_tasks[k]["departure"])
    duties[duty_index] = [copy.deepcopy(open_tasks[initial_task_key])]
    open_tasks.pop(initial_task_key)
    while len(open_tasks.keys()) > 0:
        print(f"There are {duty_index} duties scheduled and currently {len(open_tasks.keys())} tasks are not assigned yet.")
        feasible_tasks = {}
        for task_id, task in open_tasks.items():
            if task["origin"] == duties[duty_index][-1]["destination"] and task["departure"] >= duties[duty_index][-1]["arrival"] and (task["arrival"] - duties[duty_index][0]["departure"]) < max_duty_length:
                feasible_tasks[task_id] = copy.deepcopy(task)
        if len(feasible_tasks.keys()) > 0:
            min_departure_id = min(feasible_tasks, key=lambda k: feasible_tasks[k]["departure"])
            duty_task_list = copy.deepcopy(duties[duty_index])
            duty_task_list.append(copy.deepcopy(open_tasks[min_departure_id]))
            duties[duty_index] = duty_task_list
            open_tasks.pop(min_departure_id)
        #no more feasible task was found for the current duty -> start a new duty
        else:
            duty_index += 1
            #initial_task_key = min(open_tasks.keys())
            initial_task_key = min(open_tasks, key=lambda k: open_tasks[k]["departure"])
            duties[duty_index] = [copy.deepcopy(open_tasks[initial_task_key])]
            open_tasks.pop(initial_task_key)

    return duties

def calculateAverageDutyLength(duties):
    total_duty_length = 0
    number_duties = len(duties.keys())

    for duty_key in duties.keys():
        duty_length = duties[duty_key][-1]["arrival"] - duties[duty_key][0]["departure"]
        total_duty_length += duty_length

    return total_duty_length / number_duties
