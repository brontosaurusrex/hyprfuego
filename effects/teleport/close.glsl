#version 320 es
// @duration 1.6
// @reflow natural
// Video-reference transporter: blue-white shafts resolve into a dense cloud of
// softly glowing, independently flickering particles. Window content ends at 38%.
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
vec4 over(vec4 a, vec4 b) { return a + b * (1.0 - a.a); }

vec3 particles(vec2 pos, float p, float key) {
    vec2 grid = pos * 24.0;
    vec2 cell = floor(grid), local = fract(grid);
    vec3 radiance = vec3(0);
    // Neighbor cells cover each soft halo, with constant work per fragment.
    // Hundreds of points can shimmer without a loop over every particle.
    for (int y = -1; y <= 1; ++y) {
        for (int x = -1; x <= 1; ++x) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 id = cell + neighbor;
            float a = hash21(id + key);
            if (a < 0.18) continue;
            float b = hash21(id + vec2(key + 31.4, 12.7));
            float c = hash21(id + vec2(18.1, key + 69.2));
            float birth = 0.12 + c * 0.24;
            float death = 0.56 + b * 0.41;
            float lifetime = smoothstep(birth, birth + 0.065, p)
                           * (1.0 - smoothstep(death - 0.18, death, p));
            if (lifetime <= 0.001) continue;
            vec2 point = neighbor + vec2(0.12 + 0.76 * b, 0.12 + 0.76 * c);
            point += vec2(sin(p * (4.0 + b * 5.0) + a * 29.0),
                          cos(p * (4.0 + c * 5.0) + b * 37.0)) * 0.17;
            vec2 delta = local - point;
            float radius = 0.080 + 0.180 * a * a * a;
            float distance2 = dot(delta, delta) / (radius * radius);
            if (distance2 > 48.0) continue;
            float core = exp(-distance2 * 1.7);
            float halo = exp(-distance2 * 0.17);
            float shimmer = 0.5 + 0.5 * sin(p * (30.0 + c * 30.0) + a * 67.0);
            shimmer = 0.22 + 0.78 * shimmer * shimmer * shimmer;
            radiance += (vec3(0.82, 0.91, 1.0) * core * 3.4
                         + vec3(0.25, 0.45, 1.0) * halo * 0.31) * shimmer * lifetime;
        }
    }
    return radiance;
}

void main() {
    vec4 src = texture(tex, v_texcoord);
    float p = clamp(progress, 0.0, 1.0);
    if (p <= 0.0) { fragColor = src; return; }
    if (p >= 0.98 || src.a <= 0.0) { fragColor = vec4(0); return; }
    vec2 uv = (v_texcoord - window_rect.xy) / max(window_rect.zw, vec2(0.00001));
    vec2 size = max(surface_size * window_rect.zw, vec2(1));
    float aspect = size.x / size.y;
    vec2 q = vec2((uv.x - 0.5) * aspect, uv.y - 0.5);
    float key = seed * 137.31;

    // Spatially random, monotonic material breakup across the entire window.
    float density = 0.53 * noise(q * 10.0 + key)
                  + 0.30 * noise(q * 27.0 - key)
                  + 0.17 * noise(q * 67.0 + key * 0.3);
    float erase = smoothstep(0.025, 0.38, p);
    float threshold = 0.08 + 0.84 * density;
    float matter = 1.0 - smoothstep(threshold - 0.085, threshold + 0.085, erase);
    matter *= 1.0 - smoothstep(0.32, 0.38, p);
    vec4 body = src * matter;
    float charge = smoothstep(0.0, 0.05, p) * (1.0 - smoothstep(0.24, 0.38, p));
    body.rgb = mix(body.rgb, vec3(0.46, 0.61, 0.86) * body.a, charge * 0.14);

    // Narrow vertical shafts arrive first, then resolve into points from the top.
    float columns = clamp(size.x / 7.0, 48.0, 180.0);
    float gx = uv.x * columns, col = floor(gx), fx = fract(gx);
    float beam = 0.0;
    float head = smoothstep(0.0, 0.22, p) * 1.20;
    float dissolve = smoothstep(0.21, 0.68, p) * 1.15 - 0.10;
    for (int i = -1; i <= 1; ++i) {
        float offset = float(i);
        float a = hash21(vec2(col + offset + key, 7.9));
        float b = hash21(vec2(col + offset + key, 23.4));
        float center = offset + 0.12 + b * 0.76;
        float width = 0.055 + a * a * 0.10;
        float dx = (fx - center) / width;
        float shaft = exp(-dx * dx) + exp(-dx * dx * 0.065) * 0.18;
        float segment = smoothstep(-0.06, 0.04, head - uv.y + a * 0.12)
                      * smoothstep(-0.03, 0.08, uv.y - dissolve - b * 0.08);
        float modulation = 0.65 + 0.35 * sin(p * (9.0 + a * 7.0) + b * 43.0);
        beam += shaft * segment * modulation * (0.30 + a * 0.70);
    }
    beam *= smoothstep(0.0, 0.035, p) * (1.0 - smoothstep(0.48, 0.72, p));

    // Gentle irregular drift makes the cloud roll and shimmer as the shafts fade.
    vec2 flow = vec2(noise(q * 5.0 + vec2(key, -p * 2.0)),
                     noise(q * 5.0 + vec2(p * 2.0 + 31.0, key))) - 0.5;
    vec2 cloudPos = q + flow * 0.055 + vec2(0.012 * sin(q.y * 8.0 + p * 5.0), p * 0.09);
    vec3 cloud = particles(cloudPos, p, key);
    float centerGlow = exp(-dot(q * vec2(2.8 / max(aspect, 0.1), 2.0),
                                     q * vec2(2.8 / max(aspect, 0.1), 2.0)));
    float pulse = smoothstep(0.16, 0.34, p) * (1.0 - smoothstep(0.42, 0.77, p));
    float haze = (0.25 + 0.75 * density) * centerGlow * pulse;
    vec3 radiance = vec3(0.68, 0.79, 1.0) * beam * 2.6 + cloud * (1.0 + centerGlow * pulse * 2.5)
                 + vec3(0.60, 0.76, 1.0) * haze * 0.48;
    float border = smoothstep(0.0, 0.025, uv.x) * (1.0 - smoothstep(0.975, 1.0, uv.x))
                 * smoothstep(0.0, 0.025, uv.y) * (1.0 - smoothstep(0.975, 1.0, uv.y));
    radiance *= border;
    float peak = max(radiance.r, max(radiance.g, radiance.b));
    float alpha = min(0.94, 1.0 - exp(-peak)) * src.a;
    vec4 energy = vec4(radiance / max(peak, 0.00001) * alpha, alpha);
    fragColor = over(energy, body);
}
