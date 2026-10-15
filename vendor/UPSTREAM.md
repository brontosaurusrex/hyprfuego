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

Local patch: BurnProfile.hpp mirrors the original five-control bottom-up profile
using integer hashes and linear progress. CloseSeed.hpp compares a spatial grid
at three phases against the last eight closes on each workspace. It tries at most
64 candidates, accepting a minimum RMS distance of 0.04 or choosing the most
different candidate on exhaustion. At most 128 workspaces are remembered.
CPU/GPU agreement is checked by tools/render.py --profiles using native profiles
emitted by tools/test_close_seed.cpp. Rebuild/reload to use the new selection.

Local patch: isMainAppWindow in EarlySnapshot.cpp excludes parented, transient,
modal and X11 override-redirect windows. Shader rules clear
the close shader for identified children while their parent still exists; the
snapshot and fadeout hooks also check eligibility. This prevents early captures,
custom fadeouts and close-driven move retiming for those subwindows. It does not
infer main-window status from PID or size, which would misclassify independent
main windows. Applications must report child/dialog relationships accurately.

Local patch: CloseDurations.hpp stores current per-shader duration preferences.
The Lua closeduration(path, seconds) API updates them without changing window tags.
The close/reflow duration resolvers prefer this value over cached rule durations;
tagFadeout copies it once, keeping animations already in progress stable. This
fixes existing windows retaining old @5 tags after the user changes to one second.
The manager reapplies both shader paths on load/reload and rolls the runtime value
back if a duration apply fails. tools/test_close_duration.cpp covers cached old
values, unrelated paths and the timing of already-started closes.

GTK filter correction: xdg_dialog_v1 is an ancillary object whose hints have no
effect without a parent toplevel. Its mere existence no longer excludes a window;
only an actual parent/modal role does. The earlier check excluded ordinary GTK4
main windows such as Files. The live Files/GTK regression check and screenshots
are saved under build/files-filter-check/.
