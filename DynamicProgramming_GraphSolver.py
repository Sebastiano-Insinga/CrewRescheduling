from collections import defaultdict, deque
from GraphBuilder import *

#use this function to iteratively call the DP
#the graph will shrink because some paths have alreday been selected in previous iterations
def remove_Used_Nodes_and_Arcs(graph: Graph, path):
    # Remove the nodes
    for node_id in path:
        if node_id in graph.graph_nodes:
            del graph.graph_nodes[node_id]

    # Remove arcs connected to any of the nodes
    arcs_to_delete = [
        arc_id for arc_id, arc in graph.graph_arcs.items()
        if arc.start_node in path or arc.end_node in path
    ]
    for arc_id in arcs_to_delete:
        del graph.graph_arcs[arc_id]


def DP_SingleDuty(duty_id, graph: Graph, source_id: int, sink_id: int, duty_category, duty_original_starttimes, duty_original_endtimes,  duty_original_homebases, duty_original_endbases, covered_nodes, shortest_path_matrix, suitable_tasks):
    #TODO for the dynamic programming: include the maximum duty length as a restricition
    #this means for starting and terminating duties: keep track of the available time and do not proceed on infeasible paths
    #for flexible duties I need to keep track of the starting arcs and then define possible paths from all the starting nodes

    bonus_task_covered = 3000
    max_duty_length = 720
    # Build adjacency list and in-degree dictionary
    adjacency = defaultdict(list)
    in_degree = defaultdict(int)
    for arc in graph.graph_arcs.values():
        adjacency[arc.start_node].append((arc.end_node, arc.arc_cost))
        in_degree[arc.end_node] += 1
        if arc.start_node not in in_degree:
            in_degree[arc.start_node] = 0

    list_nodes_that_reduce_in_degree = []

    # Topological sort using Kahn's algorithm
    queue = deque([node_id for node_id in in_degree if in_degree[node_id] == 0])
    topo_order = []
    neighbor_counter = 0

    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for neighbor, _ in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if sink_id not in topo_order:
        print(f"The duty id is {duty_id}")
        print(f"The duty category is {duty_category}")
        print(f"The source id is {source_id}")
        print(f"The sink id is {sink_id}")
        print("topo_order looks as follows")
        for a, arc in graph.graph_arcs.items():
            if arc.end_node == sink_id:
                print(f"This is arc with arc_id {arc.arc_id} that goes from {arc.start_node} to {arc.end_node} and is of type {arc.arc_type}")
        raise ValueError("Sink node not reachable from source.")

    # Initialize DP table and predecessors
    cost_to = {node_id: float('inf') for node_id in graph.graph_nodes}
    cost_to[source_id] = 0
    predecessor = {source_id: None}

    #this is an experiment for terminating duties
    #it should restrict the maximum duty length
    ############################################################################################
    #this is a terminating duty, so the start date is already known
    if duty_category == 3:
        duty_starttime = duty_original_starttimes[duty_id]
        duty_homebase = duty_original_homebases[duty_id]
        duration_to = {node_id: float('inf') for node_id in graph.graph_nodes}
        duration_to[source_id] = 0

        # DP for the duration
        for node_id in topo_order:
            node = graph.graph_nodes[node_id]
            if node.node_type == 3: #we do not need durations from dummy start nodes because this is a terminating duty
                continue
            else:
                for neighbor_id, weight in adjacency[node_id]:
                    neighbor = graph.graph_nodes[neighbor_id]
                    if neighbor.node_type == 5: #dummy termination node
                        #duration_to[neighbor] = node.node_task["arrival"] + shortest_path_matrix[node.node_task["destination"]][duty_homebase] - duty_starttime
                        if node.node_task["destination"] == duty_homebase:
                            duration_to[neighbor_id] = node.node_task["arrival"] - duty_starttime
                        else:
                            duration_to[neighbor_id] = node.node_task["arrival"] + 60 - duty_starttime # TODO: replace this if else block by the line above as soon as shortest path matrix is complete
                    else: #all other nodes
                        duration_to[neighbor_id] = neighbor.node_task["arrival"] - duty_starttime

                    # only provide the bonus_task_covered if the driver is able to perform the task and it is not yet covered
                    if graph.graph_nodes[neighbor_id].node_task != None:
                        if graph.graph_nodes[neighbor_id].node_task["id"] in suitable_tasks[duty_id]:
                            #neighbor is already covered, so no bonus
                            if neighbor_id in covered_nodes:
                                if cost_to[node_id] + weight < cost_to[neighbor_id] and duration_to[neighbor_id] <= max_duty_length:
                                    cost_to[neighbor_id] = cost_to[node_id] + weight
                                    predecessor[neighbor_id] = node_id
                            # the neighbor has not been visited yet so we apply a bonus
                            else:
                                if cost_to[node_id] + weight - bonus_task_covered < cost_to[neighbor_id] and duration_to[neighbor_id] <= max_duty_length:
                                    cost_to[neighbor_id] = cost_to[node_id] + weight - bonus_task_covered
                                    predecessor[neighbor_id] = node_id
                        #otherwise the driver is just a passenger, but only in the case that another driver already drives the task
                        else:
                            if neighbor_id in covered_nodes:
                                if cost_to[node_id] + weight < cost_to[neighbor_id] and duration_to[neighbor_id] <= max_duty_length:
                                    cost_to[neighbor_id] = cost_to[node_id] + weight
                                    predecessor[neighbor_id] = node_id
                    #In this case the neighbor is a dummy node so we keep the old version
                    else:
                        # neighbor is already covered, so no bonus
                        if neighbor_id in covered_nodes:
                            if cost_to[node_id] + weight < cost_to[neighbor_id] and duration_to[
                                neighbor_id] <= max_duty_length:
                                cost_to[neighbor_id] = cost_to[node_id] + weight
                                predecessor[neighbor_id] = node_id
                        # the neighbor has not been visited yet so we apply a bonus
                        else:
                            if cost_to[node_id] + weight - bonus_task_covered < cost_to[neighbor_id] and duration_to[
                                neighbor_id] <= max_duty_length:
                                cost_to[neighbor_id] = cost_to[node_id] + weight - bonus_task_covered
                                predecessor[neighbor_id] = node_id

    ####################################################################################################################
    #this is a starting duty, so the end date of the duty is already known
    if duty_category == 2:
        duty_endtime = duty_original_endtimes[duty_id]
        duty_homebase = duty_original_homebases[duty_id]
        duty_endbase = duty_original_endbases[duty_id]

        # Step 1: Identify valid start nodes (real tasks connected to dummy start)
        possible_start_nodes = {}
        for arc in graph.graph_arcs.values():
            if arc.start_node == source_id and arc.arc_type == 3:
                node = graph.graph_nodes[arc.end_node]
                departure = node.node_task["departure"]
                #if duty_homebase == duty_endbase:
                if duty_endtime - departure <= max_duty_length:
                    possible_start_nodes[arc.end_node] = departure
                #else:
                #    if duty_endtime + 60 - departure <= max_duty_length:
                #        possible_start_nodes[arc.end_node] = departure

        # Initialize DP table and predecessors
        #actually this is quite similar to the regular case, but we only asign values to the allowed starting nodes and then in the end add the source node
        cost_to = {node_id: float('inf') for node_id in graph.graph_nodes}
        for node_id in possible_start_nodes:
            cost_to[node_id] = 0
            predecessor = {node_id: None}

        for node in topo_order:
            for neighbor, weight in adjacency[node]:
                # this means the neighbor was already covered by a previous DP run. We do not apply a bonus for visiting again

                if graph.graph_nodes[neighbor].node_task != None:
                    if graph.graph_nodes[neighbor].node_task["id"] in suitable_tasks[duty_id]:
                        if neighbor in covered_nodes:
                            if cost_to[node] + weight < cost_to[neighbor]:
                                cost_to[neighbor] = cost_to[node] + weight
                                predecessor[neighbor] = node
                        # the neighbor has not been visited yet so we apply a bonus
                        else:
                            if cost_to[node] + weight - bonus_task_covered < cost_to[neighbor]:
                                cost_to[neighbor] = cost_to[node] + weight - bonus_task_covered
                                predecessor[neighbor] = node
                    #otherwise driver is just a passenger, but only if the neighbor is already covered by another node
                    else:
                        if neighbor in covered_nodes:
                            if cost_to[node] + weight < cost_to[neighbor]:
                                cost_to[neighbor] = cost_to[node] + weight
                                predecessor[neighbor] = node
                else:
                    if neighbor in covered_nodes:
                        if cost_to[node] + weight < cost_to[neighbor]:
                            cost_to[neighbor] = cost_to[node] + weight
                            predecessor[neighbor] = node
                    # the neighbor has not been visited yet so we apply a bonus
                    else:
                        if cost_to[node] + weight - bonus_task_covered < cost_to[neighbor]:
                            cost_to[neighbor] = cost_to[node] + weight - bonus_task_covered
                            predecessor[neighbor] = node

        # Reconstruct path
        path = []
        current = sink_id
        while current is not None:
            path.append(current)
            current = predecessor.get(current)
        path.reverse()
        path.insert(0,source_id)

        return cost_to[sink_id], path

    #################################################################################################################
    #flexible duties need to be handled differently
    if duty_category == 4:
        # Identify possible start nodes and their departure times
        possible_start_nodes = {
            arc.end_node: graph.graph_nodes[arc.end_node].node_task["departure"]
            for arc in graph.graph_arcs.values()
            if arc.start_node == source_id and arc.arc_type == 3
        }

        #print(f"Possible start nodes for this duty: {possible_start_nodes}")

        duty_homebase = duty_original_homebases[duty_id]

        # Initialize dynamic programming state: (node, start_node) -> {cost, duration, predecessor}
        dp_state = {
            (start_node, start_node): {
                "cost": 0,
                "duration": 0,
                "predecessor": None,
                "path": [source_id, start_node]
            }
            for start_node in possible_start_nodes
        }

        # We also need a global best result tracker
        best_result = {
            "cost": float("inf"),
            "end_node": None,
            "start_node": None
        }

        #here we do not need the source anymore, it is already included in the paths and we already now the few possible starting nodes
        topo_order.remove(source_id)
        for node_id in topo_order:
            for start_node, start_departure in possible_start_nodes.items():
                state_key = (node_id, start_node)
                if state_key not in dp_state:
                    continue  # not reachable with this start_node

                current_state = dp_state[state_key]
                current_cost = current_state["cost"]

                for neighbor_id, weight in adjacency[node_id]:
                    neighbor = graph.graph_nodes[neighbor_id]

                    #Skip direct dummy start → dummy termination
                    #if graph.graph_nodes[node_id].node_type == 3 and neighbor.node_type == 5:
                    #    continue

                    # Calculate duration from the start_node’s departure time
                    #here
                    if neighbor.node_type == 5:  # dummy termination node
                        #if graph.graph_nodes[node_id].node_task["destination"] == duty_homebase
                        #and these two
                        arrival_time = graph.graph_nodes[node_id].node_task["arrival"]
                        duration = arrival_time - start_departure
                        #else:
                        #    arrival_time = graph.graph_nodes[node_id].node_task["arrival"] + 60  # placeholder for travel to homebase
                        #    duration = arrival_time - start_departure
                    else:
                        arrival_time = neighbor.node_task["arrival"]
                        duration = arrival_time - start_departure
                        #if duration == -17:
                        #    print("here")

                    if duration > max_duty_length:
                        continue  # skip invalid paths

                    # Cost and bonus logic
                    if graph.graph_nodes[neighbor_id].node_task != None:
                        if graph.graph_nodes[neighbor_id].node_task["id"] in suitable_tasks[duty_id]:
                            if neighbor_id in covered_nodes:
                                new_cost = current_cost + weight
                            else:
                                new_cost = current_cost + weight - bonus_task_covered
                        #otherwise just a passenger
                        else:
                            if neighbor_id in covered_nodes:
                                new_cost = current_cost + weight
                            else:
                                #this means that the assignment cannot be done, no driver is driving the train yet
                                #new_cost = float('inf')
                                continue
                    else:
                        if neighbor_id in covered_nodes:
                            new_cost = current_cost + weight
                        else:
                            new_cost = current_cost + weight - bonus_task_covered

                    neighbor_key = (neighbor_id, start_node)

                    # Only update if it's better
                    if neighbor_key not in dp_state or new_cost < dp_state[neighbor_key]["cost"]:
                        dp_state[neighbor_key] = {
                            "cost": new_cost,
                            "duration": duration,
                            "predecessor": node_id,
                            "path": current_state["path"] + [neighbor_id]
                        }

                        # Update best result if termination node
                        if neighbor_id == sink_id and new_cost < best_result["cost"]:
                            best_result.update({
                                "cost": new_cost,
                                "end_node": neighbor_id,
                                "start_node": start_node
                            })

        # After finding best_result
        if best_result["end_node"] is not None:
            final_key = (best_result["end_node"], best_result["start_node"])
            final_cost = dp_state[final_key]["cost"]
            final_path = dp_state[final_key]["path"]
            #start_time = graph.graph_nodes[final_path[1]].node_task["departure"]
            #end_time = graph.graph_nodes[final_path[-2]].node_task["arrival"]
            #print(f"The length of this final path of duty {duty_id} is: {end_time-start_time}")
            return final_cost, final_path
        else:
            return float("inf"), []  # No feasible path found

    ###############################################################
    if duty_category != 3 and duty_category != 2 and duty_category != 4:
    #else:
        # DP over topological order
        for node in topo_order:
            for neighbor, weight in adjacency[node]:
                #this means the neighbor was already covered by a previous DP run. We do not apply a bonus for visiting again

                if graph.graph_nodes[neighbor].node_task != None:
                    if graph.graph_nodes[neighbor].node_task["id"] in suitable_tasks[duty_id]:
                        if neighbor in covered_nodes:
                            if cost_to[node] + weight < cost_to[neighbor]:
                                cost_to[neighbor] = cost_to[node] + weight
                                predecessor[neighbor] = node
                        #the neighbor has not been visited yet so we apply a bonus
                        else:
                            if cost_to[node] + weight - bonus_task_covered < cost_to[neighbor]:
                                cost_to[neighbor] = cost_to[node] + weight - bonus_task_covered
                                predecessor[neighbor] = node
                    else:
                        if neighbor in covered_nodes:
                            if cost_to[node] + weight < cost_to[neighbor]:
                                cost_to[neighbor] = cost_to[node] + weight
                                predecessor[neighbor] = node
                else:
                    if neighbor in covered_nodes:
                        if cost_to[node] + weight < cost_to[neighbor]:
                            cost_to[neighbor] = cost_to[node] + weight
                            predecessor[neighbor] = node
                    # the neighbor has not been visited yet so we apply a bonus
                    else:
                        if cost_to[node] + weight - bonus_task_covered < cost_to[neighbor]:
                            cost_to[neighbor] = cost_to[node] + weight - bonus_task_covered
                            predecessor[neighbor] = node

    # Reconstruct path
    path = []
    current = sink_id
    while current is not None:
        path.append(current)
        current = predecessor.get(current)
    path.reverse()

    return cost_to[sink_id], path