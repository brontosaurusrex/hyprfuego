#!/usr/bin/env python3
"""Render the real GLSL shader with Mesa EGL; verify alpha and save previews."""
import ctypes
import hashlib
import argparse
import os
import json
import statistics
import time
from pathlib import Path

os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
os.environ.setdefault("EGL_PLATFORM", "surfaceless")
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
import numpy as np
from PIL import Image, ImageDraw
from OpenGL import EGL, GL

ROOT = Path(__file__).resolve().parents[1]
W, H = 800, 550


def shader(kind, source):
    obj = GL.glCreateShader(kind)
    GL.glShaderSource(obj, source)
    GL.glCompileShader(obj)
    if not GL.glGetShaderiv(obj, GL.GL_COMPILE_STATUS):
        raise RuntimeError(GL.glGetShaderInfoLog(obj).decode())
    return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shader", type=Path, default=ROOT / "shaders/burn-close.glsl")
    parser.add_argument("--output", type=Path, default=ROOT / "build")
    parser.add_argument("--benchmark", action="store_true", help="Measure warmed, synchronous shader draws on this EGL renderer")
    parser.add_argument("--benchmark-only", action="store_true", help="Warm and time draws without running validation or generating previews")
    parser.add_argument("--save-frames", action="store_true", help="Save raw premultiplied frames for before/after comparisons")
    parser.add_argument("--seeds", type=Path, help="Validate additional per-close seeds, one number per line")
    parser.add_argument("--profiles", type=Path, help="Compare native CPU profiles with the actual GLSL controls")
    args = parser.parse_args()
    display = EGL.eglGetDisplay(EGL.EGL_DEFAULT_DISPLAY)
    major, minor = ctypes.c_int(), ctypes.c_int()
    EGL.eglInitialize(display, major, minor)
    attrs = (ctypes.c_int * 15)(EGL.EGL_SURFACE_TYPE, EGL.EGL_PBUFFER_BIT,
        EGL.EGL_RENDERABLE_TYPE, 0x0040, EGL.EGL_RED_SIZE, 8, EGL.EGL_GREEN_SIZE, 8,
        EGL.EGL_BLUE_SIZE, 8, EGL.EGL_ALPHA_SIZE, 8, EGL.EGL_NONE, 0, 0)
    configs = (EGL.EGLConfig * 1)()
    count = ctypes.c_int()
    EGL.eglChooseConfig(display, attrs, configs, 1, count)
    assert count.value, "No ES3 pbuffer config"
    EGL.eglBindAPI(EGL.EGL_OPENGL_ES_API)
    ctxattrs = (ctypes.c_int * 3)(EGL.EGL_CONTEXT_CLIENT_VERSION, 3, EGL.EGL_NONE)
    ctx = EGL.eglCreateContext(display, configs[0], EGL.EGL_NO_CONTEXT, ctxattrs)
    surfaceattrs = (ctypes.c_int * 5)(EGL.EGL_WIDTH, W, EGL.EGL_HEIGHT, H, EGL.EGL_NONE)
    surface = EGL.eglCreatePbufferSurface(display, configs[0], surfaceattrs)
    EGL.eglMakeCurrent(display, surface, surface, ctx)
    print("Renderer:", GL.glGetString(GL.GL_RENDERER).decode())
    vertex = shader(GL.GL_VERTEX_SHADER, """#version 320 es
    precision highp float;
    out vec2 v_texcoord;
    void main() {
        vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
        v_texcoord = vec2(p.x, 1.0-p.y);
        gl_Position = vec4(p*2.0-1.0, 0, 1);
    }""")
    fragment = shader(GL.GL_FRAGMENT_SHADER, args.shader.read_text())
    program = GL.glCreateProgram()
    GL.glAttachShader(program, vertex)
    GL.glAttachShader(program, fragment)
    GL.glLinkProgram(program)
    if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
        raise RuntimeError(GL.glGetProgramInfoLog(program).decode())
    GL.glUseProgram(program)
    GL.glBindVertexArray(GL.glGenVertexArrays(1))
    GL.glViewport(0, 0, W, H)
    GL.glDisable(GL.GL_BLEND)
    GL.glDisable(GL.GL_DITHER)
    GL.glBindTexture(GL.GL_TEXTURE_2D, GL.glGenTextures(1))
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

    def uniform(name, *values):
        loc = GL.glGetUniformLocation(program, name)
        {1: GL.glUniform1f, 2: GL.glUniform2f, 4: GL.glUniform4f}[len(values)](loc, *values)

    GL.glUniform1i(GL.glGetUniformLocation(program, "tex"), 0)
    uniform("surface_size", W, H)
    uniform("seed", 0.37)
    source = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(source)
    box = (120, 80, 680, 470)
    draw.rounded_rectangle(box, radius=16, fill=(24, 29, 38, 255))
    draw.text((150, 105), "HYPRFUEGO   /   burn on close", fill=(240, 230, 200, 255), font_size=22)
    draw.line((145, 148, 655, 148), fill=(62, 70, 83, 255), width=2)
    for y, text in enumerate(["$ ./hyprfuego preview", "", "Bottom-up burn / translucent smoke.",
        "Original timing / fresh per-close curves.", "", "[render] Compiz-inspired close animation", "[ready] Hyprland 0.56.2 + HyprWindowShade"]):
        draw.text((150, 177 + y * 30), text, fill=(190, 215, 190, 255), font_size=17)
    data = np.asarray(source)
    GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, W, H, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, data)
    uniform("window_rect", 120/W, 80/H, 560/W, 390/H)

    def render(p):
        uniform("progress", p)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        raw = GL.glReadPixels(0, 0, W, H, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        return np.frombuffer(raw, np.uint8).reshape(H, W, 4)[::-1].copy()

    def benchmark():
        out = args.output
        out.mkdir(parents=True, exist_ok=True)
        timings = []
        # Shader compilation and the preceding readback checks are excluded.
        # No image download in the timed section; finish waits for each draw.
        for repeat in range(3):
            for phase in (0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85):
                uniform("progress", phase)
                GL.glFinish()
                start = time.perf_counter()
                GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
                GL.glFinish()
                timings.append((time.perf_counter() - start) * 1000)
        report = {"renderer": GL.glGetString(GL.GL_RENDERER).decode(),
            "resolution": [W, H], "draws": len(timings),
            "shader": str(args.shader), "shader_sha256": hashlib.sha256(args.shader.read_bytes()).hexdigest(), "seed": 0.37,
            "median_ms": statistics.median(timings),
            "p95_ms": float(np.percentile(timings, 95)), "samples_ms": timings}
        (out / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Shader draw benchmark: median {report['median_ms']:.2f} ms; p95 {report['p95_ms']:.2f} ms")
    def close_context():
        EGL.eglMakeCurrent(display, EGL.EGL_NO_SURFACE, EGL.EGL_NO_SURFACE, EGL.EGL_NO_CONTEXT)
        EGL.eglDestroySurface(display, surface)
        EGL.eglDestroyContext(display, ctx)
        EGL.eglTerminate(display)

    if args.benchmark_only:
        for phase in (0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85) * 2:
            render(phase)
        benchmark()
        close_context()
        return

    if args.profiles:
        # Compare the original bottom-up profile on a spatial grid at three phases.
        probe_source = args.shader.read_text().split("void main()", 1)[0] + """
        void main() {
            highp uint key = uint(seed * 16777216.0);
            vec2 c = vec2(v_texcoord.x, 1.0 - v_texcoord.y);
            fragColor = vec4(clamp(0.5 + 5.0 * vec3(c.y - burnFront(c.x, 0.3, key),
                c.y - burnFront(c.x, 0.5, key), c.y - burnFront(c.x, 0.7, key)),
                0.0, 1.0), 1.0);
        }
        """
        probe = GL.glCreateProgram()
        GL.glAttachShader(probe, vertex)
        GL.glAttachShader(probe, shader(GL.GL_FRAGMENT_SHADER, probe_source))
        GL.glLinkProgram(probe)
        assert GL.glGetProgramiv(probe, GL.GL_LINK_STATUS), GL.glGetProgramInfoLog(probe)
        GL.glUseProgram(probe)
        GL.glViewport(0, 0, 9, 7)
        native_profiles = np.loadtxt(args.profiles, ndmin=2)
        for row in native_profiles:
            GL.glUniform1f(GL.glGetUniformLocation(probe, "seed"), row[0])
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            raw = GL.glReadPixels(0, 0, 9, 7, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
            gpu = np.moveaxis(np.frombuffer(raw, np.uint8).reshape(7, 9, 4)[::-1, :, :3], -1, 0) / 255.0
            assert np.max(np.abs(gpu - row[1:].reshape(3, 7, 9))) < 0.005, "CPU/GPU burn profiles differ"
        GL.glUseProgram(program)
        GL.glViewport(0, 0, W, H)
        GL.glDeleteProgram(probe)
        print("PASS: CPU/GPU broad profiles agree for", len(native_profiles), "closes at three phases")

    frames = [render(p) for p in np.linspace(0, 1, 41)]
    assert np.array_equal(frames[0], data), "First frame must preserve source"
    assert not frames[-1].any(), "Final frame must be fully transparent"
    for frame in frames:
        assert not frame[data[:, :, 3] == 0].any(), "Shader leaked outside source alpha"
        assert np.all(frame[:, :, :3] <= frame[:, :, 3:4]), "Not premultiplied alpha"
    # Smoke and sparks can vary in alpha. The opaque window itself must still
    # disappear monotonically; low-alpha gas is deliberately not counted as paper.
    areas = [np.count_nonzero(f[:, :, 3] >= 254) for f in frames]
    assert all(b <= a for a, b in zip(areas, areas[1:])), "Opaque window area must decrease over time"
    # The default seed is bottom-up and uses the original linear clock.
    mid = frames[20]
    assert mid[110:160, 200:600, 3].mean() > 200, "Top disappeared too early"
    assert mid[420:450, 200:600, 3].mean() < 40, "Bottom failed to ignite"
    translucent = warm_pixels = visible_smoke = 0
    for frame in frames[6:35]:
        rgb = frame[:, :, :3].astype(np.float32)
        alpha = frame[:, :, 3]
        # Thin neutral smoke and warm sparks should survive away from paper.
        neutral = np.max(rgb, axis=2) - np.min(rgb, axis=2) < 8
        translucent += np.count_nonzero((alpha > 2) & (alpha < 50) & neutral)
        visible_smoke = max(visible_smoke, np.count_nonzero((alpha > 24) & (alpha < 140) & neutral))
        warm = (rgb[:, :, 0] > rgb[:, :, 1] * 1.8) & (rgb[:, :, 0] > 10) & (alpha < 200)
        warm_pixels += np.count_nonzero(warm)
    assert translucent > 100, "Thin smoke is missing throughout the animation"
    assert visible_smoke > 100, "Smoke became too faint to see after the fire"
    assert warm_pixels > 20, "Sparks are missing throughout the animation"

    def spatial_profile(paper):
        return np.array([np.mean(cell) for row in np.array_split(paper, 7, axis=0)
            for cell in np.array_split(row, 9, axis=1)])

    sample_seeds = (list(map(float, args.seeds.read_text().split())) if args.seeds
                    else list(np.linspace(0.031, 0.971, 18)))
    profiles = []
    pattern_samples = []
    motion_profiles = []
    nearest_recent = []
    for sample_seed in sample_seeds:
        uniform("seed", sample_seed)
        sample = render(0.5)
        paper = sample[90:460, 130:670, 3] >= 254
        profile = spatial_profile(paper)
        if all(np.sqrt(np.mean((profile - other) ** 2)) > 0.06 for other in profiles):
            profiles.append(profile)
        if len(pattern_samples) < 18:
            pattern_samples.append((sample_seed, sample))
        # Judge motion across time, not just one outline halfway through.
        motion = []
        previous_area = W * H
        for phase in (0.3, 0.5, 0.7):
            frame = sample if phase == 0.5 else render(phase)
            assert not frame[data[:, :, 3] == 0].any(), "Seeded shader leaked outside source alpha"
            assert np.all(frame[:, :, :3] <= frame[:, :, 3:4]), "Seeded shader is not premultiplied"
            opaque = frame[:, :, 3] >= 254
            area = np.count_nonzero(opaque)
            assert area <= previous_area, "Seeded opaque area increased"
            previous_area = area
            motion.extend(spatial_profile(opaque[90:460, 130:670]))
        motion = np.array(motion)
        if motion_profiles:
            nearest_recent.append(min(float(np.sqrt(np.mean((motion - old) ** 2)))
                for old in motion_profiles[-8:]))
        motion_profiles.append(motion)
    print("Distinct broad burn outlines:", len(profiles), "of", len(sample_seeds))
    distances = np.sqrt(np.mean((np.array(motion_profiles)[:, None, :]
        - np.array(motion_profiles)[None, :, :]) ** 2, axis=2))
    report = {"closes": len(sample_seeds), "distinct_midpoint_outlines": len(profiles),
        "near_pairs_rms_under_0.06": int(np.count_nonzero(np.triu(distances < 0.06, 1))),
        "recent_eight_min_rms": min(nearest_recent) if nearest_recent else None,
        "recent_eight_median_rms": statistics.median(nearest_recent) if nearest_recent else None}
    if args.profiles and nearest_recent:
        assert min(nearest_recent) > 0.01, "Native seed selection repeated recent rendered motion"
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "variety.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Recent-eight motion distance: minimum", report["recent_eight_min_rms"],
        "; median", report["recent_eight_median_rms"])
    uniform("seed", 0.37)

    checker = Image.new("RGB", (W, H), (42, 46, 52))
    cd = ImageDraw.Draw(checker)
    for y in range(0, H, 24):
        for x in range(0, W, 24):
            if (x//24 + y//24) % 2:
                cd.rectangle((x, y, x+23, y+23), fill=(49, 53, 60))
    previews = []
    for frame in frames:
        composed = checker.copy().convert("RGBA")
        # The shader emits premultiplied colour; Pillow expects straight alpha.
        straight = frame.copy()
        alpha = frame[:, :, 3:4].astype(np.float32)
        straight[:, :, :3] = np.clip(frame[:, :, :3].astype(np.float32)
            * 255.0 / np.maximum(alpha, 1.0), 0, 255).astype(np.uint8)
        composed.alpha_composite(Image.fromarray(straight))
        previews.append(composed.convert("RGB"))
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    # Compare different closes at the same phase, including the actual native
    # seed sequence when --seeds is supplied.
    pattern_sheet = Image.new("RGB", (W * 3 // 2, (H // 2 + 28) * 6), (20, 23, 29))
    pd = ImageDraw.Draw(pattern_sheet)
    for i, (sample_seed, frame) in enumerate(pattern_samples[:18]):
        straight = frame.copy()
        alpha = frame[:, :, 3:4].astype(np.float32)
        straight[:, :, :3] = np.clip(frame[:, :, :3].astype(np.float32)
            * 255.0 / np.maximum(alpha, 1.0), 0, 255).astype(np.uint8)
        composed = checker.copy().convert("RGBA")
        composed.alpha_composite(Image.fromarray(straight))
        x, y = (i % 3) * (W // 2), (i // 3) * (H // 2 + 28)
        pattern_sheet.paste(composed.convert("RGB").resize((W // 2, H // 2)), (x, y + 28))
        pd.text((x + 12, y + 6), f"close {i + 1}: seed {sample_seed:.5f}", fill="white")
    pattern_sheet.save(out / "burn-patterns.png")
    if args.save_frames:
        np.savez_compressed(out / "frames.npz", frames=np.stack(frames))
    if args.benchmark:
        benchmark()
    previews[0].save(out / "burn-preview.gif", save_all=True,
        append_images=previews[1:] + [previews[-1]] * 18, duration=30, loop=0)
    sheet = Image.new("RGB", (W*3//2, (H//2+28)*2), (20, 23, 29))
    sd = ImageDraw.Draw(sheet)
    for i, index in enumerate([0, 9, 17, 24, 31, 40]):
        x, y = (i%3)*(W//2), (i//3)*(H//2+28)
        sheet.paste(previews[index].resize((W//2, H//2)), (x, y+28))
        sd.text((x+12, y+6), f"progress {index/40:.0%}", fill="white")
    sheet.save(out / "burn-contact-sheet.png")
    print("PASS: exact endpoints, transparency bounds, premultiplied alpha,")
    print("      bottom-up ignition, original timing, decreasing opaque area, smoke and sparks.")
    print("Preview:", out / "burn-preview.gif")
    close_context()


if __name__ == "__main__":
    main()
