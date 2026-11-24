/**
 * Base models of the external spaces in the 3D scene (instead of the gate with its emoji sign).
 *
 * Own three.js geometry only: no model files, no textures, no real lights (the glow comes from
 * emissive and additive materials, so the light count of the scene and its shaders stay as they
 * are). Each model has the frame of the other spaces: a halo hull (also the click target, see
 * space-pick.js) and a base ring at y = -2, both restyled by scene-kit.js.
 *
 * build(THREE, space) -> { group, tick(t), dispose() } or null when the space has no model yet.
 */
(function (root) {
    'use strict';

    const CYAN = 0x4fc3f7, PINK = 0xff7eb6, VIOLET = 0x8866ff, ORANGE = 0xff9f43;

    function glowing(THREE, color, glow, extra = {}) {
        return new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: glow, roughness: 0.45, metalness: 0.2, ...extra });
    }

    function additive(THREE, color, opacity) {
        return new THREE.MeshBasicMaterial({ color, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    }

    /** Halo hull and base ring, as the gate and the other spaces have them. */
    function frame(THREE, group, color) {
        const hull = new THREE.Mesh(new THREE.IcosahedronGeometry(2.6, 2),
            new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.07, side: THREE.BackSide }));
        hull.position.y = 0.2;
        const base = new THREE.Mesh(new THREE.RingGeometry(2.5, 3, 32),
            new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.3, side: THREE.DoubleSide }));
        base.rotation.x = -Math.PI / 2;
        base.position.y = -2;
        group.add(hull, base);
    }

    /** Frees every geometry and material of the model and takes it out of the scene. */
    function disposeGroup(group) {
        const seen = new Set();
        group.traverse((obj) => {
            for (const part of [obj.geometry, ...[].concat(obj.material || [])]) {
                if (part && !seen.has(part) && typeof part.dispose === 'function') {
                    seen.add(part);
                    part.dispose();
                }
            }
        });
        if (group.parent) group.parent.remove(group);
    }

    /** A number in [0, 1) from an integer, the same on every start (no chance in the scene). */
    function hash(n) {
        return Math.abs(Math.sin(n * 12.9898) * 43758.5453) % 1;
    }

    /**
     * Sales: a disco. A faceted mirror ball turns on its chain, six beams in the colours of the app
     * sweep round, the tiles of a round dance floor light up in turn, spots of light wander over it.
     */
    function disco(THREE, color) {
        const group = new THREE.Group();
        const colors = [CYAN, PINK, VIOLET, ORANGE, CYAN, PINK];

        // mirror tiles: every facet its own brightness, a few catch a colour of the app
        const sphere = new THREE.SphereGeometry(0.95, 18, 12).toNonIndexed();
        const count = sphere.attributes.position.count;
        const tileColors = new Float32Array(count * 3);
        const tints = [new THREE.Color(0xffffff), new THREE.Color(CYAN), new THREE.Color(PINK), new THREE.Color(VIOLET)];
        for (let face = 0; face * 6 < count; face++) {
            const h = hash(face);
            const c = (h > 0.86 ? tints[1 + (face % 3)] : tints[0]).clone().multiplyScalar(0.45 + 0.55 * ((h * 7) % 1));
            for (let v = face * 6; v < Math.min(count, face * 6 + 6); v++) tileColors.set([c.r, c.g, c.b], v * 3);
        }
        sphere.setAttribute('color', new THREE.BufferAttribute(tileColors, 3));
        const ball = new THREE.Mesh(sphere, new THREE.MeshStandardMaterial({
            color: 0xffffff, vertexColors: true, emissive: 0x8090b0, emissiveIntensity: 0.45, metalness: 0.6, roughness: 0.22, flatShading: true,
        }));
        ball.name = 'disco-kugel';
        ball.position.y = 1.1;
        const chain = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.9, 6), glowing(THREE, 0xb0c4de, 0.1));
        chain.position.y = 2.5;
        group.add(ball, chain);

        const beams = new THREE.Group();
        beams.name = 'disco-strahlen';
        beams.position.y = 1.1;
        colors.forEach((c, i) => {
            const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.32, 3.3, 14, 1, true), additive(THREE, c, 0.13));
            beam.geometry.translate(0, -1.65, 0);       // narrow end at the ball, wide end on the floor
            beam.rotation.x = 0.42 + (i % 2) * 0.22;
            const arm = new THREE.Group();
            arm.rotation.y = (i / colors.length) * Math.PI * 2;
            arm.add(beam);
            beams.add(arm);
        });
        group.add(beams);

        // dance floor: one instanced mesh per colour, so 37 tiles cost 6 draw calls
        const floor = new THREE.Group();
        floor.name = 'disco-tanzflaeche';
        floor.position.y = -1.92;
        const cells = [];
        for (let x = -3; x <= 3; x++) for (let z = -3; z <= 3; z++) if (x * x + z * z <= 10) cells.push([x, z]);
        const tile = new THREE.BoxGeometry(0.5, 0.06, 0.5);
        const place = new THREE.Object3D();
        const tileSets = colors.map((c, k) => {
            const mine = cells.filter(([x, z]) => (x + z + 12) % colors.length === k);
            const set = new THREE.InstancedMesh(tile, glowing(THREE, c, 0.15), mine.length);
            mine.forEach(([x, z], i) => {
                place.position.set(x * 0.54, 0, z * 0.54);
                place.updateMatrix();
                set.setMatrixAt(i, place.matrix);
            });
            floor.add(set);
            return set;
        });
        group.add(floor);

        // wandering spots of light: one instanced mesh, coloured per instance
        const spotCount = 14;
        const spots = new THREE.InstancedMesh(new THREE.CircleGeometry(0.09, 10), additive(THREE, 0xffffff, 0.8), spotCount);
        spots.name = 'disco-lichtflecken';
        for (let i = 0; i < spotCount; i++) spots.setColorAt(i, new THREE.Color(colors[i % colors.length]));
        group.add(spots);

        frame(THREE, group, color);
        group.name = 'raum-modell-sales';

        const flat = new THREE.Object3D();
        flat.rotation.x = -Math.PI / 2;
        function tick(t) {
            ball.rotation.y = t * 0.6;
            beams.rotation.y = t * 0.45;
            tileSets.forEach((set, k) => { set.material.emissiveIntensity = 0.12 + 0.55 * Math.max(0, Math.sin(t * 2.2 + k)); });
            for (let i = 0; i < spotCount; i++) {
                const a = i * 0.9 + t * 0.45;
                const r = 1.0 + (i % 4) * 0.35;
                flat.position.set(Math.cos(a) * r, -1.86, Math.sin(a) * r);
                flat.updateMatrix();
                spots.setMatrixAt(i, flat.matrix);
            }
            spots.instanceMatrix.needsUpdate = true;
        }
        tick(0);
        return { group, tick, dispose: () => disposeGroup(group) };
    }

    const MODELS = { sales: disco };

    /** The model of a space, placed at the space, or null when it has none (it keeps its gate). */
    function build(THREE, space) {
        const make = space && MODELS[space.id];
        if (!make) return null;
        const model = make(THREE, space.color);
        model.group.position.set(space.position[0], space.position[1], space.position[2]);
        model.group.userData = { type: 'space-model', space: space.id };
        return model;
    }

    /** Triangles drawn per frame, instances counted. */
    function triangles(group) {
        let total = 0;
        group.traverse((obj) => {
            if (!obj.isMesh) return;
            const g = obj.geometry;
            const per = (g.index ? g.index.count : g.attributes.position.count) / 3;
            total += per * (obj.isInstancedMesh ? obj.count : 1);
        });
        return Math.round(total);
    }

    const api = { build, triangles, MODELS: Object.keys(MODELS) };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.VibeSpaceModels = api;
})(typeof window !== 'undefined' ? window : globalThis);
