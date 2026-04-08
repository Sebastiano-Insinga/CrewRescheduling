import copy
from CrewSchedule import CrewSchedule
from CrewDuty import CrewDuty
from VisualizationTools import *
from NeighborhoodOperators import *
import matplotlib.pyplot as plt
import numpy as np

#this function takes a CrewSchedule as an input and returns a dictionary having the duty ID as the key and then
#one of the four duty classes as values:
# 1: continuing duty
# 2: starting duty
# 3: terminating duty
# 4: flexible duty

#5: duty has no overlap with the time window and is therefore not considered
def categorizeDuties(currentSolution, timeWindow):
    window_start = timeWindow[0]
    window_end = timeWindow[1]

    duty_categories = {}

    for duty_id, duty in currentSolution.crew_duties.items():
        duty_start = duty.tasks[0]["arrival"] #we need at least one task to be finished before time window
        duty_end = duty.tasks[-1]["departure"] #we need at least one task departed after end of time window

        duty_category = 0
        if duty_start < window_start and duty_end > window_end:
            duty_category = 1 #continuing duty
        elif duty_start >= window_start and duty_end > window_end:
            duty_category = 2 # starting duty
        elif duty_start < window_start and duty_end <= window_end:
            duty_category = 3 # terminating duty
        elif duty_start >= window_start and duty_end <= window_end:
            duty_category = 4 #flexible duty
        else:
            duty_category = 5 #duty has no overlap with the time window

        #fill the dictionary
        duty_categories[duty_id] = duty_category
    
    return duty_categories

def getDutyHomeBases(currentSolution):
    duty_homebases= {}

    for duty_id, duty in currentSolution.crew_duties.items():
        duty_homebases[duty_id] = duty.tasks[0]["origin"]

    return duty_homebases

def getDutyEndBases(currentSolution):
    duty_endbases = {}

    for duty_id, duty in currentSolution.crew_duties.items():
        duty_endbases[duty_id] = duty.tasks[-1]["destination"]

    return duty_endbases

def getDutyStarttimes(currentSolution):
    duty_original_starttimes = {}

    for duty_id, duty in currentSolution.crew_duties.items():
        duty_original_starttimes[duty_id] = duty.tasks[0]["departure"]

    return duty_original_starttimes

def getDutyEndtimes(currentSolution):
    duty_original_endtimes = {}

    for duty_id, duty in currentSolution.crew_duties.items():
        duty_original_endtimes[duty_id] = duty.tasks[-1]["arrival"]

    return duty_original_endtimes

def getDutyBreaktimes(currentSolution):
    duty_breaktimes = {}

    for duty_id, duty in currentSolution.crew_duties.items():
        if duty.duty_break != None:
            duty_breaktimes[duty_id] = (duty.duty_break[0],duty.duty_break[1])
        else:
            duty_breaktimes[duty_id] = None

    return duty_breaktimes

#there are several node types
# 1: regular task that can be modified
# 2: start node
# 3: dummy start node
# 4: termination node
# 5: dummy termination node

#uncovered tasks have type 1 , since they are regular tasks, however are indicated by duty id -1

#a regular Node will have a task associated with the node. A dummy node will have no task assigned and have None as default
class Graph:
    def __init__(self, graph_nodes, graph_arcs, duty_start_end_nodes):
        self.graph_nodes = graph_nodes
        self.graph_arcs = graph_arcs
        self.duty_start_end_nodes = duty_start_end_nodes

    def displayGraph(self):
        #print("These are the nodes of the graph:")
        #for node_id, node in self.graph_nodes.items():
        #    print(f"Node: {node_id} of duty {node.duty_id} has type {node.node_type} and task {node.node_task}")
        #print("These are the arcs of the graph:")
        #for arc_id, arc in self.graph_arcs.items():
        #    print(f"Arc: {arc_id} has type {arc.arc_type} and connects node {arc.start_node} to node {arc.end_node} with cost {arc.arc_cost}")

        #plot_nodes(self.graph_nodes)
        plot_nodes_and_arcs(self.graph_nodes, self.graph_arcs)

class Node:
    def __init__(self, node_id, duty_id, node_type, node_task = None):
        self.node_id = node_id
        self.duty_id = duty_id
        self.node_type = node_type
        self.node_task = node_task

class Arc:
    def __init__(self, arc_id, arc_type, start_node, end_node, arc_cost, break_30_possible, break_45_possible):
        self.arc_id = arc_id
        self.arc_type = arc_type
        self.start_node = start_node
        self.end_node = end_node
        self.arc_cost = arc_cost
        self.break_30_possible = break_30_possible
        self.break_45_possible = break_45_possible


def buildGraph(currentSolution, timeWindow, shortest_path):
    #we need to assume a speed at which crew members can reach a different station since the distance is given in meters
    crew_deadhead_speed = 100

    uncovered_tasks = []
    for ut in currentSolution.uncovered_tasks:
        uncovered_tasks.append(copy.deepcopy(ut))

    window_start = timeWindow[0]
    window_end = timeWindow[1]

    #this parameter decides by how many minutes the start of a duty can be shifted either earlier or later
    START_SHIFT_WINDOW = 60

    #Here we define the nodes and arcs of the graph in a dictionary
    #this is the set of all nodes, also including (dummy) start and termination nodes
    graphNodes = {}
    #this is the set of all arcs, also including (dummy) start and termination arcs, as well as deadhead arcs
    graphArcs = {}

    #here we just keep track of the respective IDs to know which node/arc is of which type
    startNodes = []
    terminationNodes = []

    dummyStartNodes = []
    dummyTerminationNodes = []

    startArcs = []
    terminationArcs = []
    deadheadArcs = []

    node_counter = 0

    duty_categories = categorizeDuties(currentSolution, timeWindow)
    duty_homebases = getDutyHomeBases(currentSolution)
    duty_original_starttimes = getDutyStarttimes(currentSolution)
    duty_breaktimes = getDutyBreaktimes(currentSolution)

    #the duties that require a break within the window because no break is scheduled outside of the window
    break_required_in_window = []

    #a dictionary that contains duty_id as key and then a tuple of two node ids - first is the start node and seconds is termination node
    duty_start_end_nodes = {}

    #######################################
    #GENERATE NODES FOR UNCOVERED TASKS:
    # we get all regular tasks within the time window to create regular nodes
    included_uncovered_tasks = [task for task in uncovered_tasks if (task["arrival"] >= window_start and task["arrival"] <= window_end) or (task["departure"] >= window_start and task["departure"] <= window_end)]

    uncovered_tasks_included = False
    # here we filter to only tasks that contain at least one regular tasks. Other tasks are not considered
    if len(included_uncovered_tasks) > 0:
        uncovered_tasks_included = True

    if uncovered_tasks_included:
        # create a node for every uncovered task
        for ut in included_uncovered_tasks:
            graphNodes[node_counter] = Node(node_counter, -1, 1, ut)
            node_counter += 1

    node_for_task_generated = []
    #GENERATE NODES:
    for duty_id, duty_category in duty_categories.items():
        #first get the tasks of the duty
        duty = currentSolution.crew_duties[duty_id]
        tasks = duty.tasks

        start_node_id = 0
        termination_node_id = 0

        # we get all regular tasks within the time window to create regular nodes
        regular_tasks = [task for task in tasks if (task["arrival"] >= window_start and task["arrival"] <= window_end) or (task["departure"] >= window_start and task["departure"] <= window_end)]

        regular_tasks_included = False
        #here we filter to only tasks that contain at least one regular tasks. Other tasks are not considered
        if len(regular_tasks) > 0:
            regular_tasks_included = True

        if regular_tasks_included:
            # create a node for every regular task
            for rt in regular_tasks:
                #this makes sure that not multiple nodes are generated for the same task.
                #this has happened before because a task can be covered by two duties and then is present in two solutions
                #in the subsequent window then two nodes appear for the same task
                if rt["id"] not in node_for_task_generated:
                    graphNodes[node_counter] = Node(node_counter, duty_id, 1, rt)
                    node_counter += 1
                    node_for_task_generated.append(rt["id"])

            # this is a regular duty, so no dummy nodes are required
            if duty_category == 1:
                #create regular start and termination nodes
                #this is the start node
                #######################
                #define the properties of the start node for this duty here
                #find the last duty that has an arrival time smaller than the window_start
                start_task = max(
                    (task for task in tasks if task["arrival"] < window_start),
                    key=lambda t: t["arrival"],
                    default=None  # optional: avoids ValueError if no such object exists
                )
                if start_task == None:
                    print(f"ALERT: start task was set to None! this is the list of tasks: {tasks}")
                #######################
                graphNodes[node_counter] = Node(node_counter, duty_id,2, start_task)
                startNodes.append(node_counter)
                start_node_id = node_counter
                node_counter += 1

                #this is the termination node
                ######################
                #define the properties of the termination node for this duty here
                #find the first duty that has a departure time greater than the window end
                termination_task = min(
                    (task for task in tasks if task["departure"] > window_end),
                    key=lambda t: t["departure"],
                    default=None  # optional: avoids ValueError if no such object exists
                )
                if termination_task == None:
                    print(f"ALERT: termination task was set to None! this is the list of tasks: {tasks}")
                #####################
                graphNodes[node_counter] = Node(node_counter, duty_id, 4, termination_task)
                terminationNodes.append(node_counter)
                termination_node_id = node_counter
                node_counter += 1

            # this is a starting duty, so a dummy starting node is required
            elif duty_category == 2:
                # create dummy start node and regular termination node
                # this is the dummy start node
                graphNodes[node_counter] = Node(node_counter, duty_id, 3)
                dummyStartNodes.append(node_counter)
                start_node_id = node_counter
                node_counter += 1

                # this is the regular termination node
                ######################
                # define the properties of the termination node for this duty here
                # find the first duty that has a departure time greater than the window end
                termination_task = min(
                    (task for task in tasks if task["departure"] > window_end),
                    key=lambda t: t["departure"],
                    default=None  # optional: avoids ValueError if no such object exists
                )
                if termination_task == None:
                    print(f"ALERT: termination task was set to None! this is the list of tasks: {tasks}")
                #####################
                graphNodes[node_counter] = Node(node_counter, duty_id, 4, termination_task)
                terminationNodes.append(node_counter)
                termination_node_id = node_counter
                node_counter += 1

            # this is a termination duty, so a dummy termination node is required
            elif duty_category == 3:
                # create a regular start node and dummy termination node
                # this is the regular start node
                #######################
                # define the properties of the start node for this duty here
                # find the last duty that has an arrival time smaller than the window_start
                start_task = max(
                    (task for task in tasks if task["arrival"] < window_start),
                    key=lambda t: t["arrival"],
                    default=None  # optional: avoids ValueError if no such object exists
                )
                if start_task == None:
                    print(f"ALERT: start task was set to None! this is the list of tasks: {tasks}")
                #######################
                # this is the start node
                graphNodes[node_counter] = Node(node_counter, duty_id, 2, start_task)
                startNodes.append(node_counter)
                start_node_id = node_counter
                node_counter += 1

                # this is the dummy termination node
                graphNodes[node_counter] = Node(node_counter, duty_id, 5)
                dummyTerminationNodes.append(node_counter)
                termination_node_id = node_counter
                node_counter += 1

            # this is a flexible duty, so dummy start and dummy termination node is required
            elif duty_category == 4:
                # create a dummy start node and dummy termination node
                # this is the dummy start node
                graphNodes[node_counter] = Node(node_counter, duty_id, 3)
                dummyStartNodes.append(node_counter)
                start_node_id = node_counter
                node_counter += 1

                # this is the dummy termination node
                graphNodes[node_counter] = Node(node_counter, duty_id, 5)
                dummyTerminationNodes.append(node_counter)
                termination_node_id = node_counter
                node_counter += 1

            duty_start_end_nodes[duty_id] = (start_node_id, termination_node_id)

            #define if the duty requires a break within the time window
            duty_break = duty_breaktimes[duty_id]
            #this means there is no break at all, which means that there should be a break in the window
            if duty_break == None:
                break_required_in_window.append(duty_id)
            #this means there is a break, so we might not need to consider it, if it is outside the window
            elif duty_break != None:
                break_start = duty_break[0]
                break_end = duty_break[1]

                start_node = graphNodes[duty_start_end_nodes[duty_id][0]]
                end_node = graphNodes[duty_start_end_nodes[duty_id][1]]
                #regular duty
                if duty_category == 1:
                    #break was assigned inside the window
                    if break_start >= start_node.node_task["arrival"] and break_end <= end_node.node_task["departure"]:
                        break_required_in_window.append(duty_id)
                #starting duty
                elif duty_category == 2:
                    # break was assigned inside the window
                    if break_start >= tasks[0]["arrival"] and break_end <= end_node.node_task["departure"]:
                        break_required_in_window.append(duty_id)
                #terminating duty
                elif duty_category == 3:
                    # break was assigned inside the window
                    if break_start >= start_node.node_task["arrival"] and break_end <= tasks[-1]["departure"]:
                        break_required_in_window.append(duty_id)
                #flexible duty
                elif duty_category == 4:
                    # break was assigned inside the window
                    if break_start >= tasks[0]["arrival"] and break_end <= tasks[-1]["departure"]:
                        break_required_in_window.append(duty_id)

    #########################################################
    #GENERATE ARCS
    #there are 4 arc types
    #1: regular arcs
    #2: deadhead arcs
    #3: start arcs
    #4: termination arcs

    #5: idle arcs - this is a new set of arcs that indicate that no task is performed between start node and termination node, possibly making a duty shorter
    #6: duty removal arc - this is a new set of arcs only for flexible duties that completely remove a duty and are therefore desireable

    #this is the criteria if a break is possible or not in minutes
    BREAKTIME_30 = 30
    BREAKTIME_45 = 45

    arc_counter = 0

    for node_id_A, node_A in graphNodes.items():
        for node_id_B, node_B in graphNodes.items(): #go over all possible combinations in
            if node_id_A != node_id_B:
                typeA = node_A.node_type
                typeB = node_B.node_type
                # two regular nodes so include regular and deadhead trips
                if (typeA == 1 and typeB == 1) or (typeA == 2 and typeB == 1) or (typeA == 1 and typeB == 4):
                    #either add a regular arc with cost of 0 (no deadhead is required)
                    if (node_A.node_task["destination"] == node_B.node_task["origin"]) and (node_A.node_task["arrival"] <= node_B.node_task["departure"]):
                        arc_weight = 0
                        arc_type = 1 # regular arc
                        if node_B.node_task["departure"] - node_A.node_task["arrival"] >= BREAKTIME_45:
                            break_45_possible = True
                            break_30_possible = True
                        elif node_B.node_task["departure"] - node_A.node_task["arrival"] >= BREAKTIME_30:
                            break_30_possible = True
                            break_45_possible = False
                        else:
                            break_30_possible = False
                            break_45_possible = False
                        graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight, break_30_possible, break_45_possible)
                        arc_counter += 1
                    #add deadhead arcs if regular arcs are not possible
                    #elif node_A.node_task["destination"] != node_B.node_task["origin"] and node_A.node_task["arrival"] + (shortest_path[node_A.node_task["destination"]][node_B.node_task["origin"]]/crew_deadhead_speed)*60 <= node_B.node_task["departure"]:
                    elif (node_A.node_task["destination"] != node_B.node_task["origin"]) and (node_A.node_task[
                        "arrival"] + 60 <= node_B.node_task["departure"]): #TODO: replace with the line above
                        #arc_weight = shortest_path[node_A.node_task["destination"]][node_B.node_task["origin"]]
                        arc_weight = 999  # TODO: replace with line above
                        arc_type = 2  # deadhead arc
                        if node_B.node_task["departure"] - node_A.node_task["arrival"] >= BREAKTIME_45 + 60: #TODO: replace 60 by shortest_path_matrix
                            break_45_possible = True
                            break_30_possible = True
                        elif node_B.node_task["departure"] - node_A.node_task["arrival"] >= BREAKTIME_30 + 60:  # TODO: replace 60 by shortest_path_matrix
                            break_45_possible = False
                            break_30_possible = True
                        else:
                            break_30_possible = False
                            break_45_possible = False
                        graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight, break_30_possible, break_45_possible)
                        arc_counter += 1

                # dummy start node to regular node so include start arcs
                elif typeA == 3 and typeB == 1:
                    duty_A_id = node_A.duty_id # this is the duty that belongs to the respective dummy start node
                    original_start_A = duty_original_starttimes[duty_A_id] # get the original start time
                    original_homebase_A = duty_homebases[duty_A_id]
                    #add a start arc
                    if original_homebase_A == node_B.node_task["origin"] and abs(original_start_A - node_B.node_task["departure"]) <= START_SHIFT_WINDOW:
                        arc_weight = 0
                        arc_type = 3 # start arc
                        break_30_possible = False #there cannot be a break at a start arc
                        break_45_possible = False  # there cannot be a break at a start arc
                        graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight, break_30_possible, break_45_possible)
                        arc_counter += 1

                # regular node to dummy termination node so include termination arcs
                elif typeA == 1 and typeB == 5:
                    duty_B_id = node_B.duty_id  # this is the duty that belongs to the respective dummy termination node
                    original_homebase_B = duty_homebases[duty_B_id]
                    # add a start arc from every regular node
                    #we cannot care about maximum duty length here, because we do not know how much the start shifted
                    #the maximum duty length will be covered by the constraint in the model
                    #we will however punish a long deadhead by the costs of the arc
                    #arc_weight = shortest_path[node_A.node_task["destination"]][original_homebase_B]
                    arc_weight = 999 #TODO: replace with line above
                    arc_type = 4  # termination arc
                    break_30_possible = False  # there cannot be a break at a termination arc
                    break_45_possible = False  # there cannot be a break at a termination arc
                    graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight, break_30_possible, break_45_possible)
                    arc_counter += 1

                # regular start node to regular termination node of the same duty
                #this basically means that nothing happens inbetween but before and after there are tasks
                #the driver will be idle within the time window
                elif typeA == 2 and typeB == 4 and (node_A.duty_id == node_B.duty_id):
                    duty_B_id = node_B.duty_id  # this is the duty that belongs to the respective termination node

                    #this is basically a deadhead while doing nothing for the whole time window
                    # arc_weight = shortest_path[node_A.node_task["destination"]][node_B.node_task["origin"]]
                    arc_weight = 999  # TODO: replace with line above
                    arc_type = 5  # idle arc
                    if node_B.node_task["departure"] - node_A.node_task[
                        "arrival"] >= BREAKTIME_45 + 60:  # TODO: replace 60 by shortest_path_matrix
                        break_45_possible = True
                        break_30_possible = True
                    elif node_B.node_task["departure"] - node_A.node_task[
                        "arrival"] >= BREAKTIME_30 + 60:  # TODO: replace 60 by shortest_path_matrix
                        break_45_possible = False
                        break_30_possible = True
                    else:
                        break_45_possible = False
                        break_30_possible = False
                    graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight,
                                                 break_30_possible, break_45_possible)
                    arc_counter += 1

                # dummy start node to regular termination node of the same duty
                # this basically means that nothing happens inbetween but afterwards there are tasks
                # the driver will start the duty later than planned - we apply the same 1 hour time window as for regular starting arcs
                #and also no change in location is allowed
                elif typeA == 3 and typeB == 4 and (node_A.duty_id == node_B.duty_id):
                    duty_A_id = node_A.duty_id  # this is the duty that belongs to the respective dummy start node
                    original_start_A = duty_original_starttimes[duty_A_id]  # get the original start time
                    original_homebase_A = duty_homebases[duty_A_id]
                    # add a start arc
                    if original_homebase_A == node_B.node_task["origin"] and abs(
                            original_start_A - node_B.node_task["departure"]) <= START_SHIFT_WINDOW:
                        arc_weight = 0
                        arc_type = 5  # idle arc
                        break_30_possible = False  # there cannot be a break at a start-idle arc
                        break_45_possible = False  # there cannot be a break at a start-idle arc
                        graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight,
                                                     break_30_possible, break_45_possible)
                        arc_counter += 1

                # regular start node to dummy termination node of the same duty
                # this basically means that nothing happens inbetween but beforehand there are tasks
                # the driver will finish the duty earlier than planned
                elif typeA == 2 and typeB == 5 and (node_A.duty_id == node_B.duty_id):
                    duty_B_id = node_B.duty_id  # this is the duty that belongs to the respective dummy termination node
                    original_homebase_B = duty_homebases[duty_B_id]
                    # arc_weight = shortest_path[node_A.node_task["destination"]][original_homebase_B]
                    arc_weight = 999  # TODO: replace with line above
                    arc_type = 5  # idle arc
                    break_30_possible = False  # there cannot be a break at an idle-termination arc
                    break_45_possible = False  # there cannot be a break at an idle-termination arc
                    graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight,
                                                 break_30_possible, break_45_possible)
                    arc_counter += 1

                # dummy start node to dummy termination node of the same duty
                # this basically means that nothing happens inbetween
                # FOR FLEXIBLE DUTIES THIS IS GOOD: WE SAVE ONE DRIVER
                #the whole duty can be removed since other duties can take over

                elif typeA == 3 and typeB == 5 and (node_A.duty_id == node_B.duty_id):
                    arc_weight = 5000  # this comes with a huge reward since we spare one driver?? not so sure
                    arc_type = 6  # duty removal arc
                    break_30_possible = True  # we set this to True to satisfy the constraint but in fact this means there is no duty anymore
                    break_45_possible = True  # we set this to True to satisfy the constraint but in fact this means there is no duty anymore
                    graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight,
                                                 break_30_possible, break_45_possible)
                    arc_counter += 1

    deadhead_counter = 0
    for a, arc in graphArcs.items():
        if arc.arc_type == 2:
            deadhead_counter += 1
    print(f"There are {deadhead_counter} deadhead arcs in the full horizon of this this instance")
    return graphNodes, graphArcs, duty_start_end_nodes, break_required_in_window

def buildGraph_shortestPath(currentSolution, timeWindow, shortest_path, max_dh_duration, spare_duty_ids):
    #we need to assume a speed at which crew members can reach a different station since the distance is given in meters
    crew_deadhead_speed = 100

    max_deadhead_duration = max_dh_duration
    #max_deadhead_duration = 720 #this means there is no restriction on the maximal deadhead duration
    #max_deadhead_duration = 60 #here we restrict it to 1 hour

    uncovered_tasks = []
    for ut in currentSolution.uncovered_tasks:
        uncovered_tasks.append(copy.deepcopy(ut))

    window_start = timeWindow[0]
    window_end = timeWindow[1]

    #this parameter decides by how many minutes the start of a duty can be shifted either earlier or later
    START_SHIFT_WINDOW = 60

    #Here we define the nodes and arcs of the graph in a dictionary
    #this is the set of all nodes, also including (dummy) start and termination nodes
    graphNodes = {}
    #this is the set of all arcs, also including (dummy) start and termination arcs, as well as deadhead arcs
    graphArcs = {}

    #here we just keep track of the respective IDs to know which node/arc is of which type
    startNodes = []
    terminationNodes = []

    dummyStartNodes = []
    dummyTerminationNodes = []

    startArcs = []
    terminationArcs = []
    deadheadArcs = []

    node_counter = 0

    duty_categories = categorizeDuties(currentSolution, timeWindow)
    duty_homebases = getDutyHomeBases(currentSolution)
    duty_original_starttimes = getDutyStarttimes(currentSolution)
    duty_breaktimes = getDutyBreaktimes(currentSolution)

    #the duties that require a break within the window because no break is scheduled outside of the window
    break_required_in_window = []

    #a dictionary that contains duty_id as key and then a tuple of two node ids - first is the start node and seconds is termination node
    duty_start_end_nodes = {}

    #######################################
    #GENERATE NODES FOR UNCOVERED TASKS:
    # we get all regular tasks within the time window to create regular nodes
    included_uncovered_tasks = [task for task in uncovered_tasks if (task["arrival"] >= window_start and task["arrival"] <= window_end) or (task["departure"] >= window_start and task["departure"] <= window_end)]

    uncovered_tasks_included = False
    # here we filter to only tasks that contain at least one regular tasks. Other tasks are not considered
    if len(included_uncovered_tasks) > 0:
        uncovered_tasks_included = True

    if uncovered_tasks_included:
        # create a node for every uncovered task
        for ut in included_uncovered_tasks:
            graphNodes[node_counter] = Node(node_counter, -1, 1, ut)
            node_counter += 1

    node_for_task_generated = []
    #GENERATE NODES:
    for duty_id, duty_category in duty_categories.items():
        #first get the tasks of the duty
        duty = currentSolution.crew_duties[duty_id]
        tasks = duty.tasks

        start_node_id = 0
        termination_node_id = 0

        # we get all regular tasks within the time window to create regular nodes
        regular_tasks = [task for task in tasks if (task["arrival"] >= window_start and task["arrival"] <= window_end) or (task["departure"] >= window_start and task["departure"] <= window_end)]

        regular_tasks_included = False
        #here we filter to only tasks that contain at least one regular tasks. Other tasks are not considered
        if len(regular_tasks) > 0:
            regular_tasks_included = True

        if regular_tasks_included:
            # create a node for every regular task
            for rt in regular_tasks:
                if rt["id"] not in node_for_task_generated:
                    graphNodes[node_counter] = Node(node_counter, duty_id, 1, rt)
                    node_counter += 1
                    node_for_task_generated.append(rt["id"])

            # this is a regular duty, so no dummy nodes are required
            if duty_category == 1:
                #create regular start and termination nodes
                #this is the start node
                #######################
                #define the properties of the start node for this duty here
                #find the last duty that has an arrival time smaller than the window_start
                start_task = max(
                    (task for task in tasks if task["arrival"] < window_start),
                    key=lambda t: t["arrival"],
                    default=None  # optional: avoids ValueError if no such object exists
                )
                if start_task == None:
                    print(f"ALERT: start task was set to None! this is the list of tasks: {tasks}")
                #######################
                graphNodes[node_counter] = Node(node_counter, duty_id,2, start_task)
                startNodes.append(node_counter)
                start_node_id = node_counter
                node_counter += 1

                #this is the termination node
                ######################
                #define the properties of the termination node for this duty here
                #find the first duty that has a departure time greater than the window end
                termination_task = min(
                    (task for task in tasks if task["departure"] > window_end),
                    key=lambda t: t["departure"],
                    default=None  # optional: avoids ValueError if no such object exists
                )
                if termination_task == None:
                    print(f"ALERT: termination task was set to None! this is the list of tasks: {tasks}")
                #####################
                graphNodes[node_counter] = Node(node_counter, duty_id, 4, termination_task)
                terminationNodes.append(node_counter)
                termination_node_id = node_counter
                node_counter += 1

            # this is a starting duty, so a dummy starting node is required
            elif duty_category == 2:
                # create dummy start node and regular termination node
                # this is the dummy start node
                graphNodes[node_counter] = Node(node_counter, duty_id, 3)
                dummyStartNodes.append(node_counter)
                start_node_id = node_counter
                node_counter += 1

                # this is the regular termination node
                ######################
                # define the properties of the termination node for this duty here
                # find the first duty that has a departure time greater than the window end
                termination_task = min(
                    (task for task in tasks if task["departure"] > window_end),
                    key=lambda t: t["departure"],
                    default=None  # optional: avoids ValueError if no such object exists
                )
                if termination_task == None:
                    print(f"ALERT: termination task was set to None! this is the list of tasks: {tasks}")
                #####################
                graphNodes[node_counter] = Node(node_counter, duty_id, 4, termination_task)
                terminationNodes.append(node_counter)
                termination_node_id = node_counter
                node_counter += 1

            # this is a termination duty, so a dummy termination node is required
            elif duty_category == 3:
                # create a regular start node and dummy termination node
                # this is the regular start node
                #######################
                # define the properties of the start node for this duty here
                # find the last duty that has an arrival time smaller than the window_start
                start_task = max(
                    (task for task in tasks if task["arrival"] < window_start),
                    key=lambda t: t["arrival"],
                    default=None  # optional: avoids ValueError if no such object exists
                )
                if start_task == None:
                    print(f"ALERT: start task was set to None! this is the list of tasks: {tasks}")
                #######################
                # this is the start node
                graphNodes[node_counter] = Node(node_counter, duty_id, 2, start_task)
                startNodes.append(node_counter)
                start_node_id = node_counter
                node_counter += 1

                # this is the dummy termination node
                graphNodes[node_counter] = Node(node_counter, duty_id, 5)
                dummyTerminationNodes.append(node_counter)
                termination_node_id = node_counter
                node_counter += 1

            # this is a flexible duty, so dummy start and dummy termination node is required
            elif duty_category == 4:
                # create a dummy start node and dummy termination node
                # this is the dummy start node
                graphNodes[node_counter] = Node(node_counter, duty_id, 3)
                dummyStartNodes.append(node_counter)
                start_node_id = node_counter
                node_counter += 1

                # this is the dummy termination node
                graphNodes[node_counter] = Node(node_counter, duty_id, 5)
                dummyTerminationNodes.append(node_counter)
                termination_node_id = node_counter
                node_counter += 1

            duty_start_end_nodes[duty_id] = (start_node_id, termination_node_id)

            #define if the duty requires a break within the time window
            duty_break = duty_breaktimes[duty_id]
            #this means there is no break at all, which means that there should be a break in the window
            if duty_break == None:
                break_required_in_window.append(duty_id)
            #this means there is a break, so we might not need to consider it, if it is outside the window
            elif duty_break != None:
                break_start = duty_break[0]
                break_end = duty_break[1]

                start_node = graphNodes[duty_start_end_nodes[duty_id][0]]
                end_node = graphNodes[duty_start_end_nodes[duty_id][1]]
                #regular duty
                if duty_category == 1:
                    #break was assigned inside the window
                    if break_start >= start_node.node_task["arrival"] and break_end <= end_node.node_task["departure"]:
                        break_required_in_window.append(duty_id)
                #starting duty
                elif duty_category == 2:
                    # break was assigned inside the window
                    if break_start >= tasks[0]["arrival"] and break_end <= end_node.node_task["departure"]:
                        break_required_in_window.append(duty_id)
                #terminating duty
                elif duty_category == 3:
                    # break was assigned inside the window
                    if break_start >= start_node.node_task["arrival"] and break_end <= tasks[-1]["departure"]:
                        break_required_in_window.append(duty_id)
                #flexible duty
                elif duty_category == 4:
                    # break was assigned inside the window
                    if break_start >= tasks[0]["arrival"] and break_end <= tasks[-1]["departure"]:
                        break_required_in_window.append(duty_id)
    #########################################################
    #GENERATE ARCS
    #there are 4 arc types
    #1: regular arcs
    #2: deadhead arcs
    #3: start arcs
    #4: termination arcs

    #5: idle arcs - this is a new set of arcs that indicate that no task is performed between start node and termination node, possibly making a duty shorter
    #6: duty removal arc - this is a new set of arcs only for flexible duties that completely remove a duty and are therefore desireable

    #this is the criteria if a break is possible or not in minutes
    BREAKTIME_30 = 30
    BREAKTIME_45 = 45

    arc_counter = 0

    for node_id_A, node_A in graphNodes.items():
        for node_id_B, node_B in graphNodes.items(): #go over all possible combinations in
            if node_id_A != node_id_B:
                typeA = node_A.node_type
                typeB = node_B.node_type
                # two regular nodes so include regular and deadhead trips
                if (typeA == 1 and typeB == 1) or (typeA == 2 and typeB == 1) or (typeA == 1 and typeB == 4):
                    #either add a regular arc with cost of 0 (no deadhead is required)
                    if (node_A.node_task["destination"] == node_B.node_task["origin"]) and (node_A.node_task["arrival"] <= node_B.node_task["departure"]):
                        arc_weight = 0
                        arc_type = 1 # regular arc
                        if node_B.node_task["departure"] - node_A.node_task["arrival"] >= BREAKTIME_45:
                            break_45_possible = True
                            break_30_possible = True
                        if node_B.node_task["departure"] - node_A.node_task["arrival"] >= BREAKTIME_30:
                            break_45_possible = False
                            break_30_possible = True
                        else:
                            break_30_possible = False
                            break_45_possible = False
                        graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight, break_30_possible, break_45_possible)
                        arc_counter += 1
                    #add deadhead arcs if regular arcs are not possible
                    elif node_A.node_task["destination"] != node_B.node_task["origin"] and node_A.node_task["arrival"] + ((shortest_path[node_A.node_task["destination"]][node_B.node_task["origin"]]/1000.0)/crew_deadhead_speed)*60 <= node_B.node_task["departure"] and ((shortest_path[node_A.node_task["destination"]][node_B.node_task["origin"]]/1000.0)/crew_deadhead_speed)*60 <= max_deadhead_duration and node_B.node_task["departure"] - node_A.node_task["arrival"] <= 720:
                        arc_weight = (((shortest_path[node_A.node_task["destination"]][node_B.node_task["origin"]])/1000.0)/crew_deadhead_speed)*60
                        #arc_weight = 999  # TODO: replace with line above
                        arc_type = 2  # deadhead arc
                        if node_B.node_task["departure"] - node_A.node_task["arrival"] >= BREAKTIME_45 + (((shortest_path[node_A.node_task["destination"]][node_B.node_task["origin"]])/1000.0)/crew_deadhead_speed)*60: #TODO: replace 60 by shortest_path_matrix
                            break_45_possible = True
                            break_30_possible = True
                        if node_B.node_task["departure"] - node_A.node_task["arrival"] >= BREAKTIME_30 + (((shortest_path[node_A.node_task["destination"]][node_B.node_task["origin"]])/1000.0)/crew_deadhead_speed)*60: #TODO: replace 60 by shortest_path_matrix
                            break_45_possible = False
                            break_30_possible = True
                        else:
                            break_30_possible = False
                            break_45_possible = False
                        graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight, break_30_possible, break_45_possible)
                        arc_counter += 1

                # dummy start node to regular node so include start arcs
                elif typeA == 3 and typeB == 1:
                    duty_A_id = node_A.duty_id # this is the duty that belongs to the respective dummy start node
                    original_start_A = duty_original_starttimes[duty_A_id] # get the original start time
                    original_homebase_A = duty_homebases[duty_A_id]
                    #add a start arc
                    if original_homebase_A == node_B.node_task["origin"] and abs(original_start_A - node_B.node_task["departure"]) <= START_SHIFT_WINDOW:
                        arc_weight = 0
                        arc_type = 3 # start arc
                        break_30_possible = False #there cannot be a break at a start arc
                        break_45_possible = False  # there cannot be a break at a start arc
                        graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight, break_30_possible, break_45_possible)
                        arc_counter += 1

                # regular node to dummy termination node so include termination arcs
                elif typeA == 1 and typeB == 5:
                    duty_B_id = node_B.duty_id  # this is the duty that belongs to the respective dummy termination node
                    original_homebase_B = duty_homebases[duty_B_id]
                    # add a start arc from every regular node
                    #we cannot care about maximum duty length here, because we do not know how much the start shifted
                    #the maximum duty length will be covered by the constraint in the model
                    #we will however punish a long deadhead by the costs of the arc
                    arc_weight = ((shortest_path[node_A.node_task["destination"]][original_homebase_B]/1000.0)/crew_deadhead_speed)*60
                    #arc_weight = 999 #TODO: replace with line above
                    arc_type = 4  # termination arc
                    break_30_possible = False  # there cannot be a break at a termination arc
                    break_45_possible = False  # there cannot be a break at a termination arc
                    graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight, break_30_possible, break_45_possible)
                    arc_counter += 1

                # regular start node to regular termination node of the same duty
                #this basically means that nothing happens inbetween but before and after there are tasks
                #the driver will be idle within the time window
                elif typeA == 2 and typeB == 4 and (node_A.duty_id == node_B.duty_id):
                    duty_B_id = node_B.duty_id  # this is the duty that belongs to the respective termination node

                    #this is basically a deadhead while doing nothing for the whole time window
                    arc_weight = ((shortest_path[node_A.node_task["destination"]][node_B.node_task["origin"]]/1000.0)/crew_deadhead_speed)*60
                    #arc_weight = 999  # TODO: replace with line above
                    arc_type = 5  # idle arc
                    if node_B.node_task["departure"] - node_A.node_task[
                        "arrival"] >= BREAKTIME_45 + ((shortest_path[node_A.node_task["destination"]][node_B.node_task["origin"]]/1000.0)/crew_deadhead_speed)*60:  # TODO: replace 60 by shortest_path_matrix
                        break_45_possible = True
                        break_30_possible = True
                    if node_B.node_task["departure"] - node_A.node_task[
                        "arrival"] >= BREAKTIME_30 + ((shortest_path[node_A.node_task["destination"]][node_B.node_task["origin"]]/1000.0)/crew_deadhead_speed)*60:  # TODO: replace 60 by shortest_path_matrix
                        break_45_possible = False
                        break_30_possible = True
                    else:
                        break_45_possible = False
                        break_30_possible = False
                    graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight,
                                                 break_30_possible, break_45_possible)
                    arc_counter += 1

                # dummy start node to regular termination node of the same duty
                # this basically means that nothing happens inbetween but afterwards there are tasks
                # the driver will start the duty later than planned - we apply the same 1 hour time window as for regular starting arcs
                #and also no change in location is allowed
                elif typeA == 3 and typeB == 4 and (node_A.duty_id == node_B.duty_id):
                    duty_A_id = node_A.duty_id  # this is the duty that belongs to the respective dummy start node
                    original_start_A = duty_original_starttimes[duty_A_id]  # get the original start time
                    original_homebase_A = duty_homebases[duty_A_id]
                    # add a start arc
                    if original_homebase_A == node_B.node_task["origin"] and abs(
                            original_start_A - node_B.node_task["departure"]) <= START_SHIFT_WINDOW:
                        arc_weight = 0
                        arc_type = 5  # idle arc
                        break_30_possible = False  # there cannot be a break at a start-idle arc
                        break_45_possible = False  # there cannot be a break at a start-idle arc
                        graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight,
                                                     break_30_possible, break_45_possible)
                        arc_counter += 1

                # regular start node to dummy termination node of the same duty
                # this basically means that nothing happens inbetween but beforehand there are tasks
                # the driver will finish the duty earlier than planned
                elif typeA == 2 and typeB == 5 and (node_A.duty_id == node_B.duty_id):
                    duty_B_id = node_B.duty_id  # this is the duty that belongs to the respective dummy termination node
                    original_homebase_B = duty_homebases[duty_B_id]
                    arc_weight = ((shortest_path[node_A.node_task["destination"]][original_homebase_B]/1000.0)/crew_deadhead_speed)*60
                    #arc_weight = 999  # TODO: replace with line above
                    arc_type = 5  # idle arc
                    break_30_possible = False  # there cannot be a break at an idle-termination arc
                    break_45_possible = False  # there cannot be a break at an idle-termination arc
                    graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight,
                                                 break_30_possible, break_45_possible)
                    arc_counter += 1

                # dummy start node to dummy termination node of the same duty
                # this basically means that nothing happens inbetween
                # FOR FLEXIBLE DUTIES THIS IS GOOD: WE SAVE ONE DRIVER
                #the whole duty can be removed since other duties can take over

                elif typeA == 3 and typeB == 5 and (node_A.duty_id == node_B.duty_id):
                    #spare duties do not need to be used and therefore we assign an arc weight of 0
                    if node_A.duty_id in spare_duty_ids:
                        arc_weight = 0
                    #drivers that are not spare drivers should be used and therefore we penalize the duty removal arc
                    else:
                        arc_weight = 5000  #
                    arc_type = 6  # duty removal arc
                    break_30_possible = False  # we set this to True to satisfy the constraint but in fact this means there is no duty anymore
                    break_45_possible = False  # we set this to True to satisfy the constraint but in fact this means there is no duty anymore
                    graphArcs[arc_counter] = Arc(arc_counter, arc_type, node_id_A, node_id_B, arc_weight,
                                                 break_30_possible, break_45_possible)
                    arc_counter += 1

    deadhead_counter = 0
    for a, arc in graphArcs.items():
        if arc.arc_type == 2:
            deadhead_counter += 1
    print(f"There are {deadhead_counter} deadhead arcs in the full horizon of this this instance")
    return graphNodes, graphArcs, duty_start_end_nodes, break_required_in_window





