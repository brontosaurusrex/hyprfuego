#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>

// Mirror the bottom-up profile in both Hyprfuego shaders. Compare shapes once
// per close; the GPU never searches history or changes its seed mid-animation.
namespace BurnProfile {
inline uint32_t hash(uint32_t value) {
    value ^= value >> 16;
    value *= UINT32_C(0x7feb352d);
    value ^= value >> 15;
    value *= UINT32_C(0x846ca68b);
    return value ^ (value >> 16);
}
inline float control(uint32_t key, uint32_t channel) {
    return static_cast<float>(hash(key ^ (channel * UINT32_C(0x9e3779b9))) >> 8) / 16777216.0f;
}
inline float clock(float progress) { return std::clamp(progress, 0.0f, 1.0f); }
inline float front(float x, float progress, uint32_t key) {
    const float a = control(key, 10), b = control(key, 11), c = control(key, 12);
    const float d = control(key, 13), e = control(key, 14);
    const float low = std::min({a, b, c, d, e}), high = std::max({a, b, c, d, e});
    const std::array<float, 5> positions{0.0f, 0.15f + 0.20f * d, 0.40f + 0.20f * a, 0.65f + 0.20f * b, 1.0f};
    const std::array<float, 5> values{a, b, c, d, e};
    int index = 0;
    while (index < 3 && x >= positions[index + 1]) ++index;
    float blend = std::clamp((x - positions[index]) / (positions[index + 1] - positions[index]), 0.0f, 1.0f);
    blend = blend * blend * (3.0f - 2.0f * blend);
    const float timing = std::clamp((values[index] + (values[index + 1] - values[index]) * blend - low)
                                  / std::max(high - low, 0.0001f), 0.0f, 1.0f);
    const float start = 0.005f + 0.135f * timing, finish = 0.61f + 0.37f * timing;
    const float local = std::clamp((clock(progress) - start) / (finish - start), 0.0f, 1.0f);
    return -0.18f + 1.36f * local;
}
using Shape = std::array<float, 9 * 7 * 3>;
inline Shape shape(uint32_t key) {
    Shape result;
    for (int phase = 0; phase < 3; ++phase)
        for (int row = 0; row < 7; ++row)
            for (int col = 0; col < 9; ++col) {
                const std::array<float, 2> c{(col + 0.5f) / 9.0f, 1.0f - (row + 0.5f) / 7.0f};
                const float edge = c[1] - front(c[0], 0.3f + phase * 0.2f, key);
                result[phase * 63 + row * 9 + col] = std::clamp(0.5f + edge * 5.0f, 0.0f, 1.0f);
            }
    return result;
}
inline float distance(const Shape& a, const Shape& b) {
    float sum = 0.0f;
    for (std::size_t i = 0; i < a.size(); ++i) sum += (a[i] - b[i]) * (a[i] - b[i]);
    return std::sqrt(sum / a.size());
}
inline uint32_t key(float seed) { return static_cast<uint32_t>(seed * 16777216.0f); }
} // namespace BurnProfile
