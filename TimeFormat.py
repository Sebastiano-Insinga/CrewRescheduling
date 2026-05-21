from datetime import datetime
import math

def getDisplayedTimeFormat(format, time):
    displayed_time = None
    if format == 1:
        displayed_time = time
    elif format == 2:
        displayed_time = datetime.fromtimestamp(time).replace(microsecond=0)
    elif format == 3:
        baseline_day = datetime(2018, 9, 10)
        #needed to shift the minutes for the next day by 1440 minutes
        time_difference = datetime.fromtimestamp(time) - baseline_day
        displayed_time = time_difference.days * 1440 + math.ceil(datetime.fromtimestamp(time).hour * 60 + datetime.fromtimestamp(time).minute + (1.0 / 60.0) * datetime.fromtimestamp(time).second)
    else:
        print("Please provide a suitable time format (1,2 or 3)!")

    return displayed_time