import copy
import math
import time
import random
import heapq
from collections import defaultdict
from CrewSchedule import CrewSchedule
from CrewDuty import CrewDuty
from GraphBuilder import *
from VisualizationTools import *
from NeighborhoodOperators import *
from DynamicProgramming_GraphSolver import *
from TimeFormat import *
from ModelBuilder import WindowBasedModel_GUROBI, WindowBasedModel_GUROBI_ComplicatedBreaks

RANDOM_SEED = 999

def calculateInitialSolution(original_schedule, driver_status, input_open_tasks, disruption_start, disruption_end, max_duty_length, id_mapping, suitable_tasks):
    open_tasks = copy.deepcopy(input_open_tasks)
    #in Twans solution there are tasks that are part of more than one duty so we introduce the available_tasks
    available_tasks = copy.deepcopy(input_open_tasks)
    #define some greedy function here to generate a first feasible schedule to recover from the disruption
    existing_duties = {}

    print("******************************************************************")
    print(f"There are {len(open_tasks)} many open tasks at the beginning of calculating the initial solution")
    #for duty_id, st in suitable_tasks.items():
    #    print(f"Duty {duty_id} could potentially cover {len(set(st)&set(open_tasks))} tasks")

    #for duty_id, st in suitable_tasks.items():
    #    print(f"Duty {duty_id} cannot cover the following tasks {set(open_tasks)-set(st)}")
    #for duty_id, st in suitable_tasks.items():
    #    print(f"Duty {duty_id} cannot cover {len(set(open_tasks) - set(st))} tasks")

    #try to assign as many tasks possible to existing duties
    for driver_id, driver_duty in driver_status.items():
        feasible_task_found = True
        while feasible_task_found:
            #define the feasible tasks to assign to a current driver
            feasible_tasks = {}
            previously_assigned_tasks = {}
            if driver_id not in existing_duties.keys():
                #for task_id, task in open_tasks.items():
                #this is an experiment - if it doesn't work replace by open_tasks again
                for task_id, task in available_tasks.items():
                    #calculate the actual new duty length if the task would be added
                    if driver_duty["duty_length"] > 0:
                        new_duty_length = task["arrival"] - driver_duty["available_at_time"] + driver_duty["duty_length"]
                    #the duty has not started yet, therefore the duty length is 0
                    else:
                        new_duty_length = task["arrival"] - task["departure"]
                    #check if the task would be feasible
                    if task["origin"] == driver_duty["available_from_station"] and task["departure"] >= driver_duty["available_at_time"] and new_duty_length < max_duty_length and task_id in suitable_tasks[driver_id]:
                        feasible_tasks[task_id] = copy.deepcopy(task)
            else:
                #for task_id, task in open_tasks.items():
                #this is an experiment - if it does not work replace by open_tasks again
                for task_id, task in available_tasks.items():
                    #calculate the actual new duty length if the task would be added
                    if driver_duty["duty_length"] > 0:
                        new_duty_length = task["arrival"] - driver_duty["available_at_time"] + driver_duty["duty_length"]
                    # the duty has not started yet, therefore the duty length is 0
                    else:
                        new_duty_length = task["arrival"] - existing_duties[driver_id][0]["departure"]
                    # check if the task would be feasible
                    if task["origin"] == existing_duties[driver_id][-1]["destination"] and task["departure"] >= existing_duties[driver_id][-1]["arrival"] and new_duty_length < max_duty_length and task_id in suitable_tasks[driver_id]:
                        feasible_tasks[task_id] = copy.deepcopy(task)
            if len(feasible_tasks.keys()) > 0:
                previously_assigned_tasks = {}
                #if we find a task among the feasible tasks, that was assigned to the driver in the original schedule, we add it to a list
                for ta_id, ta in feasible_tasks.items():
                    if ta_id in [t["id"] for t in original_schedule[driver_id]]:
                        previously_assigned_tasks[ta_id] = copy.deepcopy(ta)
                # if we find a task among the feasible tasks, that was assigned to the driver in the original schedule, we choose the one with earliest departure
                if len(previously_assigned_tasks.keys()) > 0:
                    min_departure_id = min(previously_assigned_tasks, key=lambda k: previously_assigned_tasks[k]["departure"])
                    #print(f"I found task {min_departure_id} that was assigned to the duty in the original plan already.")
                #if among the feasible tasks no task was assigned to the driver in the original schedule, we choose the earliest feasible, however, it will be a deviation from the original
                else:
                    min_departure_id = min(feasible_tasks, key=lambda k: feasible_tasks[k]["departure"])

                if driver_id not in existing_duties.keys():
                    #existing_duties[driver_id] = [copy.deepcopy(open_tasks[min_departure_id])]
                    #this is an experiment - if it does not work replace by open_tasks again
                    existing_duties[driver_id] = [copy.deepcopy(available_tasks[min_departure_id])]
                    if min_departure_id in open_tasks:
                        open_tasks.pop(min_departure_id)
                else:
                    duty_task_list = copy.deepcopy(existing_duties[driver_id])
                    #duty_task_list.append(copy.deepcopy(open_tasks[min_departure_id]))
                    #this is an experiment - if it does not work , replace by open_tasks again
                    duty_task_list.append(copy.deepcopy(available_tasks[min_departure_id]))
                    existing_duties[driver_id] = duty_task_list
                    if min_departure_id in open_tasks:
                        open_tasks.pop(min_departure_id)
            else:
                feasible_task_found = False


    ################################################################
    spare_duty_id_list = []
    #experiment
    #try here to duplicate a fixed ratio of the duties to create spare drivers
    #this would for example duplicate 10% of the duties randomly
    spare_driver_fraction = 0.0
    max_duty_id = max(existing_duties.keys()) + 1

    spare_duty_ids = max_duty_id
    extracted_duties = list(existing_duties.values())
    k = int(len(extracted_duties) * spare_driver_fraction)

    duplicated_duties = random.sample(extracted_duties, k)

    for i in range(len(duplicated_duties)):
        existing_duties[spare_duty_ids] = copy.deepcopy(duplicated_duties[i])
        #here we assume that spare drivers can drive all tasks
        suitable_tasks[spare_duty_ids] = copy.deepcopy(input_open_tasks)
        spare_duty_id_list.append(spare_duty_ids)
        spare_duty_ids += 1

    ################################################################

    #here I decide on the breaks:
    duty_breaks = {}
    #in general a break needs to be 30 minutes if the break is at most 8 hours and 45 if more than 8 hours
    for duty_id, duty in existing_duties.items():
        #this means the duty has already existed
        if duty_id < max_duty_id:
            duty_length = duty[-1]["arrival"] - duty[0]["departure"]
            break_30_done = driver_status[duty_id]["break30done"]
            break_45_done = driver_status[duty_id]["break45done"]
        #this means it is a spare duty and therefore no break has been performed yet
        else:
            break_30_done = False
            break_45_done = False
        #decide which break length is required based on the performed break and new duty length:
        #might either be: no break required, or 15 min, 30min or 45 min
        required_break_length = None
        if (break_30_done and duty_length <= 480) or break_45_done:
            required_break_length = 0
        elif break_30_done and duty_length > 480:
            required_break_length = 15
        elif break_30_done == False and break_45_done == False and duty_length <= 480:
            required_break_length = 30
        elif break_30_done == False and break_45_done == False and duty_length > 480:
            required_break_length = 45

        if required_break_length > 0:
            break_planned = False
            #iterate over pairs of tasks and check if there is the necessary gap available
            for i in range(len(duty) - 1):
                task_A = duty[i]
                task_B = duty[i + 1]

                if task_A["arrival"] >= math.floor(duty_length/4) and task_B["departure"] - task_A["arrival"] >= required_break_length:
                    duty_breaks[duty_id] = (task_A["arrival"], task_A["arrival"]+required_break_length)
                    break_planned = True
                    break

            if break_planned == False:
                #if putting it after the first quarter at the beginning of the idle time did not work
                #then try to put it at the end of the idle time
                # iterate over pairs of tasks and check if there is the necessary gap available
                for i in range(len(duty) - 1):
                    task_A = duty[i]
                    task_B = duty[i + 1]

                    if task_B["departure"] - task_A["arrival"] >= required_break_length:
                        duty_breaks[duty_id] = (task_B["departure"]-required_break_length, task_B["departure"])
                        break_planned = True
                        break

            #if this still did not work put None
            if break_planned == False:
                duty_breaks[duty_id] = None
        #No break is required in the replanning period so we can treat it as it was already performed very early
        else:
            duty_breaks[duty_id] = (-45,0)

    #print(duty_breaks)

    uncovered_tasks = []
    for task in open_tasks.values():
        uncovered_tasks.append(task)

    #this part is removed
    #instead of creating new duties we simply assume that all tasks that cannot be assigned to an existing driver are uncovered
    '''   
    duty_index = max(driver_status.keys()) + 1  # generate a new duty index for new crew members
    new_duties = {}
    if len(open_tasks.keys()) > 0:
        initial_task_key = min(open_tasks, key=lambda k: open_tasks[k]["departure"])
        new_duties[duty_index] = [copy.deepcopy(open_tasks[initial_task_key])]
        open_tasks.pop(initial_task_key)

    while len(open_tasks.keys()) > 0:
        feasible_tasks = {}
        for task_id, task in open_tasks.items():
            if task["origin"] == new_duties[duty_index][-1]["destination"] and task["departure"] >= new_duties[duty_index][-1][
                "arrival"] and (task["arrival"] - new_duties[duty_index][0]["departure"]) < max_duty_length:
                feasible_tasks[task_id] = copy.deepcopy(task)
        if len(feasible_tasks.keys()) > 0:
            min_departure_id = min(feasible_tasks, key=lambda k: feasible_tasks[k]["departure"])
            duty_task_list = copy.deepcopy(new_duties[duty_index])
            duty_task_list.append(copy.deepcopy(open_tasks[min_departure_id]))
            new_duties[duty_index] = duty_task_list
            open_tasks.pop(min_departure_id)
        # no more feasible task was found for the current duty -> start a new duty
        else:
            duty_index += 1
            # initial_task_key = min(open_tasks.keys())
            initial_task_key = min(open_tasks, key=lambda k: open_tasks[k]["departure"])
            new_duties[duty_index] = [copy.deepcopy(open_tasks[initial_task_key])]
            open_tasks.pop(initial_task_key)
    '''
    #print("The existing duties are the following:")
    #for driver_id, duty in existing_duties.items():
    #    print(f"Driver {driver_id}: {duty}")
    #print("")
    '''
    print("The new duties are the following:")
    for driver_id, duty in new_duties.items():
        print(f"Driver {driver_id}: {duty}")
    '''
    #here I want to see the new schedule
    #this should help to analyze what is happening
    locomotives = {task['locomotive'] for task in id_mapping.values()}
    sorted_rescheduled = dict(sorted(existing_duties.items(), key=lambda item: item[1][0]["departure"]))
    #plot_gantt_chart_locomotives("Rescheduled_Solution", sorted_rescheduled, locomotives, id_mapping)
    return existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, spare_duty_id_list

def calcDifferenceToOriginalSchedule(original_schedule, new_schedule,  open_tasks):
    different_task_penalty = 0
    for driver_id, driver_duty in original_schedule.items():
        if driver_id in new_schedule.keys():
            for task_id, task in open_tasks.items():
                if (task["id"] in [t["id"] for t in original_schedule[driver_id]] and task["id"] not in [t["id"] for t in new_schedule[driver_id]]) or (task["id"] not in [t["id"] for t in original_schedule[driver_id]] and task["id"] in [t["id"] for t in new_schedule[driver_id]]):
                    different_task_penalty += 1
                    print(f"The task {task_id} was changed from driver {driver_id}")
    return different_task_penalty

def calcDifferenceToOriginalSchedule_ScheduleClass(original_schedule, new_schedule,  open_tasks):
    different_task_penalty = 0
    penalty_per_duty = {}
    for driver_id, driver_duty in original_schedule.items():
        if driver_id in new_schedule.crew_duties.keys():
            for task_id, task in open_tasks.items():
                if (task["id"] in [t["id"] for t in original_schedule[driver_id]] and task["id"] not in [t["id"] for t in new_schedule.crew_duties[driver_id].tasks]) or (task["id"] not in [t["id"] for t in original_schedule[driver_id]] and task["id"] in [t["id"] for t in new_schedule.crew_duties[driver_id].tasks]):
                    different_task_penalty += 1
                    if driver_id in penalty_per_duty.keys():
                        penalty_per_duty[driver_id] = penalty_per_duty[driver_id] + 1
                    else:
                        penalty_per_duty[driver_id] = 1
                    #print(f"The task {task_id} was changed from driver {driver_id}")

    return different_task_penalty, penalty_per_duty

def dijkstra(graph, start):
    """
    Run Dijkstra from a single source.
    graph: dict[node] -> list of (neighbor, weight)
    start: starting node
    Returns: dict[node] = distance from start
    """
    dist = defaultdict(lambda: float("inf"))
    dist[start] = 0
    pq = [(0, start)]  # (distance, node)

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in graph[u]:
            if dist[v] > d + w:
                dist[v] = d + w
                heapq.heappush(pq, (dist[v], v))

    return dist

def compute_shortest_path_matrix_dijkstra(stations, sections, station_list, directed=False):
    # Build adjacency list
    graph = defaultdict(list)
    for sec in sections.values():
        o, d, w = sec["origin"], sec["destination"], sec["distance"]
        graph[o].append((d, w))
        if not directed:
            graph[d].append((o, w))

    # Compute all-pairs shortest paths using Dijkstra
    shortest_path = {dest: {} for dest in station_list}

    for origin in station_list:
        dist = dijkstra(graph, origin)
        for dest in station_list:
            #we want it in meters
            shortest_path[dest][origin] = int(round(dist[dest]*1000,0))

    return shortest_path

def check_model_solution(model_node_paths, graph, duty_categories):
    flag = True
    for k, path in model_node_paths.items():
        #print(f"These are the nodes of the current paths for duty {k}")
        #for node in path:
            #print(f"node_id: {graph.graph_nodes[node].node_id} | node_type: {graph.graph_nodes[node].node_type}")
        if len(path) > 0:
            first_task_departure = graph.graph_nodes[path[0]].node_task["departure"]
            last_task_arrival = graph.graph_nodes[path[-1]].node_task["arrival"]
            if last_task_arrival-first_task_departure > 720:
                print(f"Duty {k} is of type {duty_categories[k]}")
                print(f"Duty {k} is infeasible becuase its duration is {last_task_arrival-first_task_departure}")
                flag = False

def printInstanceCharacteristics(method, original_schedule, initial_solution, duty_breaks, uncovered_tasks, all_tasks, maxTime, maxIter, id_mapping, disruption_start, disruption_end, window_size, runs_per_window, network_data, locomotives, suitable_tasks, max_dh_duration, rand_iter, spare_duty_ids):
    schedule_figures = []
    #####
    # here we have to calculate the shortest path matrix between all involved stations once:
    involved_stations = []
    for task_id, task in all_tasks.items():
        if task["origin"] not in involved_stations:
            involved_stations.append(task["origin"])
        if task["destination"] not in involved_stations:
            involved_stations.append(task["destination"])

    # shortest_path_matrix = []
    shortest_path_matrix = compute_shortest_path_matrix_dijkstra(network_data["stations"], network_data["sections"],
                                                                 involved_stations)
    # for origin in shortest_path_matrix.keys():
    #    for destination in shortest_path_matrix[origin].keys():
    #        print(f"Shortest path from {origin} to {destination} is {shortest_path_matrix[origin][destination]}")
    print("******************* Shortest path was computed successfully **************************")
    ###

    initial_schedule = CrewSchedule(all_tasks, initial_solution, duty_breaks, uncovered_tasks, shortest_path_matrix,
                                    id_mapping, locomotives)
    schedule_figures = initial_schedule.visualizeSchedule(schedule_figures)

    # print("This was successful")
    # initial_schedule.display_schedule()
    # define the VNS here including the neighborhood operations

    objective_value, penalty_per_duty = calcDifferenceToOriginalSchedule_ScheduleClass(original_schedule,
                                                                                       initial_schedule, all_tasks)

    incumbent_schedule = CrewSchedule(all_tasks, initial_solution, duty_breaks, uncovered_tasks, shortest_path_matrix,
                                      id_mapping, locomotives)
    time_windows = [(i, i + window_size) for i in range(disruption_start, 10080, window_size)]

    nodes, arcs, duty_start_end_nodes, break_required_in_window = buildGraph_shortestPath(incumbent_schedule,
                                                                                          time_windows[0],
                                                                                          shortest_path_matrix,
                                                                                          max_dh_duration, spare_duty_ids)
    nr_open_tasks = len(all_tasks)
    disruption_duration = disruption_end - disruption_start
    remaining_horizon = 10080 - disruption_start

    original_number_duties = len(original_schedule.keys())
    rescheduling_number_duties = len(initial_schedule.crew_duties.keys())

    durations = [
        task["arrival"] - task["departure"]
        for task in all_tasks.values()
    ]

    min_duration = min(durations)
    max_duration = max(durations)
    avg_duration = sum(durations) / len(durations)

    #compute the total km for all tasks in the rescheduling
    distances = [
        shortest_path_matrix[task["origin"]][task["destination"]]
        for task in all_tasks.values()
    ]
    total_distance_km = sum(distances)/1000

    #count the old and new tasks
    nr_old_tasks = 0
    nr_new_tasks = 0
    for task_id, task in all_tasks.items():
        task_counted = False
        for duty_id, duty in original_schedule.items():
            ids = [task["id"] for task in duty]
            if task_id in ids and task_counted == False:
                nr_old_tasks += 1
                task_counted = True
        if task_counted == False:
            nr_new_tasks += 1

    print(f"There are {nr_open_tasks} open tasks to be rescheduled, the disruption lasts {disruption_duration} minutes and the remaining horizon is {remaining_horizon} minutes. There are {original_number_duties} duties in the original schedule and {rescheduling_number_duties} duties considered for rescheduling")
    print(f"The minimum task length is {min_duration} minutes, maximum task length is {max_duration} and average task length is {avg_duration} minutes.")
    print(f"The total distance for all tasks is {total_distance_km} km")
    print(f"Out of the {nr_open_tasks} there are {nr_old_tasks} old tasks and {nr_new_tasks} new tasks.")
    print(f"The instance considers tasks between {len(involved_stations)} stations")
    print("###############################################################################")


def run_VNS(method, original_schedule, initial_solution, duty_breaks, uncovered_tasks, all_tasks, maxTime, maxIter, id_mapping, disruption_start, disruption_end, window_size, runs_per_window, network_data, locomotives, suitable_tasks, max_dh_duration, rand_iter, spare_driver_ids):
    schedule_figures = []
    #####
    #here we have to calculate the shortest path matrix between all involved stations once:
    involved_stations = []
    for task_id, task in all_tasks.items():
        if task["origin"] not in involved_stations:
            involved_stations.append(task["origin"])
        if task["destination"] not in involved_stations:
            involved_stations.append(task["destination"])

    #shortest_path_matrix = []
    shortest_path_matrix = compute_shortest_path_matrix_dijkstra(network_data["stations"], network_data["sections"], involved_stations)
    #for origin in shortest_path_matrix.keys():
    #    for destination in shortest_path_matrix[origin].keys():
    #        print(f"Shortest path from {origin} to {destination} is {shortest_path_matrix[origin][destination]}")
    print("******************* Shortest path was computed successfully **************************")
    ###

    initial_schedule = CrewSchedule(all_tasks, initial_solution, duty_breaks, uncovered_tasks, shortest_path_matrix, id_mapping, locomotives)
    schedule_figures = initial_schedule.visualizeSchedule(schedule_figures)

    #print("This was successful")
    #initial_schedule.display_schedule()
    #define the VNS here including the neighborhood operations

    objective_value, penalty_per_duty = calcDifferenceToOriginalSchedule_ScheduleClass(original_schedule, initial_schedule, all_tasks)

    incumbent_schedule = CrewSchedule(all_tasks, initial_solution, duty_breaks, uncovered_tasks, shortest_path_matrix, id_mapping, locomotives)
    best_schedule = CrewSchedule(all_tasks, initial_solution, duty_breaks, uncovered_tasks, shortest_path_matrix, id_mapping, locomotives)

    (nr_deadheads, deadheading_costs, nr_uncovered_tasks, nr_breaks_violated, nr_spared_drivers) = incumbent_schedule.evaluteScheduleObjective()
    print(f"Initially the deadheading costs are {deadheading_costs}, while there are {nr_uncovered_tasks} uncovered tasks and {nr_breaks_violated} violated breaks, we could spare {nr_spared_drivers} drivers and there are {nr_deadheads} deadheads")
    incumbent_schedule.analyze_schedule()
    ################################################
    total_start_time = time.time()

    #in this way we get the sequential window approach
    time_windows = [(i, i + window_size) for i in range(disruption_start, 10080, window_size)]
    print(f"These are the considered time windows: {time_windows}")

    #with overlaps - the idea is to shift the window only half the window size and therefore get overlapping windows
    #overlap_time_windows = [(i, i + window_size) for i in range(disruption_start, 10080, round(window_size*0.5))]

    #random.seed(42)
    #the idea is to get the same time windows, but in a different order
    #shuffled_time_windows = random.sample(time_windows, len(time_windows))

    '''
    #in this way we generate random windows
    random.seed(999)
    total_duration = 10080 - disruption_start
    num_windows = math.ceil(total_duration / window_size)

    latest_start = 10080 - window_size
    time_windows = [
        (random.randint(disruption_start, latest_start), 0)  # placeholder for now
        for _ in range(num_windows)
    ]
    # Replace end times
    time_windows = [(start, start + window_size) for start, _ in time_windows]
    '''

    step_results = []

    #time_windows = [(disruption_start, disruption_start+300), (disruption_start+600, disruption_start+900), (disruption_start+1200, disruption_start+1500), (disruption_start+1800, disruption_start+2100)]
    #window_counter = 1
    for time_window in time_windows:
        #print(f"Window start: {time_window[0]}")
        #print(f"For this run this is the {window_counter} run!")
        #print(f"The current time window is: {time_window}")
        #time_window = (2500, 2800)
        start_time = time.time()
        nodes, arcs, duty_start_end_nodes, break_required_in_window = buildGraph_shortestPath(incumbent_schedule, time_window, shortest_path_matrix, max_dh_duration, spare_driver_ids)
        end_time = time.time()
        #print(f"Building the graph in this iteration took {end_time-start_time} seconds")
        #print(f"There are {len(nodes)} nodes in the graph.")
        original_number_nodes = len(nodes)
        testGraph = Graph(copy.deepcopy(nodes), copy.deepcopy(arcs), copy.deepcopy(duty_start_end_nodes))
        #print(f"This is the uncovered task of node 0: {testGraph.graph_nodes[0].node_task} and it is currently assigned to duty {testGraph.graph_nodes[0].duty_id}")
        #for node_id, node in testGraph.graph_nodes.items():
        #    if node.node_task != None:
        #        if node.node_task["id"] == 292:
        #            print(f"This is the previous node 0 {node.node_task} and now it is assigned to duty {node.duty_id}")
        #if time_window[0] == 8593:
        #testGraph.displayGraph()

        ################################################

        #these will be required for choosing only feasible routes
        duty_original_starttimes = getDutyStarttimes(incumbent_schedule)
        duty_original_endtimes = getDutyEndtimes(incumbent_schedule)
        duty_original_homebases = getDutyHomeBases(incumbent_schedule)
        duty_original_endbases = getDutyEndBases(incumbent_schedule)
        duty_categories = categorizeDuties(incumbent_schedule, time_window)

        window_results = {}

        #this parameter is now handed to the function (1, 5, 10)
        #runs_per_window = 5

        #test dynamic programming
        start_time = time.time()

        if method == "model":
            #from here on I have the updated call for the optimization model from the JKU Laptop:
            ###
            # try here to solve the CPLEX model
            gurobi_model = WindowBasedModel_GUROBI_ComplicatedBreaks(testGraph, duty_categories, break_required_in_window,
                                                  duty_original_starttimes, duty_original_endtimes, time_window, suitable_tasks)
            gurobi_model.build_model()
            model_sol_x, model_sol_alpha, model_sol_beta = gurobi_model.solve_model()

            # print the gurobi solution here:
            # print(f"Optimal solution found by gurobi for time window {time_window}")
            sum_alpha = 0
            for i in model_sol_alpha.keys():
                if model_sol_alpha[i] > 0:
                    sum_alpha += model_sol_alpha[i]
            gurobi_covered_nodes = set()
            # print(f"There are {sum_alpha} uncovered tasks in this CPLEX solution")
            cplex_node_paths = {}
            sorted_cleaned_cplex_node_paths = {}
            print(f"These are the keys for the cplex solution in this window: {model_sol_x.keys()}")
            for k in model_sol_x.keys():
                arcs_k = []
                path_k = []
                cplex_node_path_k = []
                for a in model_sol_x[k].keys():
                    if model_sol_x[k][a] == 1:
                        arcs_k.append(a)
                        ###
                        # keep track which tasks are covered by the model
                        gurobi_covered_nodes.add(testGraph.graph_nodes[testGraph.graph_arcs[a].start_node].node_id)
                        gurobi_covered_nodes.add(testGraph.graph_nodes[testGraph.graph_arcs[a].end_node].node_id)
                        ###

                        if testGraph.graph_arcs[a].arc_type == 3:
                            cplex_node_path_k.append(testGraph.graph_arcs[a].start_node)
                            cplex_node_path_k.append(testGraph.graph_arcs[a].end_node)
                        else:
                            cplex_node_path_k.append(testGraph.graph_arcs[a].end_node)

                        if testGraph.graph_nodes[testGraph.graph_arcs[a].end_node].node_task != None:
                            path_k.append(testGraph.graph_nodes[testGraph.graph_arcs[a].end_node].node_task)

                sorted_path_k = sorted(path_k, key=lambda x: x['departure'])

                cplex_node_paths[k] = cplex_node_path_k

                cleaned_cplex_node_path_k = []
                for node in cplex_node_path_k:
                    if testGraph.graph_nodes[node].node_task != None and node not in cleaned_cplex_node_path_k:
                        cleaned_cplex_node_path_k.append(node)
                sorted_cleaned_cplex_node_path_k = sorted(cleaned_cplex_node_path_k,
                                                          key=lambda x: testGraph.graph_nodes[x].node_task['departure'])

                sorted_cleaned_cplex_node_paths[k] = sorted_cleaned_cplex_node_path_k

                flag_model = check_model_solution(sorted_cleaned_cplex_node_paths, testGraph, duty_categories)

                if flag_model == False:
                    print("in this model there was an error!")

                # print(f"Duty {k}: {sorted_path_k}")
                # print(f"The start node for duty {k} is {duty_start_end_nodes[k][0]} and the end node is {duty_start_end_nodes[k][1]}")
                # for a in arcs_k:
                # print(f"{testGraph.graph_arcs[a].arc_id} | start node {testGraph.graph_arcs[a].start_node} | end node {testGraph.graph_arcs[a].end_node}")

            # print(f"In total the Gurobi model has covered {len(gurobi_covered_nodes)} tasks.")
            # print(f"These covered tasks are the following: {gurobi_covered_nodes}")

            incumbent_schedule.updateScheduleFromWindow(sorted_cleaned_cplex_node_paths, time_window, nodes)
            schedule_figures = incumbent_schedule.visualizeSchedule(schedule_figures)
            # these will be required for choosing only feasible routes

            # print("Updating the incumbent schedule was successful")
            (nr_deadheads, deadheading_costs, nr_uncovered_tasks, nr_breaks_violated, nr_spared_drivers) = incumbent_schedule.evaluteScheduleObjective()
            print(f"Window start: {time_window[0]} | uncovered tasks: {nr_uncovered_tasks}")
            # print(f"After updating the incumbent the deadheading costs are {deadheading_costs}, while there are {nr_uncovered_tasks} uncovered tasks (out of {len(all_tasks)} tasks) and {nr_breaks_violated} violated breaks, we could spare {nr_spared_drivers} drivers")
            # window_counter += 1

        elif method == "DP":
            ###
            for i in range(runs_per_window):
                #this is to make sure that the first orderings are included when more iterations are performed. It should never get worse with more iterations
                #the seed is a composite of a fixed global value, the start of the time window and the iteration of the window
                random.seed(rand_iter*RANDOM_SEED + time_window[0] + i)
                #this is quite important here -> if the seed is not set like this it could happen that an id ordering is not included in a run with more iterations which could lead to a worse result

                overall_cost = 0
                covered_nodes = set()
                paths = {}

                ########################################
                # try this random shuffle of the duty ids
                keys = list(duty_start_end_nodes.keys())
                random.shuffle(keys)  # In-place shuffle
                ########################################

                ########################################
                #this is an experiment on taking a subset of duties within the DP method to improve the runtime
                p = 0.5  # choose 50% of the keys
                subset_size = int(len(keys) * p)

                subset = random.sample(keys, subset_size)
                ########################################

                #with this loop we only take the subset
                #for duty_id in subset:
                #with the upper for loop we shuffle the order of the duty ids
                for duty_id in keys:
                #this is an older version
                #for duty_id in duty_start_end_nodes.keys():
                    duty_category = duty_categories[duty_id]
                    #do one iteration for every duty
                    #this then turns DP into a heuristic because the sequence of duties matters
                    #here we could try different sequences
                    source_id = duty_start_end_nodes[duty_id][0]
                    sink_id = duty_start_end_nodes[duty_id][1]

                    cost, path = DP_SingleDuty(duty_id, testGraph, source_id, sink_id, duty_category, duty_original_starttimes, duty_original_endtimes, duty_original_homebases, duty_original_endbases, covered_nodes, shortest_path_matrix, suitable_tasks)
                    paths[duty_id] = path
                    #print(f"For duty {duty_id} the following path is chosen {path} with a cost of {cost}.")
                    overall_cost += cost
                    for node in path:
                        #covered nodes should only be updated as covered if there is a driver that can actually drive the train, not just as passenger
                        if testGraph.graph_nodes[node].node_task != None:
                            if testGraph.graph_nodes[node].node_task["id"] in suitable_tasks[duty_id]:
                                covered_nodes.add(node)

                    #TODO: discuss if we should keep or remove nodes and arcs that have been used
                    #this prevents that drivers can take another train as a passenger
                    #remove_Used_Nodes_and_Arcs(testGraph, path)

                end_time = time.time()
                #print(f"Solving the DP for the whole window in this iteration took {end_time - start_time} seconds")
                #print(f"The overall cost for the full graph is {overall_cost}")
                #print(f"In total there were {len(covered_nodes)} nodes selected")
                #print(f"There are {original_number_nodes - len(covered_nodes)} uncovered tasks in this time window.")

                window_results[i] = (overall_cost, copy.deepcopy(paths))

            #find the best overall solution of the repeated runs for the window
            min_costs = float('inf')
            best_paths = None
            for window_result in window_results.values():
                #print(f"The costs in this iteration are: {window_result[0]}")
                #print(f"In this iteration {window_result[2]} are covered")
                if window_result[0] <= min_costs:
                    min_costs = copy.deepcopy(window_result[0])
                    best_paths = copy.deepcopy(window_result[1])

            #print("This is the result of the dynamic programming heuristic - compare this to the GUROBI model")
            #print(best_paths)

            '''
            ########################
            # find out the number of uncovered nodes in the time window for the dynamic programming approach
            window_covered_nodes = set()
            for path_id, path in best_paths.items():
                for node in path:
                    window_covered_nodes.add(node)
            print(f"In total there were {len(window_covered_nodes)} nodes selected by the DP heuristic")
            print(f"These covered tasks are the following: {window_covered_nodes}")
            print(f"There are {original_number_nodes - len(window_covered_nodes)} uncovered tasks in this time window for the DP heuristic.")
            ########################
            '''

            step_results.append((time_window[0], nr_uncovered_tasks))

            #for duty_id, path in best_paths.items():
            #    print(f"duty: {duty_id}")
            #    print(nodes[path[0]].node_task)
            #    print(nodes[path[-1]].node_task)
            incumbent_schedule.updateScheduleFromWindow(best_paths, time_window, nodes)
            schedule_figures = incumbent_schedule.visualizeSchedule(schedule_figures)
            #incumbent_schedule.updateScheduleFromWindow(sorted_cleaned_cplex_node_paths, time_window, nodes)

            # these will be required for choosing only feasible routes

            #print("Updating the incumbent schedule was successful")
            (nr_deadheads, deadheading_costs, nr_uncovered_tasks, nr_breaks_violated, nr_spared_drivers) = incumbent_schedule.evaluteScheduleObjective()
            print(f"Window start: {time_window[0]} | uncovered tasks: {nr_uncovered_tasks}")
            #print(f"After updating the incumbent the deadheading costs are {deadheading_costs}, while there are {nr_uncovered_tasks} uncovered tasks (out of {len(all_tasks)} tasks) and {nr_breaks_violated} violated breaks, we could spare {nr_spared_drivers} drivers")
            #window_counter += 1

        else:
            raise ValueError("Provide a suitable method, either DP or model.")

    print(
        f"After performing the window rescheduling the deadheading costs are {deadheading_costs}, while there are {nr_uncovered_tasks} uncovered tasks (out of {len(all_tasks)} tasks) and {nr_breaks_violated} violated breaks, we could spare {nr_spared_drivers} drivers and there are {nr_deadheads} deadheads")
    #print(f"The disruption is from {disruption_start} to {disruption_end}")
    #print(f"The uncovered tasks are the following:")

    total_end_time = time.time()
    print(f"The total process took {total_end_time-total_start_time} seconds.")

    #for uc in incumbent_schedule.uncovered_tasks:
    #    print(uc)
    incumbent_schedule.analyze_schedule()

    print("################################")
    print("Before making the schedule break feasible")
    (nr_deadheads, deadheading_costs, nr_uncovered_tasks, nr_breaks_violated,
     nr_spared_drivers) = incumbent_schedule.evaluteScheduleObjective()
    print(
        f"After performing the window rescheduling the deadheading costs are {deadheading_costs}, while there are {nr_uncovered_tasks} uncovered tasks (out of {len(all_tasks)} tasks) and {nr_breaks_violated} violated breaks, we could spare {nr_spared_drivers} drivers and there are {nr_deadheads} deadheads")
    print("After making the schedule break feasible")
    incumbent_schedule.makeScheduleBreakFeasible()
    (nr_deadheads, deadheading_costs, nr_uncovered_tasks, nr_breaks_violated,
     nr_spared_drivers) = incumbent_schedule.evaluteScheduleObjective()
    print(
        f"After performing the window rescheduling the deadheading costs are {deadheading_costs}, while there are {nr_uncovered_tasks} uncovered tasks (out of {len(all_tasks)} tasks) and {nr_breaks_violated} violated breaks, we could spare {nr_spared_drivers} drivers and there are {nr_deadheads} deadheads")
    print("################################")

    #######################################
    #this is to evaluate the final schedule regarding the length of the duties
    bins = {
        "0-360": 0,
        "361-480": 0,
        "481-600": 0,
        "601-720": 0,
    }

    print(f"There are {len(incumbent_schedule.crew_duties.values())} duties in the schedule")
    for duty in incumbent_schedule.crew_duties.values():
        start = duty.tasks[0]["departure"]
        end = duty.tasks[-1]["arrival"]
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
    ######################################################################

    #print("The final schedule is the following")
    #incumbent_schedule.display_schedule()
        ###############################################

    return step_results, schedule_figures