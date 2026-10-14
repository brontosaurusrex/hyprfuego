#pragma once
#include <cstdint>
#include <unordered_map>

// A sequence per plugin instance, sampled ONCE at fadeout creation. Window
// addresses may be recycled, and time sampled per frame would make fire jump.
class CloseSeedSequence {
  public:
    explicit CloseSeedSequence(uint64_t initial) : m_state(initial) {}
    float next(int64_t workspace = 0) {
        static constexpr uint8_t leading[] = {0, 2, 1, 2, 1, 0};
        auto previous = m_lastLeading.find(workspace);
        uint32_t order;
        do {
            order = static_cast<uint32_t>(randomBits() % 6);
        } while (previous != m_lastLeading.end() && leading[order] == previous->second);
        m_lastLeading[workspace] = leading[order];
        // Encode the permutation directly in one of six bins. Leave generous
        // margins so float rounding cannot move it into the neighbouring bin.
        const float jitter = static_cast<float>(randomBits() >> 40) / 16777216.0f;
        return (static_cast<float>(order) + 0.125f + jitter * 0.75f) / 6.0f;
    }

  private:
    uint64_t randomBits() {
        uint64_t value = (m_state += UINT64_C(0x9e3779b97f4a7c15));
        value = (value ^ (value >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
        value = (value ^ (value >> 27)) * UINT64_C(0x94d049bb133111eb);
        value ^= value >> 31;
        return value;
    }

    uint64_t m_state;
    std::unordered_map<int64_t, uint8_t> m_lastLeading;
};
