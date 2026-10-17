#pragma once
#include "BurnProfile.hpp"
#include <cstdint>
#include <deque>
#include <unordered_map>

// A sequence per plugin instance, sampled ONCE at fadeout creation. Window
// addresses may be recycled, and time sampled per frame would make fire jump.
class CloseSeedSequence {
  public:
    static constexpr std::size_t HISTORY_SIZE = 16;
    explicit CloseSeedSequence(uint64_t initial) : m_state(initial) {}
    float next(int64_t workspace = 0) {
        // Cap remembered workspaces as well as candidate work per close.
        if (!m_recent.count(workspace) && m_recent.size() >= 128) m_recent.clear();
        auto& recent = m_recent[workspace];
        const auto first = static_cast<uint32_t>(randomBits() >> 40);
        uint32_t best = 0;
        BurnProfile::Shape bestShape{};
        float bestDistance = -1.0f;
        for (int attempt = 0; attempt < 64; ++attempt) {
            const auto candidate = attempt == 0 ? first : static_cast<uint32_t>(randomBits() >> 40);
            const auto shape = BurnProfile::shape(candidate);
            float nearest = 1.0f;
            for (const auto& previous : recent)
                nearest = std::min(nearest, BurnProfile::distance(shape, previous));
            if (nearest > bestDistance) {
                best = candidate;
                bestShape = shape;
                bestDistance = nearest;
            }
            if (nearest >= 0.04f) break;
        }
        recent.push_back(bestShape);
        if (recent.size() > HISTORY_SIZE) recent.pop_front();
        return static_cast<float>(best) / 16777216.0f;
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
    std::unordered_map<int64_t, std::deque<BurnProfile::Shape>> m_recent;
};
