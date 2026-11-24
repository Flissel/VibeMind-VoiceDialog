/**
 * Figure "disco" (Sales): a faceted mirror ball turns on its chain, six beams in the colours of the
 * app sweep round, the tiles of a round dance floor light up in turn, spots of light wander over it.
 *
 * make(THREE, color, kit) -> { group, tick(t) }; kit comes from space-models.js.
 */
(function (root) {
    'use strict';

    function disco(THREE, color, kit) {
        const { CYAN, PINK, VIOLET, ORANGE, STEEL } = kit.COLORS;
        const group = new THREE.Group();
        const colors = [CYAN, PINK, VIOLET, ORANGE, CYAN, PINK];

        // mirror tiles: every facet its own brightness, a few catch a colour of the app
        const sphere = new THREE.SphereGeometry(0.95, 18, 12).toNonIndexed();
        const count = sphere.attributes.position.count;
        const tileColors = new Float32Array(count * 3);
        const tints = [new THREE.Color(0xffffff), new THREE.Color(CYAN), new THREE.Color(PINK), new THREE.Color(VIOLET)];
        for (let face = 0; face * 6 < count; face++) {
            const h = kit.hash(face);
            const c = (h > 0.86 ? tints[1 + (face % 3)] : tints[0]).clone().multiplyScalar(0.45 + 0.55 * ((h * 7) % 1));
            for (let v = face * 6; v < Math.min(count, face * 6 + 6); v++) tileColors.set([c.r, c.g, c.b], v * 3);
        }
        sphere.setAttribute('color', new THREE.BufferAttribute(tileColors, 3));
        const ball = new THREE.Mesh(sphere, new THREE.MeshStandardMaterial({
            color: 0xffffff, vertexColors: true, emissive: 0x8090b0, emissiveIntensity: 0.45, metalness: 0.6, roughness: 0.22, flatShading: true,
        }));
        ball.name = 'disco-kugel';
        ball.position.y = 1.1;
        const chain = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.9, 6), kit.glowing(THREE, STEEL, 0.1));
        chain.position.y = 2.5;
        group.add(ball, chain);

        const beams = new THREE.Group();
        beams.name = 'disco-strahlen';
        beams.position.y = 1.1;
        colors.forEach((c, i) => {
            const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.32, 3.3, 14, 1, true), kit.additive(THREE, c, 0.13));
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
        const tileSets = colors.map((c, k) => {
            const mine = cells.filter(([x, z]) => (x + z + 12) % colors.length === k);
            const set = kit.instanced(THREE, tile, kit.glowing(THREE, c, 0.15), mine.map(([x, z]) => ({ p: [x * 0.54, 0, z * 0.54] })));
            floor.add(set);
            return set;
        });
        group.add(floor);

        // wandering spots of light: one instanced mesh, coloured per instance
        const spotCount = 14;
        const spots = new THREE.InstancedMesh(new THREE.CircleGeometry(0.09, 10), kit.additive(THREE, 0xffffff, 0.8), spotCount);
        spots.name = 'disco-lichtflecken';
        for (let i = 0; i < spotCount; i++) spots.setColorAt(i, new THREE.Color(colors[i % colors.length]));
        group.add(spots);

        kit.frame(THREE, group, color);

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
        return { group, tick };
    }

    if (typeof module !== 'undefined' && module.exports) module.exports = disco;
    else (root.VibeSpaceFigures = root.VibeSpaceFigures || {}).disco = disco;
})(typeof window !== 'undefined' ? window : globalThis);
