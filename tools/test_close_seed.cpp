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
    static constexpr int leading[] = {0, 2, 1, 2, 1, 0};
    std::map<int, int> previous;
    std::set<int> leaders;
    // Interleave workspaces: each workspace retains its own previous leader.
    for (int i = 0; i < 900; ++i) {
        const int workspace = i % 3;
        const float seed = seeds.next(workspace);
        const int order = static_cast<int>(std::floor(seed * 6.0f));
        assert(order >= 0 && order < 6);
        const int leader = leading[order];
        if (previous.count(workspace)) assert(previous[workspace] != leader);
        previous[workspace] = leader;
        leaders.insert(leader);
    }
    assert(leaders.size() == 3);
    std::cerr << "PASS: 900 interleaved closes never repeat the leader in a workspace.\n";
}
