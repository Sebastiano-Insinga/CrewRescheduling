import csv

def transformInstance_Twan(file_name, network_data, instance_data):
    #bring the data in network_data and instance_data to the desired format
    #example
    #data = [
        #["ID", "Origin", "Destination", "Departure", "Arrival"]
        #[0, 1111, 1112, 630, 792],
        #[1, 2435, 2436, 990, 1120],
        #[2, 3356, 3357, 12, 230]
    #]

    data = []
    id_mapping = {}
    modified_id = 0
    for train_section_id, train_section in instance_data['train_sections'].items():
        section_id = train_section['section']
        origin = network_data['sections'][section_id]['origin']
        destination = network_data['sections'][section_id]['destination']
        departure = train_section['departure_time']
        arrival = train_section['arrival_time']

        new_train_section = [modified_id, origin, destination, departure, arrival]
        data.append(new_train_section)

        id_mapping[modified_id] = train_section_id
        modified_id += 1

    sorted_data = sorted(data, key=lambda x: x[3])

    with open(file_name, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, delimiter="\t")  # Use tab as the delimiter
        writer.writerows(sorted_data)

    with open("ID-Mapping-"+file_name, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, delimiter="\t")  # Use tab as the delimiter

        for key, value in id_mapping.items():
            writer.writerow([key, value])

    print(f"Data written to {file_name}")