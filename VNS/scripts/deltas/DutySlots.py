from ScheduleState import (SC_BACK_HOME, SC_BREAK_SHORT, SC_CONTINUITY, SC_DH_M, SC_EXCESS,
                          SC_UNREACHABLE)

DUTY_SLOT = {
    "continuity_minutes":  (SC_CONTINUITY,  1.0),
    "unreachable_links":   (SC_UNREACHABLE, 1.0),
    "duty_excess_minutes": (SC_EXCESS,      1.0),
    "break_shortfall":     (SC_BREAK_SHORT, 1.0),
    "back_home":           (SC_BACK_HOME,   0.001),
    "crew_deadhead_km":    (SC_DH_M,        0.001),
}

COVERAGE_NAMES = frozenset({
    "cancellations",
    "loco_deadhead_km",
    "maintenance_excess_km",
    "maintenance_overdue_km",
    "maintenance_time_minutes",
    "loco_overlap_minutes",
    "loco_unreachable_links",
    "uncovered_tasks",
})


def classify(name: str) -> tuple:
    if name in DUTY_SLOT:
        return DUTY_SLOT[name]
    if name in COVERAGE_NAMES:
        return None
    raise KeyError(f"componente {name} senza delta: va messa in DUTY_SLOT o in COVERAGE_NAMES")
