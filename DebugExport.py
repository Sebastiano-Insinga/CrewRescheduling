import csv
import os

DEBUG_DIR        = "debug_tasklist"
DRIVER_DEBUG_DIR = "driver_status"


def export_task_list(task_list: list, trip_id: int, loco_id: int) -> None:
    os.makedirs(DEBUG_DIR, exist_ok=True)
    path = os.path.join(DEBUG_DIR, f"trip{trip_id}_loco{loco_id}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["type", "id", "origin", "destination", "departure", "arrival"])
        w.writeheader()
        w.writerows(task_list)


def export_feasible_drivers(feasible: list, trip_id: int, crew_state,
                            task: dict = None, task_idx: int = None,
                            loco_id: int = None) -> None:
    os.makedirs(DRIVER_DEBUG_DIR, exist_ok=True)
    loco_part = f"loco{loco_id}_" if loco_id is not None else ""
    if task is not None:
        task_type = task.get('type', 'unknown')
        path = os.path.join(DRIVER_DEBUG_DIR,
                            f"{loco_part}trip{trip_id}_task{task_idx}_{task_type}_feasible_drivers.csv")
    else:
        path = os.path.join(DRIVER_DEBUG_DIR, f"{loco_part}trip{trip_id}_feasible_drivers.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["driver_id", "station", "available_at", "first_departure"])
        w.writeheader()
        for d_id in feasible:
            w.writerow({
                "driver_id":       d_id,
                "station":         crew_state.station(d_id),
                "available_at":    crew_state.available_at(d_id),
                "first_departure": crew_state.first_departure(d_id),
            })


def export_loco_driver_selection(trip_id: int, loco_id: int, task: dict,
                                  feasible: list, selected_driver_id: int,
                                  crew_state) -> None:
    os.makedirs(DEBUG_DIR, exist_ok=True)
    task_type = task.get('type', 'unknown')
    path = os.path.join(DEBUG_DIR, f"loco{loco_id}_trip{trip_id}_task_{task_type}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "driver_id", "station", "available_at", "first_departure",
            "duty_length_base", "original_available_at", "is_selected",
        ])
        w.writeheader()
        for d_id in feasible:
            w.writerow({
                "driver_id":             d_id,
                "station":               crew_state.station(d_id),
                "available_at":          crew_state.available_at(d_id),
                "first_departure":       crew_state.first_departure(d_id),
                "duty_length_base":      crew_state.duty_length_base(d_id),
                "original_available_at": crew_state.original_available_at(d_id),
                "is_selected":           d_id == selected_driver_id,
            })


def export_loco_sequence(loco_id: int, loco_duties: dict) -> None:
    os.makedirs(DEBUG_DIR, exist_ok=True)
    path = os.path.join(DEBUG_DIR, f"loco{loco_id}_sequence.csv")
    segs = loco_duties.get(loco_id, [])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "seq", "rs_trip_id", "type", "origin", "destination", "departure", "arrival", "driver_id",
        ])
        w.writeheader()
        for i, (task, driver_id) in enumerate(segs):
            w.writerow({
                "seq":         i,
                "rs_trip_id":  task.get('rs_trip_id', ''),
                "type":        task.get('type'),
                "origin":      task.get('origin'),
                "destination": task.get('destination'),
                "departure":   task.get('departure'),
                "arrival":     task.get('arrival'),
                "driver_id":   driver_id,
            })
