/**
 * Figure "klemmbrett" (Aufträge): a clipboard on an easel; its lines get ticked one after the
 * other, then after a short pause the list starts again.
 *
 * make(THREE, color, kit) -> { group, tick(t) }; kit comes from space-models.js.
 */
(function (root) {
    'use strict';

    function klemmbrett(THREE, color, kit) {
        const { LILAC, PAPER, GREEN, INK } = kit.COLORS;
        const WOOD = 0x6b4f3a, LEG = 0x8a6a50;
        const group = new THREE.Group();

        const board = new THREE.Group();
        board.name = 'klemmbrett-brett';
        board.position.y = 0.1;
        board.rotation.x = -0.18;
        const plate = new THREE.Mesh(new THREE.BoxGeometry(1.8, 2.3, 0.08), kit.glowing(THREE, WOOD, 0.15));
        const paper = new THREE.Mesh(new THREE.BoxGeometry(1.55, 1.95, 0.02), kit.glowing(THREE, PAPER, 0.25));
        paper.position.set(0, -0.08, 0.05);
        const clip = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.22, 0.12), kit.glowing(THREE, LILAC, 0.5, { metalness: 0.6, roughness: 0.3 }));
        clip.name = 'klemmbrett-klammer';
        clip.position.set(0, 1.08, 0.08);
        board.add(plate, paper, clip);

        // five lines, each with a box and a tick of two bars; boxes, lines and bars one instanced mesh each
        const rows = [0, 1, 2, 3, 4].map((i) => 0.62 - i * 0.36);
        const ink = kit.glowing(THREE, INK, 0.12);
        const boxes = kit.instanced(THREE, new THREE.BoxGeometry(0.18, 0.18, 0.01), ink, rows.map((y) => ({ p: [-0.55, y, 0.07] })));
        const lines = kit.instanced(THREE, new THREE.BoxGeometry(0.85, 0.05, 0.01), ink,
            rows.map((y, i) => ({ p: [0.05 - (i % 2) * 0.12, y, 0.07], s: 1 - (i % 2) * 0.3 })));
        lines.name = 'klemmbrett-zeilen';
        const tickMat = kit.glowing(THREE, GREEN, 0.9);
        const short = kit.instanced(THREE, new THREE.BoxGeometry(0.1, 0.035, 0.02), tickMat, rows.map((y) => ({ p: [-0.59, y - 0.03, 0.09], r: [0, 0, -0.8] })));
        const long = kit.instanced(THREE, new THREE.BoxGeometry(0.2, 0.035, 0.02), tickMat, rows.map((y) => ({ p: [-0.5, y + 0.02, 0.09], r: [0, 0, 0.9] })));
        const ticks = new THREE.Group();
        ticks.name = 'klemmbrett-haken';
        ticks.add(short, long);
        board.add(boxes, lines, ticks);
        group.add(board);

        const legs = kit.instanced(THREE, new THREE.CylinderGeometry(0.04, 0.05, 2.4, 8), kit.glowing(THREE, LEG, 0.1),
            [[-0.6, 0.25, 0.1, 0.2], [0.6, 0.25, 0.1, -0.2], [0, -0.65, -0.25, 0]].map(([x, z, rx, rz]) => ({ p: [x, -0.95, z], r: [rx, 0, rz] })));
        legs.name = 'klemmbrett-staffelei';
        group.add(legs);

        kit.frame(THREE, group, color);

        function tick(t) {
            const shown = Math.floor((t * 0.6) % 7);       // 0..5 ticks, then a short pause, again
            short.count = long.count = Math.min(shown, rows.length);
        }
        return { group, tick };
    }

    if (typeof module !== 'undefined' && module.exports) module.exports = klemmbrett;
    else (root.VibeSpaceFigures = root.VibeSpaceFigures || {}).klemmbrett = klemmbrett;
})(typeof window !== 'undefined' ? window : globalThis);
