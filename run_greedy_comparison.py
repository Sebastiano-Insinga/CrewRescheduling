"""
Run all crew greedy methods on S01 with task_source='reader'.
Usage: python run_greedy_comparison.py
"""
import sys
from SequentialRescheduling import run_instance

INSTANCE  = sys.argv[1] if len(sys.argv) > 1 else 'S01'
RS_METHOD = sys.argv[2] if len(sys.argv) > 2 else 'randomized_greedy'

METHODS = [
    'calculateInitialSolution',
    'calculateInitialSolution_slack',
    'calculateInitialSolution_driverMRV',
    'calculateInitialSolutionBreak',
    'calculateInitialSolution_taskScarcity',
    'calculateInitialSolution_connectivity',
    'calculateInitialSolution_deadhead',
]

results = []
for m in METHODS:
    r = run_instance(INSTANCE, rs_method=RS_METHOD, method=m, task_source='reader')
    results.append((m, r['crew_uncovered']))

print()
print(f"Instance: {INSTANCE}  RS: {RS_METHOD}")
print(f"{'Method':<45} {'crew_uncovered':>15}")
print('-' * 62)
for m, u in results:
    print(f"{m:<45} {u:>15}")
