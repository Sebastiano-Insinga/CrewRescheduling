import json
import os

FORCED_LOCOS_DIR = "debug_forced_locos"


def export_forced_locos(forced: dict, all_candidates: dict) -> dict:
    loco_to_trips: dict[int, list[int]] = {}
    for trip_id in forced:
        seen_locos = set()
        for pair in all_candidates.get(trip_id, [])[1:]:
            loco_id = pair['loco']
            if loco_id in seen_locos:
                continue
            seen_locos.add(loco_id)
            loco_to_trips.setdefault(loco_id, []).append(trip_id)
    return loco_to_trips


def write_forced_locos_json(loco_to_trips: dict, instance_id: str, iter_num: int) -> None:
    os.makedirs(FORCED_LOCOS_DIR, exist_ok=True)
    path = os.path.join(FORCED_LOCOS_DIR, f"{instance_id}_iter{iter_num}.json")
    with open(path, "w") as f:
        json.dump({str(loco_id): trip_ids for loco_id, trip_ids in loco_to_trips.items()}, f, indent=2)
