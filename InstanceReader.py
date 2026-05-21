import json

def read_instance_data(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)

    # Parse trains
    trains = {}
    for train in data.get('trains', []):
        train_id = train['id']
        trains[train_id] = {
            'name': train['name']
        }

    train_sections = {}
    for train_section in data.get('train_sections', []):
            train_section_id = train_section['id']
            train_sections[train_section_id] = {
            "train": train_section['train'],
            "section": train_section['section'],
            "departure_time": train_section['departure_time'],
            "arrival_time": train_section['arrival_time'],
            "locomotive_orders": train_section['locomotive_orders']
        }

    # Parse locomotives
    locomotives = {}
    for locomotive in data.get('locomotives', []):
        locomotive_id = locomotive['id']
        locomotives[locomotive_id] = {
            'name': locomotive['name'],
            'class': locomotive['class'],
            'kilometers_since_last_maintenance': locomotive['kilometers_since_last_maintenance'],
            'initial_departure_station': locomotive['initial_departure_station'],
        }

    return {'trains': trains, 'train_sections': train_sections, 'locomotives': locomotives}

# Test code - commented out
# #01-A-50T-10L
# #58-A-2290T-114L
# #00-toy1
# file_path = "C://Users//mschlenk//OneDrive - WU Wien//Dokumente//Railway_Project//instances//literature//converted//58-A-2290T-114L.json"
# #file_path = "toy-network.json"
# railway_data = read_instance_data(file_path)
#
# total_driving_time = 0
#
# for train_id, train_info in railway_data['trains'].items():
#     print(f"Train {train_id}: {train_info['name']}")
#
# checked_train_sections = []
# max_time = 0
# for section_id, section in railway_data['train_sections'].items():
#     print(f"  Section {section_id} (Section {section['section']}):")
#     print(f"  Train: {section['train']}")
#     print(f"    Departure: {section['departure_time']}")
#     print(f"    Arrival: {section['arrival_time']}")
#     if (section['arrival_time'] - section['departure_time']) > max_time:
#         max_time = (section['arrival_time'] - section['departure_time'])
#     total_driving_time += (section['arrival_time'] - section['departure_time'])
#     print(f"    Locomotive Orders: {section['locomotive_orders']}")
#
# for loco_id, loco_info in railway_data['locomotives'].items():
#     print(f"Locomotive {loco_id}: {loco_info['name']}")
#     print(f"  Class: {loco_info['class']}")
#     print(f"  Kilometers since last maintenance: {loco_info['kilometers_since_last_maintenance']}")
#     print(f"  Initial departure station: {loco_info['initial_departure_station']}")


