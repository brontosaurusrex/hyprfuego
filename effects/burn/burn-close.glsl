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
    // Favor broad flow over fine grain, using the same three noise samples.
    return 0.68 * noise(p) + 0.24 * noise(p * 2.03 + 17.1)
         + 0.08 * noise(p * 4.11 - 9.7);
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
float advanceFront(vec2 schedule, float p) {
    float local = clamp((burnClock(p) - schedule.x) / (schedule.y - schedule.x), 0.0, 1.0);
    return mix(-0.18, 1.18, local);
}
float burnFront(float x, float p, highp uint key) {
    return advanceFront(burnSchedule(x, key), p);
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
    // Reuse this column's existing schedule: shorter burn time means taller fire.
    vec2 localSchedule = burnSchedule(uv.x, profileKey);
    float front = advanceFront(localSchedule, p);
    float fastBurn = clamp((0.84 - (localSchedule.y - localSchedule.x)) / 0.235, 0.0, 1.0);
    float flameScale = mix(0.65, 2.15, fastBurn * fastBurn);
    // A stationary irregular contour burns monotonically; the gas moves freely.
    float contour = fbm(vec2(pos.x * 14.0 + variant, pos.y * 9.0));
    float edge = (pos.y - front) + (contour - 0.5) * 0.055;
    float remain = smoothstep(-0.004, 0.007, edge);
    float alive = smoothstep(0.0, 0.065, p) * (1.0 - smoothstep(0.84, 1.0, p));

    // Dark brown/black char, without the continuous yellow outline.
    float charred = exp(-max(edge, 0.0) * 65.0) * alive;
    vec4 paper = src * remain;
    paper.rgb = mix(paper.rgb, vec3(0.018, 0.009, 0.004) * paper.a, charred * 0.94);

    // Broad, coherent tongues rise quickly; thin tips fade into the air.
    float plume = pow(noise(vec2(uv.x * 4.0, variant + 41.5)), 3.0);
    float height = 0.045 + 0.09 * fbm(vec2(pos.x * 9.0 + variant, -t * 1.4))
                 + 0.30 * plume;
    // Quiet patches stay low; fast patches produce taller, localized tongues.
    height *= flameScale;
    float h = max(edge, 0.0) / height;
    float flameAlpha = 0.0;
    vec3 fireColor = vec3(0);
    // Outside the visible envelope only a tiny core tail remains: below
    // 2e-7 at -0.12 height units, and below 1e-14 at +0.25. Skip
    // two turbulence fields there; reuse the remaining fade for heat colour.
    if (edge > -0.12 && (h < 1.45 || edge < 0.25)) {
        float warp = fbm(vec2(pos.x * 6.5 + variant, pos.y * 3.5 - t * 2.0));
        vec2 gas = vec2(pos.x * 20.0 + variant + (warp - 0.5) * 1.3,
                        pos.y * 5.5 - t * 4.2);
        float detail = fbm(gas);
        float body = smoothstep(0.20 + h * 0.48, 0.65 + h * 0.32, detail);
        float falloff = exp(-h * 1.9);
        flameAlpha = body * falloff
            * smoothstep(-0.025, 0.012, edge) * (1.0 - smoothstep(0.45, 1.45, h)) * alive;
        float core = exp(-abs(edge) * 130.0) * smoothstep(0.28, 0.72, detail) * alive;
        flameAlpha = clamp(flameAlpha * 0.80 + core * 0.70, 0.0, 0.92) * src.a;
        float heat = clamp(body * 0.45 + falloff * falloff * 0.55, 0.0, 1.0);
        fireColor = mix(vec3(0.30, 0.06, 0.012), vec3(0.95, 0.43, 0.10), heat);
        float hot = heat * heat;
        fireColor = mix(fireColor, vec3(1.0, 0.91, 0.70), hot * hot * hot * 0.90);
    }

    // Smoke originates below its current position and drifts upward. A soft
    // emission envelope and broken density avoid a gray strip glued to the edge.
    float smokeAlpha = 0.0;
    vec3 smokeColor = vec3(0.40, 0.38, 0.35);
    if (edge > -0.65 && edge < 0.65) {
        float curl = noise(vec2(pos.x * 5.0 + variant, pos.y * 3.0 - t * 0.8));
        vec2 emissionUV = uv + vec2((curl - 0.5) * 0.065 / (pixels.x / pixels.y), 0.13);
        float smokeEdge = 1.0 - emissionUV.y - burnFront(emissionUV.x, max(p - 0.12, 0.0), profileKey);
        float density = fbm(vec2(pos.x * 16.0 + (curl - 0.5) * 1.8 + variant,
                                   pos.y * 5.8 - t * 1.7));
        float envelope = exp(-abs(smokeEdge) * 8.0);
        float trail = smoothstep(-0.65, -0.30, edge)
                    * (1.0 - smoothstep(0.35, 0.65, edge));
        smokeAlpha = smoothstep(0.27, 0.73, density) * trail * envelope * alive * 0.30 * src.a;
        smokeColor = mix(vec3(0.32, 0.30, 0.28), vec3(0.58, 0.57, 0.54), curl);
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
        float life = 0.11 + c * 0.23;
        if (age >= life) continue;
        float age01 = age / life;
        float drift = (c - 0.5) * 0.4;
        float x = b * aspect + (age * drift + sin(age * 12.0 + a * 17.0) * age * 0.08);
        float rise = 0.85 + a * 1.25;
        // Reject horizontally before evaluating the expensive burn profile.
        // The shear can shift x by at most ten vertical radii times its slope.
        vec2 r = max(vec2(1.0, 1.8) / pixels.y,
                     vec2(0.0018 + c * 0.003, 0.003 + a * 0.007));
        float shear = drift / rise;
        if (abs(pos.x - x) > 10.0 * (r.x + r.y * abs(shear))) continue;
        float originY = burnFront(b, birth, profileKey);
        float y = originY + (age * rise - age * age * 0.7);
        vec2 d = pos - vec2(x, y);
        d.x -= d.y * shear;
        // The halo beyond ten radii is below 1e-10 alpha. Most pixels miss a
        // tiny ember entirely; reject them before divides, exponentials/color.
        if (any(greaterThan(abs(d), r * 10.0))) continue;
        float distance2 = dot(d / r, d / r);
        float hotCore = exp(-distance2 * 1.9);
        float brightness = ((0.55 + c * 1.25) * hotCore + 0.10 * exp(-distance2 * 0.35))
            * smoothstep(0.0, 0.025, age) * (1.0 - smoothstep(0.35, 1.0, age01)) * alive;
        float alpha = clamp(brightness, 0.0, 0.96) * src.a;
        vec3 color = mix(vec3(1.0, 0.46, 0.085), vec3(0.52, 0.075, 0.012), age01);
        color = mix(color, vec3(1.0, 0.86, 0.52), hotCore * (1.0 - age01) * 0.55);
        sparks = over(vec4(color * alpha, alpha), sparks);
    }
    vec4 smoke = vec4(smokeColor * smokeAlpha, smokeAlpha);
    vec4 fire = vec4(fireColor * flameAlpha, flameAlpha);
    fragColor = over(sparks, over(fire, over(smoke, paper)));
}
