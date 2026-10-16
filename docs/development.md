# Development

## Source layout

| Path | Purpose |
| --- | --- |
| `hyprfuego` | Build, preview, effect selection, duration and configuration controls |
| `effects/burn/burn-close.glsl` | Burn close shader |
| `effects/burn/burn-close-size-preview.glsl` | Optional constant-size flame experiment |
| `effects/burn/burn-close-{classic,smoky,detailed}.glsl` | Preserved historical burn variants |
| `effects/teleport/close.glsl` | Transporter dissolve and independent energy tail |
| `shaders/` | Compatibility symlinks to the burn shaders |
| `vendor/HyprWindowShade/` | Pinned plugin with local integration patches |
| `tools/` | Native regression tests, control tests and GLSL rendering |
| `docs/images/` | Published previews and their source/asset hashes |
| `build/` | Ignored binaries, generated previews and local validation records |

Keep the active GLSL burn schedule synchronized with `BurnProfile.hpp` and the
constant-size shader. The CPU compares broad shapes on a 9×7 grid at three phases
against the last eight closes on the same workspace. It tries at most 64 seeds,
accepting an RMS distance of 0.04 or choosing the most different candidate.
This reduces recent repetition; it cannot guarantee that no two closes resemble
each other. History resets when the plugin unloads.

## Build and checks

```bash
./hyprfuego build
./hyprfuego check
python3 -m unittest discover -s tools -p 'test_*.py'
```

The native plugin requires the exact compositor/header commit documented in the
[README](../README.md). Build products use a source fingerprint under `build/`;
`build/plugin.json` identifies the current binary and checksum. Do not delete the
loaded binary or its manifest while the effect is enabled.

The two native regressions can run without a compositor:

```bash
mkdir -p build/tests
g++ -std=c++17 -O2 tools/test_close_seed.cpp -o build/tests/test-close-seed
build/tests/test-close-seed build/tests/profiles.txt > build/tests/seeds.txt
g++ -std=c++17 -O2 tools/test_close_duration.cpp -o build/tests/test-close-duration
build/tests/test-close-duration
python3 tools/render.py --seeds build/tests/seeds.txt --profiles build/tests/profiles.txt --output build/tests/render
```

The seed test checks 1,000 samples and 900 interleaved workspace closes. The
duration regression checks the 0.1–20-second range, a five-to-one-second change
with stale per-window values, unrelated shaders and animations already in
progress. Rendering compares the CPU/GPU profiles across 128 closes and checks
visibility and alpha invariants.
Software-rendered checks do not replace a live desktop preview.

Teleport's renderer checks exact endpoints, alpha bounds, monotonically decreasing
opaque area and 18 seeded wakes. It renders a second source with different RGB
but identical alpha: from 40% onward both results must be pixel-identical, proving
that the tail contains only generated energy. Energy must remain visible at 65%.
The RGB comparison also checks that material breaks up in the upper, middle and
lower thirds together, rather than following a directional wipe. All wake pixels
must have red <= green <= blue, guarding the requested bluish-white palette.
Control regressions also cover effect switching, preserved duration preferences,
the selected effect's default duration and failed-switch rollback.

`// @reflow natural` opts a close shader out of survivor movement retiming. It
does not shorten the snapshot lifetime or use an overlay that would inherit the
compositor's fade-out opacity. Focus and input remain owned by Hyprland; the
snapshot is visual and receives no input. Burn omits the directive and retains
its synchronized reflow.

The live two-window teleport check on 2026-10-16 used a two-second effect: the
surviving window had focus after 0.087 seconds and received keyboard input after
0.324 seconds. A screenshot at 60% shows the energy wake over the active window.
Local evidence is in `build/teleport-handoff/`. The test restored the original
workspace and notification setting, and left the selected effect/duration intact.

## Updating published previews

```bash
python3 tools/update_previews.py --hardware
python3 tools/update_previews.py --effect teleport --hardware
```

Omit `--hardware` to use Mesa software rendering. The default burn command compiles
and runs the native regressions, validates both GLSL variants, and renders the
burn shader. It copies these generated assets into `docs/images/`:

- `burn-preview.gif`: one complete burn, followed by a pause.
- `burn-contact-sheet.png`: six phases of that burn.
- `burn-patterns.png`: the first 18 native-generated closes at 50% progress.

`manifest.json` records the renderer, default duration, seed and source/asset
hashes. These synthetic previews contain no desktop captures. Scratch data,
including the 128 seeds, profiles, variety report and benchmark, stays in
`build/previews/`. The default `build/burn-*.png` and GIF paths are refreshed too.

The README's main image, `docs/images/files-burn-desktop.png`, is a manually
captured live desktop screenshot. The preview generator leaves it unchanged;
it is not included in the generated asset manifest.

Teleport generates `teleport-preview.gif`, `teleport-contact-sheet.png` and
`teleport-manifest.json`. Its manifest records the content/energy checks and
source hashes separately from the burn's native profile validation.

## Performance

The accepted profile uses 48 sparks and the original three-octave turbulence.
It retains early lifetime rejection, spark halo culling and flame/smoke envelope
checks. These changes reduce work while retaining the selected visual settings.

Warmed 800×550 draws on an Intel HD 520, measured on 2026-10-15 with 24 draws per
version:

| Shader | Median | 95th percentile |
| --- | --- | --- |
| Before the performance work | 15.14 ms | 16.18 ms |
| After optimization: 48 sparks, three-octave turbulence | 4.48 ms | 6.48 ms |

This run used about 70% less GPU draw time. Raw samples and tested shader hashes
are in [the baseline report](benchmarks/intel-hd520-before.json) and
[the current report](benchmarks/intel-hd520-current.json).

These burn measurements predate the subsequent palette/flow refinements; the
reports retain the exact tested shader hashes. The video-inspired teleport
shader measured on 2026-10-16 took **2.00 ms median / 4.20 ms p95** at the same
800×550 resolution on the Intel HD 520. Its samples and shader hash are in the
[teleport report](benchmarks/intel-hd520-teleport.json).

These are single-pass shader timings, excluding compilation and image readback.
They are not whole-desktop frame times or FPS measurements. Larger windows,
snapshot capture, compositing and other GPU activity can change live behavior.

To measure the current shader on the available GPU:

```bash
LIBGL_ALWAYS_SOFTWARE=0 python3 tools/render.py --benchmark-only --output build/gpu-benchmark
```

For a software measurement with raw comparison frames:

```bash
python3 tools/render.py --benchmark --save-frames --output build/software-benchmark
```

## Constant-size flame experiment

```bash
./hyprfuego preview --size-test
```

With burn selected, this previews 760×480 and 440×260 windows using a 600-device-pixel reference for
flames, smoke and sparks. It affects only the preview windows; ordinary windows
keep the active shader. To validate it offscreen with the generated seeds:

```bash
python3 tools/render.py --shader shaders/burn-close-size-preview.glsl --seeds build/previews/seeds.txt --profiles build/previews/profiles.txt --output build/size-preview
```

## Live regression checks

The following behaviors have been checked on the pinned compositor:

- Both window contents and decorations burn when an app unmaps with a null buffer.
- Files/Nautilus and ordinary GTK main windows burn; transient/modal dialogs do not.
- A window with a stale `@5` tag and a newly opened window both finish at the newly selected one-second duration.
- Enable/disable, plugin reload and configuration error checks work in the live session.

The renderer uses a synthetic window to make visual checks reproducible. Local
Files/dialog and duration screenshots remain under `build/files-filter-check/`
and `build/timing-fix/live/`; they are not published as README assets.

Superseded experiment reports and source checkpoints are kept locally under
`build/history/`, with their obsolete PNG/GIF/raw-frame outputs removed. Native
plugin build directories are retained so cleanup cannot remove a loaded binary.
