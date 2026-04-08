import csv
import pandas as pd

def writeSolution_Twan(schedule):
    data = {
        "Costs": [1, 1, 1, 1, 1, 1],
        "Duration": [462, 462, 395, 477, 394, 478],
        "Task_1": [190, 340, 69, 104, 201, 460],
        "Task_2": [191, 341, 288, 453, 202, 461],
        "Task_3": [342, 6, 16, 128, 254, 462],
        "Task_4": [343, 7, 206, None, 204, 463],
        "Task_5": [344, 8, None, None, 205, None],
        "Task_6": [345, 9, None, None, 251, None],
        "Task_7": [None, None, None, None, None, None],
        "Task_8": [None, None, None, None, None, None],
        "Task_9": [None, None, None, None, None, None],
        "Task_10": [None, None, None, None, None, None]
    }

    # Convert the dictionary into a pandas DataFrame
    df = pd.DataFrame(data)

    # Specify the path where you want to save the file
    output_file = 'Output_Twan.xlsx'

    # Write the DataFrame to the Excel file
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Solution_1')

    print(f"File saved to {output_file}")