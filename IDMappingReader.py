import ast

def readIDMapping(id_mapping_path):
    data_dict = {}
    with open(id_mapping_path, "r") as file:
        for line in file:
            key, value = line.strip().split("\t", 1)
            data_dict[int(key)] = ast.literal_eval(value)  # Convert string representation of dict to actual dict
    return data_dict