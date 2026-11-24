/**
 * Base models of the external spaces in the 3D scene (instead of the gate with its emoji sign).
 *
 * One file per figure in space-figures/, one table here: which space shows which figure. To swap a
 * figure, change its line in FIGURES (and load its file in index.html); nothing else changes.
 *
 * Own three.js geometry only: no model files, no textures, no real lights (the glow comes from
 * emissive and additive materials, so the light count of the scene and its shaders stay as they
 * are). Each figure has the frame of the other spaces: a halo hull (also the click target, see
 * space-pick.js) and a base ring at y = -2, both restyled by scene-kit.js.
 *
 * build(THREE, space) -> { group, tick(t), dispose() } or null when the space has no figure (it keeps its gate).
 */
(function (root) {
    'use strict';

    /** Space -> figure. A figure is the file renderer/space-figures/<name>.js. */
    const FIGURES = { sales: 'disco', marketing: 'leuchtturm', learning: 'buch', events: 'buehne' };

    const COLORS = {
        CYAN: 0x4fc3f7, PINK: 0xff7eb6, VIOLET: 0x8866ff, ORANGE: 0xff9f43, GOLD: 0xffc857, GREEN: 0x9ccc65,
        AMBER: 0xffb74d, LILAC: 0xb39ddb, PAPER: 0xf4f0f8, STEEL: 0xb0c4de, DARK: 0x2a2440, STONE: 0x3a3550, INK: 0x6a6488,
    };

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

    /** A number in [0, 1) from an integer, the same on every start (no chance in the scene). */
    function hash(n) {
        return Math.abs(Math.sin(n * 12.9898) * 43758.5453) % 1;
    }

    /** One instanced mesh from placements { p: [x, y, z], r: [x, y, z]?, s: number?, c: color? }. */
    function instanced(THREE, geometry, material, placements) {
        const mesh = new THREE.InstancedMesh(geometry, material, placements.length);
        const place = new THREE.Object3D();
        placements.forEach((one, i) => {
            place.position.set(one.p[0], one.p[1], one.p[2]);
            const r = one.r || [0, 0, 0];
            place.rotation.set(r[0], r[1], r[2]);
            place.scale.setScalar(one.s === undefined ? 1 : one.s);
            place.updateMatrix();
            mesh.setMatrixAt(i, place.matrix);
            if (one.c !== undefined) mesh.setColorAt(i, new THREE.Color(one.c));
        });
        return mesh;
    }

    const kit = { COLORS, glowing, additive, frame, hash, instanced };

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

    /** The builder of a figure: from its file in node, from its loaded script in the page. */
    function figure(name) {
        if (typeof module !== 'undefined' && module.exports) return require(`./space-figures/${name}.js`);
        return (root.VibeSpaceFigures || {})[name] || null;
    }

    /** The figure of a space, placed at the space, or null when it has none (it keeps its gate). */
    function build(THREE, space) {
        const name = space ? FIGURES[space.id] : null;
        const make = name ? figure(name) : null;
        if (!make) return null;
        const { group, tick } = make(THREE, space.color, kit);
        group.name = `raum-modell-${space.id}`;
        group.position.set(space.position[0], space.position[1], space.position[2]);
        group.userData = { type: 'space-model', space: space.id, figure: name };
        tick(0);
        return { group, tick, dispose: () => disposeGroup(group) };
    }

    /** Triangles drawn per frame, instances counted, hidden parts not. */
    function triangles(group) {
        let total = 0;
        group.traverse((obj) => {
            if (!obj.isMesh || !obj.visible) return;
            const g = obj.geometry;
            const per = (g.index ? g.index.count : g.attributes.position.count) / 3;
            total += per * (obj.isInstancedMesh ? obj.count : 1);
        });
        return Math.round(total);
    }

    const api = { build, triangles, FIGURES, kit };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.VibeSpaceModels = api;
})(typeof window !== 'undefined' ? window : globalThis);
