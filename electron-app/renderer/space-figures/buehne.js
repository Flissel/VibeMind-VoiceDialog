/**
 * Figure "buehne" (Events): a small stage with a pointed roof and a back wall, a garland of
 * pennants sways in the wind, two spots sweep over the boards.
 *
 * make(THREE, color, kit) -> { group, tick(t) }; kit comes from space-models.js.
 */
(function (root) {
    'use strict';

    function buehne(THREE, color, kit) {
        const { AMBER, PINK, CYAN, GREEN, VIOLET, DARK, STEEL } = kit.COLORS;
        const group = new THREE.Group();

        const stage = new THREE.Group();
        stage.name = 'buehne-boden';
        const floor = new THREE.Mesh(new THREE.BoxGeometry(2.8, 0.35, 1.6), kit.glowing(THREE, DARK, 0.12));
        floor.position.y = -1.8;
        const edge = new THREE.Mesh(new THREE.BoxGeometry(2.82, 0.06, 0.06), kit.glowing(THREE, AMBER, 0.6));
        edge.position.set(0, -1.6, 0.8);
        const back = new THREE.Mesh(new THREE.BoxGeometry(2.7, 2.3, 0.05), kit.glowing(THREE, 0x5a2f60, 0.25));
        back.position.set(0, -0.48, -0.75);
        stage.add(floor, edge, back);
        const posts = kit.instanced(THREE, new THREE.CylinderGeometry(0.06, 0.06, 2.6, 8), kit.glowing(THREE, STEEL, 0.1),
            [{ p: [-1.3, -0.35, 0.65] }, { p: [1.3, -0.35, 0.65] }]);
        stage.add(posts);
        group.add(stage);

        const roof = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 1.75, 0.9, 4, 1), kit.glowing(THREE, AMBER, 0.35, { flatShading: true }));
        roof.name = 'buehne-dach';
        roof.rotation.y = Math.PI / 4;
        roof.scale.set(1, 1, 0.65);
        roof.position.y = 1.35;
        group.add(roof);

        // the garland: eleven pennants, one instanced mesh, coloured per pennant, sagging in the middle
        const colors = [AMBER, PINK, CYAN, GREEN, VIOLET];
        const flagCount = 11;
        const flags = new THREE.InstancedMesh(new THREE.ConeGeometry(0.11, 0.26, 3), kit.glowing(THREE, 0xffffff, 0.5), flagCount);
        flags.name = 'buehne-wimpel';
        const hangs = [];
        for (let i = 0; i < flagCount; i++) {
            flags.setColorAt(i, new THREE.Color(colors[i % colors.length]));
            hangs.push([-1.25 + i * 0.25, 0.82 - 0.22 * Math.sin((i / (flagCount - 1)) * Math.PI)]);
        }
        group.add(flags);

        const spots = new THREE.Group();
        spots.name = 'buehne-spots';
        for (const side of [-1, 1]) {
            const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.45, 2.2, 12, 1, true), kit.additive(THREE, side < 0 ? PINK : CYAN, 0.16));
            beam.geometry.translate(0, -1.1, 0);
            beam.position.set(side * 1.2, 0.85, 0.5);
            spots.add(beam);
        }
        group.add(spots);

        kit.frame(THREE, group, color);

        const place = new THREE.Object3D();
        function tick(t) {
            for (let i = 0; i < flagCount; i++) {
                place.position.set(hangs[i][0], hangs[i][1], 0.68);
                place.rotation.set(Math.PI, 0, Math.sin(t * 2 + i) * 0.15);   // point down, sway
                place.updateMatrix();
                flags.setMatrixAt(i, place.matrix);
            }
            flags.instanceMatrix.needsUpdate = true;
            spots.children.forEach((b, i) => { b.rotation.z = (i ? 1 : -1) * (0.35 + Math.sin(t * 0.9 + i * 2) * 0.2); });
        }
        return { group, tick };
    }

    if (typeof module !== 'undefined' && module.exports) module.exports = buehne;
    else (root.VibeSpaceFigures = root.VibeSpaceFigures || {}).buehne = buehne;
})(typeof window !== 'undefined' ? window : globalThis);
