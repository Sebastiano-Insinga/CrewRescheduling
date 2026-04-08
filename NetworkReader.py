import json
import os

def read_network_data(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)

    # Parse stations
    stations = {}
    for station in data.get('stations', []):
        station_id = station['id']
        stations[station_id] = {
            'name': station['name'],
        }

    # Parse sections
    sections = {}
    for section in data.get('sections', []):
        section_id = section['id']
        sections[section_id] = {
            'name': section['name'],
            'origin': section['origin'],
            'destination': section['destination'],
            'distance': section['distance'],
        }

    # Parse maintenance points
    maintenance_points = {}
    for mp in data.get('maintenance_points', []):
        mp_id = mp['id']
        maintenance_points[mp_id] = {
            'name': mp['name'],
            'station': mp['station'],
            'maintainable_locomotive_classes': mp.get('maintainable_locomotive_classes', []),
        }

    # Parse locomotive classes
    locomotive_classes = {}
    for loco_class in data.get('locomotive_classes', []):
        loco_class_id = loco_class['id']
        locomotive_classes[loco_class_id] = {
            'name': loco_class['name'],
            'max_kilometers_before_maintenance': loco_class['max_kilometers_before_maintenance'],
            'maintenance_duration': loco_class['maintenance_duration'],
        }

    return {
        'stations': stations,
        'sections': sections,
        'maintenance_points': maintenance_points,
        'locomotive_classes': locomotive_classes,
    }

import os
# Use absolute path based on this file's location
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
file_path = os.path.join(parent_dir, "manuel", "frisch-network.json")
network_data = read_network_data(file_path)

# Print parsed data
print("Stations:")
for station_id, station_info in network_data['stations'].items():
    print(f"  Station {station_id}: {station_info['name']}")

print("\nSections:")
for section_id, section_info in network_data['sections'].items():
    print(f"  Section {section_id} ({section_info['name']}):")
    print(
        f"    Origin: {section_info['origin']}, Destination: {section_info['destination']}, Distance: {section_info['distance']}")

print("\nMaintenance Points:")
for mp_id, mp_info in network_data['maintenance_points'].items():
    print(f"  Maintenance Point {mp_id}: {mp_info['name']}")
    print(f"    Station: {mp_info['station']}, Maintainable Classes: {mp_info['maintainable_locomotive_classes']}")

print("\nLocomotive Classes:")
for loco_class_id, loco_class_info in network_data['locomotive_classes'].items():
    print(f"  Locomotive Class {loco_class_id}: {loco_class_info['name']}")
    print(
        f"    Max KM Before Maintenance: {loco_class_info['max_kilometers_before_maintenance']}, Maintenance Duration: {loco_class_info['maintenance_duration']}")
