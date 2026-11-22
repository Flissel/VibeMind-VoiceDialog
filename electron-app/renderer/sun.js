/**
 * The sun of the Desktop space ("Light Planet").
 *
 * Replaces the wobbling single-colour blob: a round star with flowing granulation,
 * dark spots and a hot rim, a soft corona with streamers, three prominences, a
 * banded dust ring and soft dust particles. Everything is driven by one shared
 * `u_time` uniform, so the render loop only has to set
 * `planet.material.uniforms.u_time.value` as before.
 *
 * Contract kept for the rest of the app:
 *   - `planet` is the click target and carries the uniforms u_time, u_pulse,
 *     u_color, u_handPos and u_intensity (hand tracking writes u_handPos).
 *   - `particles` is a THREE.Points (the loop rotates Points of this space).
 */
(function (root) {
    'use strict';

    const NOISE = `
        vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
        vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
        vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
        vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
        float snoise(vec3 v) {
            const vec2 C = vec2(1.0/6.0, 1.0/3.0);
            const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
            vec3 i  = floor(v + dot(v, C.yyy));
            vec3 x0 = v - i + dot(i, C.xxx);
            vec3 g = step(x0.yzx, x0.xyz);
            vec3 l = 1.0 - g;
            vec3 i1 = min(g.xyz, l.zxy);
            vec3 i2 = max(g.xyz, l.zxy);
            vec3 x1 = x0 - i1 + C.xxx;
            vec3 x2 = x0 - i2 + C.yyy;
            vec3 x3 = x0 - D.yyy;
            i = mod289(i);
            vec4 p = permute(permute(permute(
                i.z + vec4(0.0, i1.z, i2.z, 1.0))
                + i.y + vec4(0.0, i1.y, i2.y, 1.0))
                + i.x + vec4(0.0, i1.x, i2.x, 1.0));
            float n_ = 0.142857142857;
            vec3 ns = n_ * D.wyz - D.xzx;
            vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
            vec4 x_ = floor(j * ns.z);
            vec4 y_ = floor(j - 7.0 * x_);
            vec4 x = x_ * ns.x + ns.yyyy;
            vec4 y = y_ * ns.x + ns.yyyy;
            vec4 h = 1.0 - abs(x) - abs(y);
            vec4 b0 = vec4(x.xy, y.xy);
            vec4 b1 = vec4(x.zw, y.zw);
            vec4 s0 = floor(b0)*2.0 + 1.0;
            vec4 s1 = floor(b1)*2.0 + 1.0;
            vec4 sh = -step(h, vec4(0.0));
            vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
            vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
            vec3 p0 = vec3(a0.xy, h.x);
            vec3 p1 = vec3(a0.zw, h.y);
            vec3 p2 = vec3(a1.xy, h.z);
            vec3 p3 = vec3(a1.zw, h.w);
            vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
            p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
            vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
            m = m * m;
            return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
        }
        float fbm(vec3 p) {
            float sum = 0.0;
            float amp = 0.5;
            for (int i = 0; i < 4; i++) {
                sum += amp * snoise(p);
                p = p * 2.03 + vec3(1.7, 9.2, 4.1);
                amp *= 0.5;
            }
            return sum;
        }
    `;

    const CORE_VERTEX = `
        uniform float u_time;
        uniform float u_pulse;
        uniform vec3 u_handPos;
        varying vec3 vDir;
        varying vec3 vWorldPos;
        varying vec3 vWorldNormal;
        ${NOISE}
        void main() {
            vDir = normalize(position);
            vec3 pos = position;
            // A living edge, far gentler than the old blob (0.15): the star stays round.
            pos += normal * snoise(vDir * 3.0 + u_time * 0.12) * 0.022;
            pos *= 1.0 + sin(u_time * 1.3) * 0.012 * u_pulse;
            if (length(u_handPos) > 0.0) {
                vec3 toHand = normalize(u_handPos - pos);
                float influence = max(0.0, 1.0 - length(pos - u_handPos) * 0.5);
                pos += toHand * influence * 0.3;
            }
            vec4 world = modelMatrix * vec4(pos, 1.0);
            vWorldPos = world.xyz;
            vWorldNormal = normalize(mat3(modelMatrix) * normal);
            gl_Position = projectionMatrix * viewMatrix * world;
        }
    `;

    const CORE_FRAGMENT = `
        uniform float u_time;
        uniform float u_intensity;
        uniform vec3 u_color;
        varying vec3 vDir;
        varying vec3 vWorldPos;
        varying vec3 vWorldNormal;
        ${NOISE}
        vec3 heatColor(float h) {
            vec3 ember  = vec3(0.50, 0.06, 0.00);
            vec3 orange = vec3(1.00, 0.42, 0.04);
            vec3 yellow = vec3(1.00, 0.80, 0.30);
            vec3 white  = vec3(1.00, 0.97, 0.86);
            vec3 c = mix(ember, orange, smoothstep(0.00, 0.40, h));
            c = mix(c, yellow, smoothstep(0.35, 0.75, h));
            return mix(c, white, smoothstep(0.78, 1.05, h));
        }
        void main() {
            vec3 p = normalize(vDir);
            float t = u_time;
            // Slow large flows warp the fine granulation, so the cells drift instead of sliding.
            vec3 flow = vec3(fbm(p * 1.6 + vec3(0.0, t * 0.030, 0.0)),
                             fbm(p * 1.6 + vec3(5.2, 1.3, t * 0.026)),
                             fbm(p * 1.6 + vec3(t * 0.022, 8.1, 2.4)));
            vec3 q = p * 3.4 + flow * 0.9;
            float cells = 1.0 - abs(snoise(q * 2.6 + t * 0.07));       // bright cells, dark lanes
            float fine  = fbm(q * 5.5 - t * 0.05);
            float heat  = 0.46 + 0.30 * cells * cells + 0.20 * fine + 0.22 * flow.x;
            // A few slowly wandering spots.
            float spot = smoothstep(0.52, 0.74, snoise(p * 1.35 + vec3(11.0, t * 0.008, 3.0)));
            heat *= 1.0 - 0.72 * spot;

            vec3 N = normalize(vWorldNormal);
            vec3 V = normalize(cameraPosition - vWorldPos);
            float mu = max(dot(N, V), 0.0);
            vec3 color = heatColor(heat);
            color *= 0.58 + 0.42 * pow(mu, 0.55);                        // limb darkening
            color += vec3(1.0, 0.45, 0.10) * pow(1.0 - mu, 3.0) * 0.75;  // hot rim
            color *= mix(vec3(1.0), u_color / max(max(u_color.r, u_color.g), max(u_color.b, 0.001)), 0.25);
            gl_FragColor = vec4(color * u_intensity, 1.0);
        }
    `;

    const SHELL_VERTEX = `
        varying vec3 vWorldPos;
        varying vec3 vWorldNormal;
        varying vec3 vCentre;
        void main() {
            vec4 world = modelMatrix * vec4(position, 1.0);
            vWorldPos = world.xyz;
            vWorldNormal = normalize(mat3(modelMatrix) * normal);
            vCentre = modelMatrix[3].xyz;
            gl_Position = projectionMatrix * viewMatrix * world;
        }
    `;

    /** Drawn on the inside of a larger sphere; brightness falls off with the distance from the limb. */
    const CORONA_FRAGMENT = `
        uniform float u_time;
        uniform float u_inner;   // radius of the star
        uniform float u_outer;   // radius of this shell
        varying vec3 vWorldPos;
        varying vec3 vWorldNormal;
        varying vec3 vCentre;
        ${NOISE}
        void main() {
            vec3 V = normalize(cameraPosition - vWorldPos);
            float d = clamp(dot(-normalize(vWorldNormal), V), 0.0, 1.0);
            float impact = u_outer * sqrt(max(1.0 - d * d, 0.0));       // distance of the sight line from the centre
            float x = clamp((impact - u_inner) / (u_outer - u_inner), 0.0, 1.0);
            vec3 rel = vWorldPos - vCentre;
            vec3 perp = normalize(rel - V * dot(rel, V));               // direction around the disc
            float rays = snoise(perp * 2.6 + vec3(0.0, 0.0, u_time * 0.05));
            float fine = snoise(perp * 7.0 - vec3(u_time * 0.08));
            float glow = pow(1.0 - x, 3.2) * 0.85;
            float streamers = pow(max(rays, 0.0), 1.6) * pow(1.0 - x, 1.35) * (0.55 + 0.25 * fine);
            float alpha = (glow + streamers * 0.6) * smoothstep(1.0, 0.82, x);
            vec3 color = mix(vec3(1.0, 0.78, 0.40), vec3(1.0, 0.34, 0.08), smoothstep(0.0, 0.8, x));
            gl_FragColor = vec4(color * alpha, alpha);
        }
    `;

    const RING_VERTEX = `
        varying vec3 vLocal;
        void main() {
            vLocal = position;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `;

    const RING_FRAGMENT = `
        uniform float u_time;
        uniform float u_inner;
        uniform float u_outer;
        varying vec3 vLocal;
        ${NOISE}
        void main() {
            float r = length(vLocal.xy);
            float d = (r - u_inner) / (u_outer - u_inner);
            float angle = atan(vLocal.y, vLocal.x);
            // Many thin bands with two real gaps; a slow shimmer runs around the ring.
            float bands = 0.55 + 0.45 * snoise(vec3(d * 26.0, 0.0, 3.0));
            float thin  = 0.80 + 0.20 * snoise(vec3(d * 95.0, 1.0, 7.0));
            float gaps  = smoothstep(0.010, 0.030, abs(d - 0.34)) * smoothstep(0.006, 0.020, abs(d - 0.71));
            float edge  = smoothstep(0.0, 0.06, d) * smoothstep(1.0, 0.90, d);
            float drift = 0.88 + 0.12 * snoise(vec3(cos(angle) * 1.5, sin(angle) * 1.5, d * 3.0 + u_time * 0.04));
            float alpha = bands * thin * gaps * edge * drift * 0.62;
            vec3 color = mix(vec3(1.00, 0.80, 0.50), vec3(0.62, 0.36, 0.20), d);
            gl_FragColor = vec4(color, alpha);
        }
    `;

    const FLARE_VERTEX = `
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `;

    const FLARE_FRAGMENT = `
        uniform float u_time;
        uniform float u_phase;
        varying vec2 vUv;
        void main() {
            float along = pow(sin(vUv.x * 3.14159265), 0.6);     // fades into the surface at both feet
            float flicker = 0.55 + 0.45 * sin(u_time * 0.7 + u_phase) * sin(u_time * 0.23 + u_phase * 2.0);
            float alpha = along * clamp(flicker, 0.12, 1.0) * 0.9;
            gl_FragColor = vec4(vec3(1.0, 0.50, 0.14) * alpha, alpha);
        }
    `;

    /** A soft round dot; without it PointsMaterial draws hard squares. */
    function softDotTexture(THREE, doc) {
        if (!doc || !doc.createElement) return null;
        const canvas = doc.createElement('canvas');
        canvas.width = canvas.height = 64;
        const ctx = canvas.getContext && canvas.getContext('2d');
        if (!ctx) return null;
        const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
        gradient.addColorStop(0, 'rgba(255,255,255,1)');
        gradient.addColorStop(0.35, 'rgba(255,255,255,0.55)');
        gradient.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, 64, 64);
        return new THREE.CanvasTexture(canvas);
    }

    /**
     * Builds the parts of the sun. Nothing is added to a scene here.
     * @returns {{planet, corona, ring, particles, flares: Array, parts: Array, time: {value: number}}}
     */
    function buildSun(THREE, options = {}) {
        const radius = options.radius || 1.5;
        const random = options.random || Math.random;
        const doc = options.document !== undefined ? options.document : root.document;
        const time = { value: 0 }; // one object, shared by every material below

        const planet = new THREE.Mesh(
            new THREE.SphereGeometry(radius, 96, 64),
            new THREE.ShaderMaterial({
                vertexShader: CORE_VERTEX,
                fragmentShader: CORE_FRAGMENT,
                uniforms: {
                    u_time: time,
                    u_pulse: { value: 1.0 },
                    u_color: { value: new THREE.Color(0xffaa44) },
                    u_handPos: { value: new THREE.Vector3(0, 0, 0) },
                    u_intensity: { value: 1.0 },
                },
            }),
        );
        planet.userData = { type: 'planet', title: 'Light Planet' };

        const coronaRadius = radius * 2.3;
        const corona = new THREE.Mesh(
            new THREE.SphereGeometry(coronaRadius, 48, 32),
            new THREE.ShaderMaterial({
                vertexShader: SHELL_VERTEX,
                fragmentShader: CORONA_FRAGMENT,
                uniforms: { u_time: time, u_inner: { value: radius * 0.98 }, u_outer: { value: coronaRadius } },
                side: THREE.BackSide,
                transparent: true,
                depthWrite: false,
                blending: THREE.AdditiveBlending,
            }),
        );
        corona.userData = { type: 'sun-corona' };

        const ringInner = radius * 1.55;
        const ringOuter = radius * 2.6;
        const ring = new THREE.Mesh(
            new THREE.RingGeometry(ringInner, ringOuter, 160, 1),
            new THREE.ShaderMaterial({
                vertexShader: RING_VERTEX,
                fragmentShader: RING_FRAGMENT,
                uniforms: { u_time: time, u_inner: { value: ringInner }, u_outer: { value: ringOuter } },
                side: THREE.DoubleSide,
                transparent: true,
                depthWrite: false,
            }),
        );
        ring.rotation.x = Math.PI / 2 + 0.3;
        ring.userData = { type: 'sun-ring' };

        // Prominences: half arcs standing on the surface.
        const flares = [];
        const up = new THREE.Vector3(0, 1, 0);
        const flareGeometry = new THREE.TorusGeometry(radius * 0.34, radius * 0.022, 8, 48, Math.PI);
        for (let i = 0; i < 3; i++) {
            const theta = random() * Math.PI * 2;
            const phi = Math.acos(2 * random() - 1);
            const dir = new THREE.Vector3(
                Math.sin(phi) * Math.cos(theta), Math.sin(phi) * Math.sin(theta), Math.cos(phi));
            const flare = new THREE.Mesh(flareGeometry, new THREE.ShaderMaterial({
                vertexShader: FLARE_VERTEX,
                fragmentShader: FLARE_FRAGMENT,
                uniforms: { u_time: time, u_phase: { value: random() * 6.283 } },
                transparent: true,
                depthWrite: false,
                blending: THREE.AdditiveBlending,
                side: THREE.DoubleSide,
            }));
            flare.position.copy(dir).multiplyScalar(radius * 0.985);
            flare.quaternion.setFromUnitVectors(up, dir);
            flare.rotateY(random() * Math.PI);
            flare.scale.setScalar(0.8 + random() * 0.6);
            flare.userData = { type: 'sun-flare' };
            flares.push(flare);
        }

        // Dust: most of it near the ring plane, the rest as a thin halo.
        const count = options.particleCount || 500;
        const positions = new Float32Array(count * 3);
        const colors = new Float32Array(count * 3);
        const tilt = new THREE.Euler(0.3, 0, 0);
        const point = new THREE.Vector3();
        for (let i = 0; i < count; i++) {
            if (random() < 0.65) {
                const r = ringInner + random() * (ringOuter - ringInner) * 1.25;
                const a = random() * Math.PI * 2;
                point.set(Math.cos(a) * r, (random() - 0.5) * 0.22, Math.sin(a) * r).applyEuler(tilt);
            } else {
                const r = radius * (1.7 + random() * 1.4);
                const theta = random() * Math.PI * 2;
                const phi = Math.acos(2 * random() - 1);
                point.set(r * Math.sin(phi) * Math.cos(theta), r * Math.sin(phi) * Math.sin(theta), r * Math.cos(phi));
            }
            positions.set([point.x, point.y, point.z], i * 3);
            const warm = 0.55 + random() * 0.45;
            colors.set([1.0, 0.55 + warm * 0.35, 0.2 + warm * 0.35], i * 3);
        }
        const particleGeometry = new THREE.BufferGeometry();
        particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        particleGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        const dot = softDotTexture(THREE, doc);
        const particles = new THREE.Points(particleGeometry, new THREE.PointsMaterial({
            size: 0.11,
            map: dot,
            vertexColors: true,
            transparent: true,
            opacity: 0.85,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
        }));
        particles.userData = { type: 'sun-dust' };

        return { planet, corona, ring, particles, flares, parts: [planet, corona, ring, ...flares, particles], time };
    }

    const api = { buildSun };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.VibeSun = api;
})(typeof window !== 'undefined' ? window : globalThis);
