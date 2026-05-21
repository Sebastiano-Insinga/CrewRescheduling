import csv

def readOpenRescheduledTasks(rescheduled_tasks_file):
    open_tasks = {}
    with open(rescheduled_tasks_file, "r") as file:
        reader = csv.reader(file, delimiter="\t")
        for row in reader:
            task_id = int(row[0])  # First column as ID

            open_tasks[task_id] = {
                "id": task_id,
                "origin": int(row[1]),
                "destination": int(row[2]),
                "departure": int(row[3]),
                "arrival": int(row[4])
            }

    return open_tasks