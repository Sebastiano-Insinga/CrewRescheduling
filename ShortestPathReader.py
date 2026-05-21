import json

def read_shortest_path_data(file_path):
    # Load the JSON file
    with open(file_path, 'r') as file:
        shortest_path_matrix = json.load(file)

    """
    # Example: Accessing paths and weights
    for start_node, destinations in shortest_path_matrix.items():
        print(f"Start node: {start_node}")
        for end_node, data in destinations.items():
            path = data["path"]
            weight = data["weight"]
            print(f"  End node: {end_node}")
            print(f"    Path: {path}")
            print(f"    Weight: {weight}")
    """
    return shortest_path_matrix