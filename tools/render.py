#!/usr/bin/env python3
"""Render the real GLSL shader with Mesa EGL; verify alpha and save previews."""
import ctypes
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
    parser.add_argument("--save-frames", action="store_true", help="Save raw premultiplied frames for before/after comparisons")
    parser.add_argument("--seeds", type=Path, help="Validate additional per-close seeds, one number per line")
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
    for y, text in enumerate(["$ ./hyprfuego preview", "", "Window contents stay intact above the fire.",
        "Flames rise from the bottom edge.", "", "[render] Compiz-inspired close animation", "[ready] Hyprland 0.56.2 + HyprWindowShade"]):
        draw.text((150, 177 + y * 30), text, fill=(190, 215, 190, 255), font_size=17)
    data = np.asarray(source)
    GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, W, H, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, data)
    uniform("window_rect", 120/W, 80/H, 560/W, 390/H)

    def render(p):
        uniform("progress", p)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        raw = GL.glReadPixels(0, 0, W, H, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        return np.frombuffer(raw, np.uint8).reshape(H, W, 4)[::-1].copy()

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
    # An off-centre window burns upward, with parts deliberately finishing first.
    mid = frames[20]
    assert mid[110:160, 200:600, 3].mean() > 60, "Every part of the top disappeared too early"
    assert mid[400:450, 200:600, 3].mean() < 30, "Bottom failed to burn; only translucent smoke should remain"
    # In the burned region below the flame there should be translucent gas
    # and a few warm, detached sparks, rather than another opaque rectangle.
    residue = mid[320:430, 150:650]
    translucent = (residue[:, :, 3] > 2) & (residue[:, :, 3] < 128)
    assert np.count_nonzero(translucent) > 100, "Smoke is missing from burned region"
    # Ember trajectories can cross this lower region at different times when
    # effect scale changes. Check their visibility across the animation.
    warm_pixels = 0
    for frame in frames[6:35]:
        rgb = frame[320:430, 150:650, :3].astype(np.float32)
        warm = (rgb[:, :, 0] > rgb[:, :, 1] * 1.8) & (rgb[:, :, 0] > 10)
        warm_pixels += np.count_nonzero(warm)
    assert warm_pixels > 20, "Detached embers are missing throughout the animation"

    # Regions should burn at different rates, and the leading region should
    # change with the per-window seed rather than always being the same side.
    leading = []
    for sample_seed in (0.17, 0.37, 0.71):
        uniform("seed", sample_seed)
        sample = render(0.5)
        coverage = [np.mean(part[:, :, 3] >= 254)
            for part in np.array_split(sample[90:460, 130:670], 3, axis=1)]
        print("Opaque left/middle/right at seed", sample_seed, ":", [round(v, 3) for v in coverage])
        assert max(coverage) - min(coverage) > 0.08, "Burn speed is too uniform across the window"
        leading.append(int(np.argmin(coverage)))
    assert len(set(leading)) > 1, "The same side always burns first"
    if args.seeds:
        counts = [0, 0, 0]
        previous_leader = None
        for sample_seed in map(float, args.seeds.read_text().split()):
            uniform("seed", sample_seed)
            sample = render(0.5)
            coverage = [np.mean(part[:, :, 3] >= 254)
                for part in np.array_split(sample[90:460, 130:670], 3, axis=1)]
            leader = int(np.argmin(coverage))
            assert leader != previous_leader, "Consecutive closes repeated their leading region"
            previous_leader = leader
            counts[leader] += 1
        assert all(counts), "Per-close seeds failed to produce all three leading regions"
        print("Actual close-seed sequence, leading left/middle/right:", counts)
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
    if args.save_frames:
        np.savez_compressed(out / "frames.npz", frames=np.stack(frames))
    if args.benchmark:
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
            "median_ms": statistics.median(timings),
            "p95_ms": float(np.percentile(timings, 95)), "samples_ms": timings}
        (out / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Shader draw benchmark: median {report['median_ms']:.2f} ms; p95 {report['p95_ms']:.2f} ms")
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
    print("      uneven seeded burn speeds, decreasing opaque area, smoke and detached embers.")
    print("Preview:", out / "burn-preview.gif")
    EGL.eglMakeCurrent(display, EGL.EGL_NO_SURFACE, EGL.EGL_NO_SURFACE, EGL.EGL_NO_CONTEXT)
    EGL.eglDestroySurface(display, surface)
    EGL.eglDestroyContext(display, ctx)
    EGL.eglTerminate(display)


if __name__ == "__main__":
    main()
