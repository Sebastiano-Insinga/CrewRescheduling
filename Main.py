import argparse as _argparse
_parser = _argparse.ArgumentParser(description="Crew rescheduling VNS experiments")
_parser.add_argument("--instances", nargs="+", metavar="S01",
                     help="Instance IDs to run, e.g. --instances S01 S02 S03. Default: S01-S18.")
_args = _parser.parse_args()

#Reader functions
from NetworkReader import read_network_data
from InstanceReader import read_instance_data
from ShortestPathReader import read_shortest_path_data
from RollingStockSolutionReader import readRollingStockSolution
from IDMappingReader import readIDMapping
from ReadSolution_Twan import *
from MatchTaskIDsToOriginalInput import *
from OpenRescheduledTasksReader import *
from FixSolution_Twan import *

from pathlib import Path

#Preprocessors
from InstanceAndNetworkPreprocessor import *
from ReschedulingPreprocessor import *
from TransformInstance_Twan import transformInstance_Twan

#Postprocessors
from Extract_Solution_Quality import *

#Methods and analysis
from GreedyCrewScheduling import *
from VNS_Rescheduling import *
from DataAnalysis import perform_data_analysis

#Visualization
from VisualizationTools import *
from Dashboards import *

from TimeFormat import getDisplayedTimeFormat
import csv
import os

#Cluster
from Cluster_Functions import *

'''
instances_folder_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//converted_fixed"
solutions_folder_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//solutions//json"
shortest_path_file_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//literature//converted//frisch-network-shortestpaths.json"
shortest_path_matrix = read_shortest_path_data(shortest_path_file_path)
network_file_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//converted_fixed//frisch-network.json"
network_data = read_network_data(network_file_path)

instance_names = [file.replace(".json","") for file in os.listdir(instances_folder_path) if os.path.isfile(os.path.join(instances_folder_path, file))]
print(instance_names)
instance_names_cleaned = instance_names[4:-3]
print(instance_names_cleaned)

#instance_file_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//literature//converted//58-A-2290T-114L.json"
instance_file_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//literature//converted//52-A-2000T-105L.json"
instance_data = read_instance_data(instance_file_path)

#solution_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//solutions//json//01-A-50T-10L.sol"
solution_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//solutions//json//58-A-2290T-114L.sol"

#print(network_data)
#print(instance_data)

#transformInstance_Twan("Transformed_01-A-50T-10L.tsv", network_data, instance_data)
#perform_data_analysis(network_data, instance_data)

#instance = "52-A-2000T-105L.tsv"
instance = "58-A-2290T-114L.tsv"
crew_scheduling_instance = "C://Users//mschlenk//PycharmProjects//CrewScheduling//SingleDay_Minutes_Transformed_Instances//Transformed-"+instance
id_mapping = readIDMapping("C://Users//mschlenk//PycharmProjects//CrewScheduling//SingleDay_Minutes_ID_Mappings//ID-Mapping-Transformed-"+instance)

reliefPoints = sorted(extractReliefPoints(network_data, instance_data, 30))
print("These are the assumed relief points")
print(reliefPoints)
combined_tasks, infeasible_tasks, nr_combined_tasks = combineCrewTasksByReliefPoints(crew_scheduling_instance, id_mapping, reliefPoints)

#visualizeTasks(combined_tasks)

print("The combined tasks are:")
for task_id, task in combined_tasks.items():
    print(task_id, ": ", task)
print(f"There have {nr_combined_tasks} tasks been combined")
print("##############")
print(f"There are {len(infeasible_tasks)} infeasible tasks")
print("The infeasible tasks are:")
print(infeasible_tasks)
#combineTripsByReliefPoints(network_data, instance_data, reliefPoints)

#assumed train speed is 57 km/h, 3 hour maintenance
#instance = "58-A-2290T-114L.json"
#readRollingStockSolution(instance, solution_path, network_data, instance_data, shortest_path_matrix, 57, 10800, True, '2018-09-10')
'''

"""
for instance in instance_names_cleaned:
    instance_path = instances_folder_path+"//"+instance+".json"
    solution_path = solutions_folder_path+"//"+instance+".sol"

    instance_data = read_instance_data(instance_path)

    #there are 3 display time formats
    #1: display the regular epoch time
    #2: display the date time format (e.g. 2018-09-10 08:10:00)
    #3: display the minute time format starting from 2018-09-10 00:00:00, meaning that 2018-09-10 08:10:00 is displayed as 8*60 + 10 = 490, and every subsequent day is displayed by adding 1440)
    readRollingStockSolution(instance, solution_path, network_data, instance_data, shortest_path_matrix, 57, 10800, 3, False, '2018-09-10')
"""

#instance = "52-A-2000T-105L.tsv"
instance = "58-A-2290T-114L.tsv"
#instance = "15-A-190T-21L.tsv"
#disruption_file = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//disrupted//validation20//52-A-2000T-105L-disrupted_1.json"
#disruption_file = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//disrupted//58-A-2290T-114L-disrupted_2.json"
#disruption_file = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//disrupted//15-A-190T-21L-disrupted_2.json"
#disruption_file = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//validation20_new//52-A-2000T-105L-disrupted_1.json"
disruption_file = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//manuel-instances//manuel//manuel-45-A-1650T-91L-disrupted_1.json"

#greedy_crew_schedule = performGreedyCrewScheduling("C://Users//mschlenk//PycharmProjects//CrewScheduling//SingleDay_Minutes_Transformed_Instances//Transformed-"+instance, 720)

#for duty_id in greedy_crew_schedule.keys():
    #print(f"Duty {duty_id} performs the following tasks {greedy_crew_schedule[duty_id]}")

#avg_duty_length = calculateAverageDutyLength(greedy_crew_schedule)

#print(f"The average duty length is {avg_duty_length/60} hours.")

#crew_scheduling_instance = "C://Users//mschlenk//PycharmProjects//CrewScheduling//SingleDay_Minutes_Transformed_Instances//Transformed-"+instance
#id_mapping = readIDMapping("C://Users//mschlenk//PycharmProjects//CrewScheduling//SingleDay_Minutes_ID_Mappings//ID-Mapping-Transformed-"+instance)
#print(id_mapping)
#locomotives = {task['locomotive'] for task in id_mapping.values()}
#print(locomotives)

#plot_gantt_chart_locomotives(instance, greedy_crew_schedule, locomotives, id_mapping)
'''
for instance in instance_names_cleaned:
    greedy_crew_schedule = performGreedyCrewScheduling("C://Users//mschlenk//PycharmProjects//CrewScheduling//SingleDay_Minutes_Transformed_Instances//Transformed-" + instance + ".tsv",720)
    id_mapping = readIDMapping("C://Users//mschlenk//PycharmProjects//CrewScheduling//SingleDay_Minutes_ID_Mappings//ID-Mapping-Transformed-" + instance + ".tsv")
    locomotives = {task['locomotive'] for task in id_mapping.values()}
    plot_gantt_chart_locomotives(instance, greedy_crew_schedule, locomotives, id_mapping)
'''

#calculateInitialSolution(driver_status, open_tasks, 1040, 1160, 720)

########################################################################################################################
'''
instance = "58-A-2290T-114L.tsv"
#perform the VNS Run on the weekly instance
crew_scheduling_instance = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Weekly_Minutes_Transformed_Instances//Transformed-"+instance
id_mapping = readIDMapping("C://Users//mschlenk//PycharmProjects//CrewScheduling//Weekly_Minutes_ID_Mappings//ID-Mapping-Transformed-"+instance)

solution_twan = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Dense_Weekly_Solution_Twan.xlsx"
new_format_solution_twan = readSolution_Twan(solution_twan, crew_scheduling_instance)

#performAnalysis_Solution_Twan(solution_twan, crew_scheduling_instance, shortest_path_matrix, 100)

driver_status, disrupted_tasks, open_tasks = generateReschedulingInput(new_format_solution_twan, disruption_file, id_mapping)

existing_duties, new_duties = calculateInitialSolution(new_format_solution_twan, driver_status, open_tasks, 500, 550, 720)

print(calcDifferenceToOriginalSchedule(greedy_crew_schedule, existing_duties, open_tasks))

run_VNS(new_format_solution_twan, existing_duties, open_tasks, 3600, 100, id_mapping)

#for weekly horizon
#plot_gantt_chart_locomotives("Solution_Twan-58-A-2290T-114L", new_format_solution_twan, locomotives, id_mapping)
'''
#instance = "58-A-2290T-114L"
instance = "15-A-190T-21L"
#instance_file_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//literature//converted//51-A-1950T-103L.json"
#instance_file_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//literature//converted//52-A-2000T-105L.json"
#instance_data = read_instance_data(instance_file_path)

#solution_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//solutions//json//01-A-50T-10L.sol"
#solution_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//solutions//json//58-A-2290T-114L.sol"
solution_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Rolling_Stock_Rescheduling//new//58-A-2290T-114L.sol"

'''
#
########################################################################################################################
#experiment withy the real rescheduling solutions by Roberto
instance_file_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//literature//converted//"+instance+".json"
instance_data = read_instance_data(instance_file_path)
solution_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//solutions-resch-manuel//solutions-resch-manuel//manuel//manuel-15-A-190T-21L-disrupted_1.json_428000_t0_i696717_s2816381868.sol"
#readRollingStockSolution(instance, solution_path, network_data, instance_data, shortest_path_matrix, 57, 10800, 3, False, '2018-09-10')

original_instance_path = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Weekly_Minutes_Transformed_Instances//Transformed-"+instance+".tsv"
rescheduled_instance_path = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Rescheduled_Weekly_Minutes_Transformed_Instances//Transformed-"+instance+".tsv"
id_mapping_path = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Rescheduled_Weekly_Minutes_ID_Mappings//ID-Mapping-Transformed-"+instance+".tsv"
matchedID_rescheduling_instance_path = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Final_Rescheduled_IDMatched_Instances//Transformed-"+instance+".tsv"
matchedID_id_mapping_path = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Final_Rescheduled_IDMatched_ID_Mappings//ID-Mapping-Transformed-"+instance+".tsv"

#matchTaskIDsToOriginalInput(original_instance_path, rescheduled_instance_path, id_mapping_path, matchedID_rescheduling_instance_path, matchedID_id_mapping_path)
#########################################################################################################################
'''

'''
#import all solutions by Roberto, modify them to my format and then update the IDs so they match to the original input
#read the rescheduled solution
for instance in instance_names_cleaned:
    instance_file_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//literature//converted//"+instance+".json"
    # instance_file_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//literature//converted//52-A-2000T-105L.json"
    instance_data = read_instance_data(instance_file_path)

    # solution_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//solutions//json//01-A-50T-10L.sol"
    # solution_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//solutions//json//58-A-2290T-114L.sol"
    solution_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Rolling_Stock_Rescheduling//new//"+instance+".sol"

    readRollingStockSolution(instance, solution_path, network_data, instance_data, shortest_path_matrix, 57, 10800, 3, False, '2018-09-10')
##############################################################
for instance in instance_names_cleaned:
    original_instance_path = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Weekly_Minutes_Transformed_Instances//Transformed-"+instance+".tsv"
    rescheduled_instance_path = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Rescheduled_Weekly_Minutes_Transformed_Instances//Transformed-"+instance+".tsv"
    id_mapping_path = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Rescheduled_Weekly_Minutes_ID_Mappings//ID-Mapping-Transformed-"+instance+".tsv"
    matchedID_rescheduling_instance_path = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Rescheduled_IDMatched_Weekly_Minutes_Instances//Transformed-"+instance+".tsv"
    matchedID_id_mapping_path = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Rescheduled_IDMatched-IDMappings//ID-Mapping-Transformed-"+instance+".tsv"


    matchTaskIDsToOriginalInput(original_instance_path, rescheduled_instance_path, id_mapping_path, matchedID_rescheduling_instance_path, matchedID_id_mapping_path)

########################################################################################################################
'''
functions = []

#perform the VNS Run on the weekly instance
#instance = "15-A-190T-21L.tsv"
#instance = "41-A-1450T-82L-randomized.tsv"
#instance = "45-A-1650T-91L.tsv"
#instance = "50-A-1900T-102L-randomized.tsv"
#instance = "51-A-1950T-103L.tsv"
#instance = "58-A-2290T-114L.tsv"


#use this code to transform the cluster output to a table version of the results
'''
document = "output_8774323.log"
input_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Text_Outputs//"+document
output_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Extracted_Text_Outputs//Extracted_"+document
#extract_solution_quality_section_and_loco_knowledge(input_path, output_path)
extract_solution_quality_sideways_table(input_path, output_path)
extract_solution_quality_sideways_table_excel(input_path, output_path)
'''

'''
#this is a loop to iterate over all instances in the Textoutput Folder and extract the solution quality
input_folder = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Text_Outputs"
for log_file in os.listdir(input_folder):
    input_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Text_Outputs//" + log_file
    output_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Extracted_Text_Outputs//Extracted_" + log_file
    extract_solution_quality_sideways_table_excel(input_path, output_path)

#combine all the extracted excel files to one combined excel table
combine_excel_tables(
    input_folder="C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Extracted_Text_Outputs",
    output_folder="C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Combined_Excel_Files",
    suffix="_1.0_1.0_720.xlsx"
)
'''

'''
#INCLUDING SPARE DRIVERS
#this is a loop to iterate over all instances in the Textoutput Folder and extract the solution quality
input_folder = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Text_Outputs"
for log_file in os.listdir(input_folder):
    input_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Text_Outputs//" + log_file
    output_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Extracted_Text_Outputs//Extracted_" + log_file
    extract_solution_quality_sideways_table_excel_incl_sparedrivers(input_path, output_path)


#combine all the extracted excel files to one combined excel table
combine_excel_tables(
    input_folder="C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Extracted_Text_Outputs",
    output_folder="C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Combined_Excel_Files",
    suffix="_1.0_1.0_720_0.2.xlsx"
)
'''

'''
#FOR THE GREEDY SOLUTION
#INCLUDING SPARE DRIVERS
#this is a loop to iterate over all instances in the Textoutput Folder and extract the solution quality
input_folder = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Text_Outputs"
for log_file in os.listdir(input_folder):
    input_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Text_Outputs//" + log_file
    output_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Extracted_Text_Outputs//Extracted_" + log_file
    extract_solution_quality_sideways_table_excel_greedy(input_path, output_path)


#combine all the extracted excel files to one combined excel table
combine_excel_tables(
    input_folder="C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Extracted_Text_Outputs",
    output_folder="C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Combined_Excel_Files",
    suffix="_1.0_1.0_720.xlsx"
)
'''
'''
#this is for analyzing duty lengths
#this is a loop to iterate over all instances in the Textoutput Folder and extract the solution quality
input_folder = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Analyze_Duty_Lengths//Text_Inputs"
for log_file in os.listdir(input_folder):
    input_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Analyze_Duty_Lengths//Text_Inputs//" + log_file
    output_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Analyze_Duty_Lengths//Extracted_Outputs//Extracted_" + log_file
    extract_duty_lengths(input_path, output_path)
'''
#fix_slurm_files("C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Slurm_Files")

#generate_slurm_files("run_rescheduling_test.slurm", "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Slurm_Files", all_instances)

#generate_master_slurm("C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//Computational_Experiments//Slurm_Files")



import csv as csv_module

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_default_instances = [f"S{str(i).zfill(2)}.tsv" for i in range(1, 19)]
all_instances = [f"{i}.tsv" if not i.endswith(".tsv") else i for i in _args.instances] if _args.instances else _default_instances

window_size_set = [300]
runs_per_window_set = [1]
randomization_iterations = [1]
method = "DP"
max_dh_duration = 720
loco_types = [0, 1, 2, 3]
section_types = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
min_loco_knowledge_set = [1.0]
min_section_knowledge_set = [1.0]

output_dir = os.path.join(BASE_DIR, "results_experiments", "28-04")
os.makedirs(output_dir, exist_ok=True)
csv_path = os.path.join(output_dir, "results.csv")
csv_columns = [
    "instance", "window_size", "runs_per_window", "rand_iter", "method",
    "max_dh_duration", "min_loco_knowledge", "min_section_knowledge",
    "disruption_start", "disruption_end",
    "nr_deadheads", "deadheading_costs", "nr_uncovered_tasks",
    "nr_breaks_violated", "nr_spared_drivers", "total_time_seconds",
]
write_header = not os.path.exists(csv_path)
with open(csv_path, "a", newline="") as _f:
    if write_header:
        csv_module.DictWriter(_f, fieldnames=csv_columns).writeheader()

network_file_path = os.path.join(BASE_DIR, "single_type", "network.json")
network_data = read_network_data(network_file_path)

for instance in all_instances:
    inst_id = instance.replace(".tsv", "")
    for window_size in window_size_set:
        for runs_per_window in runs_per_window_set:
            for min_loco_knowledge in min_loco_knowledge_set:
                for min_section_knowledge in min_section_knowledge_set:
                    for rand_iter in randomization_iterations:
                        print("#################################################################################")
                        print(f"Instance: {inst_id} | Window size: {window_size} | Runs per window: {runs_per_window} | Method: {method} | Min loco knowledge: {min_loco_knowledge} | Min section knowledge: {min_section_knowledge} | Max dh duration: {max_dh_duration} | Random iteration: {rand_iter}")

                        crew_scheduling_instance = os.path.join(BASE_DIR, "Final_Rescheduled_Instances", f"Transformed-{inst_id}.tsv")
                        id_mapping = readIDMapping(os.path.join(BASE_DIR, "Final_Rescheduled_ID_Mappings", f"ID-Mapping-Transformed-{inst_id}.tsv"))
                        disruption_file = os.path.join(BASE_DIR, "single_type", f"{inst_id}.json")
                        path_rescheduled_open_tasks = os.path.join(BASE_DIR, "Final_Rescheduled_Instances", f"Transformed-{inst_id}.tsv")
                        rescheduled_id_mapping = readIDMapping(os.path.join(BASE_DIR, "Final_Rescheduled_ID_Mappings", f"ID-Mapping-Transformed-{inst_id}.tsv"))
                        solution_twan_txt_format = os.path.join(BASE_DIR, "results_twan_txt", f"Transformed-{inst_id}_sol.txt")

                        locomotives = {task['locomotive'] for task in id_mapping.values()}

                        disruption_start, disruption_end, disrupted_sections = readDisruption(disruption_file)
                        print(f"Disruption starts at {disruption_start} and ends at {disruption_end}.")

                        internal_format_solution_twan, uncovered_tasks_twan, duty_breaks, loco_knowledge, section_knowledge, suitable_tasks = readSolution_Twan_txt_Format_incl_Uncovered(
                            solution_twan_txt_format, crew_scheduling_instance, id_mapping,
                            loco_types, section_types, min_loco_knowledge, min_section_knowledge
                        )

                        fixed_internal_format_solution_twan, fixed_duty_breaks, loco_knowledge, section_knowledge, suitable_tasks = fixSolutionTwan(
                            internal_format_solution_twan, uncovered_tasks_twan, duty_breaks,
                            loco_knowledge, section_knowledge, suitable_tasks,
                            loco_types, section_types, min_loco_knowledge, min_section_knowledge,
                            network_data, instance, disruption_start
                        )

                        driver_status, disrupted_tasks, open_tasks = generateReschedulingInput(
                            fixed_internal_format_solution_twan, fixed_duty_breaks, disruption_file, id_mapping
                        )

                        rescheduled_open_tasks = readOpenRescheduledTasks(path_rescheduled_open_tasks)

                        tasks_already_performed = [tid for tid, t in rescheduled_open_tasks.items() if t["departure"] <= disruption_start]
                        for tid in tasks_already_performed:
                            rescheduled_open_tasks.pop(tid, None)

                        for duty_id, st in suitable_tasks.items():
                            for task_id, task in rescheduled_open_tasks.items():
                                if task_id not in id_mapping.keys():
                                    suitable_tasks[duty_id].append(task["id"])

                        print(f"There is a disruption from {disruption_start} to {disruption_end}.")

                        existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, spare_driver_ids = calculateInitialSolution(
                            fixed_internal_format_solution_twan, driver_status, rescheduled_open_tasks,
                            disruption_start, disruption_end, 720, id_mapping, suitable_tasks
                        )

                        step_results, schedule_figures, final_metrics = run_VNS(
                            method, fixed_internal_format_solution_twan, existing_duties, duty_breaks,
                            uncovered_tasks, rescheduled_open_tasks, 3600, 100, rescheduled_id_mapping,
                            disruption_start, disruption_end, window_size, runs_per_window,
                            network_data, locomotives, suitable_tasks, max_dh_duration, rand_iter, spare_driver_ids
                        )

                        row = {
                            "instance": inst_id,
                            "window_size": window_size,
                            "runs_per_window": runs_per_window,
                            "rand_iter": rand_iter,
                            "method": method,
                            "max_dh_duration": max_dh_duration,
                            "min_loco_knowledge": min_loco_knowledge,
                            "min_section_knowledge": min_section_knowledge,
                            "disruption_start": disruption_start,
                            "disruption_end": disruption_end,
                            **final_metrics,
                        }
                        with open(csv_path, "a", newline="") as _f:
                            csv_module.DictWriter(_f, fieldnames=csv_columns).writerow(row)
                        print(f"Result saved: {row}")
