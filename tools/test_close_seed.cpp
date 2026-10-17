// Test the actual plugin seed generator without running a compositor.
#include "../vendor/HyprWindowShade/CloseSeed.hpp"
#include <cassert>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <set>
#include <map>
#include <fstream>

int main(int argc, char** argv) {
    CloseSeedSequence seeds(123456789);
    std::set<float> samples;
    std::ofstream profiles;
    if (argc > 1) profiles.open(argv[1]);
    // Repeated closes need different seeds even with no window-address input.
    for (int i = 0; i < 1000; ++i) {
        const float seed = seeds.next();
        assert(std::isfinite(seed) && seed >= 0.0f && seed < 1.0f);
        samples.insert(seed);
        const auto key = BurnProfile::key(seed);
        // Preserve the linear clock and enforce the half-strength curve range.
        float previousStep = 0.2f;
        for (int phase = 1; phase <= 4; ++phase) {
            const float step = BurnProfile::clock(phase * 0.2f + 0.1f)
                - BurnProfile::clock(phase * 0.2f - 0.1f);
            assert(std::abs(step - previousStep) < 0.00001f);
            previousStep = step;
        }
        float low = 1.0f, high = 0.0f;
        for (int col = 0; col <= 32; ++col) {
            const float height = BurnProfile::front(col / 32.0f, 0.5f, key);
            low = std::min(low, height);
            high = std::max(high, height);
        }
        assert(high - low < 0.27f);
        if (i < 128) {
            std::cout << std::setprecision(9) << seed << '\n';
            if (profiles) {
                profiles << std::setprecision(9) << seed;
                for (float height : BurnProfile::shape(BurnProfile::key(seed))) profiles << ' ' << height;
                profiles << '\n';
            }
        }
    }
    assert(samples.size() > 990);
    std::cerr << "PASS: 1000 close seeds in range; " << samples.size()
              << " distinct values, independent of window address.\n";
    std::cerr << "PASS: half-strength curve range and linear clock preserved.\n";
    std::map<int, std::deque<BurnProfile::Shape>> previous;
    float nearest = 1.0f;
    // Compare actual broad shapes across three phases, including the last
    // eight closes on each workspace despite closes interleaved elsewhere.
    for (int i = 0; i < 900; ++i) {
        const int workspace = i % 3;
        const float seed = seeds.next(workspace);
        assert(std::isfinite(seed) && seed >= 0.0f && seed < 1.0f);
        const auto shape = BurnProfile::shape(BurnProfile::key(seed));
        for (const auto& old : previous[workspace]) {
            const float distance = BurnProfile::distance(shape, old);
            nearest = std::min(nearest, distance);
            assert(distance > 0.005f);
        }
        previous[workspace].push_back(shape);
        if (previous[workspace].size() > 8) previous[workspace].pop_front();
    }
    std::cerr << "PASS: 900 interleaved workspace closes differ from their last eight shapes; minimum RMS " << nearest << ".\n";
}
