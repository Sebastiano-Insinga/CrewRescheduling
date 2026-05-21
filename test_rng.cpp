// Compile: g++ -std=c++11 -o test_rng test_rng.cpp
// Run:     ./test_rng
// Compare output with test_rng.py
#include <iostream>
#include <random>

int main() {
    std::mt19937 g(42);

    // Test 1: uniform_int_distribution with various ranges
    int ranges[] = {1, 2, 3, 5, 9};
    for (int r : ranges) {
        std::uniform_int_distribution<int> d(0, r);
        std::cout << "range 0-" << r << ": ";
        for (int i = 0; i < 10; i++)
            std::cout << d(g) << " ";
        std::cout << std::endl;
    }
    return 0;
}
