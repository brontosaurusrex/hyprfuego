#!/usr/bin/env python3
"""Validate the current shader and refresh the README's generated previews."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/previews"
IMAGES = ROOT / "docs/images"
ASSETS = ("burn-preview.gif", "burn-contact-sheet.png", "burn-patterns.png", "burn-theme-colors.png")


def run(*args, **kwargs):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True, **kwargs)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hardware", action="store_true", help="Use the available GPU instead of Mesa software rendering")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)
    seed_test = OUTPUT / "test-close-seed"
    duration_test = OUTPUT / "test-close-duration"
    run("g++", "-std=c++17", "-O2", "tools/test_close_seed.cpp", "-o", seed_test)
    with (OUTPUT / "seeds.txt").open("w") as stream:
        run(seed_test, OUTPUT / "profiles.txt", stdout=stream)
    run("g++", "-std=c++17", "-O2", "tools/test_close_duration.cpp", "-o", duration_test)
    run(duration_test)
    theme_test = OUTPUT / "test-theme-colors"
    run("g++", "-std=c++17", "-O2", "tools/test_theme_colors.cpp", "-o", theme_test)
    run(theme_test, OUTPUT / "theme-test")
    for name in ("burn-close.glsl", "burn-close-size-preview.glsl"):
        run("glslangValidator", "-S", "frag", ROOT / "shaders" / name)
    environment = os.environ.copy()
    environment["LIBGL_ALWAYS_SOFTWARE"] = "0" if args.hardware else "1"
    run(sys.executable, "tools/render.py", "--seeds", OUTPUT / "seeds.txt",
        "--profiles", OUTPUT / "profiles.txt", "--benchmark", "--output", OUTPUT,
        env=environment)
    for name in ASSETS:
        shutil.copyfile(OUTPUT / name, IMAGES / name)
        # Keep the default `./hyprfuego check` preview paths current as well.
        shutil.copyfile(OUTPUT / name, ROOT / "build" / name)
    shutil.copyfile(OUTPUT / "variety.json", ROOT / "build/variety.json")
    report = json.loads((OUTPUT / "benchmark.json").read_text())
    sources = ("shaders/burn-close.glsl", "shaders/burn-close-size-preview.glsl",
        "tools/render.py", "tools/update_previews.py", "tools/test_close_seed.cpp",
        "vendor/HyprWindowShade/BurnProfile.hpp", "vendor/HyprWindowShade/CloseSeed.hpp",
        "vendor/HyprWindowShade/ThemeColors.hpp")
    duration = float(re.search(r"(?m)^// @duration\s+([0-9.]+)", (ROOT / sources[0]).read_text())[1])
    manifest = {"renderer": report["renderer"], "resolution": report["resolution"],
        "reference_seed": 0.37, "default_duration_seconds": duration,
        "validated_closes": len((OUTPUT / "seeds.txt").read_text().split()),
        "sources": {name: digest(ROOT / name) for name in sources},
        "assets": {name: digest(IMAGES / name) for name in ASSETS}}
    (IMAGES / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Updated README previews in", IMAGES.relative_to(ROOT))


if __name__ == "__main__":
    main()
