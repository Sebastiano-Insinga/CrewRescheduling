"""
Test deterministic mode of RollingStockGreedy vs C++ (d_rate=1.0 c_list=1).

Usage:
  python test_deterministic.py <instance_id> <cpp_solution_json>

  <instance_id>       e.g. S01
  <cpp_solution_json> path to JSON produced by C++ binary with d_rate=1.0 c_list=1

C++ command (Linux):
  ./binary --main::instance single_type/S01.json --main::d_rate 1.0 --main::c_list 1 \
           --main::print_solution true > cpp_solution.json
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from RollingStockGreedy import load_data, randomized_greedy

INSTANCE_DIR       = 'single_type'
NETWORK_FILE       = os.path.join(INSTANCE_DIR, 'network.json')
SHORTESTPATHS_FILE = os.path.join(INSTANCE_DIR, 'network-shortestpaths.json')

instance_id      = sys.argv[1] if len(sys.argv) > 1 else 'S01'
cpp_solution_path = sys.argv[2] if len(sys.argv) > 2 else None

instance_file = os.path.join(INSTANCE_DIR, f'{instance_id}.json')
instance, network, sp = load_data(instance_file, NETWORK_FILE, SHORTESTPATHS_FILE)

py_sol = randomized_greedy(instance, network, sp, deterministic=True)

py_by_trip = {e['id_trip']: e for e in py_sol}
py_canceled = sum(1 for e in py_sol if e['locomotive'] == 'canceled')
print(f"Python  — trips: {len(py_sol)}, canceled: {py_canceled}")

if cpp_solution_path:
    with open(cpp_solution_path) as f:
        cpp_sol = json.load(f)
    cpp_by_trip  = {e['id_trip']: e for e in cpp_sol}
    cpp_canceled = sum(1 for e in cpp_sol if e['locomotive'] == 'canceled')
    print(f"C++     — trips: {len(cpp_sol)}, canceled: {cpp_canceled}")

    mismatches = []
    for tid, py_e in py_by_trip.items():
        cpp_e = cpp_by_trip.get(tid)
        if cpp_e is None:
            mismatches.append((tid, 'missing in C++', None))
            continue
        if (py_e['locomotive']               != cpp_e['locomotive'] or
            py_e['maintenance_at_departure'] != cpp_e['maintenance_at_departure'] or
            py_e['maintenance_at_destination'] != cpp_e['maintenance_at_destination']):
            mismatches.append((tid, py_e, cpp_e))

    if not mismatches:
        print("\nOK: outputs identical — logic correct, any random-mode diff = RNG only")
    else:
        print(f"\nMISMATCH: {len(mismatches)} trips differ")
        for tid, py_e, cpp_e in mismatches[:10]:
            print(f"  trip {tid}:")
            print(f"    Python: {py_e}")
            print(f"    C++:    {cpp_e}")
else:
    print("\nNo C++ solution provided. Python solution saved to test_det_output.json")
    with open('test_det_output.json', 'w') as f:
        json.dump(py_sol, f, indent=3)
    print("Run C++ with d_rate=1.0 c_list=1 on same instance, then rerun with path as arg.")
