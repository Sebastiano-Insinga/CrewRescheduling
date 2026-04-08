import csv
from datetime import datetime
import json
from ReschedulingPreprocessor import getDisplayedTimeFormat

def readRollingStockSolution(instance, sol_filename, network_data, instance_data, shortest_path_matrix, train_speed, maintenance_time, displayTimeFormat,  extractSingleDay_Bool, extractedSingleDay_Date):
    with open(sol_filename, "r") as file:
        solution_data = json.load(file)

    locomotives = []
    # Step 2: Accessing the data
    for trip in solution_data:
        if trip['locomotive'] not in locomotives and trip['locomotive'] != "canceled":
            locomotives.append(trip['locomotive'])
        #print(f"Trip ID: {trip['id_trip']}, Locomotive: {trip['locomotive']}, "
        #      f"Maintenance at Departure: {trip['maintenance_at_departure']}, "
        #      f"Maintenance at Destination: {trip['maintenance_at_destination']}")

    #print(set(locomotives))

    locomotive_set = set(locomotives)
    locomotive_tasks = {}
    for locomotive in locomotive_set:
        #initialize empty list of trips
        for trip in solution_data:
            if trip['locomotive'] == locomotive:
                if locomotive in locomotive_tasks.keys():
                    locomotive_tasks[locomotive].append(trip)
                else:
                    locomotive_tasks[locomotive] = [trip]

    #print(locomotive_tasks)

    tasks_to_write = []
    id_mapping = {}
    id = 1
    for locomotive in locomotive_tasks.keys():
        print(f"These are the trips for locomotive {locomotive}")
        previous_trip = None
        previous_departure = None
        previous_arrival = None
        previous_origin = None
        previous_destination = None
        previous_maintenance_at_departure = None
        previous_maintenance_at_destination = None
        for trip in locomotive_tasks[locomotive]:
            departure = instance_data['train_sections'][trip['id_trip']]['departure_time']
            arrival =  instance_data['train_sections'][trip['id_trip']]['arrival_time']
            section_id = instance_data['train_sections'][trip['id_trip']]['section']
            origin = network_data['sections'][section_id]['origin']
            destination = network_data['sections'][section_id]['destination']
            maintenance_at_departure = trip['maintenance_at_departure']
            maintenance_at_destination = trip['maintenance_at_destination']

            #filter out all electrification tasks!
            if origin != destination:
                #this makes sure that if the extractSingleDay_Bool parameter is true, only trips on the respective day of extractedSingleDay_Date will be added to the instance
                trip_day = datetime.fromtimestamp(arrival).date()
                single_day_contains_trip = True
                #if the boolean parameter is false, then it will single_day_contains_trip will always be true und therefore not exclude any trips from the instance file
                if extractSingleDay_Bool == True:
                    if str(trip_day) != extractedSingleDay_Date:
                        single_day_contains_trip = False


                #insert deadhead trips
                if previous_destination != None:
                    if previous_destination != origin:
                        if previous_maintenance_at_destination == "true" and single_day_contains_trip:
                            #print(f"Maintenance at Station {previous_destination} (Time: {round(maintenance_time / 3600, 2)} hours / From {datetime.fromtimestamp(previous_arrival).replace(microsecond=0)} to {datetime.fromtimestamp(previous_arrival + maintenance_time).replace(microsecond=0)})")
                            print(
                                f"Maintenance at Station {previous_destination} (Time: {round(maintenance_time / 3600, 2)} hours / From {getDisplayedTimeFormat(displayTimeFormat,previous_arrival)} to {getDisplayedTimeFormat(displayTimeFormat,previous_arrival + maintenance_time)})")
                            deadhead_distance = shortest_path_matrix[str(previous_destination)][str(origin)]['weight']
                            # calculate travel time in seconds
                            deadhead_travel_time = ((deadhead_distance / 1000) / train_speed) * 3600
                            #print(f"Deadhead trip from Station {previous_destination} to Station {origin} (Time: {round(deadhead_travel_time / 3600, 2)} hours / From {datetime.fromtimestamp(previous_arrival + maintenance_time).replace(microsecond=0)} to {datetime.fromtimestamp(round(previous_arrival + maintenance_time + deadhead_travel_time,2)).replace(microsecond=0)})")
                            print(
                                f"Deadhead trip from Station {previous_destination} to Station {origin} (Time: {round(deadhead_travel_time / 3600, 2)} hours / From {getDisplayedTimeFormat(displayTimeFormat,previous_arrival + maintenance_time)} to {getDisplayedTimeFormat(displayTimeFormat,round(previous_arrival + maintenance_time + deadhead_travel_time, 2))})")
                            #new_task = [id, previous_destination, origin, datetime.fromtimestamp(previous_arrival + maintenance_time).replace(microsecond=0), datetime.fromtimestamp(round(previous_arrival + maintenance_time + deadhead_travel_time,2)).replace(microsecond=0)]
                            new_task = [id, previous_destination, origin,
                                        getDisplayedTimeFormat(displayTimeFormat,previous_arrival + maintenance_time),
                                        getDisplayedTimeFormat(displayTimeFormat,
                                            round(previous_arrival + maintenance_time + deadhead_travel_time, 2))]
                            tasks_to_write.append(new_task)
                            id_mapping[id] = {'task_type': 'deadhead',
                                              'locomotive': locomotive,
                                              'first_train_section': previous_trip['id_trip'],
                                              'first_section': instance_data['train_sections'][previous_trip['id_trip']][
                                                  'section'],
                                              'first_departure_time':
                                                  instance_data['train_sections'][previous_trip['id_trip']][
                                                      'departure_time'],
                                              'first_arrival_time':
                                                  instance_data['train_sections'][previous_trip['id_trip']][
                                                      'arrival_time'],
                                              'second_train_section': trip['id_trip'],
                                              'second_section': instance_data['train_sections'][trip['id_trip']][
                                                  'section'],
                                              'second_departure_time': instance_data['train_sections'][trip['id_trip']][
                                                  'departure_time'],
                                              'second_arrival_time': instance_data['train_sections'][trip['id_trip']][
                                                  'arrival_time']
                                              }
                            id += 1
                        elif maintenance_at_departure == "true" and single_day_contains_trip:
                                deadhead_distance = shortest_path_matrix[str(previous_destination)][str(origin)]['weight']
                                # calculate travel time in seconds
                                deadhead_travel_time = ((deadhead_distance / 1000) / train_speed) * 3600
                                #print(f"Deadhead trip from Station {previous_destination} to Station {origin} (Time: {round(deadhead_travel_time / 3600, 2)} hours / From {datetime.fromtimestamp(previous_arrival).replace(microsecond=0)} to {datetime.fromtimestamp(round(previous_arrival + deadhead_travel_time, 2)).replace(microsecond=0)})")
                                print(f"Deadhead trip from Station {previous_destination} to Station {origin} (Time: {round(deadhead_travel_time / 3600, 2)} hours / From {getDisplayedTimeFormat(displayTimeFormat,previous_arrival)} to {getDisplayedTimeFormat(displayTimeFormat,round(previous_arrival + deadhead_travel_time, 2))})")
                                #new_task = [id, previous_destination, origin,datetime.fromtimestamp(previous_arrival).replace(microsecond=0), datetime.fromtimestamp(round(previous_arrival + deadhead_travel_time, 2)).replace(microsecond=0)]
                                new_task = [id, previous_destination, origin,
                                            getDisplayedTimeFormat(displayTimeFormat,previous_arrival),
                                            getDisplayedTimeFormat(displayTimeFormat,
                                                round(previous_arrival + deadhead_travel_time, 2))]
                                tasks_to_write.append(new_task)
                                id_mapping[id] = {'task_type': 'deadhead',
                                                  'locomotive': locomotive,
                                                  'first_train_section': previous_trip['id_trip'],
                                                  'first_section':
                                                      instance_data['train_sections'][previous_trip['id_trip']]['section'],
                                                  'first_departure_time':
                                                      instance_data['train_sections'][previous_trip['id_trip']][
                                                          'departure_time'],
                                                  'first_arrival_time':
                                                      instance_data['train_sections'][previous_trip['id_trip']][
                                                          'arrival_time'],
                                                  'second_train_section': trip['id_trip'],
                                                  'second_section': instance_data['train_sections'][trip['id_trip']][
                                                      'section'],
                                                  'second_departure_time': instance_data['train_sections'][trip['id_trip']][
                                                      'departure_time'],
                                                  'second_arrival_time': instance_data['train_sections'][trip['id_trip']][
                                                      'arrival_time']
                                                  }
                                id += 1
                                #print(f"Maintenance at Station {origin} (Time: {round(maintenance_time / 3600, 2)} hours / From {datetime.fromtimestamp(previous_arrival + deadhead_travel_time).replace(microsecond=0)} to {datetime.fromtimestamp(previous_arrival + deadhead_travel_time + maintenance_time).replace(microsecond=0)})")
                                print(
                                    f"Maintenance at Station {origin} (Time: {round(maintenance_time / 3600, 2)} hours / From {getDisplayedTimeFormat(displayTimeFormat,previous_arrival + deadhead_travel_time)} to {getDisplayedTimeFormat(displayTimeFormat,previous_arrival + deadhead_travel_time + maintenance_time)})")
                        elif single_day_contains_trip:
                            deadhead_distance = shortest_path_matrix[str(previous_destination)][str(origin)]['weight']
                            #calculate travel time in seconds
                            deadhead_travel_time = ((deadhead_distance/1000)/train_speed)*3600
                            #print(f"Deadhead trip from Station {previous_destination} to Station {origin} (Time: {round(deadhead_travel_time/3600,2)} hours / From {datetime.fromtimestamp(previous_arrival).replace(microsecond=0)} to {datetime.fromtimestamp(round(previous_arrival + deadhead_travel_time,2)).replace(microsecond=0)})")
                            print(
                                f"Deadhead trip from Station {previous_destination} to Station {origin} (Time: {round(deadhead_travel_time / 3600, 2)} hours / From {getDisplayedTimeFormat(displayTimeFormat,previous_arrival)} to {getDisplayedTimeFormat(displayTimeFormat,round(previous_arrival + deadhead_travel_time, 2))})")
                            new_task = [id, previous_destination, origin,
                                        getDisplayedTimeFormat(displayTimeFormat,previous_arrival),
                                        getDisplayedTimeFormat(displayTimeFormat,round(previous_arrival + deadhead_travel_time, 2))]
                            tasks_to_write.append(new_task)
                            id_mapping[id] = {'task_type': 'deadhead',
                                              'locomotive': locomotive,
                                              'first_train_section': previous_trip['id_trip'],
                                              'first_section': instance_data['train_sections'][previous_trip['id_trip']]['section'],
                                              'first_departure_time': instance_data['train_sections'][previous_trip['id_trip']][
                                                  'departure_time'],
                                              'first_arrival_time': instance_data['train_sections'][previous_trip['id_trip']][
                                                  'arrival_time'],
                                              'second_train_section': trip['id_trip'],
                                              'second_section': instance_data['train_sections'][trip['id_trip']][
                                                  'section'],
                                              'second_departure_time': instance_data['train_sections'][trip['id_trip']][
                                                  'departure_time'],
                                              'second_arrival_time': instance_data['train_sections'][trip['id_trip']][
                                                  'arrival_time']
                                              }
                            #id_mapping[id] = ['deadhead', locomotive, previous_trip['id_trip'],
                            #                  instance_data['train_sections'][previous_trip['id_trip']], locomotive, trip['id_trip'],
                            #                  instance_data['train_sections'][trip['id_trip']]]
                            id += 1

                if single_day_contains_trip:
                    #print(f"From Station {origin} to  Station {destination} (Time: {round((arrival-departure)/3600,2)} hours / From {datetime.fromtimestamp(departure).replace(microsecond=0)} to {datetime.fromtimestamp(arrival).replace(microsecond=0)})")
                    print(
                        f"From Station {origin} to  Station {destination} (Time: {round((arrival - departure) / 3600, 2)} hours / From {getDisplayedTimeFormat(displayTimeFormat,departure)} to {getDisplayedTimeFormat(displayTimeFormat,arrival)})")
                    new_task = [id, origin, destination,
                                getDisplayedTimeFormat(displayTimeFormat,departure),
                                getDisplayedTimeFormat(displayTimeFormat,arrival)]
                    tasks_to_write.append(new_task)

                    id_mapping[id] = {'task_type':'regular',
                                      'locomotive': locomotive,
                                      'train_section': trip['id_trip'],
                                      'section': instance_data['train_sections'][trip['id_trip']]['section'],
                                      'departure_time': instance_data['train_sections'][trip['id_trip']]['departure_time'],
                                      'arrival_time': instance_data['train_sections'][trip['id_trip']]['arrival_time']
                                      }

                    id += 1
            previous_trip = trip
            previous_departure = departure
            previous_arrival = arrival
            previous_origin = origin
            previous_destination = destination
            previous_maintenance_at_departure = trip['maintenance_at_departure']
            previous_maintenance_at_destination = trip['maintenance_at_destination']

        print()

        #transformed_instance_path = "Transformed-58-A-2290T-114L.tsv"

        transformed_instance_path = "Transformed-"+instance+".tsv"

        #do we need to sort them by some time?
        #sorted_tasks = sorted(tasks_to_write, key=lambda x: x[3])

        #this was used to create the original instances that were then sent to Twan
        '''
        with open("Weekly_Minutes_Transformed_Instances//"+transformed_instance_path, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, delimiter="\t")  # Use tab as the delimiter
            writer.writerows(tasks_to_write)

        with open("Weekly_Minutes_ID_Mappings//"+"ID-Mapping-" + transformed_instance_path, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, delimiter="\t")  # Use tab as the delimiter

            for key, value in id_mapping.items():
                writer.writerow([key, value])
        '''

        '''
        #this is now used to read the rescheduled rolling stock solutions to get the new open tasks for rescheduling
        with open("Rescheduled_Weekly_Minutes_Transformed_Instances//"+transformed_instance_path, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, delimiter="\t")  # Use tab as the delimiter
            writer.writerows(tasks_to_write)

        with open("Rescheduled_Weekly_Minutes_ID_Mappings//"+"ID-Mapping-" + transformed_instance_path, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, delimiter="\t")  # Use tab as the delimiter

            for key, value in id_mapping.items():
                writer.writerow([key, value])
        '''

        # this is now used to read the read the corrected rescheduled rolling stock solutions to get the new open tasks for rescheduling
        with open("Final_Rescheduled_Instances//" + transformed_instance_path, mode="w",
                  newline="", encoding="utf-8") as file:
            writer = csv.writer(file, delimiter="\t")  # Use tab as the delimiter
            writer.writerows(tasks_to_write)

        with open("Final_Rescheduled_ID_Mappings//" + "ID-Mapping-" + transformed_instance_path, mode="w",
                  newline="", encoding="utf-8") as file:
            writer = csv.writer(file, delimiter="\t")  # Use tab as the delimiter

            for key, value in id_mapping.items():
                writer.writerow([key, value])