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
instance = "41-A-1450T-82L-randomized.tsv"
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



instance_set_20 = ["01-A-50T-10L-randomized.tsv", "05-A-90T-16L-randomized.tsv", "08-A-120T-18L-randomized.tsv", "09-A-130T-19L-randomized.tsv", "10-A-140T-19L.tsv", "14-A-180T-21L-randomized.tsv", "17-A-250T-24L-randomized.tsv", "19-A-350T-30L.tsv", "21-A-450T-37L-randomized.tsv", "23-A-550T-43L.tsv", "27-A-750T-54L-randomized.tsv", "35-A-1150T-70L.tsv", "37-A-1250T-72L.tsv", "38-A-1300T-76L.tsv", "39-A-1350T-79L-randomized.tsv", "41-A-1450T-82L-randomized.tsv", "45-A-1650T-91L.tsv", "50-A-1900T-102L-randomized.tsv", "51-A-1950T-103L.tsv", "52-A-2000T-105L.tsv"]

instance_set = ["15-A-190T-21L.tsv", "41-A-1450T-82L-randomized.tsv",  "45-A-1650T-91L.tsv", "50-A-1900T-102L-randomized.tsv", "51-A-1950T-103L.tsv", "58-A-2290T-114L.tsv"]
#instance_set = ["45-A-1650T-91L.tsv"]
#window_size_set = [150, 300, 450]
window_size_set = [300]
#runs_per_window_set = [1,5,10]
runs_per_window_set = [1]
method = "DP"

# ===== CONFIGURATION: Select which instances to run =====
# Test with single instance using custom TSV solution file
# all_instances = ["01-A-50T-10L-randomized.tsv"]

# Use all instances that have solution files available in SOLUTION_FOLDER
all_instances = ["01-A-50T-10L-randomized.tsv",
                 "05-A-90T-16L-randomized.tsv",
                 "08-A-120T-18L-randomized.tsv",
                 "09-A-130T-19L-randomized.tsv",
                 "14-A-180T-21L.tsv",
                 "15-A-190T-21L-randomized.tsv",
                 "17-A-250T-24L-randomized.tsv",
                 "21-A-450T-37L-randomized.tsv",
                 "23-A-550T-43L.tsv",
                 "27-A-750T-54L.tsv",
                 "35-A-1150T-70L.tsv",
                 "37-A-1250T-72L.tsv",
                 "38-A-1300T-76L.tsv",
                 "39-A-1350T-79L-randomized.tsv",
                 "41-A-1450T-82L-randomized.tsv",
                 "45-A-1650T-91L.tsv",
                 "50-A-1900T-102L-randomized.tsv",
                 "51-A-1950T-103L.tsv",
                 "52-A-2000T-105L.tsv"]

# Uncomment below for fewer instances (testing)
# all_instances = ["01-A-50T-10L-randomized.tsv"]
# ==================================================

# Custom solution file mappings (instance_name -> path_to_solution_file)
CUSTOM_SOLUTION_FILES = {
    "01-A-50T-10L-randomized.tsv": "C:\\Users\\sebastiano insinga\\Desktop\\Vienna\\TESI\\Austrian Istances\\results\\Twan_format(txt)\\Transformed-01-A-50T-10L-randomized_sol.txt",
    # Add more instances as needed
}

# Function to auto-discover solution files
def find_solution_file(instance_name, solution_folder):
    """
    Automatically find solution file for an instance in the given folder.
    Looks for files matching pattern: Transformed-<instance_name_without_ext>_sol.txt
    """
    import os
    instance_base = instance_name.replace(".tsv", "")
    solution_filename = f"Transformed-{instance_base}_sol.txt"
    solution_path = os.path.join(solution_folder, solution_filename)
    
    if os.path.exists(solution_path):
        return solution_path
    return None

# Solution folder path
SOLUTION_FOLDER = "C:\\Users\\sebastiano insinga\\Desktop\\Vienna\\TESI\\Austrian Istances\\results\\Twan_format(txt)"

loco_types = [0,1,2,3]
section_types = [0,1,2,3,4,5,6,7,8,9]

max_dh_duration = 720 #no limit on the deadhead duration
#max_dh_duration = 60 #max 1 hour crew deadhead

min_loco_knowledge_set = [1.0]
min_section_knowledge_set = [1.0]

min_loco_knowledge_set = [1.0]
min_section_knowledge_set = [1.0]

network_file_path = "C:\\Users\\sebastiano insinga\\Desktop\\General\\Code_CrewRescheduling_Manuel\\Computational_Experiments\\Instances\\frisch-network.json"
network_data = read_network_data(network_file_path)

#randomization_iterations = [1,2,3,4,5,6,7,8,9,10]
randomization_iterations = [1]

for instance in all_instances:
    for window_size in window_size_set:
        for runs_per_window in runs_per_window_set:
            for min_loco_knowledge in min_loco_knowledge_set:
                for min_section_knowledge in min_section_knowledge_set:
                    for rand_iter in randomization_iterations:
                        print("#################################################################################")
                        print(f"Instance: {instance} | Window size: {window_size} | Runs per window: {runs_per_window} | Method: {method} | Min locomotive knowledge: {min_loco_knowledge} | Min section knowledge: {min_section_knowledge} | Max deadheadh duration: {max_dh_duration} | Random iteration: {rand_iter}")

                        #####################################################################
                        #here we aim to make the data reading and processing step more unified
                        path_instance_folder = "C:\\Users\\sebastiano insinga\\Desktop\\General\\Code_CrewRescheduling_Manuel\\Computational_Experiments\\Instances"
                        time_limit = "12"  # here you have the options 10 or 12 hours
                        sol_type = "2"  # here you have the options 1 (only feasible duties) or 2 (also infeasible duties)

                        crew_scheduling_instance = path_instance_folder + "\\Crew_Scheduling_Instances\\Transformed-" + instance
                        id_mapping = readIDMapping(path_instance_folder + "\\ID_Mappings_Scheduling\\ID-Mapping-Transformed-" + instance)
                        disruption_file = path_instance_folder + "\\Disruption_Files\\manuel-" + instance.replace(".tsv", "") + "-disrupted_1.json"
                        path_rescheduled_open_tasks = path_instance_folder + "\\Crew_Rescheduling_Instances\\Transformed-" + instance
                        rescheduled_id_mapping = readIDMapping(path_instance_folder + "\\ID_Mappings_Rescheduling\\ID-Mapping-Transformed-" + instance)
                        solution_twan_txt_format = path_instance_folder + "\\Original_Crew_Plans\\Transformed-" + instance.replace(".tsv", "_sol_" + time_limit + "_" + sol_type + ".txt")
                        ######################################################################
                        
                        # Try to use custom/auto-discovered solution file
                        if instance in CUSTOM_SOLUTION_FILES:
                            solution_twan_txt_format = CUSTOM_SOLUTION_FILES[instance]
                            print(f"Using custom solution file: {solution_twan_txt_format}")
                        else:
                            # Try to auto-discover solution file from folder
                            discovered_solution = find_solution_file(instance, SOLUTION_FOLDER)
                            if discovered_solution:
                                solution_twan_txt_format = discovered_solution
                                print(f"Using auto-discovered solution file: {solution_twan_txt_format}")


                        # perform the VNS Run on the weekly day instance
                        ###crew_scheduling_instance = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Weekly_Minutes_Transformed_Instances//Transformed-" + instance
                        ###id_mapping = readIDMapping("C://Users//mschlenk//PycharmProjects//CrewScheduling//Weekly_Minutes_ID_Mappings//ID-Mapping-Transformed-" + instance)

                        ###disruption_file = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//manuel-instances//manuel//manuel-" + instance.replace(".tsv","") + "-disrupted_1.json"

                        #path for the 20 instances
                        #path_rescheduled_open_tasks = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Rescheduled_IDMatched_Weekly_Minutes_Instances//Transformed-"+instance
                        #Path for the first 6 instances
                        ###path_rescheduled_open_tasks = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Final_Rescheduled_IDMatched_Instances//Transformed-"+instance

                        rescheduled_open_tasks = readOpenRescheduledTasks(path_rescheduled_open_tasks)

                        #print(f"these are the rescheduled open tasks {rescheduled_open_tasks}")

                        #path for 20 instances
                        #rescheduled_id_mapping = readIDMapping("C://Users//mschlenk//PycharmProjects//CrewScheduling//Rescheduled_IDMatched-IDMappings//ID-Mapping-Transformed-" + instance)
                        #Path for 6 instances
                        ###rescheduled_id_mapping = readIDMapping("C://Users//mschlenk//PycharmProjects//CrewScheduling//Final_Rescheduled_IDMatched_ID_Mappings//ID-Mapping-Transformed-"+instance)


                        #perform the VNS Run on the single day instance
                        #crew_scheduling_instance = "C://Users//mschlenk//PycharmProjects//CrewScheduling//SingleDay_Minutes_Transformed_Instances//Transformed-"+instance
                        #id_mapping = readIDMapping("C://Users//mschlenk//PycharmProjects//CrewScheduling//SingleDay_Minutes_ID_Mappings//ID-Mapping-Transformed-"+instance)


                        locomotives = {task['locomotive'] for task in id_mapping.values()}
                        #this solution corresponds to the "58-A-2290T-114L.tsv" instance
                        time_limit = "12" #here you have the options 10 or 12 hours
                        sol_type = "2" #here you have the options 1 (only feasible duties) or 2 (also infeasible duties)

                        #this is the path for the 6 instances
                        ###solution_twan_txt_format = "C://Users//mschlenk//PycharmProjects//CrewScheduling//results_Twan//Transformed-"+instance.replace(".tsv","_sol_"+time_limit+"_"+sol_type+".txt")
                        #this is the path for th 20 instances
                        #solution_twan_txt_format = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//20_Instances_Paper//Original_Plan_Solutions//Transformed-" + instance.replace(".tsv", "_sol_" + time_limit + "_" + sol_type + ".txt")

                        disruption_start, disruption_end, disrupted_sections = readDisruption(disruption_file)
                        print(f"Disruption starts at {disruption_start} and ends at {disruption_end}. The disrupted sections are {disrupted_sections}")
                        internal_format_solution_twan, uncovered_tasks_twan, duty_breaks, loco_knowledge, section_knowledge, suitable_tasks = readSolution_Twan_txt_Format_incl_Uncovered(solution_twan_txt_format, crew_scheduling_instance, id_mapping, loco_types, section_types, min_loco_knowledge, min_section_knowledge)
                        #print("Reading the new txt format of Twan's solution was successfull")
                        #print(f"In Twan's solution there are {len(uncovered_tasks_twan)} uncovered tasks, namely: {uncovered_tasks_twan}")

                        #fix twans solution here in the sense that there are no uncovered tasks anymore and all duties have the correct breaks
                        fixed_internal_format_solution_twan, fixed_duty_breaks, loco_knowledge, section_knowledge, suitable_tasks = fixSolutionTwan(internal_format_solution_twan, uncovered_tasks_twan, duty_breaks, loco_knowledge, section_knowledge, suitable_tasks, loco_types, section_types, min_loco_knowledge, min_section_knowledge, network_data, instance, disruption_start)

                        #getKnowledgeStatistics(loco_knowledge, section_knowledge)

                        #this solution corresponds to the "58-A-2290T-114L.tsv" instance
                        #solution_twan = "C://Users//mschlenk//PycharmProjects//CrewScheduling//Solution_Twan.xlsx"
                        #internal_format_solution_twan, duty_breaks = readSolution_Twan(solution_twan, crew_scheduling_instance)

                        #performAnalysis_Solution_Twan(solution_twan, crew_scheduling_instance, shortest_path_matrix, 100)

                        driver_status, disrupted_tasks, open_tasks = generateReschedulingInput(fixed_internal_format_solution_twan, fixed_duty_breaks, disruption_file, id_mapping)


                        #now I must remove the task that have started before the start of the disruption
                        tasks_already_performed = []
                        for task_id, task in rescheduled_open_tasks.items():
                            if task["departure"] <= disruption_start:
                                tasks_already_performed.append(task_id)
                        for task_id in tasks_already_performed:
                            rescheduled_open_tasks.pop(task_id, None)

                        for duty_id, st in suitable_tasks.items():
                            for task_id, task in rescheduled_open_tasks.items():
                                #this makes sure that the new deadheads can be covered by all drivers
                                if task_id not in id_mapping.keys():
                                    suitable_tasks[duty_id].append(task["id"])

                        print(f"There is a disruption from {disruption_start} to {disruption_end}.")
                        #for the current instanc it should be from 1717 to 2112

                        existing_duties, duty_breaks, uncovered_tasks, suitable_tasks, spare_driver_ids = calculateInitialSolution(fixed_internal_format_solution_twan, driver_status, rescheduled_open_tasks, disruption_start, disruption_end, 720, id_mapping, suitable_tasks)
                        #existing_duties, new_duties = calculateInitialSolution(new_format_solution_twan, driver_status, open_tasks, 5, 10, 720)

                        #print(f"There are {len(existing_duties)} existing duties!")

                        #print(f"There are {len(uncovered_tasks)} uncovered tasks")
                        #print("The uncovered tasks are the following:")
                        #print(uncovered_tasks)
                        #print("The difference to the original schedule is")
                        #print(calcDifferenceToOriginalSchedule(greedy_crew_schedule, existing_duties, open_tasks))

                        #run_VNS(internal_format_solution_twan, existing_duties, duty_breaks, uncovered_tasks, open_tasks, 3600, 100, id_mapping)

                        printInstanceCharacteristics(method, fixed_internal_format_solution_twan, existing_duties, duty_breaks, uncovered_tasks, rescheduled_open_tasks, 3600, 100, rescheduled_id_mapping, disruption_start, disruption_end, window_size, runs_per_window, network_data, locomotives, suitable_tasks, max_dh_duration, rand_iter, spare_driver_ids)
                        #step_results, schedule_figures = run_VNS(method, fixed_internal_format_solution_twan, existing_duties, duty_breaks, uncovered_tasks, rescheduled_open_tasks, 3600, 100, rescheduled_id_mapping, disruption_start, disruption_end, window_size, runs_per_window, network_data, locomotives, suitable_tasks, max_dh_duration, rand_iter, spare_driver_ids)


                        #functions.append((window_size, runs_per_window, step_results))

                        #app = createScheduleDashboard_MultiWindow(instance, method, window_size, runs_per_window, schedule_figures)
                        #if __name__ == "__main__":
                        #    app.run(debug=True)

                        #do the randomized iterations only for the DP run, for model one run is sufficient
                        if method == "model":
                            break

#plotStepwiseImprovement(functions)
