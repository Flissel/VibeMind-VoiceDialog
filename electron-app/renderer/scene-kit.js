/**
 * Shared look of the multiverse scene.
 *
 * `polish(app)` runs once after the spaces are built and upgrades the parts every
 * space has in common, without touching what makes each object clickable:
 *   - the big see-through hulls around objects become soft halos (same mesh, so
 *     they stay click targets, but no more faceted grey discs),
 *   - the angular base rings become round rings with soft edges and a slow sweep,
 *   - square point particles become soft round dots.
 * The helpers are also used by the single objects (sun.js builds its own parts).
 *
 * `time` is one shared uniform; multiverse.js sets it once per frame.
 */
(function (root) {
    'use strict';

    const time = { value: 0 };
    let dotTexture;

    const HALO_VERTEX = `
        varying vec3 vWorldPos;
        varying vec3 vWorldNormal;
        void main() {
            vec4 world = modelMatrix * vec4(position, 1.0);
            vWorldPos = world.xyz;
            vWorldNormal = normalize(mat3(modelMatrix) * normal);
            gl_Position = projectionMatrix * viewMatrix * world;
        }
    `;

    // Drawn on the inside of the hull: bright behind the object, gone at the outline.
    const HALO_FRAGMENT = `
        uniform vec3 u_color;
        uniform float u_strength;
        uniform float u_time;
        varying vec3 vWorldPos;
        varying vec3 vWorldNormal;
        void main() {
            vec3 V = normalize(cameraPosition - vWorldPos);
            float d = clamp(dot(-normalize(vWorldNormal), V), 0.0, 1.0);
            float breathe = 0.92 + 0.08 * sin(u_time * 0.6);
            float alpha = pow(d, 2.4) * u_strength * breathe;
            gl_FragColor = vec4(u_color * alpha, alpha);
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
        uniform vec3 u_color;
        uniform float u_opacity;
        uniform float u_inner;
        uniform float u_outer;
        uniform float u_time;
        uniform float u_phase;
        varying vec3 vLocal;
        void main() {
            float r = length(vLocal.xy);
            float d = clamp((r - u_inner) / (u_outer - u_inner), 0.0, 1.0);
            // A bright core line with a wide soft skirt on both sides.
            float core = exp(-pow((d - 0.42) * 7.0, 2.0));
            float skirt = smoothstep(0.0, 0.35, d) * smoothstep(1.0, 0.5, d) * 0.35;
            // One brighter arc travels slowly around the ring.
            float angle = atan(vLocal.y, vLocal.x);
            float sweep = 0.75 + 0.25 * cos(angle - u_time * 0.25 - u_phase);
            float alpha = (core + skirt) * sweep * u_opacity;
            gl_FragColor = vec4(u_color * (1.0 + core * 0.6), alpha);
        }
    `;

    /** A soft round dot for PointsMaterial; null where there is no canvas (tests). */
    function softDot(THREE, doc = root.document) {
        if (dotTexture !== undefined) return dotTexture;
        dotTexture = null;
        if (!doc || !doc.createElement) return dotTexture;
        const canvas = doc.createElement('canvas');
        canvas.width = canvas.height = 64;
        const ctx = canvas.getContext && canvas.getContext('2d');
        if (!ctx) return dotTexture;
        const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
        gradient.addColorStop(0, 'rgba(255,255,255,1)');
        gradient.addColorStop(0.35, 'rgba(255,255,255,0.55)');
        gradient.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, 64, 64);
        dotTexture = new THREE.CanvasTexture(canvas);
        return dotTexture;
    }

    function haloMaterial(THREE, color, strength) {
        return new THREE.ShaderMaterial({
            vertexShader: HALO_VERTEX,
            fragmentShader: HALO_FRAGMENT,
            uniforms: { u_color: { value: new THREE.Color(color) }, u_strength: { value: strength }, u_time: time },
            side: THREE.BackSide,
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
        });
    }

    function ringMaterial(THREE, color, opacity, inner, outer, phase = 0) {
        return new THREE.ShaderMaterial({
            vertexShader: RING_VERTEX,
            fragmentShader: RING_FRAGMENT,
            uniforms: {
                u_color: { value: new THREE.Color(color) }, u_opacity: { value: opacity },
                u_inner: { value: inner }, u_outer: { value: outer }, u_time: time, u_phase: { value: phase },
            },
            side: THREE.DoubleSide,
            transparent: true,
            depthWrite: false,
        });
    }

    /** A hull is a big inside-out, see-through sphere drawn in one flat colour. */
    function isGlowHull(THREE, obj) {
        const m = obj.material;
        return Boolean(obj.isMesh && m && m.type === 'MeshBasicMaterial' && m.side === THREE.BackSide && m.transparent);
    }

    /** A base ring lies flat below its object. */
    function isBaseRing(obj) {
        const m = obj.material;
        return Boolean(obj.isMesh && obj.geometry && obj.geometry.type === 'RingGeometry'
            && m && m.type === 'MeshBasicMaterial' && m.transparent
            && Math.abs(Math.abs(obj.rotation.x) - Math.PI / 2) < 0.01 && obj.position.y <= -1.9);
    }

    function isPlainPoints(obj) {
        const m = obj.material;
        return Boolean(obj.isPoints && m && m.type === 'PointsMaterial' && !m.map);
    }

    /**
     * Upgrades the common parts below `rootObject` in place.
     * @returns {{halos: number, rings: number, points: number}} what was changed
     */
    function polishObject(THREE, rootObject, doc = root.document) {
        const done = { halos: 0, rings: 0, points: 0 };
        const found = [];
        rootObject.traverse((obj) => { if (!obj.userData || !obj.userData.kitPolished) found.push(obj); });
        for (const obj of found) {
            if (isGlowHull(THREE, obj)) {
                const old = obj.material;
                // Old hulls were 0.06 to 0.2 opaque everywhere; the halo is that bright only at its centre.
                obj.material = haloMaterial(THREE, old.color.getHex(), Math.min(0.9, old.opacity * 3.2 + 0.12));
                old.dispose();
                done.halos++;
            } else if (isBaseRing(obj)) {
                const p = obj.geometry.parameters;
                const inner = p.innerRadius * 0.86;
                const outer = p.outerRadius * 1.22;
                const old = obj.material;
                obj.geometry.dispose();
                obj.geometry = new THREE.RingGeometry(inner, outer, 128, 1);
                obj.material = ringMaterial(THREE, old.color.getHex(), Math.min(1, old.opacity * 2.6), inner, outer, done.rings * 1.7);
                old.dispose();
                done.rings++;
            } else if (isPlainPoints(obj)) {
                const map = softDot(THREE, doc);
                if (map) {
                    obj.material.map = map;
                    obj.material.size *= 2.0; // a soft dot reads smaller than a hard square
                    obj.material.transparent = true;
                    obj.material.depthWrite = false;
                    obj.material.needsUpdate = true;
                }
                done.points++;
            } else {
                continue;
            }
            obj.userData = { ...obj.userData, kitPolished: true };
        }
        return done;
    }

    /** Polishes the whole scene of a MultiverseApp. Safe to call again; finished parts are skipped. */
    function polish(app, THREE = root.THREE, doc = root.document) {
        return polishObject(THREE, app.scene, doc);
    }

    const api = { time, softDot, haloMaterial, ringMaterial, isGlowHull, isBaseRing, isPlainPoints, polishObject, polish };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.VibeSceneKit = api;
})(typeof window !== 'undefined' ? window : globalThis);
