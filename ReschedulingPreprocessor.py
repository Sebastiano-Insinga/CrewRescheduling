import copy
import json
from TimeFormat import getDisplayedTimeFormat

def readDisruption(disruption_file):
    with open(disruption_file, 'r') as f:
        disruption_data = json.load(f)

    disruption_start = getDisplayedTimeFormat(3,disruption_data["disruption_start"])  #get the disruption on the respective day
    disruption_end = getDisplayedTimeFormat(3,disruption_data["disruption_end"])
    disrupted_sections = []
    for section in disruption_data["disrupted_sections"]:
        disrupted_sections.append(section)

    return disruption_start, disruption_end, disrupted_sections

def generateReschedulingInput(original_schedule, duty_breaks, disruption_file, id_mapping):

    VARIANT_AVAILABLE_WHEN_IDLE_DURING_DISRUPTION = 2 # 1 means available at next scheduled task, 2 means available at time of disruption start

    #print(f"the original schedule has {len(original_schedule.keys())} duties.")
    disruption_start, disruption_end, disrupted_sections = readDisruption(disruption_file)

    #print("The start of the disruption is: ", disruption_start)
    #print("The end of the disruption is: ", disruption_end)
    #print("The disrupted sections are: ", disrupted_sections)

    #temporary until we have clarified how we deal with the daily horizon
    #disruption_start = 5
    #disruption_end = 10

    #disruption_start = 400
    #disruption_end = 450

    #define tasks that are performed during the disruption
    disrupted_tasks = {}
    #from now on a driver_id is equivalent to the duty_id, since then we have the full information on breaks, length of the duty etc.
    driver_status = {}
    #driver_status[duty_id] = {"duty_length": 240, "break30done": False, "break45done": False, "available_from_station": station123, "available_at_time": 654}
    for duty_id, duty in original_schedule.items():

        ######################################
        #here we define the status of the break at the time of the disruption
        #the break can be either completed, currently in progress or not started yet
        #then we need to differentiate between 30 mins and 45 mins breaks when the break was completed or in progress

        # in the next step one of them can be set to True
        # if all stay False, a break needs to be planned in rescheduling
        # when a break is currently performed it will be finished and the respective starting time will be later
        # then it will also be seen as "already done"
        break30done = False
        break45done = False
        break30performing = False
        break45performing = False

        #check here if breaks were even considered in the solution of twan, otherwise a break is definitely required
        if duty_breaks[duty_id] != None:
            duty_break = duty_breaks[duty_id]
            break_duration = duty_break[1]-duty_break[0]

            # this means the break was already completed before the disruption happened
            if duty_break[1] <= disruption_start:
                if break_duration == 30:
                    break30done = True
                elif break_duration == 45:
                    break45done = True
            #this means the driver was currently on a break when the disruption happened
            elif duty_break[1] > disruption_start and duty_break[0] <= disruption_start:
                if break_duration == 30:
                    break30performing = True
                elif break_duration == 45:
                    break45performing = True

        #######################################
        for task in original_schedule[duty_id]:
            #regular task during the disruption
            if (task["departure"] < disruption_start and task["arrival"] > disruption_start and id_mapping[task["id"]]["task_type"] == "regular"):
                #regular trip is disrupted
                if id_mapping[task["id"]]["section"] in disrupted_sections:
                    disrupted_tasks[task["id"]] = copy.deepcopy(task)

                    #calculate the driver status for the disrupted task
                    available_from_station = task["destination"]
                    available_at_time = task["arrival"] + (disruption_end - disruption_start)
                    #this is needed because the driver needs to finish the task
                    duty_length = max(0,available_at_time - duty[0]["departure"])

                    driver_status[duty_id] = {"duty_length": duty_length, "break30done": break30done, "break45done": break45done, "available_from_station": available_from_station, "available_at_time": available_at_time}

                #regular trip is not affected by disruption
                else:
                    # calculate the driver status for the disrupted task
                    available_from_station = task["destination"]
                    available_at_time = task["arrival"]
                    #this is needed because the driver needs to finish the task
                    duty_length = max(0,available_at_time - duty[0]["departure"])
                    driver_status[duty_id] = {"duty_length": duty_length, "break30done": break30done, "break45done": break45done, "available_from_station": available_from_station, "available_at_time": available_at_time}

            #deadhead trip during the disruption - but here in fact it does snot make a difference because we assume the train is available after deadhead
            if (task["departure"] < disruption_start and task["arrival"] > disruption_start and id_mapping[task["id"]]["task_type"] == "deadhead"):
                # calculate the driver status for the disrupted task
                available_from_station = task["destination"]
                available_at_time = task["arrival"]
                # this is needed because the driver needs to finish the task
                duty_length = max(0,available_at_time - duty[0]["departure"])
                driver_status[duty_id] = {"duty_length": duty_length, "break30done": break30done, "break45done": break45done, "available_from_station": available_from_station,"available_at_time": available_at_time}

    count_nr_affected_duties = len(driver_status.keys())
    print(f"There are {count_nr_affected_duties} duties directly affected by the disruption.")

    ########################################
    #new way to count affected duties
    new_count_nr_affected_duties = 0
    for duty_id, duty in original_schedule.items():
        duty_counted = False
        for task in original_schedule[duty_id]:
            # regular task during the disruption
            if ((task["arrival"] > disruption_start and task["arrival"] < disruption_end) or (task["departure"] > disruption_start and task["departure"] < disruption_end)) and id_mapping[task["id"]]["task_type"] == "regular":
                # regular trip is disrupted
                if id_mapping[task["id"]]["section"] in disrupted_sections and duty_counted == False:
                    new_count_nr_affected_duties += 1
                    duty_counted = True
            if ((task["arrival"] > disruption_start and task["arrival"] < disruption_end) or (task["departure"] > disruption_start and task["departure"] < disruption_end)) and id_mapping[task["id"]]["task_type"] == "deadhead" and duty_counted == False:
                new_count_nr_affected_duties += 1
                duty_counted = True

    print(f"There are {new_count_nr_affected_duties} duties directly affected by the disruption according to the new computation.")
    ########################################

    for duty_id in original_schedule.keys():
        #this means that a driver was currently not performing a task during the start of the disruption
        #for these cases we also have to consider the case, that a driver might be on a mandatory break
        if duty_id not in driver_status:
            tasks_after_disruption = [task for task in original_schedule[duty_id] if task["departure"] > disruption_start]

            # If there are any tasks after the disruption, find the one with the smallest departure time
            if tasks_after_disruption:
                min_departure_task = min(tasks_after_disruption, key=lambda task: task["departure"])

                available_from_station = min_departure_task["origin"]
                #Variant 1: driver is available at start of the next task
                if VARIANT_AVAILABLE_WHEN_IDLE_DURING_DISRUPTION == 1:
                    #for this varaint the break will be finished anyway and therefore we can set the break to done
                    if break30performing == True:
                        break30done = True
                    if break45performing == True:
                        break45done = True
                    available_at_time = min_departure_task["departure"]
                # Variant 2: driver is immediately available at time of disruption, except if a break is performed, then after the end of break
                elif VARIANT_AVAILABLE_WHEN_IDLE_DURING_DISRUPTION == 2:
                    if break30performing == True:
                        available_at_time = duty_break[1]
                        break30done = True
                    elif break45performing == True:
                        available_at_time = duty_break[1]
                        break45done = True
                    else:
                        available_at_time = disruption_start
                # this is needed because the driver needs to finish the task
                duty_length = max(0,available_at_time - original_schedule[duty_id][0]["departure"])
                driver_status[duty_id] = {"duty_length": duty_length, "break30done": False, "break45done": False,"available_from_station": available_from_station,"available_at_time": available_at_time}

            #else:
            #    print(f"All tasks of duty {duty_id} have alredy been completed")

    #define tasks that are completely open and have not started yet
    open_tasks = {}
    for duty_id, duty in original_schedule.items():
        for task in original_schedule[duty_id]:
            #regular task that would have started after the disruption
            if (task["departure"] > disruption_start):
                open_tasks[task["id"]] = copy.deepcopy(task)



    #print("The disrupted tasks are the following")
    #for task in disrupted_tasks.values():
    #    print(task)
    #print("The open tasks are the following")
    #for task in open_tasks.values():
    #    print(task)
    #print("the status of the drivers is the following")
    #for driver_id, driver in driver_status.items():
    #    print("driver ", driver_id, ": ", driver)

    return driver_status, disrupted_tasks, open_tasks