// Regression: existing windows can retain @5, @1 and default tags together.
#include "../vendor/HyprWindowShade/CloseDurations.hpp"
#include <cassert>
#include <iostream>
#include <limits>

int main() {
    CloseDurations durations;
    const std::string main = "/shader/burn-close.glsl", preview = "/shader/burn-close-size-preview.glsl";
    assert(durations.set(main, 5.0f));
    assert(durations.set(preview, 5.0f));
    const float alreadyClosing = durations.resolve(main, 1.0f);
    assert(durations.set(main, 1.0f));
    assert(durations.set(preview, 1.0f));
    for (float staleWindowTag : {5.0f, 1.15f, 1.0f, -1.0f}) {
        assert(durations.resolve(main, staleWindowTag) == 1.0f);
        assert(durations.resolve(preview, staleWindowTag) == 1.0f);
    }
    assert(alreadyClosing == 5.0f); // Existing animations retain their start clock.
    assert(durations.resolve("/other/shader", 2.0f) == 2.0f);
    assert(!durations.set(main, std::numeric_limits<float>::quiet_NaN()));
    assert(!durations.set(main, 0.0f));
    assert(!durations.set(main, 0.09f));
    assert(!durations.set(main, 20.1f));
    assert(durations.resolve(main, 5.0f) == 1.0f);
    for (float seconds : {0.1f, 0.75f, 5.1f, 12.5f, 20.0f}) {
        assert(durations.set(main, seconds));
        assert(durations.resolve(main, 1.15f) == seconds);
    }
    durations.clear();
    assert(durations.resolve(main, 2.0f) == 2.0f);
    std::cout << "PASS: 0.1-to-20-second preferences override cached durations; active closes keep their clock.\n";
}
