from collections import Counter
from collections import defaultdict
import statistics
import matplotlib.pyplot as plt


def perform_data_analysis(networkData, instanceData):
    #Analysis of the trip durations
    totalDrivingTime = 0
    maxTime = 0
    minTime = 100000
    travelTimes = []
    for section_id, section in instanceData['train_sections'].items():
        if (section['arrival_time'] - section['departure_time']) > maxTime:
            maxTime = (section['arrival_time'] - section['departure_time'])
        if (section['arrival_time'] - section['departure_time']) < minTime:
            minTime = (section['arrival_time'] - section['departure_time'])
        travelTimes.append((section['arrival_time'] - section['departure_time']))
        totalDrivingTime += (section['arrival_time'] - section['departure_time'])
    number_trains = len(instanceData['trains'].items())
    number_locomotives = len(instanceData['locomotives'].items())
    avg_driving_time = totalDrivingTime / number_trains
    avg_driving_time_hours = avg_driving_time / 3600
    maxTimeHours = maxTime / 3600
    minTimeHours = minTime / 3600
    median_travel_time = statistics.median(travelTimes)
    median_travel_time_hours = median_travel_time / 3600

    print(f"There are {number_trains} trains to be scheduled")
    print(f"There are {number_locomotives} locomotives available to operate the trains")
    print(f"The average driving time for a train is {avg_driving_time} seconds ({avg_driving_time_hours} hours)")
    print(f"The median driving time is: {median_travel_time} ({median_travel_time_hours} hours)")
    print(f"The minimum driving time for a train is {minTime} seconds ({minTimeHours} hours)")
    print(f"The maximum driving time for a train is {maxTime} seconds ({maxTimeHours} hours)")

    # Create a histogram of the travel times
    plt.figure(figsize=(8, 6))
    plt.hist(travelTimes, bins=50, color='lightblue', edgecolor='black')

    # Add labels and title
    plt.xlabel("Travel time (seconds)")
    plt.ylabel("Frequency")
    plt.title("Histogram of Traveltimes")

    # Show the plot
    plt.show()

    #Analysis of the stations
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
    sorted_result_destinations = {key: result_destinations[key] for key in sorted(result_destinations.keys(), reverse=True)}
    print(sorted_result_destinations)

    # Produce a histogram for origins with frequencies on the x-axis
    frequencies_origins = []
    for freq, origins in sorted_result_origins.items():
        frequencies_origins.extend([freq] * len(origins))
    plt.figure(figsize=(10, 6))
    plt.hist(frequencies_origins, bins=range(1, max(frequencies_origins) + 2), color='lightblue', edgecolor='black', align='left',
             rwidth=0.8)
    plt.xlabel("Frequency")
    plt.ylabel("Number of Origins")
    plt.title("Histogram for origins")
    plt.show()

    # Produce a histogram for destinations with frequencies on the x-axis
    frequencies_destinations = []
    for freq, destinations in sorted_result_destinations.items():
        frequencies_destinations.extend([freq] * len(destinations))
    plt.figure(figsize=(10, 6))
    plt.hist(frequencies_destinations, bins=range(1, max(frequencies_destinations) + 2), color='lightblue',
             edgecolor='black',
             align='left',
             rwidth=0.8)
    plt.xlabel("Frequency")
    plt.ylabel("Number of destinations")
    plt.title("Histogram for destinations")
    plt.show()

    # Produce a histogram for origins with frequencies on the y-axis
    origin_frequency = {origin: freq for freq, origins in sorted_result_origins.items() for origin in origins}
    origins = list(origin_frequency.keys())
    frequencies = list(origin_frequency.values())
    plt.figure(figsize=(10, 6))
    plt.bar(origins, frequencies, color='lightblue', edgecolor='black')
    plt.xlabel("Origin")
    plt.ylabel("Frequency")
    plt.title("Histogram for origins")
    plt.show()

    # Produce a histogram for origins with frequencies on the y-axis
    destination_frequency = {destination: freq for freq, destinations in sorted_result_destinations.items() for destination in destinations}
    destinations = list(destination_frequency.keys())
    frequencies = list(destination_frequency.values())
    plt.figure(figsize=(10, 6))
    plt.bar(destinations, frequencies, color='lightblue', edgecolor='black')
    plt.xlabel("Destination")
    plt.ylabel("Frequency")
    plt.title("Histogram for destinations")
    plt.show()
