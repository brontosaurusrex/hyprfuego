# Hyprfuego

A Compiz-inspired burn animation for closing Hyprland windows: soft, turbulent
flames, a charred edge, drifting embers and translucent smoke. Open and move animations
keep your existing settings. The shader runs for 1.15 seconds only during close.

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
translucent smoke residue and detached warm embers.
These checks use software rendering and do not replace a live desktop preview.
The control tests exercise repeated enable, rollback and preserving personal config.

## Compatibility and tuning

Pinned for **Hyprland 0.56.2**, commit
`efb50993780079460b0cbed1363e2166a2de1d9f`. The loader verifies the running commit
and the built file's checksum. After a Hyprland upgrade it refuses to load this
plugin until the integration is updated. Disable remains available after updates.
Keep this source directory in place while enabled: configuration and startup
loading refer to its paths.

Edit `shaders/burn-close.glsl` to change the palette or flame geometry. Its
`// @duration 1.15` sets the duration. The plugin reloads shader edits automatically;
no rebuild is needed. Source pixels above the burn front remain unchanged except
for the narrow charred edge. Transparent source areas stay transparent, which
confines the flames to the window snapshot's existing alpha. Fullscreen windows
follow HyprWindowShade's default fullscreen policy; no fullscreen override is added.

The softer flame shader uses advected noise for translucent wisps, a few taller
flame tongues, pale rolling smoke and 48 procedural ember trajectories. The
burn front uses five independently randomized speeds joined with smooth curves.
Their positions also vary continuously, producing differently sized fast and slow
patches instead of choosing among six left/middle/right orders. Different parts
therefore ignite and finish at different times, while already burned areas stay gone.
Each close gets a fresh seed from a plugin-owned random sequence, rather than
from the window's potentially reused memory address. That seed is stored for
the entire fadeout, keeping the flames steady within one animation. Seed generation
runs once per close and adds no per-pixel work.
This profile update is shader-only and reloads automatically on subsequent closes;
it needs no new plugin binary. Both the normal and constant-size shaders use it.
Two closes can naturally have the same broad leading side while their shapes differ.
Embers spawn at their part of the moving front, with individual births,
lifetimes, sideways drift, bright cores, orange halos and short streaks. They
scale with window size so they remain visible on a scaled desktop.
Smoke and sparks can remain in the burned region until the effect ends. They
stay inside the snapshot's original alpha, so they do not draw over unrelated
areas of the desktop. These are procedural shader particles, not a separate
particle simulator. The original stylized shader is preserved as
`shaders/burn-close-classic.glsl`, and the first softer, even-speed version as
`shaders/burn-close-smoky.glsl`. `Pasted image.png` is the user's burning-paper
reference for the localized tall flames, hot char edge and pale smoke.

Check the close seed generator and render its actual sequence through GLSL:

```bash
mkdir -p build/randomization
g++ -std=c++17 -O2 tools/test_close_seed.cpp -o build/randomization/test-close-seed
build/randomization/test-close-seed > build/randomization/seeds.txt
python3 tools/render.py --seeds build/randomization/seeds.txt --output build/randomization
```

The native test checks range and variation across 1,000 samples and fresh seeds
across 900 interleaved workspace closes. The render test checks that actual seeds
produce left-, middle-, and right-leading burns, and at least 12 distinct broad
outlines in 18 closes. It groups similar outlines so tiny contour jitter cannot
disguise repeated templates. `build/randomization/burn-patterns.png` compares the
closes at the same animation phase. The old six-order shader fails this check;
the continuous profile produced 17 distinct outlines from the same 18 seeds.

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

The active shader keeps all 48 ember trajectories and the same flame/smoke
detail. It skips expensive ember shading outside each tiny spark's visible halo,
reuses the known birth phase instead of regenerating its burn schedule, and
evaluates flame/smoke turbulence only inside their visible envelopes. Only
exponentially tiny glow tails are culled. It keeps the original 1.15-second timing.
The previous shader is preserved as `shaders/burn-close-detailed.glsl`.

On 2026-10-14, warmed 800x550 single-shader draws on Mesa llvmpipe measured
98.56 ms median before and 50.91 ms after (24 draws per version). This is a
48.4% reduction in software-rendering time, not a live desktop GPU FPS result.
Comparing 41 RGBA frames found seven changed channel values, each by one 8-bit
step; all other values matched. Shader validation, uneven regional burning,
smoke, ember visibility and transparency checks pass.

Reproduce a software-renderer measurement and save raw comparison frames with:

```bash
python3 tools/render.py --benchmark --save-frames --output build/benchmark
```

Before/after samples and images are in `build/performance-before/` and
`build/performance-after/`; `build/performance-comparison.json` records the
timings, shader hashes and pixel comparison. This measures the shader alone;
compositor passes and live frame pacing still need observation on the desktop.

The user created Btrfs root snapshot **29**, named **beforeFire**, before testing.
That snapshot excludes `/home`, so the config backups are the separate undo path
for this integration.
