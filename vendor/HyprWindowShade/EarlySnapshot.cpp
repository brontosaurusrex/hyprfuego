// Hyprfuego local fix: capture before a null-buffer commit clears window pixels.
#include "Globals.hpp"
#include <hyprland/src/protocols/core/Compositor.hpp>
#include <hyprland/src/protocols/XDGShell.hpp>
#include <hyprland/src/xwayland/XSurface.hpp>
#include <hyprutils/utils/ScopeGuard.hpp>

static CFunctionHook* earlyCommitHook = nullptr;
static std::unordered_map<Desktop::View::CWindow*, SP<Render::IFramebuffer>> earlySnapshots;
using TCommitState = void (*)(CWLSurfaceResource*, SSurfaceState&);

bool isMainAppWindow(PHLWINDOW window) {
    if (!window || window->parent() || window->isModal()) return false;
    if (auto xdg = window->m_xdgSurface.lock()) {
        if (xdg->m_popup) return false;
        // GTK may create an xdg_dialog object for an ordinary main window.
        // The protocol says it has no effect without a parent. Parenthood and
        // isModal() above describe the actual role; object existence does not.
        if (auto top = xdg->m_toplevel.lock(); top && top->m_parent) return false;
    }
    if (auto x11 = window->m_xwaylandSurface.lock()) {
        if (x11->m_parent || x11->m_transient || x11->m_modal || x11->m_overrideRedirect) return false;
    }
    return true;
}

static void hkCommitState(CWLSurfaceResource* surface, SSurfaceState& state) {
    PHLWINDOW window;
    // Only an explicit null-buffer attach unmaps a Wayland toplevel. SHM
    // buffers may already have been released after upload, so use the current
    // texture/size to determine whether there are still pixels to preserve.
    if (surface && state.updated.bits.buffer && !state.buffer &&
        surface->m_current.texture && surface->m_current.size.x > 0 &&
        surface->m_current.size.y > 0 && !g_pHyprRenderer->m_bRenderingSnapshot) {
        if (auto wlSurface = Desktop::View::CWLSurface::fromResource(surface->m_self.lock()))
            window = Desktop::View::CWindow::fromView(wlSurface->view());
    }

    // The map entry exists for this commit call only. No per-frame copies,
    // retained client buffers, or callbacks outliving a plugin unload.
    Hyprutils::Utils::CScopeGuard cleanup([&window] {
        if (window) earlySnapshots.erase(window.get());
    });
    if (window && window->m_isMapped && isMainAppWindow(window) && window->wlSurface()->resource().get() == surface) {
        const auto it = g_mWindowRuleShaders.find(window.get());
        if (it != g_mWindowRuleShaders.end() && !it->second.closeAnim.empty() &&
            !window->m_ruleApplicator->noAnim().valueOrDefault()) {
            try {
                if (auto snapshot = g_pHyprRenderer->makeSnapshotFB(window))
                    earlySnapshots[window.get()] = std::move(snapshot);
            } catch (...) {
                // A capture failure must never interfere with the app's commit.
            }
        }
    }
    // Calls updateFrom(), which clears size/texture, then triggers unmap and
    // CWindowFadeout::create synchronously. Its hook consumes our saved snapshot.
    reinterpret_cast<TCommitState>(earlyCommitHook->m_original)(surface, state);
}

SP<Render::IFramebuffer> takeEarlySnapshot(Desktop::View::CWindow* window) {
    auto it = earlySnapshots.find(window);
    if (it == earlySnapshots.end()) return nullptr;
    auto result = std::move(it->second);
    earlySnapshots.erase(it);
    return result;
}

bool initEarlySnapshotHook() {
    for (const auto& match : HyprlandAPI::findFunctionsByName(PHANDLE, "commitState")) {
        if (match.signature != "_ZN18CWLSurfaceResource11commitStateER13SSurfaceState") continue;
        earlyCommitHook = HyprlandAPI::createFunctionHook(PHANDLE, match.address, reinterpret_cast<void*>(&hkCommitState));
        return earlyCommitHook && earlyCommitHook->hook();
    }
    return false;
}

void cleanupEarlySnapshotHook() {
    if (earlyCommitHook) HyprlandAPI::removeFunctionHook(PHANDLE, earlyCommitHook);
    earlyCommitHook = nullptr;
    earlySnapshots.clear();
}
