// Theme changes are sampled at close creation; existing closes retain their tint.
#include "../vendor/HyprWindowShade/ThemeColors.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
#include <sstream>

int main(int argc, char** argv) {
    assert(argc == 2);
    const std::filesystem::path root(argv[1]);
    const auto config = root / "config", state = root / "state";
    const auto mode = config / "hyprfuego/theme-colors";
    const auto palette = state / "omarchy/current/theme/colors.toml";
    std::filesystem::create_directories(mode.parent_path());
    std::filesystem::create_directories(palette.parent_path());
    std::filesystem::remove(mode);
    assert(ThemeColors::read(config, state)[3] == 0);
    std::ofstream(mode) << "on\n";
    std::filesystem::remove(palette);
    assert(ThemeColors::read(config, state)[3] == 0);
    std::ofstream(palette) << "mode = \"dark\"\n accent = \"#102030\" # dark accent\n";
    const auto first = ThemeColors::read(config, state);
    assert(first[3] == 1 && first[2] == 1);
    assert(std::abs(first[0] - 1.f / 3.f) < 0.00001f);
    assert(std::abs(first[1] - 2.f / 3.f) < 0.00001f);
    std::ofstream(palette) << "accent = '#90ffb0'\n";
    const auto second = ThemeColors::read(config, state);
    assert(second != first && second[1] == 1 && first[2] == 1);
    std::ofstream(mode) << "off\n";
    assert(ThemeColors::read(config, state)[3] == 0);
    assert(second[3] == 1); // Existing close's copy survives a toggle.
    for (const auto* text : {"accent = '#000000'", "accent = '#ffffff'", "accent = '#f0e0d0'"}) {
        std::istringstream source(text);
        const auto accent = ThemeColors::parseAccent(source);
        assert(accent[3] == 1 && std::max({accent[0], accent[1], accent[2]}) == 1);
        for (float component : accent) assert(std::isfinite(component) && component >= 0 && component <= 1);
    }
    for (const auto* text : {"", "accent = '#invalid'", "accent = '#1234567'", "accent = '#123456' extra", "accent = 'blue'"}) {
        std::istringstream source(text);
        assert(ThemeColors::parseAccent(source)[3] == 0);
    }
    std::cout << "PASS: theme on/off, missing/invalid palettes, hue-preserving brightness, theme switches and stable close colors.\n";
}
