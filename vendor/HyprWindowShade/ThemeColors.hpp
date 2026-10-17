#pragma once
#include <algorithm>
#include <array>
#include <charconv>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

namespace ThemeColors {
using Accent = std::array<float, 4>; // RGB tint; alpha enables themed flames.

inline std::string trim(const std::string& value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    return first == std::string::npos ? "" : value.substr(first, value.find_last_not_of(" \t\r\n") - first + 1);
}

inline Accent parseAccent(std::istream& source) {
    std::string line;
    while (std::getline(source, line)) {
        const auto equals = line.find('=');
        if (equals == std::string::npos || trim(line.substr(0, equals)) != "accent") continue;
        const auto value = trim(line.substr(equals + 1));
        if (value.size() < 9 || (value[0] != '"' && value[0] != '\'') || value[1] != '#' || value[8] != value[0]) return {};
        const auto tail = trim(value.substr(9));
        if (!tail.empty() && tail[0] != '#') return {};
        unsigned rgb = 0;
        const auto parsed = std::from_chars(value.data() + 2, value.data() + 8, rgb, 16);
        if (parsed.ec != std::errc{} || parsed.ptr != value.data() + 8) return {};
        Accent accent{float((rgb >> 16) & 255), float((rgb >> 8) & 255), float(rgb & 255), 1.0f};
        const float peak = std::max({accent[0], accent[1], accent[2]});
        // Preserve the accent's hue while making even dark accents luminous.
        // A black accent becomes neutral fire, rather than invisible flames.
        for (int i = 0; i < 3; ++i) accent[i] = peak > 0 ? accent[i] / peak : 1.0f;
        return accent;
    }
    return {};
}

inline Accent read(const std::filesystem::path& config, const std::filesystem::path& state) {
    std::ifstream mode(config / "hyprfuego/theme-colors");
    std::string setting;
    if (!std::getline(mode, setting) || trim(setting) != "on") return {};
    std::ifstream colors(state / "omarchy/current/theme/colors.toml");
    return parseAccent(colors); // Missing or invalid palette keeps natural fire.
}

inline Accent current() {
    const char* home = std::getenv("HOME");
    if (!home || !*home) return {};
    const char* config = std::getenv("XDG_CONFIG_HOME");
    const char* state = std::getenv("XDG_STATE_HOME");
    return read(config && *config ? std::filesystem::path(config) : std::filesystem::path(home) / ".config",
                state && *state ? std::filesystem::path(state) : std::filesystem::path(home) / ".local/state");
}
} // namespace ThemeColors
