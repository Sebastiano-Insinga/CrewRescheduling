import sys
sys.path.insert(0, ".")

from VNS_Rescheduling import calculateInitialSolution


original_schedule = {
    3: [
        {"id": 101, "origin": 10, "destination": 20, "departure": 400, "arrival": 460},
        {"id": 102, "origin": 20, "destination": 30, "departure": 510, "arrival": 570},
    ],
    5: [
        {"id": 201, "origin": 30, "destination": 40, "departure": 420, "arrival": 480},
        {"id": 203, "origin": 30, "destination": 40, "departure": 590, "arrival": 650},
    ]
}

driver_status = {
    3: {"duty_length": 60, "break30done": False, "break45done": False,
        "available_from_station": 20, "available_at_time": 500},
    5: {"duty_length": 60, "break30done": False, "break45done": False,
        "available_from_station": 30, "available_at_time": 500},
}

open_tasks = {
    102: {"id": 102, "origin": 20, "destination": 30, "departure": 510, "arrival": 570},
    103: {"id": 103, "origin": 30, "destination": 40, "departure": 590, "arrival": 650},
    201: {"id": 201, "origin": 30, "destination": 40, "departure": 510, "arrival": 570},
    203: {"id": 203, "origin": 30, "destination": 40, "departure": 590, "arrival": 650},
}

id_mapping = {
    102: {"task_type": "regular", "loco_type": "A", "section_type": "X", "locomotive": "L1", "section": "S1"},
    103: {"task_type": "regular", "loco_type": "A", "section_type": "X", "locomotive": "L1", "section": "S1"},
    201: {"task_type": "regular", "loco_type": "B", "section_type": "Y", "locomotive": "L2", "section": "S2"},
    203: {"task_type": "regular", "loco_type": "B", "section_type": "Y", "locomotive": "L2", "section": "S2"},
}

suitable_tasks = {
    3: [102, 103],
    5: [201, 203, 103],
}

existing_duties, duty_breaks, uncovered_tasks, suitable_tasks_out, spare_ids = calculateInitialSolution(
    original_schedule, driver_status, open_tasks,
    disruption_start=500, disruption_end=550,
    max_duty_length=720, id_mapping=id_mapping, suitable_tasks=suitable_tasks
)
