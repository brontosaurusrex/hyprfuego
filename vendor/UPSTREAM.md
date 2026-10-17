# Vendored HyprWindowShade

- Upstream: <https://github.com/ManofJELLO/HyprWindowShade>
- Revision: `a4c6b8af424a189072427c4c90ef2938e1b481d3`
- Tested compositor: Hyprland 0.56.2, `efb50993780079460b0cbed1363e2166a2de1d9f`
- License: MIT; see [HyprWindowShade/LICENSE](HyprWindowShade/LICENSE).

The source is included for reproducible offline builds. The shader, manager and
local patches below are Hyprfuego additions. Upstream documentation remains in
[HyprWindowShade/README.md](HyprWindowShade/README.md).

## Snapshot preservation

`EarlySnapshot.cpp` hooks an explicit null-buffer attach on a mapped main window
with a close shader. It captures the full window before `updateFrom()` clears its
texture, then supplies that framebuffer to `CWindowFadeout::create`. The snapshot
exists only for that synchronous commit; ordinary commits, subsurfaces and
windows without close shaders keep their original path.

`Globals.hpp`, `Hooks.cpp` and `main.cpp` connect the hook and unload cleanup.
This avoids decoration-only burns without making per-frame copies or retaining
client buffers.

## Close seeds and profiles

`CloseSeed.hpp` generates a fresh seed once per close, independently of recycled
window addresses. The seed stays fixed throughout the fadeout. `BurnProfile.hpp`
mirrors the shader's four/five/six-control bottom-up profiles with integer hashes
and linear progress, allowing CPU/GPU agreement checks and comparison with the
last sixteen closes on each workspace. Candidate counts follow a 20/60/20 percent
mix. Point spacing uses separate hash channels from control values, preserving
smooth joins and the existing height limits. Candidate selection and stored
workspace history are bounded. Open and move shaders retain their existing
per-window seeds.

## Main-window filter

`isMainAppWindow()` excludes actual parented, transient, modal, popup and X11
override-redirect windows. Rule processing clears the close shader for children
while their parent still exists; snapshot capture and fadeout creation also check
eligibility. Ineligible windows do not receive custom close/reflow timing.

The existence of an `xdg_dialog_v1` object alone does not exclude a window: the
protocol's hints have no effect without a parent toplevel. This keeps normal GTK
main windows, including Files, eligible. Independent windows are not classified
by PID or window size. Apps must report their relationships correctly.

## Optional theme colors

`ThemeColors.hpp` reads the user-controlled `hyprfuego/theme-colors` setting and
Omarchy's active accent once in `tagFadeout()`. Its brightness-normalized tint
is retained in the fadeout and uploaded through the cached `theme_accent`
uniform. Theme switches and toggles affect the next close, with no per-frame
filesystem work. Zero is the default uniform, preserving natural fire when off.

## Runtime duration

`CloseDurations.hpp` stores per-shader preferences exposed through the Lua
`closeduration(path, seconds)` API. Close and reflow creation prefer the current
value over cached window-rule durations. `tagFadeout()` copies that value once,
so animations already underway retain their original clock.

The manager applies preferences to the main and size-preview shaders at plugin
load/reload and rolls them back if a settings update fails. Window tags stay
stable, preventing stale `@5` values from overriding a new one-second preference.

All native patches require rebuilding and reloading the plugin. GLSL edits alone
reload automatically. See [development and validation](../docs/development.md).
