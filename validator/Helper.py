"""Shared helpers for the validator checks.

Domain-neutral only: anything encoding a crew or loco rule belongs in
CrewChecks / LocoChecks, not here.
"""
from collections import defaultdict

# Tolerance on float comparisons. Times come out of divisions
# (metres/1000/speed*60), so two logically equal values differ in the last bit.
# The sign always shifts the threshold towards the permissive side: a validator
# in doubt must acquit, false positives from rounding cost more than a missed
# violation of one microminute.
EPS = 1e-6


def describe(a) -> str:
    """Short label of an assignment, used inside violation messages."""
    return (f"{a['type']} {a['origin']}->{a['destination']} "
            f"[{a['departure']:.1f}, {a['arrival']:.1f}]")

#TODO: change default dict, choice about structure of the grouping

def group_by_driver(sol) -> dict:
    """driver_id -> assignments ordered by (departure, arrival).

    Sorting is a correctness precondition of every chaining check, so it lives
    in one place: inlined in three callers, one of them eventually drops the
    tie-break on arrival and the check changes behaviour without failing.
    """
    by_driver = defaultdict(list)
    for a in sol.assignments:
        by_driver[a['driver']].append(a)
    for tasks in by_driver.values():
        tasks.sort(key=lambda a: (a['departure'], a['arrival']))
    return by_driver


def group_by_loco(sol) -> dict:
    """locomotive_id -> assignments ordered by (departure, arrival).

    crew_deadhead carries no locomotive and is left out: the driver travels as
    a passenger, the loco is elsewhere.
    """
    by_loco = defaultdict(list)
    for a in sol.assignments:
        if a['locomotive'] is not None:
            by_loco[a['locomotive']].append(a)
    for tasks in by_loco.values():
        tasks.sort(key=lambda a: (a['departure'], a['arrival']))
    return by_loco


def check_chaining(kind, entity_id, tasks, gap_hint: str = "") -> list:
    """Two tasks in a row must not overlap in time and must touch in space.

    Identical in both domains: a driver and a locomotive can each be in one
    place at a time, and waiting is legal for both — only overlapping is not.
    What differs is the label and, for the crew, the hint that a crew_deadhead
    should have covered the jump.
    """
    violations = []
    for prev, nxt in zip(tasks, tasks[1:]):
        if nxt['departure'] < prev['arrival'] - EPS:
            overlap = prev['arrival'] - nxt['departure']
            violations.append(
                f"{kind} {entity_id}: time overlap of {overlap:.1f} min between "
                f"{describe(prev)} and {describe(nxt)}")
        if prev['destination'] != nxt['origin']:
            violations.append(
                f"{kind} {entity_id}: spatial gap {prev['destination']}->{nxt['origin']} "
                f"between {describe(prev)} and {describe(nxt)}{gap_hint}")
    return violations
