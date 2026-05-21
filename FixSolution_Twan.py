import copy
import math
import csv
import random
from VNS_Rescheduling import compute_shortest_path_matrix_dijkstra

def fixSolutionTwan(duties, uncovered_tasks, duty_breaks, loco_knowledge, section_knowledge, suitable_tasks, loco_types, section_types, min_loco_knowledge, min_section_knowledge, network_data, instance_name, disruption_start):

    #######
    #this part is new
    #here we want to be accurate with the deadheads and the shortest path matrix
    involved_stations = []
    for task_id, task in uncovered_tasks.items():
        if task["origin"] not in involved_stations:
            involved_stations.append(task["origin"])
        if task["destination"] not in involved_stations:
            involved_stations.append(task["destination"])

    # shortest_path_matrix = []
    shortest_path_matrix = compute_shortest_path_matrix_dijkstra(network_data["stations"], network_data["sections"],
                                                                 involved_stations)
    crew_deadhead_speed = 100

    #######
    max_duty_key = max(duties.keys())

    original_max_duty = max_duty_key + 1
    duty_id = max_duty_key + 1
    duty_breaks[duty_id] = None

    #implement a function here that creates new duties for the uncovered tasks
    #here we should already allow taxi rides
    #then we should also account for the correct breaks...maybe we need to split duties that do not have a break and create two new duties
    while len(uncovered_tasks) > 0:
        feasible_tasks = []
        if duty_id in duties.keys():
            for task_id, task in uncovered_tasks.items():
                new_duty_length = task['arrival'] - duties[duty_id][0]['departure']
                #check if this task would still fit in the current duty

                #this was the older version without the shortest path
                #if new_duty_length <= 720 and duties[duty_id][-1]['arrival'] + 60 <= task["departure"]:
                if new_duty_length <= 720 and duties[duty_id][-1]['arrival'] + (((shortest_path_matrix[duties[duty_id][-1]['destination']][task["origin"]])/1000.0)/crew_deadhead_speed)*60 <= task["departure"]:
                    feasible_tasks.append(copy.deepcopy(task))
        else:
            task = min(uncovered_tasks.values(), key=lambda obj: obj["departure"])
            duties[duty_id] = [task]
            uncovered_tasks.pop(task['id'],None)

        if len(feasible_tasks) > 0:
            task = min(feasible_tasks, key=lambda obj: obj["departure"])
            new_tasks = copy.deepcopy(duties[duty_id])
            new_tasks.append(task)
            duties[duty_id] = new_tasks
            uncovered_tasks.pop(task['id'], None)
        # no feasible task found so create a new duty
        else:
            duty_id += 1
            duty_breaks[duty_id] = None

    ####
    #define the section and driver knowledge of the additional drivers here and then update the suitable tasks
    for duty_id in range(original_max_duty, max(duties.keys())+1):
        lk = []
        sk = []
        for task in duties[duty_id]:
            lk.append(task["loco_type"])
            sk.append(task["section_type"])

        lk_set = set(lk)
        sk_set = set(sk)
        #at least 50% locomotive types per driver
        #min_loco_knowledge = 0.5
        while len(lk_set) < min_loco_knowledge*len(loco_types):
            available = [x for x in loco_types if x not in lk_set]
            additional_type = random.choice(available)
            lk_set.add(additional_type)

        # at least 50% section types per driver
        #min_section_knowledge = 0.5
        while len(sk_set) < min_section_knowledge * len(section_types):
            available = [x for x in section_types if x not in sk_set]
            additional_type = random.choice(available)
            sk_set.add(additional_type)

        loco_knowledge[duty_id] = copy.deepcopy(lk_set)
        section_knowledge[duty_id] = copy.deepcopy(sk_set)

    #print("###################################")
    #print("These are the suitable tasks before the additional duties")
    #for duty_id, st in suitable_tasks.items():
    #    print(f"The suitable tasks of duty {duty_id} are {sorted(st)}")
    #print("###################################")
    for duty_id in range(original_max_duty, max(duties.keys())+1):
        lk = loco_knowledge[duty_id]
        sk = section_knowledge[duty_id]
        suitable = []
        for inner_duty_id in range(max(duties.keys())):
            for task in duties[inner_duty_id]:
                if task["loco_type"] in lk and task["section_type"] in sk:
                    suitable.append(task["id"])
        suitable_tasks[duty_id] = copy.deepcopy(suitable)

    ###
    for duty_id, duty in duties.items():
        #insert breaks for the newly added duties
        if duty_id >= max_duty_key + 1:
            duty_length = duty[-1]["arrival"] - duty[0]["departure"]
            break_planned = False
            # iterate over pairs of tasks and check if there is the necessary gap available
            for i in range(len(duty) - 1):
                task_A = duty[i]
                task_B = duty[i + 1]
                if duty_length <= 480:
                    #case 1: no deadheading required
                    if task_A["destination"] == task_B["origin"]:
                        # here we have a simple rule, the break cannot be in the first quarter of the shift
                        if task_A["arrival"] >= math.floor(duty_length / 6) and task_B["departure"] - task_A["arrival"] >= 30:
                            duty_breaks[duty_id] = (task_A["arrival"], task_A["arrival"] + 30)
                            break_planned = True
                            break
                    #case 2: a deadhead is required
                    else:
                        #this was the old version before the shortest path matrix
                        #if task_A["arrival"] >= math.floor(duty_length / 4) and task_B["departure"] - task_A["arrival"] >= (30 + 60):
                        if task_A["arrival"] >= math.floor(duty_length / 6) and task_B["departure"] - task_A["arrival"] >= (30 + (((shortest_path_matrix[task_A["destination"]][task_B["origin"]])/1000.0)/crew_deadhead_speed)*60):
                            duty_breaks[duty_id] = (task_A["arrival"], task_A["arrival"] + 30)
                            break_planned = True
                            break

                elif duty_length > 480:
                    # here we have a simple rule, the break cannot be in the first quarter of the shift
                    # case 1: no deadheading required
                    if task_A["destination"] == task_B["origin"]:
                        if task_A["arrival"] >= math.floor(duty_length / 6) and task_B["departure"] - task_A["arrival"] >= 45:
                            duty_breaks[duty_id] = (task_A["arrival"], task_A["arrival"] + 45)
                            break_planned = True
                            break
                    #case 2: deadhead required
                    else:
                        #this was the old version without shortet path matrix
                        #if task_A["arrival"] >= math.floor(duty_length / 6) and task_B["departure"] - task_A["arrival"] >= (45 + 60):
                        if task_A["arrival"] >= math.floor(duty_length / 6) and task_B["departure"] - task_A["arrival"] >= (45 + (((shortest_path_matrix[task_A["destination"]][task_B["origin"]])/1000.0)/crew_deadhead_speed)*60):
                            duty_breaks[duty_id] = (task_A["arrival"], task_A["arrival"] + 45)
                            break_planned = True
                            break
            if break_planned == False:
                # this is only after reading the original plan: here it should always be possible to put a break, but maybe it cannot be directly after the task
                for i in range(len(duty) - 1):
                    task_A = duty[i]
                    task_B = duty[i + 1]
                    if duty_length <= 480:
                        # here we have a simple rule, the break cannot be in the first quarter of the shift
                        # case 1: no deadheading required
                        if task_A["destination"] == task_B["origin"]:
                            if task_B["departure"] - task_A["arrival"] >= 30:
                                duty_breaks[duty_id] = (task_B["departure"] - 30, task_B["departure"])
                                break_planned = True
                                break
                        #case 2
                        else:
                            sp = (((shortest_path_matrix[task_A["destination"]][task_B["origin"]])/1000.0)/crew_deadhead_speed)*60
                            if task_B["departure"] - task_A["arrival"] >= (30 + sp):
                                duty_breaks[duty_id] = (task_B["departure"] - (30+sp), task_B["departure"] - sp)
                                break_planned = True
                                break
                    elif duty_length > 480:
                        # here we have a simple rule, the break cannot be in the first quarter of the shift
                        # case 1: no deadheading required
                        if task_A["destination"] == task_B["origin"]:
                            if task_B["departure"] - task_A["arrival"] >= 45:
                                duty_breaks[duty_id] = (task_B["departure"] - 45, task_B["departure"])
                                break_planned = True
                                break
                        else:
                            sp = (((shortest_path_matrix[task_A["destination"]][task_B["origin"]]) / 1000.0) / crew_deadhead_speed) * 60
                            if task_B["departure"] - task_A["arrival"] >= (45 + sp):
                                duty_breaks[duty_id] = (task_B["departure"] - (45+sp), task_B["departure"] - sp)
                                break_planned = True
                                break


            # this means also in the solution by twan no break was possible
            if break_planned == False:
                duty_breaks[duty_id] = None

    #There might still be duties that do not have a break and are longer than 6 hours!
    #this is infeasible:
    #therefore we will split these duties into two separate duties
    #the knowledge will be transferred

    additional_duty_key = max(duties.keys()) + 1
    additional_duties = {}
    for duty_id, duty in duties.items():
        duty_length = duty[-1]["arrival"] - duty[0]["departure"]
        #we do this for duties that are longer than 6 hours
        if duty_length > 360 and duty_breaks[duty_id] == None:
            #now split the duties into two
            split_flag_1 = False
            split_flag_2 = False
            if len(duty) > 1:
                duty_part_1 = []
                duty_part_2 = []

                #we decide to added thew first task in either case
                #NOTE that we might add a task that is longer than 6 hours, but we cannot do anything about this
                duty_part_1.append(duty[0])
                split_flag_1 = True
                #at least we notify in a message
                if duty[0]["arrival"] - duty[0]["departure"] > 360:
                    print("The first task of the duty is longer than 6 hours and there no break is possible in general")
                for i in range(1, len(duty)):
                    task_A = duty[i]
                    #this means that it still fits in the first part
                    if task_A["arrival"] - duty_part_1[0]["departure"] <= 360:
                        duty_part_1.append(task_A)
                        #we have successfully added a task to duty 1
                    #this means that it does not fit in the first part so we will put everything that is remaining in the second part
                    else:
                        for j in range(i, len(duty)):
                            task = duty[j]
                            duty_part_2.append(task)
                            #we have successfully added a task to duty 2
                            split_flag_2 = True
                        #after putting everything in the second part we break the upper loop
                        break
                #Only modify the duties if the split was successful
                if split_flag_1 == True and split_flag_2 == True:
                    #print("Splitting the duties was successfull")
                    #new duty is added
                    additional_duties[additional_duty_key] = duty_part_2
                    #knowledge for the new duty is the same as for the original one
                    suitable_tasks[additional_duty_key] = copy.deepcopy(suitable_tasks[duty_id])
                    duty_breaks[additional_duty_key] = None
                    additional_duty_key += 1
                    #old duty is updated to only the first part
                    duties[duty_id] = duty_part_1
                #else:
                    #print("###SPLITTING NOT SUCESSFULL")

            else:
                print("The duty contains a single task that is longer than 6 hours and therefore no break is possible in general")

    #add the new duties
    for duty_id, duty in additional_duties.items():
        duties[duty_id] = duty

    #print("###################################")
    #print("These are the suitable tasks at the end")
    #print(f"The dict suitable tasks has {len(suitable_tasks.keys())} keys")
    #for duty_id, st in suitable_tasks.items():
    #    print(f"The suitable tasks of duty {duty_id} are {sorted(list(set(st)))}")
    #print("###################################")

    #count how many breaks are missing in the plan of twan
    missing_breaks = 0
    dead_heads = 0
    slack_duties = 0
    total_tasks_covered = []

    nr_duties_violating = 0
    violating_duties = []
    for duty_id, duty in duties.items():
        for task in duty:
            if task not in total_tasks_covered:
                total_tasks_covered.append(task)
        violating = False
        duty_length = duty[-1]["arrival"] - duty[0]["departure"]
        if duty_breaks[duty_id] == None:
            missing_breaks += 1
            violating = True
            #print(f"The length of the break-infeasible duty is: {duty_length} and consists of {len(duty)} tasks")
        internal_deadhead = False
        for i in range(len(duty) - 1):
            task_A = duty[i]
            task_B = duty[i + 1]
            if task_B["origin"] != task_A["destination"]:
                violating = True
                internal_deadhead = True
        if violating == True:
            nr_duties_violating +=1
            slack_duties += len(duty)
            violating_duties.append(duty_id)
        if internal_deadhead == True:
            dead_heads+=1
    print(f"After fixing the original plan of Twan we have {len(duties.keys())} duties with {missing_breaks} missing breaks and in {dead_heads} duties there is an internal deadhead")
    print(f"The number of duties violating either the break constraint or require a deadhead within the duty is: {nr_duties_violating} resulting in {slack_duties} tasks that should be in a slack duty.")
    print(f"In total there are {len(total_tasks_covered)} tasks covered")
    print(f"The violating duties are the following: {violating_duties}")
    '''
    #####
    #write the duties for sebastiano
    with open("Repaired_solution_twan_"+instance_name, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")

        for duty_id, duty in duties.items():
            task_ids = [task["id"] for task in duty]
            writer.writerow([duty_id] + task_ids)
    #####
    '''
    #############
    #here we classify the duties regarding their length
    # initialize counters
    bins = {
        "0-360": 0,
        "361-480": 0,
        "481-600": 0,
        "601-720": 0,
    }

    for duty in duties.values():
        start = duty[0]["departure"]
        end = duty[-1]["arrival"]

        #only count the duties that end after the start of the disruption
        if end >= disruption_start:
            length = end - start  # duty length in minutes

            if 0 <= length <= 360:
                bins["0-360"] += 1
            elif 361 <= length <= 480:
                bins["361-480"] += 1
            elif 481 <= length <= 600:
                bins["481-600"] += 1
            elif 601 <= length <= 720:
                bins["601-720"] += 1

    # results
    print("This are the duty categories of the original plan")
    for k, v in bins.items():
        print(f"{k}: {v}")

    #############
    return duties, duty_breaks, loco_knowledge, section_knowledge, suitable_tasks