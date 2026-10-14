#version 320 es
// @duration 1.15
// Hyprfuego: turbulent translucent fire, rising smoke and ballistic embers.
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
float fbm(vec2 p) {
    return 0.57 * noise(p) + 0.28 * noise(p * 2.03 + 17.1)
         + 0.15 * noise(p * 4.11 - 9.7);
}
vec4 over(vec4 foreground, vec4 background) {
    return foreground + background * (1.0 - foreground.a);
}
void main() {
    vec4 src = texture(tex, v_texcoord);
    float p = clamp(progress, 0.0, 1.0);
    if (p <= 0.0) { fragColor = src; return; }
    if (p >= 1.0 || src.a <= 0.0) { fragColor = vec4(0); return; }

    vec2 uv = (v_texcoord - window_rect.xy) / max(window_rect.zw, vec2(0.00001));
    vec2 pixels = max(surface_size * window_rect.zw, vec2(1));
    // Use window-height units so flames and sparks keep their proportions.
    vec2 pos = vec2(uv.x * pixels.x / pixels.y, 1.0 - uv.y);
    float variant = seed * 23.71;
    float t = p * 3.8;
    float front = mix(-0.18, 1.18, p);
    // A stationary irregular contour burns monotonically; the gas moves freely.
    float contour = fbm(vec2(pos.x * 14.0 + variant, pos.y * 9.0));
    float edge = pos.y - front + (contour - 0.5) * 0.095;
    float remain = smoothstep(-0.004, 0.007, edge);
    float alive = smoothstep(0.0, 0.065, p) * (1.0 - smoothstep(0.84, 1.0, p));

    // Dark brown/black char, without the continuous yellow outline.
    float charred = exp(-max(edge, 0.0) * 65.0) * alive;
    vec4 paper = src * remain;
    paper.rgb = mix(paper.rgb, vec3(0.018, 0.009, 0.004) * paper.a, charred * 0.94);

    // Domain-warped noise shears and stretches upward into semi-transparent wisps.
    float warp = fbm(vec2(pos.x * 9.0 + variant, pos.y * 7.0 - t * 1.7));
    vec2 gas = vec2(pos.x * 24.0 + variant + (warp - 0.5) * 2.8,
                    pos.y * 11.0 - t * 3.6);
    float detail = fbm(gas);
    float height = 0.07 + 0.20 * fbm(vec2(pos.x * 12.0 + variant, -t * 1.15));
    float h = max(edge, 0.0) / height;
    float body = smoothstep(0.22 + h * 0.42, 0.62 + h * 0.28, detail);
    float flameAlpha = body * exp(-h * 1.65)
        * smoothstep(-0.025, 0.012, edge) * (1.0 - smoothstep(0.7, 1.8, h)) * alive;
    float core = exp(-abs(edge) * 100.0) * smoothstep(0.28, 0.72, detail) * alive;
    flameAlpha = clamp(flameAlpha * 0.88 + core * 0.65, 0.0, 0.94) * src.a;
    float heat = clamp(body * 0.6 + exp(-h * 3.0) * 0.4, 0.0, 1.0);
    vec3 fireColor = mix(vec3(0.42, 0.045, 0.008), vec3(1.0, 0.34, 0.035), heat);
    fireColor = mix(fireColor, vec3(1.0, 0.82, 0.44), pow(heat, 5.0) * 0.75);

    // Rolling smoke is separate from the disappearing paper. It is visible in
    // the burned-away region too, and thins out toward the end of the animation.
    float curl = fbm(vec2(pos.x * 6.0 + variant, pos.y * 6.0 - t * 0.95));
    float soot = fbm(vec2(pos.x * 11.0 + (curl - 0.5) * 3.5 + variant,
                         pos.y * 9.0 - t * 1.35));
    float smokeBand = smoothstep(-0.35, -0.06, edge)
                    * (1.0 - smoothstep(0.12, 0.48, edge));
    float smokeAlpha = smoothstep(0.3, 0.73, soot) * smokeBand * alive * 0.32 * src.a;
    vec3 smokeColor = mix(vec3(0.16, 0.15, 0.135), vec3(0.52, 0.49, 0.44), curl);

    // Each ember has a fixed birth point, lifetime and upward trajectory. These
    // move through space rather than flickering in place on a noise grid.
    vec4 sparks = vec4(0);
    float aspect = pixels.x / pixels.y;
    for (int i = 0; i < 22; ++i) {
        float id = float(i);
        float a = hash21(vec2(id + variant, 4.13));
        float b = hash21(vec2(id + variant, 8.91));
        float birth = 0.08 + a * 0.62;
        float age = p - birth;
        float life = 0.13 + b * 0.23;
        if (age <= 0.0 || age >= life) continue;
        float age01 = age / life;
        float x = b * aspect + sin(age * 16.0 + a * 17.0) * age * 0.15;
        float y = mix(-0.18, 1.18, birth) + age * (0.7 + a * 0.65);
        vec2 d = pos - vec2(x, y);
        // Elongated hot core plus a very faint halo; radii are pixel based.
        vec2 r = vec2(0.8 + b * 0.8, 1.5 + a * 2.0) / pixels.y;
        float distance2 = dot(d / r, d / r);
        float brightness = (exp(-distance2 * 1.5) + 0.15 * exp(-distance2 * 0.16))
            * sin(age01 * 3.14159265) * alive;
        float alpha = clamp(brightness, 0.0, 0.9) * src.a;
        vec3 color = mix(vec3(1.0, 0.61, 0.17), vec3(0.65, 0.09, 0.01), age01);
        sparks = over(vec4(color * alpha, alpha), sparks);
    }
    vec4 smoke = vec4(smokeColor * smokeAlpha, smokeAlpha);
    vec4 fire = vec4(fireColor * flameAlpha, flameAlpha);
    fragColor = over(sparks, over(fire, over(smoke, paper)));
}
