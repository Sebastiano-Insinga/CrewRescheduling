import csv
import pandas as pd
import copy
import math
import random

def getKnowledgeStatistics(loco_knowledge, section_knowledge):
    total_locos = 4
    total_sections = 10

    def get_percentage(known_items, total):
        return round(len(set(known_items)) / total * 100)

    # Compute each driver's locomotive and section knowledge %
    driver_stats = {}
    for driver_id in set(loco_knowledge.keys()) | set(section_knowledge.keys()):
        loco_pct = get_percentage(loco_knowledge.get(driver_id, []), total_locos)
        sect_pct = get_percentage(section_knowledge.get(driver_id, []), total_sections)
        driver_stats[driver_id] = (loco_pct, sect_pct)

    # Aggregate counts by exact percentage combinations
    combo_counts = {}
    for loco_pct, sect_pct in driver_stats.values():
        combo_counts[(loco_pct, sect_pct)] = combo_counts.get((loco_pct, sect_pct), 0) + 1

    total_drivers = len(driver_stats)

    # Aggregate single-dimension statistics
    loco_distribution = {}
    sect_distribution = {}
    for loco_pct, sect_pct in driver_stats.values():
        loco_distribution[loco_pct] = loco_distribution.get(loco_pct, 0) + 1
        sect_distribution[sect_pct] = sect_distribution.get(sect_pct, 0) + 1

    # Print locomotive knowledge distribution
    print("\nLocomotive Knowledge Distribution:")
    print("-" * 40)
    print(f"{'Knowledge %':<15}{'% of Drivers':>15}")
    print("-" * 40)
    for pct in sorted(loco_distribution):
        driver_pct = loco_distribution[pct] / total_drivers * 100
        print(f"{pct:>6}%{'':<9}{driver_pct:>13.1f}%")
    print("-" * 40)

    # Print section knowledge distribution
    print("\nSection Knowledge Distribution:")
    print("-" * 40)
    print(f"{'Knowledge %':<15}{'% of Drivers':>15}")
    print("-" * 40)
    for pct in sorted(sect_distribution):
        driver_pct = sect_distribution[pct] / total_drivers * 100
        print(f"{pct:>6}%{'':<9}{driver_pct:>13.1f}%")
    print("-" * 40)

    # Print combined summary
    print("\nCombined Knowledge Summary:")
    print("-" * 60)
    print(f"{'Loco %':<10}{'Section %':<15}{'% of Drivers':>15}")
    print("-" * 60)
    for (loco_pct, sect_pct), count in sorted(combo_counts.items()):
        driver_pct = count / total_drivers * 100
        print(f"{loco_pct:>6}%{'':<4}{sect_pct:>8}%{'':<8}{driver_pct:>13.1f}%")
    print("-" * 60)

def readSolution_Twan_txt_Format_incl_Uncovered(solution_file, instance_file, id_mapping, loco_types, section_types, min_loco_knowledge, min_section_knowledge):
    random.seed(42)

    # Load original tasks from the instance file
    tasks = {}
    with open(instance_file, "r") as file:
        reader = csv.reader(file, delimiter="\t")
        for row in reader:
            task_id = int(row[0])

            if 'section' in id_mapping[task_id].keys():
                section_type = id_mapping[task_id]["section"] % len(section_types)
            #otherwise we have a deadhead task
            else:
                section_type = id_mapping[task_id]["first_section"] % len(section_types)

            tasks[task_id] = {
                "id": task_id,
                "origin": int(row[1]),
                "destination": int(row[2]),
                "departure": int(row[3]),
                "arrival": int(row[4]),
                "loco_type" : id_mapping[task_id]["locomotive"] % len(loco_types),
                "section_type": section_type
            }

    duties = {}
    uncovered = {}

    with open(solution_file, "r") as file:
        lines = file.readlines()

    # Split into covered and uncovered sections
    covered_lines = []
    uncovered_lines = []
    in_uncovered_section = False

    for line in lines:
        line = line.strip()
        if line.startswith("MyIndex"):
            in_uncovered_section = True
            continue
        if not in_uncovered_section:
            if line and not line.startswith("Costs"):
                covered_lines.append(line)
        else:
            if line:
                uncovered_lines.append(line)

    # Parse covered duties (same as before)
    for index, line in enumerate(covered_lines):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        try:
            costs = float(parts[0])
            duration = float(parts[1])
            task_ids = [int(p) for p in parts[2:] if p.strip()]
        except ValueError:
            continue

        #print(f"Covered Duty {index}: Costs={costs}, Duration={duration}, Tasks={task_ids}")
        duties[index] = []
        for task_id in task_ids:
            if task_id in tasks:
                duties[index].append(copy.deepcopy(tasks[task_id]))

    # Parse uncovered tasks
    for line in uncovered_lines:
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        try:
            task_id = int(parts[1])  # 'Index' column = task_id
            uncovered[task_id] = {
                "id": task_id,
                "origin": int(parts[4]),
                "destination": int(parts[5]),
                "departure": int(parts[2]),
                "arrival": int(parts[3])
            }
        except ValueError:
            continue

        #print(f"Uncovered Task {task_id}: {uncovered[task_id]}")

    # Optional: sort duties
    sorted_duties = dict(sorted(duties.items(), key=lambda item: min(d['departure'] for d in item[1])))

    duty_breaks = {}
    # in general a break needs to be 30 minutes if the break is at most 8 hours and 45 if more than 8 hours
    for duty_id, duty in sorted_duties.items():
        duty_length = duty[-1]["arrival"] - duty[0]["departure"]
        break_planned = False
        # iterate over pairs of tasks and check if there is the necessary gap available
        for i in range(len(duty) - 1):
            task_A = duty[i]
            task_B = duty[i + 1]
            if duty_length <= 480:
                # here we have a simple rule, the break cannot be in the first quarter of the shift
                if task_A["arrival"] >= math.floor(duty_length / 4) and task_B["departure"] - task_A["arrival"] >= 30:
                    duty_breaks[duty_id] = (task_A["arrival"], task_A["arrival"] + 30)
                    break_planned = True
                    break
            elif duty_length > 480:
                # here we have a simple rule, the break cannot be in the first quarter of the shift
                if task_A["arrival"] >= math.floor(duty_length / 4) and task_B["departure"] - task_A["arrival"] >= 45:
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
                    if task_B["departure"] - task_A["arrival"] >= 30:
                        duty_breaks[duty_id] = (task_B["departure"] - 30, task_B["departure"])
                        break_planned = True
                        break
                elif duty_length > 480:
                    # here we have a simple rule, the break cannot be in the first quarter of the shift
                    if task_B["departure"] - task_A["arrival"] >= 45:
                        duty_breaks[duty_id] = (task_B["departure"] - 45, task_B["departure"])
                        break_planned = True
                        break

        # this means also in the solution by twan no break was possible
        if break_planned == False:
            duty_breaks[duty_id] = None

    #print(duties)
    #print(duty_breaks)

    ########################################################################
    #add section and locomotive specification for each task here (randomly but based on the original plan)
    #assume there are 4 types of locomotives
    #assume there are 10 types of sections/areas
    #loco_types = [0,1,2,3]
    #section_types = [0,1,2,3,4,5,6,7,8,9]

    #these are dictionary having the duty id as the key and having a list of types as the value
    #this will be later used to create the set of suitable tasks for each driver
    loco_knowledge = {}
    section_knowledge = {}

    for duty_id, duty in sorted_duties.items():
        nr_tasks = len(duty)
        lk = []
        sk = []
        for task in duty:
            loco_type = id_mapping[task["id"]]["locomotive"] % len(loco_types)
            #this means we have a regular task
            if 'section' in id_mapping[task["id"]].keys():
                section_type = id_mapping[task["id"]]["section"] % len(section_types)
            #otherwise we have a deadhead task
            else:
                section_type = id_mapping[task["id"]]["first_section"] % len(section_types)
            task["loco_type"] = loco_type
            task["section_type"] = section_type
            lk.append(loco_type)
            sk.append(section_type)

        lk_set = set(lk)
        sk_set = set(sk)
        #at least 50% locomotive types per driver
        # min_loco_knowledge = 0.5
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

    for task_id, task in uncovered.items():
        task["loco_type"] = random.choice(loco_types)
        task["section_type"] = random.choice(section_types)

    #for duty_id, duty in sorted_duties.items():
    #    print(f"The locomotive knowledge of driver {duty_id} is: {loco_knowledge[duty_id]}")

    #for duty_id, duty in sorted_duties.items():
    #    print(f"The section knowledge of driver {duty_id} is: {section_knowledge[duty_id]}")

    #for duty_id, duty in sorted_duties.items():
    #    for task in duty:
    #        id = task["id"]
    #        loco_type = task["loco_type"]
    #        print(f"The locomotive type of task {id} is {loco_type}")

    suitable_tasks = {}
    for duty_id, duty in sorted_duties.items():
        lk = loco_knowledge[duty_id]
        sk = section_knowledge[duty_id]
        suitable = []
        for t_index, t in tasks.items():
            if t["loco_type"] in lk and t["section_type"] in sk:
                suitable.append(t["id"])
        '''        
        for inner_duty_id, inner_duty in sorted_duties.items():
            for task in inner_duty:
                if task["loco_type"] in lk and task["section_type"] in sk:
                    suitable.append(task["id"])
        for task_id, task in uncovered.items():
            if task["loco_type"] in lk and task["section_type"] in sk:
                suitable.append(task["id"])
        '''
        suitable_tasks[duty_id] = copy.deepcopy(suitable)

    #for duty_id, duty in sorted_duties.items():
    #    print(f"The suitable tasks of duty {duty_id} are {sorted(suitable_tasks[duty_id])}")
    ##########################################################################

    return sorted_duties, uncovered, duty_breaks, loco_knowledge, section_knowledge, suitable_tasks

def readSolution_Twan_txt_Format(solution_file, instance_file):
    duties = {}
    # read the original problem
    tasks = {}
    with open(instance_file, "r") as file:
        reader = csv.reader(file, delimiter="\t")
        for row in reader:
            task_id = int(row[0])  # First column as ID
            tasks[task_id] = {
                "id": task_id,
                "origin": int(row[1]),
                "destination": int(row[2]),
                "departure": int(row[3]),
                "arrival": int(row[4])
            }

    with open(solution_file, "r") as file:
        header_skipped = False
        index = 0
        for line in file:
            line = line.strip()
            if not header_skipped:
                if line.startswith("Costs"):
                    header_skipped = True
                continue
            if line.startswith("MyIndex"):
                break  # Stop reading at the start of uncovered tasks
            if not line:
                continue  # Skip empty lines

            # Split the line by tabs
            parts = line.split("\t")
            if len(parts) < 3:
                continue  # Malformed line, skip

            try:
                costs = float(parts[0])
                duration = float(parts[1])
                task_ids = [int(p) for p in parts[2:] if p.strip()]
            except ValueError:
                continue  # Malformed data, skip

            #print(f"Costs: {costs}, Duration: {duration}, Tasks: {task_ids}")

            # Reconstruct the tasks from the original instance
            duties[index] = []
            for task_id in task_ids:
                if task_id in tasks:
                    duties[index].append(copy.deepcopy(tasks[task_id]))
            index += 1

    # Sort duties by first departure time
    sorted_duties = dict(sorted(duties.items(), key=lambda item: min(d['departure'] for d in item[1])))

    # here I decide on the breaks:
    duty_breaks = {}
    # in general a break needs to be 30 minutes if the break is at most 8 hours and 45 if more than 8 hours
    for duty_id, duty in sorted_duties.items():
        duty_length = duty[-1]["arrival"] - duty[0]["departure"]
        break_planned = False
        # iterate over pairs of tasks and check if there is the necessary gap available
        for i in range(len(duty) - 1):
            task_A = duty[i]
            task_B = duty[i + 1]
            if duty_length <= 480:
                # here we have a simple rule, the break cannot be in the first quarter of the shift
                if task_A["arrival"] >= math.floor(duty_length / 4) and task_B["departure"] - task_A["arrival"] >= 30:
                    duty_breaks[duty_id] = (task_A["arrival"], task_A["arrival"] + 30)
                    break_planned = True
                    break
            elif duty_length > 480:
                # here we have a simple rule, the break cannot be in the first quarter of the shift
                if task_A["arrival"] >= math.floor(duty_length / 4) and task_B["departure"] - task_A["arrival"] >= 45:
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
                    if task_B["departure"] - task_A["arrival"] >= 30:
                        duty_breaks[duty_id] = (task_B["departure"] - 30, task_B["departure"])
                        break_planned = True
                        break
                elif duty_length > 480:
                    # here we have a simple rule, the break cannot be in the first quarter of the shift
                    if task_B["departure"] - task_A["arrival"] >= 45:
                        duty_breaks[duty_id] = (task_B["departure"] - 45, task_B["departure"])
                        break_planned = True
                        break

        # this means also in the solution by twan no break was possible
        if break_planned == False:
            duty_breaks[duty_id] = None

    #print(duties)
    #print(duty_breaks)
    return sorted_duties, duty_breaks

def readSolution_Twan(solution_file, instance_file):
    duties = {}
    #read the original problem
    tasks = {}
    with open(instance_file, "r") as file:
        reader = csv.reader(file, delimiter="\t")
        for row in reader:
            task_id = int(row[0])  # First column as ID
            tasks[task_id] = {
                "id": task_id,
                "origin": int(row[1]),
                "destination": int(row[2]),
                "departure": int(row[3]),
                "arrival": int(row[4])
            }
    # Read the solution of twan
    df = pd.read_excel(solution_file, sheet_name='Solution_2')

    for index, row in df.iterrows():
        costs = row['Costs']
        duration = row['Duration']
        task_ids = row[2:].dropna().tolist()  # Get task columns, drop NaN, and convert to list

        #print(f"Costs: {costs}, Duration: {duration}, Tasks: {task_ids}")

    #create a solution that can be plotted by the visualization tool based on the solution and the original instance
    for index, row in df.iterrows():
        duties[index] = []
        ids = row[2:].dropna().tolist()  # Get task columns, drop NaN, and convert to list
        for id in ids:
            if id in tasks.keys():
                new_tasks = duties[index]
                new_tasks.append(copy.deepcopy(tasks[id]))
                duties[index] = new_tasks

    sorted_duties = dict(sorted(duties.items(), key=lambda item: min(d['departure'] for d in item[1])))

    # here I decide on the breaks:
    duty_breaks = {}
    # in general a break needs to be 30 minutes if the break is at most 8 hours and 45 if more than 8 hours
    for duty_id, duty in sorted_duties.items():
        duty_length = duty[-1]["arrival"] - duty[0]["departure"]
        break_planned = False
        # iterate over pairs of tasks and check if there is the necessary gap available
        for i in range(len(duty) - 1):
            task_A = duty[i]
            task_B = duty[i + 1]
            if duty_length <= 480:
                # here we have a simple rule, the break cannot be in the first quarter of the shift
                if task_A["arrival"] >= math.floor(duty_length / 4) and task_B["departure"] - task_A["arrival"] >= 30:
                    duty_breaks[duty_id] = (task_A["arrival"], task_A["arrival"] + 30)
                    break_planned = True
                    break
            elif duty_length > 480:
                # here we have a simple rule, the break cannot be in the first quarter of the shift
                if task_A["arrival"] >= math.floor(duty_length / 4) and task_B["departure"] - task_A["arrival"] >= 45:
                    duty_breaks[duty_id] = (task_A["arrival"], task_A["arrival"] + 45)
                    break_planned = True
                    break
        if break_planned == False:
            #this is only after reading the original plan: here it should always be possible to put a break, but maybe it cannot be directly after the task
            for i in range(len(duty) - 1):
                task_A = duty[i]
                task_B = duty[i + 1]
                if duty_length <= 480:
                    # here we have a simple rule, the break cannot be in the first quarter of the shift
                    if task_B["departure"] - task_A["arrival"] >= 30:
                        duty_breaks[duty_id] = (task_B["departure"]-30, task_B["departure"])
                        break_planned = True
                        break
                elif duty_length > 480:
                    # here we have a simple rule, the break cannot be in the first quarter of the shift
                    if task_B["departure"] - task_A["arrival"] >= 45:
                        duty_breaks[duty_id] = (task_B["departure"]-45, task_B["departure"])
                        break_planned = True
                        break

        #this means also in the solution by twan no break was possible
        if break_planned == False:
            duty_breaks[duty_id] = None

    #print(duties)
    #print(duty_breaks)
    return sorted_duties, duty_breaks

def performAnalysis_Solution_Twan(solution_file, instance_file, shortest_path_matrix, passenger_train_speed):
    print(shortest_path_matrix)
    #here I want to get some insight on the length of the duties - both feasible and infeasible duties
    # read the original problem
    tasks = {}
    with open(instance_file, "r") as file:
        reader = csv.reader(file, delimiter="\t")
        for row in reader:
            task_id = int(row[0])  # First column as ID
            tasks[task_id] = {
                "id": task_id,
                "origin": int(row[1]),
                "destination": int(row[2]),
                "departure": int(row[3]),
                "arrival": int(row[4])
            }

    #print(tasks)
    # Read the solution of twan
    df = pd.read_excel(solution_file, sheet_name='Solution_2')

    number_feasible_duties = 0.0
    number_infeasible_duties = 0.0

    total_duration_feasible_duties = 0.0
    total_duration_infeasible_duties = 0.0

    max_duration_feasible_duties = 0.0
    max_duration_infeasible_duties = 0.0

    total_deadhead_duration = 0
    shortest_path_not_found = 0

    number_travel_time_exceeded = 0
    total_travel_time_exceeded = 0

    for index, row in df.iterrows():
        costs = row['Costs']
        duration = row['Duration']
        task_ids = row[2:].dropna().tolist()
        #duty is feasible
        if costs == 1:
            number_feasible_duties += 1.0
            total_duration_feasible_duties += duration
            if duration > max_duration_feasible_duties:
                max_duration_feasible_duties = duration
            #duty is infeasible
        elif costs == 10:
            number_infeasible_duties += 1.0
            total_duration_infeasible_duties += duration
            if duration > max_duration_infeasible_duties:
                max_duration_infeasible_duties = duration

            #identify the deadhead duration
            #first of all get the starting station and end station
            first_task_id = task_ids[0]
            last_task_id = task_ids[-1]

            first_station = tasks[int(first_task_id)]["origin"]
            last_station = tasks[int(last_task_id)]["destination"]
            #this means that the shortest path is known
            shortest_path_found = False
            if str(first_station) in shortest_path_matrix:
                if str(last_station) in shortest_path_matrix[str(first_station)]:
                    shortest_path_found = True
                    deadhead_distance = shortest_path_matrix[str(first_station)][str(last_station)]['weight']
                    deadhead_travel_time = ((deadhead_distance / 1000) / passenger_train_speed) * 3600
                    total_deadhead_duration += deadhead_travel_time

                    if (duration + deadhead_travel_time/60) > 720:
                        number_travel_time_exceeded += 1
                        total_travel_time_exceeded += (duration + deadhead_travel_time/60)
            #shortest path was not precomputed for this
            if not shortest_path_found:
                shortest_path_not_found += 1


    avg_duration_feasible_duties = total_duration_feasible_duties / number_feasible_duties
    avg_duration_infeasible_duties = total_duration_infeasible_duties / number_infeasible_duties
    avg_deadhead_duration = total_deadhead_duration / (number_infeasible_duties-shortest_path_not_found)
    avg_travel_time_exceeded = total_travel_time_exceeded / number_travel_time_exceeded

    print(f"There are {number_feasible_duties} feasible duties with an average duration of {avg_duration_feasible_duties} and a maximum duration of {max_duration_feasible_duties}.")
    print(
        f"There are {number_infeasible_duties} infeasible duties with an average duration of {avg_duration_infeasible_duties} and a maximum duration of {max_duration_infeasible_duties}.")
    print(
        f"The average deadhead duration for an infeasible duty is {avg_deadhead_duration} seconds - so {avg_deadhead_duration / 3600} hours.")
    print(f"ATTENTION: for {shortest_path_not_found} deadheads the shortest path was not found.")
    print(f"In {number_travel_time_exceeded} cases the total travel time would be more than 12 hours.")
    print(f"For those that exceed the travel time, the average duration is {avg_travel_time_exceeded} minutes - so {avg_travel_time_exceeded/60} hours.")
