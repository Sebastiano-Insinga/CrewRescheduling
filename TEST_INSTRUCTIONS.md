# Test Instructions: Python vs C++ RandomizedGreedy

## Step 1 — Verify RNG (CppMT19937 vs GCC std::mt19937)

Goal: confirm Python RNG produces identical sequence to GCC.

### Linux (GCC)
```bash
g++ -std=c++11 -o test_rng test_rng.cpp
./test_rng > cpp_rng_output.txt
cat cpp_rng_output.txt
```

### macOS (Python)
```bash
python test_rng.py > py_rng_output.txt
cat py_rng_output.txt
```

### Compare
Copy `cpp_rng_output.txt` to macOS, then:
```bash
diff cpp_rng_output.txt py_rng_output.txt
```
- No output → RNG identical, `CppMT19937` correct
- Differences → RNG mismatch, Python replication of GCC has a bug

---

## Step 2 — Verify Logic (deterministic mode, no randomness)

Goal: confirm Python logic matches C++ logic independently of RNG.

### Linux — Run C++ in deterministic mode (d_rate=1.0 c_list=1, already default)
```bash
./binary --main::instance single_type/S01.json \
         --main::d_rate 1.0 \
         --main::c_list 1 \
         --main::print_solution true > cpp_solution.json
```

### macOS — Run Python in deterministic mode
```bash
python test_deterministic.py S01
# saves test_det_output.json
```

### Compare
Copy `cpp_solution.json` to macOS, then:
```bash
python test_deterministic.py S01 cpp_solution.json
```

Results:
- `OK: outputs identical` → Python logic correct. Any difference in random mode = RNG only.
- `MISMATCH: N trips differ` → logical bug in Python replication, independent of seed.

---

## Interpretation Matrix

| Step 1 RNG | Step 2 Logic | Conclusion |
|------------|--------------|------------|
| identical  | identical    | Python fully correct, random-mode diffs = statistical only |
| identical  | mismatch     | Logic bug in Python — fix in RollingStockGreedy.py |
| mismatch   | identical    | CppMT19937 wrong but logic ok — fix uniform_int() |
| mismatch   | mismatch     | Fix RNG first, then retest logic |
