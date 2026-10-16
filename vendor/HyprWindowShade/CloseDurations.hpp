#pragma once
#include <cmath>
#include <string>
#include <unordered_map>

// Per-shader live preferences take precedence over cached window-rule tags.
// Sample once when creating a close, so an in-flight animation keeps its clock.
class CloseDurations {
  public:
    bool set(const std::string& path, float seconds) {
        if (path.empty() || !std::isfinite(seconds) || seconds < 0.1f || seconds > 20.0f) return false;
        m_values[path] = seconds;
        return true;
    }
    float resolve(const std::string& path, float cachedOverride = -1.0f) const {
        const auto it = m_values.find(path);
        return it == m_values.end() ? cachedOverride : it->second;
    }
    void clear() { m_values.clear(); }
  private:
    std::unordered_map<std::string, float> m_values;
};
