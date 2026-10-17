# Development

## Source layout

| Path | Purpose |
| --- | --- |
| `hyprfuego` | Build, preview, duration and configuration controls |
| `shaders/burn-close.glsl` | Active close shader |
| `shaders/burn-close-size-preview.glsl` | Optional constant-size flame experiment |
| `shaders/burn-close-classic.glsl` | Preserved original stylized shader |
| `shaders/burn-close-smoky.glsl` | Preserved first softer shader |
| `shaders/burn-close-detailed.glsl` | Preserved shader before envelope optimizations |
| `vendor/HyprWindowShade/` | Pinned plugin with local integration patches |
| `tools/` | Native regression tests, control tests and GLSL rendering |
| `docs/images/` | Published previews and their source/asset hashes |
| `build/` | Ignored binaries, generated previews and local validation records |

Keep the active GLSL burn schedule synchronized with `BurnProfile.hpp` and the
constant-size shader. The CPU compares broad shapes on a 9×7 grid at three phases
against the last sixteen closes on the same workspace. It tries at most 64 seeds,
accepting an RMS distance of 0.04 or choosing the most different candidate.
This reduces recent repetition; it cannot guarantee that no two closes resemble
each other. History resets when the plugin unloads.

The broad burn outline blends halfway toward a uniform front, halving its
vertical variation at every phase. Flame turbulence and spark count are unchanged.

Candidate profiles use five control points about 60% of the time, with four and
six points about 20% each. Interior positions use independent hash channels and
bounded jitter around even spacing. The five-point positions retain their
original ranges; all counts use the same smoothstep joins, normalized timing,
height limits and linear progress. Native tests check the distribution, smooth
joins, minimum spacing, monotonic advance and the sixteen-close history.

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

The native regressions can run without a compositor:

```bash
mkdir -p build/tests
g++ -std=c++17 -O2 tools/test_close_seed.cpp -o build/tests/test-close-seed
build/tests/test-close-seed build/tests/profiles.txt > build/tests/seeds.txt
g++ -std=c++17 -O2 tools/test_close_duration.cpp -o build/tests/test-close-duration
build/tests/test-close-duration
g++ -std=c++17 -O2 tools/test_theme_colors.cpp -o build/tests/test-theme-colors
build/tests/test-theme-colors build/tests/theme-colors
python3 tools/render.py --seeds build/tests/seeds.txt --profiles build/tests/profiles.txt --output build/tests/render
```

The seed test checks 1,000 samples and 900 interleaved workspace closes. The
duration regression checks a five-to-one-second change with stale per-window
values, unrelated shaders and animations already in progress. Rendering compares
the CPU/GPU profiles across 128 closes and checks visibility and alpha invariants.
Software-rendered checks do not replace a live desktop preview.

The theme-color regression covers toggles, missing or invalid palettes, dark and
neutral accent brightness, theme switches, and colors retained by active closes.
The renderer checks blue, pink and neutral tints, unchanged alpha and geometry,
and restoration of natural fire when the tint is disabled.

## Updating published previews

```bash
python3 tools/update_previews.py --hardware
```

Omit `--hardware` to use Mesa software rendering. The command compiles and runs
the native regressions, validates both GLSL variants, and renders the main shader.
It copies these generated assets into `docs/images/`:

- `burn-preview.gif`: one complete burn, followed by a pause.
- `burn-contact-sheet.png`: six phases of that burn.
- `burn-patterns.png`: the first 18 native-generated closes at 50% progress.
- `burn-theme-colors.png`: blue, pink and neutral flame palettes at 50% progress.

`manifest.json` records the renderer, default duration, seed and source/asset
hashes. These synthetic previews contain no desktop captures. Scratch data,
including the 128 seeds, profiles, variety report and benchmark, stays in
`build/previews/`. The default `build/burn-*.png` and GIF paths are refreshed too.

The README's main image, `docs/images/files-burn-desktop.png`, is a manually
captured live desktop screenshot. The preview generator leaves it unchanged;
it is not included in the generated asset manifest.

## Performance

The accepted profile uses 48 sparks and the original three-octave turbulence.
It retains early lifetime rejection, spark halo culling and flame/smoke envelope
checks. These changes reduce work while retaining the selected visual settings.

Warmed 800×550 draws on an Intel HD 520, measured on 2026-10-15 with 24 draws per
version:

| Shader | Median | 95th percentile |
| --- | --- | --- |
| Before the performance work | 15.14 ms | 16.18 ms |
| Current: 48 sparks, three-octave turbulence | 4.48 ms | 6.48 ms |

This run used about 70% less GPU draw time. Raw samples and tested shader hashes
are in [the baseline report](benchmarks/intel-hd520-before.json) and
[the current report](benchmarks/intel-hd520-current.json).

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

This previews 760×480 and 440×260 windows using a 600-device-pixel reference for
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
