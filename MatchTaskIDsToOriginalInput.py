import csv

def matchTaskIDsToOriginalInput(original_instance_path, rescheduled_instance_path, id_mapping_path, output_instance_path, output_id_mapping_path):
    # File paths
    original_file = original_instance_path
    rescheduled_file = rescheduled_instance_path
    id_mappings_file = id_mapping_path
    output_rescheduled = output_instance_path
    output_id_mappings = output_id_mapping_path

    # Step 1: Read original instance
    original_map = {}
    max_original_id = 0
    with open(original_file, "r", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            id_orig = int(row[0])
            key = tuple(row[1:])
            original_map[key] = id_orig
            max_original_id = max(max_original_id, id_orig)

    # Step 2: Process rescheduled file
    used_original_ids = set()
    new_id = max_original_id + 1
    rescheduled_processed = []
    id_translation_map = {}  # maps old rescheduled ID -> new ID

    with open(rescheduled_file, "r", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            old_id = int(row[0])
            key = tuple(row[1:])
            if key in original_map and original_map[key] not in used_original_ids:
                new_assigned_id = original_map[key]
                used_original_ids.add(new_assigned_id)
            else:
                new_assigned_id = new_id
                new_id += 1
            rescheduled_processed.append([str(new_assigned_id)] + list(key))
            id_translation_map[old_id] = new_assigned_id

    # Step 3: Update ID mappings file
    updated_id_mappings = []
    with open(id_mappings_file, "r", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            old_id = int(row[0])
            new_id = id_translation_map.get(old_id, old_id)
            updated_id_mappings.append([str(new_id)] + row[1:])

    # Step 4: Write output files
    with open(output_rescheduled, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerows(rescheduled_processed)

    with open(output_id_mappings, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerows(updated_id_mappings)

    print(f"Rescheduled file written to '{output_rescheduled}'")
    print(f"ID mappings file updated to '{output_id_mappings}'")