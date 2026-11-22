#pragma once
#include <string>
#include <unordered_set>

// Dedicated final color filter, independent of user layer shader/animation maps.
// Set once through Lua; namespaces need not exist yet. Rendering is main-thread-only.
struct LayerFilter {
    std::string path;
    std::unordered_set<std::string> excluded;
    const std::string* forNamespace(const std::string& name) const {
        return path.empty() || excluded.contains(name) ? nullptr : &path;
    }
    void clear() {path.clear();excluded.clear();}
};
