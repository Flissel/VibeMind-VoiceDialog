/**
 * Figure "buch" (Lernen): an open book on a reading stand; points of light rise from its pages
 * and fade out above it, like ideas leaving the page.
 *
 * make(THREE, color, kit) -> { group, tick(t) }; kit comes from space-models.js.
 */
(function (root) {
    'use strict';

    function buch(THREE, color, kit) {
        const { GREEN, PAPER, STEEL, STONE, INK } = kit.COLORS;
        const group = new THREE.Group();

        const stand = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.16, 1.6, 10), kit.glowing(THREE, STEEL, 0.1));
        stand.position.y = -1.1;
        const foot = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.7, 0.12, 20), kit.glowing(THREE, STONE, 0.1));
        foot.position.y = -1.95;
        group.add(stand, foot);

        // the open book, tilted to the reader; both halves share geometry and material
        const book = new THREE.Group();
        book.name = 'buch-aufgeschlagen';
        book.position.y = -0.2;
        book.rotation.x = 0.35;
        const coverGeo = new THREE.BoxGeometry(1.05, 0.06, 1.4);
        const pagesGeo = new THREE.BoxGeometry(0.98, 0.12, 1.3);
        const coverMat = kit.glowing(THREE, GREEN, 0.3);
        const pagesMat = kit.glowing(THREE, PAPER, 0.25);
        const lines = [];
        for (const side of [-1, 1]) {
            const half = new THREE.Group();
            half.rotation.z = side * 0.16;
            const cover = new THREE.Mesh(coverGeo, coverMat);
            cover.position.x = side * 0.55;
            const pages = new THREE.Mesh(pagesGeo, pagesMat);
            pages.position.set(side * 0.53, 0.08, 0);
            half.add(cover, pages);
            book.add(half);
            // lines of text, in the frame of the book (half turned by side * 0.16 about z)
            for (let l = 0; l < 5; l++) {
                const x = side * 0.53, y = 0.145, a = side * 0.16;
                lines.push({ p: [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a), -0.45 + l * 0.22], r: [0, 0, a], s: 1 - (l % 2) * 0.28 });
            }
        }
        const text = kit.instanced(THREE, new THREE.BoxGeometry(0.7, 0.01, 0.04), kit.glowing(THREE, INK, 0.1), lines);
        text.name = 'buch-zeilen';
        book.add(text);
        group.add(book);

        // rising points of light: one instanced mesh, two shades of the colour of the space
        const sparkCount = 16;
        const sparks = new THREE.InstancedMesh(new THREE.SphereGeometry(0.06, 8, 6), kit.glowing(THREE, 0xffffff, 1.0), sparkCount);
        sparks.name = 'buch-lichtpunkte';
        const starts = [];
        for (let i = 0; i < sparkCount; i++) {
            sparks.setColorAt(i, new THREE.Color(i % 3 ? 0xeaffd0 : GREEN));
            starts.push({ x: Math.sin(i * 7.1) * 0.8, z: Math.cos(i * 3.3) * 0.45, p: i / sparkCount });
        }
        group.add(sparks);

        kit.frame(THREE, group, color);

        const place = new THREE.Object3D();
        function tick(t) {
            for (let i = 0; i < sparkCount; i++) {
                const s = starts[i];
                const k = (t * 0.18 + s.p) % 1;                     // 0 on the page, 1 high above
                place.position.set(s.x * (1 - k * 0.4) + Math.sin(t + s.p * 9) * 0.1, 0.05 + k * 2.3, s.z);
                place.scale.setScalar(k > 0.8 ? (1 - k) / 0.2 : 1);
                place.updateMatrix();
                sparks.setMatrixAt(i, place.matrix);
            }
            sparks.instanceMatrix.needsUpdate = true;
        }
        return { group, tick };
    }

    if (typeof module !== 'undefined' && module.exports) module.exports = buch;
    else (root.VibeSpaceFigures = root.VibeSpaceFigures || {}).buch = buch;
})(typeof window !== 'undefined' ? window : globalThis);
