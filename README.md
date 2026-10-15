# Hyprfuego

A Compiz-inspired burn animation for closing Hyprland windows: soft, turbulent
flames, a charred edge, drifting embers and translucent smoke. Open and move animations
keep your existing settings. The shader defaults to 1.15 seconds and runs only during close.

Uses the exact HyprWindowShade revision that passed the live test on this machine.
Its C++ source is included in `vendor/HyprWindowShade`, with upstream's
MIT license and a local fix for null-buffer closes (see `vendor/UPSTREAM.md`).
The flame shader and management command are Hyprfuego's own code.
This is a shader recreation, not a port of Compiz's original particle engine.

## Try it

```bash
cd ~/source/hyprfuego
./hyprfuego preview
```

Run inside your ordinary Hyprland terminal. It opens one floating terminal which
burns away after five seconds. The temporary rule is cleared with a config reload;
a plugin loaded just for the preview is then unloaded. Personal configuration
files are not edited by preview. If Hyprfuego is already enabled, it stays enabled.

Enable the effect for all windows and load it at future session starts:

```bash
./hyprfuego enable
```

This backs up `~/.config/hypr/hyprland.lua`, creates the managed
`~/.config/hypr/hyprfuego.lua`, and adds a marked `dofile` block to the main config.
The plugin is loaded after the compositor starts, never during config parsing.
The command also loads it in the current session and checks `hyprctl configerrors`.
If applying the config fails, the previous files are restored. Repeated enable
commands replace the same block rather than adding duplicate rules.

Disable it with:

```bash
./hyprfuego disable
```

This removes only the marked configuration block, reloads the config and unloads
Hyprfuego's own plugin. Other settings and subsequent personal edits are preserved.
The managed module, source, build products and backups remain available.

After a plugin source update, replace the running build with:

```bash
./hyprfuego reload
```

This builds first, checks that the loaded plugin belongs to this source directory,
then unloads the previous build and loads the new one. Existing burn rules stay
enabled. If loading fails, it attempts to put the previous binary back.

The local snapshot fix addresses applications that attach a null buffer to unmap:
Hyprland 0.56.2 applies that state before taking its normal close snapshot, so it
can capture the decorations after the surface contents have already disappeared.
Hyprfuego captures the full window just before applying that null-buffer commit
and gives the earlier image to the existing close-animation path. It makes no
per-frame window copies and keeps the temporary snapshot for that commit only.
The user confirmed that this snapshot fix also burns application contents on
the live desktop after reloading the patched plugin.

## Build and validation

```bash
./hyprfuego build
./hyprfuego check
python3 -m unittest discover -s tools -p 'test_*.py'
```

Build requires the installed Hyprland development headers, C++23 compiler, make,
pkg-config and binutils, with Hyprland's development dependencies. The source is
vendored, so no download or sudo command is needed. Builds live under `build/`.

`check` uses glslangValidator and Python with PyOpenGL, NumPy and Pillow. It runs
the actual GLSL shader in a surfaceless Mesa EGL context and saves
`build/burn-preview.gif` and `build/burn-contact-sheet.png`. It verifies exact
first/last frames, transparent margins, premultiplied alpha, decreasing opaque
area, bottom-to-top burning of an off-centre window inside a monitor snapshot,
visible translucent smoke residue and warm sparks.
These checks use software rendering and do not replace a live desktop preview.
The control tests exercise repeated enable, rollback and preserving personal config.

## Compatibility and tuning

Pinned for **Hyprland 0.56.2**, commit
`efb50993780079460b0cbed1363e2166a2de1d9f`. The loader verifies the running commit
and the built file's checksum. After a Hyprland upgrade it refuses to load this
plugin until the integration is updated. Disable remains available after updates.
Keep this source directory in place while enabled: configuration and startup
loading refer to its paths.

Set the close duration in seconds:

```bash
./hyprfuego duration          # show the current duration
./hyprfuego duration 1.8      # slower: 1.8 seconds
./hyprfuego duration 0.8      # faster: 0.8 seconds
./hyprfuego duration default  # restore the shader default (1.15 seconds)
```

Values from 0.1 to 5 seconds are supported. The preference is saved in
`~/.config/hyprfuego/config.json` (or `$XDG_CONFIG_HOME/hyprfuego/config.json`).
When enabled, the command applies it immediately with a config reload and checks
for errors; a failed apply restores the previous setting, runtime value and managed rule.
It also controls previews and persists across logins and enable/disable cycles.
The duration changes playback time, retaining the original linear progress curve.
The setting applies to all closes started after the command, including windows
that were already open. A close already in progress keeps its original duration.
Window tags stay stable; the plugin resolves the current duration at close creation,
so legacy `@5` tags cannot override a newer one-second setting.
The native regression test is `tools/test_close_duration.cpp`. A live terminal
check reproduced a retained `@5` tag on an existing window, changed the setting
to one second, and verified that both it and a newly opened terminal had finished
before 1.4 seconds. The screenshots and counts are in `build/timing-fix/live/`.

The effect applies to ordinary main application windows. Child/transient windows,
modal dialogs and X11 override-redirect windows keep
the normal close behavior. This uses the relationships and roles reported by the
application; an auxiliary window reported as an independent ordinary toplevel
cannot be identified reliably from process ID alone. A Wayland dialog object by
itself does not disqualify a main window: GTK may create one without assigning a
parent. Independent main windows
from the same app are each eligible. The filter is applied before snapshot
capture and again before burn/reflow timing is attached.
A live GTK/Nautilus check verifies a visible burn on Files and a plain GTK main
window, with no fire on a transient/modal dialog. Screenshots and pixel counts
are under `build/files-filter-check/`.

The burn rises from the bottom with the original five smoothly joined speed
controls and variable patch widths. Left/right sweeps, central holes and the
later independently accelerating patches are not used. A fresh seed is selected
once per close; the plugin compares the broad motion against the previous eight
closes on that workspace. It tries at most 64 candidates, choosing the most
different candidate if none clears the distance threshold. Similar patterns can
still occur over time. CPU/GPU profile agreement is checked by rendering the
controls directly. Both normal and constant-size preview shaders use this profile.
Changes to the native seed selection or main-window filter require
`./hyprfuego reload`; shader edits reload automatically.

Edit `shaders/burn-close.glsl` to change the palette or flame geometry. Its
`// @duration 1.15` is the default used when there is no duration preference.
Untouched source areas stay intact except for the narrow charred edge and the
translucent fire/smoke. Transparent source areas stay transparent, so the effect
remains inside the window snapshot's original alpha. Fullscreen windows retain
HyprWindowShade's default fullscreen policy.

The shader uses two-octave noise, 32 procedural ember trajectories, and pale
smoke wisps advected upward from earlier points on the burn. Sparks have
individual birth times, lifetimes and sideways drift, with a bright core, halo
and short streak. They are checked for activity before computing their burn-front
origin. Smoke is broken up by moving noise and can remain visible after the flame
passes. These are shader approximations, not a fluid or particle simulation.
The original stylized shader remains in `shaders/burn-close-classic.glsl` and the
first softer version in `shaders/burn-close-smoky.glsl`.

Check the close seed generator and render its actual sequence through GLSL:

```bash
mkdir -p build/randomization
g++ -std=c++17 -O2 tools/test_close_seed.cpp -o build/randomization/test-close-seed
build/randomization/test-close-seed build/randomization/profiles.txt > build/randomization/seeds.txt
python3 tools/render.py --seeds build/randomization/seeds.txt --profiles build/randomization/profiles.txt --output build/randomization
```

The native test checks range and variation across 1,000 samples and compares
900 interleaved workspace closes with their previous eight shapes. The render
test checks 128 actual seeds at three animation phases, verifies CPU/GPU profile
agreement, transparency and decreasing opaque area, and reports broad shape
similarity in `build/randomization/variety.json`.
`build/randomization/burn-patterns.png` compares the first 18 closes at the same
animation phase. The comparison measures whole outlines rather than tiny
flame/particle details, so cosmetic noise cannot disguise repeated templates.


## Test constant-size flames

```bash
./hyprfuego preview --size-test
```

This previews a separate shader on a 760x480 window, then a 440x260 window.
Flame height, smoke detail and spark dimensions use the same pixel reference
on both, rather than scaling with window height. This is a preview only:
ordinary windows continue to use `shaders/burn-close.glsl`. The candidate is
`shaders/burn-close-size-preview.glsl`; it is not enabled globally.
The command updates the loaded Hyprfuego plugin first if a newer build is ready,
which also activates the per-workspace pattern fix.

`./hyprfuego status` shows whether the config block and plugin are active.

## Rendering cost

The current shader uses 32 sparks rather than 48, checks lifetime before
calculating each active spark's geometry, and uses two-octave turbulence for flame warp and detail. This restores more
texture than the first performance pass while keeping less work than the original
three-octave fields.
Flame and smoke calculations are limited to their visible envelopes. The previous
active shader and plugin manifest are saved under `build/directions-before/` as
a local rollback checkpoint; these generated artifacts are not included in Git.

On 2026-10-15, warmed 800x550 draws on the Intel HD 520 measured
15.14 ms median before and 2.97 ms after (24 draws per version),
about 80% less GPU draw time. The current p95 was 5.05 ms. Reports
are in `build/directions-gpu-before/` and `build/middle-ground-gpu/`.

These GPU timings measure a single shader pass, not total compositor frame time.
The 800x550 validation source is smaller than many desktop windows, so live frame
pacing still needs observation during ordinary use.

Reproduce a software-renderer measurement and save raw comparison frames with:

```bash
python3 tools/render.py --benchmark --save-frames --output build/benchmark
# Use the actual GPU when a render device is available:
LIBGL_ALWAYS_SOFTWARE=0 python3 tools/render.py --benchmark-only --output build/gpu-benchmark
```

`benchmark.json` records the renderer, shader hash, draw times and resolution.
Native and GPU profile checks, smoke visibility, transparency and 128-close
motion comparisons are saved under `build/middle-ground-gpu/`; the constant-size
variant is checked under `build/middle-ground-size-gpu/`.

The user created Btrfs root snapshot **29**, named **beforeFire**, before testing.
That snapshot excludes `/home`, so the config backups are the separate undo path
for this integration.
