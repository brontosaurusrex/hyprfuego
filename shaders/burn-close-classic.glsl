#version 320 es
// @duration 1.15
// Hyprfuego: a rising burn front, turbulent flames and drifting embers.
precision highp float;
in vec2 v_texcoord;
out vec4 fragColor;
uniform sampler2D tex;
uniform float progress;
uniform float seed;
uniform vec2 surface_size;
uniform vec4 window_rect;

float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash21(i), hash21(i + vec2(1, 0)), f.x),
               mix(hash21(i + vec2(0, 1)), hash21(i + vec2(1)), f.x), f.y);
}
float turbulence(vec2 p) {
    return 0.57 * noise(p) + 0.28 * noise(p * 2.03 + 17.1)
         + 0.15 * noise(p * 4.11 - 9.7);
}
void main() {
    vec4 src = texture(tex, v_texcoord);
    float p = clamp(progress, 0.0, 1.0);
    // Exact endpoints preserve the first frame and leave no final snapshot.
    if (p <= 0.0) { fragColor = src; return; }
    if (p >= 1.0) { fragColor = vec4(0); return; }

    // Closing textures cover the monitor: work in the window's sub-rectangle.
    vec2 uv = (v_texcoord - window_rect.xy) / max(window_rect.zw, vec2(0.00001));
    vec2 pixels = max(surface_size * window_rect.zw, vec2(1));
    vec2 pos = vec2(uv.x * pixels.x / pixels.y, 1.0 - uv.y);
    float t = p * 4.0;
    float variation = seed * 19.73;
    float grain = turbulence(vec2(pos.x * 10.0 + variation, pos.y * 5.0 - t));
    float front = mix(-0.25, 1.35, p);
    float edge = pos.y - front + (grain - 0.5) * 0.14;
    float remaining = smoothstep(-0.009, 0.012, edge);
    float ignite = smoothstep(0.0, 0.07, p) * (1.0 - smoothstep(0.87, 1.0, p));

    // Keep a blackened rim on the unburned side of the paper/window.
    float charred = 1.0 - 0.85 * exp(-max(edge, 0.0) * 75.0) * ignite;
    vec4 paper = src * remaining;
    paper.rgb *= charred;

    // Narrow tongues rise into the remaining window above the moving rim.
    float height = 0.035 + 0.19 * pow(turbulence(vec2(pos.x * 17.0 + variation, -t * 2.1)), 1.7);
    float flame = (1.0 - smoothstep(height * 0.55, height, edge))
                * smoothstep(-0.025, 0.008, edge) * ignite;
    float heat = clamp(1.0 - max(edge, 0.0) / max(height, 0.001), 0.0, 1.0);
    vec3 fire = mix(vec3(0.8, 0.025, 0.002), vec3(1.0, 0.27, 0.005), smoothstep(0.1, 0.6, heat));
    fire = mix(fire, vec3(1.0, 0.88, 0.28), smoothstep(0.7, 1.0, heat));
    float rim = exp(-abs(edge) * 135.0) * ignite;
    flame = max(flame, rim);

    // A sparse, moving ember field; source alpha prevents painting other windows.
    vec2 emberPos = vec2(pos.x * 65.0 + sin(t * 2.0 + pos.y * 6.0), (pos.y - p * 0.5) * 42.0);
    vec2 cell = floor(emberPos);
    vec2 delta = fract(emberPos) - vec2(0.5);
    float ember = (1.0 - smoothstep(0.015, 0.15, length(delta)))
                * step(0.96, hash21(cell + variation))
                * smoothstep(0.025, 0.06, edge) * (1.0 - smoothstep(0.10, 0.32, edge)) * ignite;
    float fireAlpha = clamp(max(flame, ember), 0.0, 1.0) * src.a;
    vec3 fireColor = mix(fire, vec3(1.0, 0.7, 0.12), step(flame, ember));
    // Premultiplied alpha, as required by the compositor's blend function.
    fragColor = vec4(fireColor * fireAlpha + paper.rgb * (1.0 - fireAlpha),
                     fireAlpha + paper.a * (1.0 - fireAlpha));
}
