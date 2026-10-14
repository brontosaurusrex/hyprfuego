// Test the actual plugin seed generator without running a compositor.
#include "../vendor/HyprWindowShade/CloseSeed.hpp"
#include <cassert>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <set>
#include <map>

int main() {
    CloseSeedSequence seeds(123456789);
    std::set<float> samples;
    // Repeated closes need different seeds even with no window-address input.
    for (int i = 0; i < 1000; ++i) {
        const float seed = seeds.next();
        assert(std::isfinite(seed) && seed >= 0.0f && seed < 1.0f);
        samples.insert(seed);
        if (i < 18) std::cout << std::setprecision(9) << seed << '\n';
    }
    assert(samples.size() > 990);
    std::cerr << "PASS: 1000 close seeds in range; " << samples.size()
              << " distinct values, independent of window address.\n";
    std::map<int, float> previous;
    // Interleave workspaces, including repeated single-window closes. The
    // shader uses the full seed for continuous profiles, not its old order bin.
    for (int i = 0; i < 900; ++i) {
        const int workspace = i % 3;
        const float seed = seeds.next(workspace);
        assert(std::isfinite(seed) && seed >= 0.0f && seed < 1.0f);
        if (previous.count(workspace)) assert(previous[workspace] != seed);
        previous[workspace] = seed;
    }
    std::cerr << "PASS: 900 interleaved workspace closes receive fresh seeds.\n";
}
