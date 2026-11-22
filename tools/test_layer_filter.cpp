#include "../vendor/HyprWindowShade/LayerFilter.hpp"
#include <cassert>
#include <iostream>
int main() {
    LayerFilter filter;
    assert(!filter.forNamespace("unseen-menu"));
    filter.path="correction.frag";
    filter.excluded={"color-correct-panel","omarchy-background"};
    // No layer registration or map-event processing is needed before draw one.
    for(const auto* ns:{"unseen-menu","omarchy-menu","omarchy-keyboard-panel","popup-owner"})
        assert(filter.forNamespace(ns) && *filter.forNamespace(ns)=="correction.frag");
    assert(!filter.forNamespace("color-correct-panel"));
    assert(!filter.forNamespace("omarchy-background"));
    filter.excluded.erase("omarchy-background");
    assert(filter.forNamespace("omarchy-background"));
    filter.path="replacement.frag";
    assert(*filter.forNamespace("unseen-menu")=="replacement.frag");
    filter.clear();
    assert(!filter.forNamespace("unseen-menu") && filter.excluded.empty());
    std::cout<<"PASS: first-draw namespace resolution, exclusions, replacement and unload cleanup\n";
}
