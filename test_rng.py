"""
Compare CppMT19937 output against C++ test_rng.cpp.
Run test_rng.cpp first:  g++ -std=c++11 -o test_rng test_rng.cpp && ./test_rng
Then run this:           python test_rng.py
Outputs must be identical.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from RollingStockGreedy import CppMT19937

rng = CppMT19937(42)

ranges = [1, 2, 3, 5, 9]
for r in ranges:
    vals = [rng.uniform_int(0, r) for _ in range(10)]
    print(f"range 0-{r}: {' '.join(map(str, vals))}")
