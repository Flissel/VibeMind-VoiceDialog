/**
 * Figure "leuchtturm" (Marketing): a striped lighthouse on a rock sends its signal out. The
 * double beam turns round, the lamp breathes, small rings of sound and light go out over the sea.
 *
 * make(THREE, color, kit) -> { group, tick(t) }; kit comes from space-models.js.
 */
(function (root) {
    'use strict';

    function leuchtturm(THREE, color, kit) {
        const { PINK, PAPER, STEEL, STONE } = kit.COLORS;
        const LIGHT = 0xffd98a;
        const group = new THREE.Group();

        const rock = new THREE.Mesh(new THREE.DodecahedronGeometry(1.1, 0), kit.glowing(THREE, STONE, 0.08, { flatShading: true }));
        rock.name = 'leuchtturm-fels';
        rock.scale.set(1.3, 0.45, 1.1);
        rock.position.y = -1.75;
        group.add(rock);

        // the tower: four rings, narrowing upwards, pink and white in turn
        const tower = new THREE.Group();
        tower.name = 'leuchtturm-turm';
        for (let i = 0; i < 4; i++) {
            const h = 0.62, r0 = 0.62 - i * 0.07, r1 = r0 - 0.07;
            const ring = new THREE.Mesh(new THREE.CylinderGeometry(r1, r0, h, 20), kit.glowing(THREE, i % 2 ? PAPER : PINK, i % 2 ? 0.12 : 0.3));
            ring.position.y = -1.25 + h / 2 + i * h;
            tower.add(ring);
        }
        const gallery = new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.04, 8, 28), kit.glowing(THREE, STEEL, 0.2));
        gallery.rotation.x = Math.PI / 2;
        gallery.position.y = 1.25;
        const cap = new THREE.Mesh(new THREE.ConeGeometry(0.36, 0.42, 16), kit.glowing(THREE, PINK, 0.35));
        cap.position.y = 1.89;
        tower.add(gallery, cap);
        group.add(tower);

        const lamp = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.42, 16), kit.glowing(THREE, 0xfff3c4, 1.2, { transparent: true, opacity: 0.9 }));
        lamp.name = 'leuchtturm-lampe';
        lamp.position.y = 1.47;
        group.add(lamp);

        // the beam: two cones back to back, the narrow ends in the lamp
        const beam = new THREE.Group();
        beam.name = 'leuchtturm-strahl';
        beam.position.y = 1.47;
        for (const side of [1, -1]) {
            const cone = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.5, 3.0, 16, 1, true), kit.additive(THREE, LIGHT, 0.32));
            cone.geometry.translate(0, -1.5, 0);
            cone.rotation.z = side * Math.PI / 2;
            beam.add(cone);
        }
        group.add(beam);

        // rings going out over the water at the foot of the rock: the message spreading
        const waveCount = 3;
        const waves = new THREE.InstancedMesh(new THREE.RingGeometry(0.96, 1, 48), kit.additive(THREE, color, 0.35), waveCount);
        waves.name = 'leuchtturm-wellen';
        group.add(waves);

        kit.frame(THREE, group, color);

        const place = new THREE.Object3D();
        place.rotation.x = -Math.PI / 2;
        function tick(t) {
            beam.rotation.y = t * 0.8;
            lamp.material.emissiveIntensity = 1.0 + 0.35 * Math.sin(t * 2.4);
            for (let i = 0; i < waveCount; i++) {
                const k = (t * 0.22 + i / waveCount) % 1;      // 0 at the rock, 1 at the base ring
                place.position.set(0, -1.9, 0);
                place.scale.setScalar(1.3 + k * 1.5);
                place.updateMatrix();
                waves.setMatrixAt(i, place.matrix);
            }
            waves.instanceMatrix.needsUpdate = true;
        }
        return { group, tick };
    }

    if (typeof module !== 'undefined' && module.exports) module.exports = leuchtturm;
    else (root.VibeSpaceFigures = root.VibeSpaceFigures || {}).leuchtturm = leuchtturm;
})(typeof window !== 'undefined' ? window : globalThis);
