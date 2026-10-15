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
// The original bottom-up profile, with a fresh curve for each close.
// Keep this profile in sync with vendor/HyprWindowShade/BurnProfile.hpp.
highp uint profileHash(highp uint value) {
    value ^= value >> 16u;
    value *= 0x7feb352du;
    value ^= value >> 15u;
    value *= 0x846ca68bu;
    return value ^ (value >> 16u);
}
float profileControl(highp uint key, highp uint channel) {
    return float(profileHash(key ^ (channel * 0x9e3779b9u)) >> 8u) / 16777216.0;
}
float burnClock(float p) { return clamp(p, 0.0, 1.0); }
vec2 burnSchedule(float x, highp uint key) {
    // The original five-control curve profile; no independently surging knots.
    float a = profileControl(key, 10u), b = profileControl(key, 11u);
    float c = profileControl(key, 12u), d = profileControl(key, 13u);
    float e = profileControl(key, 14u);
    float low = min(min(a, b), min(min(c, d), e));
    float high = max(max(a, b), max(max(c, d), e));
    vec3 knots = vec3(0.15 + 0.20 * d, 0.40 + 0.20 * a, 0.65 + 0.20 * b);
    float timing;
    if (x < knots.x) timing = mix(a, b, smoothstep(0.0, knots.x, x));
    else if (x < knots.y) timing = mix(b, c, smoothstep(knots.x, knots.y, x));
    else if (x < knots.z) timing = mix(c, d, smoothstep(knots.y, knots.z, x));
    else timing = mix(d, e, smoothstep(knots.z, 1.0, x));
    timing = clamp((timing - low) / max(high - low, 0.0001), 0.0, 1.0);
    return vec2(mix(0.005, 0.14, timing), mix(0.61, 0.98, timing));
}
float burnFront(float x, float p, highp uint key) {
    vec2 schedule = burnSchedule(x, key);
    float local = clamp((burnClock(p) - schedule.x) / (schedule.y - schedule.x), 0.0, 1.0);
    return mix(-0.18, 1.18, local);
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
    highp uint profileKey = uint(seed * 16777216.0);
    float t = p * 3.8;
    float front = burnFront(uv.x, p, profileKey);
    // A stationary irregular contour burns monotonically; the gas moves freely.
    float contour = fbm(vec2(pos.x * 14.0 + variant, pos.y * 9.0));
    float edge = (pos.y - front) + (contour - 0.5) * 0.055;
    float remain = smoothstep(-0.004, 0.007, edge);
    float alive = smoothstep(0.0, 0.065, p) * (1.0 - smoothstep(0.84, 1.0, p));

    // Dark brown/black char, without the continuous yellow outline.
    float charred = exp(-max(edge, 0.0) * 65.0) * alive;
    vec4 paper = src * remain;
    paper.rgb = mix(paper.rgb, vec3(0.018, 0.009, 0.004) * paper.a, charred * 0.94);

    // A few taller tongues, like burning paper, rather than a uniform comb.
    float plume = pow(noise(vec2(uv.x * 4.0, variant + 41.5)), 3.0);
    float height = 0.045 + 0.09 * fbm(vec2(pos.x * 12.0 + variant, -t * 1.15))
                 + 0.30 * plume;
    float h = max(edge, 0.0) / height;
    float flameAlpha = 0.0;
    vec3 fireColor = vec3(0);
    // Away from the flame envelope, only an exponentially tiny core tail
    // remains (less than 1e-10 alpha at 0.25 window heights). Avoid generating
    // two full turbulence fields for those otherwise unaffected pixels.
    if (edge > -0.25 && (h < 1.8 || edge < 0.25)) {
        float warp = fbm(vec2(pos.x * 9.0 + variant, pos.y * 7.0 - t * 1.7));
        vec2 gas = vec2(pos.x * 24.0 + variant + (warp - 0.5) * 2.8,
                        pos.y * 11.0 - t * 3.6);
        float detail = fbm(gas);
        float body = smoothstep(0.22 + h * 0.42, 0.62 + h * 0.28, detail);
        flameAlpha = body * exp(-h * 1.65)
            * smoothstep(-0.025, 0.012, edge) * (1.0 - smoothstep(0.7, 1.8, h)) * alive;
        float core = exp(-abs(edge) * 100.0) * smoothstep(0.28, 0.72, detail) * alive;
        flameAlpha = clamp(flameAlpha * 0.88 + core * 0.65, 0.0, 0.94) * src.a;
        float heat = clamp(body * 0.6 + exp(-h * 3.0) * 0.4, 0.0, 1.0);
        fireColor = mix(vec3(0.42, 0.045, 0.008), vec3(1.0, 0.34, 0.035), heat);
        fireColor = mix(fireColor, vec3(1.0, 0.87, 0.52), pow(heat, 3.8) * 0.85);
    }

    // Smoke originates below its current position and drifts upward. A soft
    // emission envelope and broken density avoid a gray strip glued to the edge.
    float smokeAlpha = 0.0;
    vec3 smokeColor = vec3(0.46, 0.45, 0.43);
    if (edge > -0.65 && edge < 0.65) {
        float curl = noise(vec2(pos.x * 5.0 + variant, pos.y * 4.0 - t * 0.65));
        vec2 emissionUV = uv + vec2((curl - 0.5) * 0.065 / (pixels.x / pixels.y), 0.13);
        float smokeEdge = 1.0 - emissionUV.y - burnFront(emissionUV.x, max(p - 0.12, 0.0), profileKey);
        float density = fbm(vec2(pos.x * 16.0 + (curl - 0.5) * 3.0 + variant,
                                   pos.y * 7.0 - t * 1.8));
        float envelope = exp(-abs(smokeEdge) * 8.0);
        float trail = smoothstep(-0.65, -0.30, edge)
                    * (1.0 - smoothstep(0.35, 0.65, edge));
        smokeAlpha = smoothstep(0.30, 0.75, density) * trail * envelope * alive * 0.34 * src.a;
        smokeColor = mix(vec3(0.38, 0.37, 0.35), vec3(0.68, 0.67, 0.64), curl);
    }

    // Sparse sparks are born on the current burn front. Check lifetime
    // before evaluating their front/trajectory; inactive sparks cost no geometry.
    vec4 sparks = vec4(0);
    float aspect = pixels.x / pixels.y;
    for (int i = 0; i < 48; ++i) {
        float id = float(i);
        float a = hash21(vec2(id + variant, 4.13));
        float birth = 0.06 + a * 0.74;
        float age = p - birth;
        if (age <= 0.0 || age >= 0.34) continue;
        float b = hash21(vec2(id + variant, 8.91));
        float c = hash21(vec2(id + variant, 15.77));
        float life = 0.18 + c * 0.16;
        if (age >= life) continue;
        float age01 = age / life;
        vec2 origin = vec2(b, burnFront(b, birth, profileKey));
        float drift = (c - 0.5) * 0.6;
        float x = origin.x * aspect + (age * drift + sin(age * 16.0 + a * 17.0) * age * 0.13);
        float rise = 1.0 + a * 1.2;
        float y = origin.y + (age * rise - age * age * 0.7);
        vec2 d = pos - vec2(x, y);
        d.x -= d.y * drift / rise;
        // Scale with the window instead of subpixel device-sized dots. Each
        // spark has a bright core, an orange halo and a short motion streak.
        vec2 r = max(vec2(1.6, 2.8) / pixels.y,
                     vec2(0.0035 + c * 0.002, 0.007 + a * 0.006));
        // The halo beyond ten radii is below 1e-10 alpha. Most pixels miss a
        // tiny ember entirely; reject them before divides, exponentials/color.
        if (any(greaterThan(abs(d), r * 10.0))) continue;
        float distance2 = dot(d / r, d / r);
        float hotCore = exp(-distance2 * 1.9);
        float brightness = (1.4 * hotCore + 0.30 * exp(-distance2 * 0.22))
            * smoothstep(0.0, 0.025, age) * (1.0 - smoothstep(0.55, 1.0, age01)) * alive;
        float alpha = clamp(brightness, 0.0, 0.96) * src.a;
        vec3 color = mix(vec3(1.0, 0.52, 0.055), vec3(0.85, 0.16, 0.015), age01);
        color = mix(color, vec3(1.0, 0.92, 0.63), hotCore * (1.0 - age01) * 0.8);
        sparks = over(vec4(color * alpha, alpha), sparks);
    }
    vec4 smoke = vec4(smokeColor * smokeAlpha, smokeAlpha);
    vec4 fire = vec4(fireColor * flameAlpha, flameAlpha);
    fragColor = over(sparks, over(fire, over(smoke, paper)));
}
