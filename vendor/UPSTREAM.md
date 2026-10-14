HyprWindowShade is based on:
https://github.com/ManofJELLO/HyprWindowShade

Commit: a4c6b8af424a189072427c4c90ef2938e1b481d3
Hyprland: efb50993780079460b0cbed1363e2166a2de1d9f (0.56.2)
License: MIT; see HyprWindowShade/LICENSE.

This upstream revision passed the user's live load, rendering, close-animation,
and unload test on 2026-10-14. No network access is required to build Hyprfuego.

Local patch: EarlySnapshot.cpp hooks CWLSurfaceResource::commitState only for
an explicit null-buffer attach on a mapped main window with a close shader.
It captures the full window before updateFrom() clears its texture and size,
then substitutes that framebuffer in CWindowFadeout::create. The temporary
snapshot is scoped to that one synchronous commit call. Ordinary commits,
subsurfaces, windows without close shaders and client close semantics are unchanged.
Globals.hpp, Hooks.cpp and main.cpp connect the hook and its unload cleanup.
This patch requires a rebuilt plugin and a live reload; editing GLSL is insufficient.

Local patch: CloseSeed.hpp supplies a cheap random sequence seeded once at plugin
load. tagFadeout samples it once per close and stores that seed in FadeoutAnim.
The old close seed was derived only from a window pointer, so reused addresses
could repeat the same burn pattern. Open/move shaders retain their existing
per-window seeds. This change also requires rebuilding/reloading the plugin.

The close sequence additionally remembers the last leading region per workspace
and selects a different one next time. The permutation is encoded directly in
one of six float seed bins and decoded with floor(seed * 6) in Hyprfuego's shader.
This avoids a second GPU hash undoing the non-repetition rule. Independent random
fractions within each bin still vary the fine flame/smoke/ember details.
