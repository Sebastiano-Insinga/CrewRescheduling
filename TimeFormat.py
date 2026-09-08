from datetime import datetime
from zoneinfo import ZoneInfo
import math

# Gli epoch nei JSON delle istanze sono orari locali austriaci. Il fuso va
# ancorato esplicitamente: datetime.fromtimestamp() senza tz usa quello della
# macchina, e lo stesso S01 dava obiettivo 11137.4 sul Mac (CEST) contro
# 21794.5 sul cluster (UTC), perche' disruption_start/end si spostavano di 120
# minuti. Definito qui perche' TimeFormat non importa nulla di locale: e' il
# solo punto del progetto da cui chiunque puo' prenderlo senza creare cicli.
INSTANCE_TZ = ZoneInfo("Europe/Vienna")


def instance_datetime(epoch_seconds: float) -> datetime:
    """Epoch -> datetime naive nell'ora locale dell'istanza.

    Naive di proposito: i confronti e le sottrazioni nel resto del codice
    avvengono contro datetime senza tzinfo, e mischiare aware e naive solleva
    TypeError.
    """
    return datetime.fromtimestamp(epoch_seconds, tz=INSTANCE_TZ).replace(tzinfo=None)


def getDisplayedTimeFormat(format, time):
    displayed_time = None
    if format == 1:
        displayed_time = time
    elif format == 2:
        displayed_time = instance_datetime(time).replace(microsecond=0)
    elif format == 3:
        baseline_day = datetime(2018, 9, 10)
        dt = instance_datetime(time)
        #needed to shift the minutes for the next day by 1440 minutes
        time_difference = dt - baseline_day
        displayed_time = time_difference.days * 1440 + math.ceil(dt.hour * 60 + dt.minute + (1.0 / 60.0) * dt.second)
    else:
        print("Please provide a suitable time format (1,2 or 3)!")

    return displayed_time
