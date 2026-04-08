from GraphBuilder import *
#import cplex
import gurobipy as gp
from gurobipy import Model, GRB

class WindowBasedModel_GUROBI:
    def __init__(self, graph, duty_categories, duties_require_break, duty_original_starttimes, duty_original_endtimes, time_window, suitable_tasks):
        self.graph = graph
        self.x = {}
        self.alpha = {}
        self.beta = {}
        self.cancellation_cost = 3000
        self.break_violation_cost = 50
        self.max_duty_length = 720

        self.suitable_tasks = suitable_tasks

        seen_duties = set()
        self.unique_duty_ids = []
        for node in self.graph.graph_nodes.values():
            if node.duty_id not in seen_duties and node.duty_id != -1:
                seen_duties.add(node.duty_id)
                self.unique_duty_ids.append(node.duty_id)

        self.arcs_allowing_break = [arc_id for arc_id, a in self.graph.graph_arcs.items() if a.break_possible]
        self.duties_require_break = duties_require_break
        self.duty_categories = duty_categories
        self.duty_original_starttimes = duty_original_starttimes
        self.duty_original_endtimes = duty_original_endtimes

        # Create a new Gurobi environment
        self.env = gp.Env(empty=True)

        # Set WLS license parameters
        self.env.setParam("WLSAccessID", "96daee41-16c8-4add-a427-2028f293967a")
        self.env.setParam("WLSSecret", "23a86426-6aa9-4181-9ebd-774a96e2ffc7")
        self.env.setParam("LicenseID", 2690047)  # Replace with your numeric license ID

        # Start the environment (connects to Gurobi WLS server)
        self.env.start()

        self.model = Model("WindowBasedModel", env=self.env)
        self.model.setParam("Threads", 1)
        self.model.setParam("TimeLimit", 3600)
        self.model.ModelSense = GRB.MINIMIZE

        #self.graph.displayGraph()

    def build_model(self):
        for k in self.unique_duty_ids:
            self.x[k] = {}
            for a, arc in self.graph.graph_arcs.items():
                var_name = f"x_{k}_{a}"
                self.x[k][a] = self.model.addVar(vtype=GRB.BINARY, obj=arc.arc_cost, name=var_name)

        for i, node in self.graph.graph_nodes.items():
            if node.node_type == 1:
                self.alpha[i] = self.model.addVar(vtype=GRB.BINARY, obj=self.cancellation_cost, name=f"alpha_{i}")

        for k in self.unique_duty_ids:
            self.beta[k] = self.model.addVar(vtype=GRB.BINARY, obj=self.break_violation_cost, name=f"beta_{k}")

        self.model.update()


        for k in self.unique_duty_ids:
            start_node_id = self.graph.duty_start_end_nodes[k][0]
            outgoing_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.start_node == start_node_id]
            self.model.addConstr(sum(self.x[k][a] for a in outgoing_arcs) == 1, name=f"StartArc_{k}")

        for k in self.unique_duty_ids:
            end_node_id = self.graph.duty_start_end_nodes[k][1]
            incoming_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.end_node == end_node_id]
            self.model.addConstr(sum(self.x[k][a] for a in incoming_arcs) == 1, name=f"EndArc_{k}")


        for k in self.unique_duty_ids:
            for node_id in self.graph.graph_nodes:
                #only do this for regular arcs
                if self.graph.graph_nodes[node_id].node_type == 1:
                    in_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.end_node == node_id]
                    out_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.start_node == node_id]
                    self.model.addConstr(sum(self.x[k][a] for a in out_arcs) - sum(self.x[k][a] for a in in_arcs) == 0,
                                         name=f"FlowBalance_{k}_{node_id}")

        #manually enforce that there can only be start arcs assigned to 1, if the respective (dummy) start node is included
        for k in self.unique_duty_ids:
            start_node_id = self.graph.duty_start_end_nodes[k][0]
            prohibited_start_arcs = [a for a, arc in self.graph.graph_arcs.items() if (arc.arc_type in [3] and arc.start_node != start_node_id) or (self.graph.graph_nodes[arc.start_node].node_type in [2,3] and arc.start_node != start_node_id)]
            for a in prohibited_start_arcs:
                self.model.addConstr(self.x[k][a] == 0, name=f"ProhibitedStartArc_{k}")

        # manually enforce that there can only be end arcs assigned to 1, if the respective (dummy) end node is included
        for k in self.unique_duty_ids:
            end_node_id = self.graph.duty_start_end_nodes[k][1]
            prohibited_termination_arcs = [a for a, arc in self.graph.graph_arcs.items() if (arc.arc_type in [4] and arc.end_node != end_node_id) or (self.graph.graph_nodes[arc.end_node].node_type in [4,5] and arc.end_node != end_node_id)]
            for a in prohibited_termination_arcs:
                self.model.addConstr(self.x[k][a] == 0, name=f"ProhibitedTerminationArc_{k}")

        for k in self.duties_require_break:
            self.model.addConstr(sum(self.x[k][a] for a in self.arcs_allowing_break) + self.beta[k] >= 1,
                                 name=f"Break_{k}")

        #this was added for the version with suitable tasks in the constraint -- check if this is correct
        # --> if node.node_task["id"] in suitable_tasks[k]
        for i, node in self.graph.graph_nodes.items():
            if node.node_type == 1:
                incoming_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.end_node == i]
                self.model.addConstr(sum(self.x[k][a] for k in self.unique_duty_ids for a in incoming_arcs if a in self.x[k] if node.node_task["id"] in self.suitable_tasks[k]) + self.alpha[i] >= 1,
                                     name=f"Cover_{i}")

        for k in self.unique_duty_ids:
            category = self.duty_categories[k]

            if category == 2:
                endtime = self.duty_original_endtimes[k]
                start_node_id = self.graph.duty_start_end_nodes[k][0]
                out_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.start_node == start_node_id]
                expr = sum(self.x[k][a] * self.graph.graph_nodes[self.graph.graph_arcs[a].end_node].node_task["departure"] for a in out_arcs if self.graph.graph_arcs[a].arc_type == 3)
                self.model.addConstr(expr >= endtime - self.max_duty_length, name=f"MaxDur_Start_{k}")

            elif category == 3:
                starttime = self.duty_original_starttimes[k]
                end_node_id = self.graph.duty_start_end_nodes[k][1]
                in_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.end_node == end_node_id]
                expr = sum(self.x[k][a] * self.graph.graph_nodes[self.graph.graph_arcs[a].start_node].node_task["arrival"] for a in in_arcs if self.graph.graph_arcs[a].arc_type == 4)
                self.model.addConstr(expr <= self.max_duty_length + starttime, name=f"MaxDur_End_{k}")

            elif category == 4:
                start_node_id = self.graph.duty_start_end_nodes[k][0]
                end_node_id = self.graph.duty_start_end_nodes[k][1]
                out_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.start_node == start_node_id]
                in_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.end_node == end_node_id]
                expr = sum(self.x[k][a] * self.graph.graph_nodes[self.graph.graph_arcs[a].start_node].node_task["arrival"] for a in in_arcs if self.graph.graph_arcs[a].arc_type == 4) - \
                       sum(self.x[k][a] * self.graph.graph_nodes[self.graph.graph_arcs[a].end_node].node_task["departure"] for a in out_arcs if self.graph.graph_arcs[a].arc_type == 3)
                self.model.addConstr(expr <= self.max_duty_length, name=f"MaxDur_Flex_{k}")

        self.model.write("Gurobi_model.lp")

    def solve_model(self):
        sol_x = {}
        sol_alpha = {}
        sol_beta = {}

        self.model.optimize()

        if self.model.status in [GRB.OPTIMAL, GRB.TIME_LIMIT]:
            for k in self.unique_duty_ids:
                sol_x[k] = {a: self.x[k][a].X for a in self.x[k]}
                sol_beta[k] = self.beta[k].X
            for i in self.alpha:
                sol_alpha[i] = self.alpha[i].X
            return sol_x, sol_alpha, sol_beta
        else:
            print("No feasible solution found.")
            return None, None, None


class WindowBasedModel_GUROBI_ComplicatedBreaks:
    def __init__(self, graph, duty_categories, duties_require_break, duty_original_starttimes, duty_original_endtimes, time_window, suitable_tasks):
        self.graph = graph
        self.x = {}
        self.y = {}
        self.alpha = {}
        self.beta = {}
        self.cancellation_cost = 3000
        self.break_violation_cost = 2500
        self.max_duty_length = 720
        self.break_types = [0, 30, 45]
        self.max_duty_length_per_breaktype = {}
        self.max_duty_length_per_breaktype[0] = 360
        self.max_duty_length_per_breaktype[30] = 480
        self.max_duty_length_per_breaktype[45] = 720

        self.suitable_tasks = suitable_tasks

        seen_duties = set()
        self.unique_duty_ids = []
        for node in self.graph.graph_nodes.values():
            if node.duty_id not in seen_duties and node.duty_id != -1:
                seen_duties.add(node.duty_id)
                self.unique_duty_ids.append(node.duty_id)

        self.arcs_allowing_break_30 = [arc_id for arc_id, a in self.graph.graph_arcs.items() if a.break_30_possible]
        self.arcs_allowing_break_45 = [arc_id for arc_id, a in self.graph.graph_arcs.items() if a.break_45_possible]
        self.duties_require_break = duties_require_break
        self.duty_categories = duty_categories
        self.duty_original_starttimes = duty_original_starttimes
        self.duty_original_endtimes = duty_original_endtimes

        # Create a new Gurobi environment
        self.env = gp.Env(empty=True)

        # Set WLS license parameters
        self.env.setParam("WLSAccessID", "96daee41-16c8-4add-a427-2028f293967a")
        self.env.setParam("WLSSecret", "23a86426-6aa9-4181-9ebd-774a96e2ffc7")
        self.env.setParam("LicenseID", 2690047)  # Replace with your numeric license ID

        # Start the environment (connects to Gurobi WLS server)
        self.env.start()

        self.model = Model("WindowBasedModel", env = self.env)
        self.model.setParam("Threads", 1)
        self.model.setParam("TimeLimit", 3600)
        self.model.ModelSense = GRB.MINIMIZE

        #self.graph.displayGraph()

    def build_model(self):
        for k in self.unique_duty_ids:
            self.x[k] = {}
            for a, arc in self.graph.graph_arcs.items():
                var_name = f"x_{k}_{a}"
                self.x[k][a] = self.model.addVar(vtype=GRB.BINARY, obj=arc.arc_cost, name=var_name)

        for i, node in self.graph.graph_nodes.items():
            if node.node_type == 1:
                self.alpha[i] = self.model.addVar(vtype=GRB.BINARY, obj=self.cancellation_cost, name=f"alpha_{i}")

        for k in self.unique_duty_ids:
            self.beta[k] = self.model.addVar(vtype=GRB.BINARY, obj=self.break_violation_cost, name=f"beta_{k}")

        #additional variables for complicated break rules
        #variable y defines if duty is long or short
        for k in self.unique_duty_ids:
            self.y[k] = {}
            for break_type in self.break_types:
                var_name = f"y_{k}_{break_type}"
                self.y[k][break_type] = self.model.addVar(vtype=GRB.BINARY, obj=0, name=var_name)

        self.model.update()

        #make hard constraint for breaks
        for k in self.unique_duty_ids:
            self.model.addConstr(self.beta[k] == 0, name=f"Hard_Break_Constraint_{k}")


        for k in self.unique_duty_ids:
            start_node_id = self.graph.duty_start_end_nodes[k][0]
            outgoing_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.start_node == start_node_id]
            self.model.addConstr(sum(self.x[k][a] for a in outgoing_arcs) == 1, name=f"StartArc_{k}")

        for k in self.unique_duty_ids:
            end_node_id = self.graph.duty_start_end_nodes[k][1]
            incoming_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.end_node == end_node_id]
            self.model.addConstr(sum(self.x[k][a] for a in incoming_arcs) == 1, name=f"EndArc_{k}")


        for k in self.unique_duty_ids:
            for node_id in self.graph.graph_nodes:
                #only do this for regular arcs
                if self.graph.graph_nodes[node_id].node_type == 1:
                    in_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.end_node == node_id]
                    out_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.start_node == node_id]
                    self.model.addConstr(sum(self.x[k][a] for a in out_arcs) - sum(self.x[k][a] for a in in_arcs) == 0,
                                         name=f"FlowBalance_{k}_{node_id}")

        #manually enforce that there can only be start arcs assigned to 1, if the respective (dummy) start node is included
        for k in self.unique_duty_ids:
            start_node_id = self.graph.duty_start_end_nodes[k][0]
            prohibited_start_arcs = [a for a, arc in self.graph.graph_arcs.items() if (arc.arc_type in [3] and arc.start_node != start_node_id) or (self.graph.graph_nodes[arc.start_node].node_type in [2,3] and arc.start_node != start_node_id)]
            for a in prohibited_start_arcs:
                self.model.addConstr(self.x[k][a] == 0, name=f"ProhibitedStartArc_{k}")

        # manually enforce that there can only be end arcs assigned to 1, if the respective (dummy) end node is included
        for k in self.unique_duty_ids:
            end_node_id = self.graph.duty_start_end_nodes[k][1]
            prohibited_termination_arcs = [a for a, arc in self.graph.graph_arcs.items() if (arc.arc_type in [4] and arc.end_node != end_node_id) or (self.graph.graph_nodes[arc.end_node].node_type in [4,5] and arc.end_node != end_node_id)]
            for a in prohibited_termination_arcs:
                self.model.addConstr(self.x[k][a] == 0, name=f"ProhibitedTerminationArc_{k}")

        #30 minute break requirements
        for k in self.duties_require_break:
            self.model.addConstr(sum(self.x[k][a] for a in self.arcs_allowing_break_30) + self.beta[k] >= self.y[k][30],
                                 name=f"Break_30_{k}")

        # 45 minute break requirements
        for k in self.duties_require_break:
            self.model.addConstr(sum(self.x[k][a] for a in self.arcs_allowing_break_45) + self.beta[k] >= self.y[k][45],
                                 name=f"Break_45_{k}")

        for k in self.unique_duty_ids:
            expr = sum(self.y[k][break_type] for break_type in self.break_types)
            self.model.addConstr(expr == 1, name=f"Assign_Duty_Length{k}")

        # this was added for the version with suitable tasks in the constraint -- check if this is correct
        # --> if node.node_task["id"] in suitable_tasks[k]
        for i, node in self.graph.graph_nodes.items():
            if node.node_type == 1:
                incoming_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.end_node == i]
                self.model.addConstr(sum(self.x[k][a] for k in self.unique_duty_ids for a in incoming_arcs if a in self.x[k] if node.node_task["id"] in self.suitable_tasks[k]) + self.alpha[i] >= 1,
                                     name=f"Cover_{i}")

        for k in self.unique_duty_ids:
            category = self.duty_categories[k]

            if category == 2:
                endtime = self.duty_original_endtimes[k]
                start_node_id = self.graph.duty_start_end_nodes[k][0]
                out_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.start_node == start_node_id]
                expr = sum(self.x[k][a] * self.graph.graph_nodes[self.graph.graph_arcs[a].end_node].node_task["departure"] for a in out_arcs if self.graph.graph_arcs[a].arc_type == 3)
                max_duty_length_expr = sum(self.max_duty_length_per_breaktype[break_type] * self.y[k][break_type] for break_type in self.break_types)
                self.model.addConstr(expr >= endtime - max_duty_length_expr, name=f"MaxDur_Start_{k}")

            elif category == 3:
                starttime = self.duty_original_starttimes[k]
                end_node_id = self.graph.duty_start_end_nodes[k][1]
                in_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.end_node == end_node_id]
                expr = sum(self.x[k][a] * self.graph.graph_nodes[self.graph.graph_arcs[a].start_node].node_task["arrival"] for a in in_arcs if self.graph.graph_arcs[a].arc_type == 4)
                max_duty_length_expr = sum(self.max_duty_length_per_breaktype[break_type] * self.y[k][break_type] for break_type in self.break_types)
                self.model.addConstr(expr <= max_duty_length_expr + starttime, name=f"MaxDur_End_{k}")

            elif category == 4:
                start_node_id = self.graph.duty_start_end_nodes[k][0]
                end_node_id = self.graph.duty_start_end_nodes[k][1]
                out_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.start_node == start_node_id]
                in_arcs = [a for a, arc in self.graph.graph_arcs.items() if arc.end_node == end_node_id]
                expr = sum(self.x[k][a] * self.graph.graph_nodes[self.graph.graph_arcs[a].start_node].node_task["arrival"] for a in in_arcs if self.graph.graph_arcs[a].arc_type == 4) - \
                       sum(self.x[k][a] * self.graph.graph_nodes[self.graph.graph_arcs[a].end_node].node_task["departure"] for a in out_arcs if self.graph.graph_arcs[a].arc_type == 3)
                max_duty_length_expr = sum(self.max_duty_length_per_breaktype[break_type] * self.y[k][break_type] for break_type in self.break_types)
                self.model.addConstr(expr <= max_duty_length_expr, name=f"MaxDur_Flex_{k}")

        self.model.write("Gurobi_model.lp")

    def solve_model(self):
        sol_x = {}
        sol_alpha = {}
        sol_beta = {}

        self.model.optimize()

        if self.model.status in [GRB.OPTIMAL, GRB.TIME_LIMIT]:
            for k in self.unique_duty_ids:
                sol_x[k] = {a: self.x[k][a].X for a in self.x[k]}
                sol_beta[k] = self.beta[k].X
            for i in self.alpha:
                sol_alpha[i] = self.alpha[i].X
            return sol_x, sol_alpha, sol_beta
        else:
            print("No feasible solution found.")
            return None, None, None

'''
class WindowBasedModel_CPLEX:
    def __init__(self, graph, duty_categories, duties_require_break, duty_original_starttimes, duty_original_endtimes):
        self.graph = graph
        self.x = {}
        #uncovered task
        self.alpha = {}
        #break violation
        self.beta = {}
        #the cost that must be paid if a task is not covered
        self.cancellation_cost = 100
        self.break_violation_cost = 50
        self.max_duty_length = 720

        seen_duties = set()
        self.unique_duty_ids = []
        for node in self.graph.graph_nodes.values():
            #node duty id -1 indicates an uncovered task
            if node.duty_id not in seen_duties and (node.duty_id != -1):
                seen_duties.add(node.duty_id)
                self.unique_duty_ids.append(node.duty_id)

        self.arcs_allowing_break = []
        for arc_id, a in self.graph.graph_arcs.items():
            if a.break_possible == True:
                self.arcs_allowing_break.append(arc_id)
        self.duties_require_break = duties_require_break

        self.duty_categories = duty_categories
        self.duty_original_starttimes = duty_original_starttimes
        self.duty_original_endtimes = duty_original_endtimes

        self.cpx = cplex.Cplex()
        self.cpx.parameters.threads.set(1)
        self.cpx.objective.set_sense(self.cpx.objective.sense.minimize)

        #self.cpx.set_log_stream(None)
        #self.cpx.set_error_stream(None)
        #self.cpx.set_warning_stream(None)
        #self.cpx.set_results_stream(None)

        self.cpx.parameters.timelimit.set(3600)

    def build_model(self):
        # first define the variables, which are binary variables with two indices for duties and arcs
        for k in self.unique_duty_ids:
            x_k = {}
            for a, arc in self.graph.graph_arcs.items():
                varName = "x" + str(k) + str(a)
                x_k[a] = self.cpx.variables.get_num()
                self.cpx.variables.add(obj=[arc.arc_cost], types=["B"], names=[varName])
            self.x[k] = x_k

        # binary variables for uncovered tasks
        for i, node in self.graph.graph_nodes.items():
            #uncovered tasks can only be regular nodes of type 1
            if node.node_type == 1:
                varName = "alpha" + str(i)
                self.alpha[i] = self.cpx.variables.get_num()
                self.cpx.variables.add(obj=[self.cancellation_cost], types=["B"], names=[varName])

        # binary variables for violated breaks
        for k in self.unique_duty_ids:
            varName = "beta" + str(k)
            self.beta[k] = self.cpx.variables.get_num()
            self.cpx.variables.add(obj=[self.break_violation_cost], types=["B"], names=[varName])

        #now define the constraints

        #only one outgoing arc from start node of duty k
        for k in self.unique_duty_ids:
            start_node_id = self.graph.duty_start_end_nodes[k][0]
            #define the outgoing arcs for the start node of duty k
            outgoing_arcs = [arc_id for arc_id, arc in self.graph.graph_arcs.items() if arc.start_node == start_node_id]
            myInd = []
            myVal = []
            for a in outgoing_arcs:
                myInd.append(self.x[k][a])
                myVal.append(1)
            self.cpx.linear_constraints.add(lin_expr=[cplex.SparsePair(ind=myInd, val=myVal)], senses=["E"],
                                            rhs=[1], names=["OnlyOneOutgoingStartArc%d" % (k)])

        # only one incoming arc to termination node of duty k
        for k in self.unique_duty_ids:
            termination_node_id = self.graph.duty_start_end_nodes[k][1]
            # define the incoming arcs for the termination node of duty k
            incoming_arcs = [arc_id for arc_id, arc in self.graph.graph_arcs.items() if
                             arc.end_node == termination_node_id]
            myInd = []
            myVal = []
            for a in incoming_arcs:
                myInd.append(self.x[k][a])
                myVal.append(1)
            self.cpx.linear_constraints.add(lin_expr=[cplex.SparsePair(ind=myInd, val=myVal)], senses=["E"],
                                            rhs=[1], names=["OnlyOneIncomingTerminationArc%d" % (k)])

        #balance of each incoming and outgoing arc
        for k in self.unique_duty_ids:
            for node_id, node in self.graph.graph_nodes.items():
                outgoing_arcs = [arc_id for arc_id, arc in self.graph.graph_arcs.items() if
                                 arc.start_node == node_id]
                incoming_arcs = [arc_id for arc_id, arc in self.graph.graph_arcs.items() if
                                 arc.end_node == node_id]
                myInd = []
                myVal = []
                for a in outgoing_arcs:
                    myInd.append(self.x[k][a])
                    myVal.append(1)
                for a in incoming_arcs:
                    myInd.append(self.x[k][a])
                    myVal.append(-1)
                self.cpx.linear_constraints.add(lin_expr=[cplex.SparsePair(ind=myInd, val=myVal)], senses=["E"],
                                                rhs=[0], names=["BalanceIncomingOutgoingArcs%d%d" % (k, node_id)])

        #include break if required
        for k in self.duties_require_break:
            myInd = []
            myVal = []
            for a in self.arcs_allowing_break:
                myInd.append(self.x[k][a])
                myVal.append(1)
            myInd.append(self.beta[k])
            myVal.append(1)
            self.cpx.linear_constraints.add(lin_expr=[cplex.SparsePair(ind=myInd, val=myVal)], senses=["G"],
                                            rhs=[1], names=["AtLeastOneBreakIfRequired%d" % (k)])

        #determine uncovered tasks
        for i, node in self.graph.graph_nodes.items():
            if node.node_type == 1:
                myInd = []
                myVal = []
                incoming_arcs = [arc_id for arc_id, arc in self.graph.graph_arcs.items() if
                                 arc.end_node == i]
                for k in self.unique_duty_ids:
                    for a in incoming_arcs:
                        myInd.append(self.x[k][a])
                        myVal.append(1)
                myInd.append(self.alpha[i])
                myVal.append(1)
                self.cpx.linear_constraints.add(lin_expr=[cplex.SparsePair(ind=myInd, val=myVal)], senses=["G"],
                                                rhs=[1], names=["DetermineUncoveredTasks%d" % (i)])

        #define the 3 types of maximum duty duration constraints for starting, termination and flexible duties
        for k in self.unique_duty_ids:
            duty_category = self.duty_categories[k]
            #starting duty
            if duty_category == 2:
                duty_endtime = self.duty_original_endtimes[k]
                start_node_id = self.graph.duty_start_end_nodes[k][0]
                # define the outgoing arcs for the start node of duty k
                outgoing_arcs = [arc_id for arc_id, arc in self.graph.graph_arcs.items() if
                                 arc.start_node == start_node_id]
                myInd = []
                myVal = []
                for a in outgoing_arcs:
                    starttime_a = a.end_node["departure"]
                    myInd.append(self.x[k][a])
                    myVal.append(starttime_a)
                self.cpx.linear_constraints.add(lin_expr=[cplex.SparsePair(ind=myInd, val=myVal)], senses=["G"],
                                                rhs=[duty_endtime - self.max_duty_length], names=["MaxDutyLength_StartingDuties%d" % (k)])
            #termination duty
            elif duty_category == 3:
                duty_starttime = self.duty_original_starttimes[k]
                end_node_id = self.graph.duty_start_end_nodes[k][1]
                # define the incoming arcs for the termination node of duty k
                incoming_arcs = [arc_id for arc_id, arc in self.graph.graph_arcs.items() if
                                 arc.end_node == end_node_id]
                myInd = []
                myVal = []
                for a in incoming_arcs:
                    endtime_a = a.start_node["arrival"]
                    myInd.append(self.x[k][a])
                    myVal.append(endtime_a)
                self.cpx.linear_constraints.add(lin_expr=[cplex.SparsePair(ind=myInd, val=myVal)], senses=["L"],
                                                rhs=[self.max_duty_length + duty_starttime],
                                                names=["MaxDutyLength_TerminatingDuties%d" % (k)])
            # flexible duty
            elif duty_category == 4:
                start_node_id = self.graph.duty_start_end_nodes[k][0]
                # define the outgoing arcs for the start node of duty k
                outgoing_arcs = [arc_id for arc_id, arc in self.graph.graph_arcs.items() if
                                 arc.start_node == start_node_id]
                end_node_id = self.graph.duty_start_end_nodes[k][1]
                # define the incoming arcs for the termination node of duty k
                incoming_arcs = [arc_id for arc_id, arc in self.graph.graph_arcs.items() if
                                 arc.end_node == end_node_id]
                myInd = []
                myVal = []
                for a in outgoing_arcs:
                    starttime_a = a.end_node["departure"]
                    myInd.append(self.x[k][a])
                    myVal.append(-starttime_a)
                for a in incoming_arcs:
                    endtime_a = a.start_node["arrival"]
                    myInd.append(self.x[k][a])
                    myVal.append(endtime_a)
                self.cpx.linear_constraints.add(lin_expr=[cplex.SparsePair(ind=myInd, val=myVal)], senses=["L"],
                                                rhs=[self.max_duty_length],
                                                names=["MaxDutyLength_FlexibleDuties%d" % (k)])

    def solve_model(self):
        sol_x = {}
        sol_alpha = {}
        sol_beta = {}

        self.cpx.solve()

        if self.cpx.solution.get_status() != 1 and self.cpx.solution.get_status() != 103 and self.cpx.solution.get_status() != 108:
            myObj = self.cpx.solution.get_objective_value()
            mySol = self.cpx.solution.get_values()
            for k in self.unique_duty_ids:
                sol_x_k = {}
                sol_beta[k] = mySol[self.beta[k]]
                for a in self.graph.graph_arcs:
                    sol_x_k[a] = mySol[self.x[k][a]]
                sol_x[k] = sol_x_k
            for i, node in self.graph.graph_nodes.items():
                if node.node_type == 1:
                    sol_alpha[i] = mySol[self.alpha[i]]

            return sol_x, sol_alpha, sol_beta
'''
