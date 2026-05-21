from collections import Counter
from collections import defaultdict
import csv
import copy

def removeEmptySections(networkData, instanceData):
    for train_section_id, train_section in instanceData['train_sections'].items():
        section_id = train_section['section']
        if section_id in networkData['sections'].keys():
            continue
        else:
            section = train_section["section"]
            print(str(train_section_id)+"\t"+str(section))

def combineCrewTasksByReliefPoints(crew_scheduling_instance, id_mapping, relief_points):
    duties = {}  # this will represent the greedy solution
    tasks = {}
    combined_tasks = {}
    count_combined_tasks = 0
    infeasible_tasks = []
    with open(crew_scheduling_instance, "r") as file:
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

    total_task_duration = 0
    max_total_duration = 0
    number_tasks = len(tasks.keys())
    for task in tasks.values():
        total_task_duration += task["arrival"] - task["departure"]
        if (task["arrival"] - task["departure"]) > max_total_duration:
            max_total_duration = task["arrival"] - task["departure"]
    avg_task_duration = total_task_duration / number_tasks
    print(
        f"Before combining the tasks the average duration of a task is {avg_task_duration} minutes, which is {avg_task_duration / 60} hours.")
    print(f"Before combining the tasks the maximum duration of a task is {max_total_duration} minutes, which is {max_total_duration / 60} hours.")

    print(f"Initially we consider {len(relief_points)} relief points!")
    #add the last stop of a locomotive to the list of relief points because it does not make sense for a locomotive to go somewhere, where there is no option to exchange drivers
    for task_id, task in tasks.items():
        if task_id+1 in id_mapping.keys():
            if id_mapping[task_id]["locomotive"] != id_mapping[task_id+1]["locomotive"]:
                relief_points.append(task["destination"])
    #remove_duplicates
    relief_points = list(set(relief_points))
    print(f"Now we consider {len(relief_points)} relief points after adding the last stops of each locomotive")
    print("The new relief points are")
    print(sorted(relief_points))

    task_id = 1
    while len(tasks) > 0:
        task = tasks[task_id]
        locomotive = id_mapping[task_id]['locomotive']
        #this means the driver could change at the next station and we can therefore keep the task as it is
        if task["destination"] in relief_points:
            combined_tasks[task_id] = copy.deepcopy(task)
            tasks.pop(task_id)
            task_id += 1
        #the next station is not a relief point and therefore the driver needs to continue to drive the locomotive
        else:
            additional_task_counter = 1
            # store the information on the task because we need to combine this task with the subsequent task
            initial_origin = task["origin"]
            initial_destination = task["destination"]
            initial_departure = task["departure"]
            initial_arrival = task["arrival"]

            add_new_task = True
            while add_new_task:
                #this means the locomotive continues and there is another destination that is a relief point

                #check if we still have tasks to assign
                if task_id+additional_task_counter in id_mapping.keys():
                    if id_mapping[task_id+additional_task_counter]["locomotive"] == locomotive and tasks[task_id+additional_task_counter]["destination"] in relief_points:
                        combined_tasks[task_id+additional_task_counter] = {"id": task_id,
                        "origin": initial_origin,
                        "destination": tasks[task_id+additional_task_counter]["destination"],
                        "departure": initial_departure,
                        "arrival": tasks[task_id+additional_task_counter]["arrival"]
                        }
                        #delete the tasks that were combined
                        for index in range(task_id,task_id+additional_task_counter+1):
                            tasks.pop(index)
                        task_id += additional_task_counter+1
                        count_combined_tasks += additional_task_counter
                        add_new_task = False
                    elif id_mapping[task_id+additional_task_counter]["locomotive"] == locomotive:
                        additional_task_counter += 1
                    else:
                        #print("The task cannot be combined because there is no relief point after the locomotive has started")
                        for index in range(task_id,task_id+additional_task_counter+1):
                            infeasible_tasks.append(index)
                            tasks.pop(index)
                        add_new_task = False
                        task_id += additional_task_counter+1
                else:
                    add_new_task = False

    total_task_duration = 0
    max_total_duration = 0
    number_tasks = len(combined_tasks.keys())
    for task in combined_tasks.values():
        total_task_duration += task["arrival"] - task["departure"]
        if (task["arrival"] - task["departure"]) > max_total_duration:
            max_total_duration = task["arrival"] - task["departure"]
    avg_task_duration = total_task_duration/number_tasks
    print(f"The average duration of the combined tasks is {avg_task_duration} minutes, which is {avg_task_duration/60} hours.")
    print(f"The maximum duration of a combined task is {max_total_duration}, which is {max_total_duration/60} hours.")

    return combined_tasks, infeasible_tasks, count_combined_tasks


def extractReliefPoints(networkData, instanceData, categoryCountReliefPoints):
    # Analysis of the stations
    list_origins = []
    list_destinations = []
    for train_section_id, train_section in instanceData['train_sections'].items():
        section_id = train_section['section']
        if section_id in networkData['sections'].keys():
            origin = networkData['sections'][section_id]['origin']
            destination = networkData['sections'][section_id]['destination']
            list_origins.append(origin)
            list_destinations.append(destination)
        else:
            section = train_section["section"]
            print(section)

    # Count occurrences of each origin
    counts_origins = Counter(list_origins)
    count_dict_origins = defaultdict(list)
    for number, count in counts_origins.items():
        count_dict_origins[count].append(number)
    result_origins = dict(count_dict_origins)
    # Sort the dictionary by keys from largest to smallest
    sorted_result_origins = {key: result_origins[key] for key in sorted(result_origins.keys(), reverse=True)}
    print(sorted_result_origins)

    # Count occurrences of each origin
    counts_destinations = Counter(list_destinations)
    count_dict_destinations = defaultdict(list)
    for number, count in counts_destinations.items():
        count_dict_destinations[count].append(number)
    result_destinations = dict(count_dict_destinations)
    # Sort the dictionary by keys from largest to smallest
    sorted_result_destinations = {key: result_destinations[key] for key in
                                  sorted(result_destinations.keys(), reverse=True)}
    print(sorted_result_destinations)

    # Get the two highest keys from each dictionary
    top_keys_dict1 = sorted(sorted_result_origins.keys(), reverse=True)[:categoryCountReliefPoints]
    top_keys_dict2 = sorted(sorted_result_destinations.keys(), reverse=True)[:categoryCountReliefPoints]

    # Extract the values from these keys
    top_values_dict1 = [value for key in top_keys_dict1 for value in sorted_result_origins[key]]
    top_values_dict2 = [value for key in top_keys_dict2 for value in sorted_result_destinations[key]]

    # Combine the values and remove duplicates
    result = list(set(top_values_dict1 + top_values_dict2))

    print(result)

    count_origins = sum(len(value) for value in sorted_result_origins.values())
    print(f"There are {count_origins} different origins in this instance")
    count_destinations = sum(len(value) for value in sorted_result_destinations.values())
    print(f"There are {count_destinations} different destinations in this instance")

    # Extract the values from these keys
    total_values_dict1 = [value for key in sorted_result_origins.keys() for value in sorted_result_origins[key]]
    total_values_dict2 = [value for key in sorted_result_destinations.keys() for value in sorted_result_destinations[key]]
    total_stations = list(set(total_values_dict1 + total_values_dict2))
    print(f"In total there are {len(total_stations)} stations used in this instance")

    print(f"For a category count of the highest {categoryCountReliefPoints} groups there are {len(result)} out of {len(total_stations)} relief points, which are {100*len(result)/len(total_stations)} %")

    return result

def combineTripsByReliefPoints(network_data, instance_data, relief_points):
    #this will hold the actual tasks for the crew based on the relief points, with origin, destination and departure arrival time
    train_tasks = {}
    task_id = 0

    train_dict = {}
    for train_id in instance_data['trains'].keys():
        train_sections = []
        for train_section_id, train_section in instance_data['train_sections'].items():
            if train_section["train"] == train_id:
                train_sections.append(train_section)
        train_dict[train_id] = train_sections
    #print(train_dict)

    for train_id in instance_data['trains'].keys():
        #just to make sure they are sorted correctly
        specific_train_sections = sorted(train_dict[train_id], key=lambda x: x["departure_time"])
        #specific_train_sections = train_dict[train_id]
        print()
        print(train_id)
        print()
        print(specific_train_sections)
        print()
        for train_section in specific_train_sections:
            departure = train_section["departure_time"]
            arrival = train_section["arrival_time"]
            section_id = train_section["section"]
            if section_id in network_data['sections'].keys():
                origin = network_data['sections'][section_id]['origin']
                destination = network_data['sections'][section_id]['destination']
                train_tasks[task_id] = {
                    "origin": origin,
                    "destination": destination,
                    "departure_time": departure,
                    "arrival_time": arrival,
                }
                task_id += 1
            else:
                section = train_section["section"]
                print(f"This section was removed {section}!")

    print("These are the tasks for the crew scheduling")
    print(train_tasks)