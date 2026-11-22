/**
 * Names under the idea bubbles of the overview, and a 30-second marker for a new bubble.
 *
 * The 3D bubbles carry no text. This layer draws one HTML label per bubble on top of
 * the canvas and moves it every frame to the bubble's place on screen. A bubble that
 * was just added gets a pulsing ring; if it sits outside the view or behind the
 * camera, the marker sticks to the nearest edge and an arrow points towards it.
 *
 * The layer only reads from MultiverseApp (bubble list, camera, container); it changes
 * nothing in the scene. The pure helpers at the top are covered by bubble-labels.test.js.
 */
(function (root) {
    'use strict';

    const NEW_HIGHLIGHT_MS = 30000;
    const NAME_MAX = 26;
    const EDGE_MARGIN = 56;

    function truncateName(name, max = NAME_MAX) {
        const text = typeof name === 'string' ? name.trim() : '';
        if (!text) return 'Ohne Namen';
        if (text.length <= max) return text;
        return text.slice(0, max - 1) + '…';
    }

    /** Where to draw the marker for a projected point; pins it to the edge when it is not visible. */
    function placeMarker(point, width, height, margin = EDGE_MARGIN) {
        const cx = width / 2;
        const cy = height / 2;
        let x = Number.isFinite(point.x) ? point.x : cx;
        let y = Number.isFinite(point.y) ? point.y : cy - 1;
        const broken = !Number.isFinite(point.x) || !Number.isFinite(point.y);
        if (point.behind) {
            // Behind the camera the projection is mirrored through the centre.
            x = width - x;
            y = height - y;
        }
        const inside = x >= margin && x <= width - margin && y >= margin && y <= height - margin;
        if (inside && !point.behind && !broken) return { x, y, offscreen: false, angle: 0 };

        let dx = x - cx;
        let dy = y - cy;
        if (dx === 0 && dy === 0) dy = -1;
        if (point.behind || inside) {
            // Push the direction out to the edge even if the mirrored point landed inside.
            const reach = Math.max(width, height);
            const length = Math.hypot(dx, dy);
            dx = (dx / length) * reach;
            dy = (dy / length) * reach;
        }
        const halfW = cx - margin;
        const halfH = cy - margin;
        const scale = Math.min(
            dx === 0 ? Infinity : halfW / Math.abs(dx),
            dy === 0 ? Infinity : halfH / Math.abs(dy),
        );
        const angle = Math.round((Math.atan2(dy, dx) * 180) / Math.PI);
        return {
            x: Math.round(cx + dx * scale),
            y: Math.round(cy + dy * scale),
            offscreen: true,
            angle: angle === -0 ? 0 : angle,
        };
    }

    /** Distant bubbles sit in the fog; their names fade with them but stay readable. */
    function labelOpacity(distance) {
        const near = 8;
        const far = 25;
        if (!(distance > near)) return 1;
        if (distance >= far) return 0.45;
        return 1 - ((distance - near) / (far - near)) * 0.55;
    }

    /**
     * Moves a label down until it no longer covers one that is already placed.
     * `placed` collects the boxes of this frame; boxes are {x, y, w, h} with x as the centre.
     */
    function avoidOverlap(box, placed, step = 17, tries = 4) {
        const out = { ...box };
        for (let i = 0; i < tries; i++) {
            const hit = placed.some((p) =>
                Math.abs(p.x - out.x) < (p.w + out.w) / 2 && Math.abs(p.y - out.y) < (p.h + out.h) / 2);
            if (!hit) break;
            out.y += step;
        }
        placed.push(out);
        return out;
    }

    /** True for the live message of a new top-level row in the ideas table (a bubble). */
    function isLiveTopLevelIdea(message) {
        if (!message || message.source !== 'supabase' || message.table !== 'ideas') return false;
        const node = message.node;
        return Boolean(node && node.id && !node.parent_id);
    }

    /** Same shape and placement as the bubble_created handler in index.html. */
    function bubbleDataFromIdea(node, random = Math.random) {
        const angle = random() * Math.PI * 2;
        const ring = 2 + random() * 2;
        return {
            id: node.id,
            db_id: node.id,
            title: node.title,
            color: { r: 0.3 + random() * 0.4, g: 0.5 + random() * 0.3, b: 0.8 + random() * 0.2 },
            position: { x: Math.cos(angle) * ring, y: -0.5 + random() * 1, z: Math.sin(angle) * ring },
            radius: 0.6 + random() * 0.3,
        };
    }

    const STYLE = `
#bubble-label-layer { position: fixed; pointer-events: none; overflow: hidden; z-index: 2; }
#bubble-label-layer.is-hidden { display: none; }
.bubble-label {
    position: absolute; left: 0; top: 0; transform: translate(-50%, 0);
    max-width: 190px; padding: 2px 8px; border-radius: 9px;
    font: 500 12px/1.35 system-ui, -apple-system, "Segoe UI", sans-serif;
    color: rgba(226, 232, 245, 0.92); background: rgba(10, 8, 18, 0.55);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.8); will-change: transform;
}
.bubble-label.is-new {
    color: #fff; background: rgba(56, 132, 255, 0.85); font-weight: 700; font-size: 13px;
    box-shadow: 0 0 14px rgba(86, 156, 255, 0.75);
}
.bubble-new-ring {
    position: absolute; left: 0; top: 0; border-radius: 50%;
    border: 2px solid rgba(120, 180, 255, 0.95); box-shadow: 0 0 18px rgba(86, 156, 255, 0.7);
    will-change: transform;
}
/* The ring itself stays put so the bubble is marked at every moment; a copy pulses outwards. */
.bubble-new-ring::after {
    content: ''; position: absolute; inset: -2px; border-radius: 50%;
    border: 2px solid rgba(120, 180, 255, 0.95);
    animation: bubble-new-pulse 1.6s ease-out infinite;
}
.bubble-new-ring.is-offscreen { border-style: dashed; }
.bubble-new-ring.is-offscreen::after { animation: none; display: none; }
.bubble-new-arrow {
    position: absolute; left: 0; top: 0; width: 0; height: 0;
    border-top: 9px solid transparent; border-bottom: 9px solid transparent;
    border-left: 15px solid rgba(120, 180, 255, 0.95); display: none;
}
@keyframes bubble-new-pulse {
    0% { opacity: 1; scale: 0.85; }
    100% { opacity: 0; scale: 1.7; }
}
@media (prefers-reduced-motion: reduce) { .bubble-new-ring::after { animation: none; display: none; } }
`;

    class BubbleLabelLayer {
        constructor(getApp, doc = root.document) {
            this.getApp = getApp;
            this.doc = doc;
            this.entries = new Map(); // bubble id -> { label, ring, arrow, text }
            this.newUntil = new Map(); // bubble id -> timestamp
            this.layer = null;
            this._tick = this._tick.bind(this);
        }

        start() {
            if (this.layer) return;
            const style = this.doc.createElement('style');
            style.id = 'bubble-label-style';
            style.textContent = STYLE;
            this.doc.head.appendChild(style);
            this.layer = this.doc.createElement('div');
            this.layer.id = 'bubble-label-layer';
            this.layer.setAttribute('aria-hidden', 'true');
            this.doc.body.appendChild(this.layer);
            root.requestAnimationFrame(this._tick);
        }

        /** Highlight a bubble for 30 seconds. Unknown ids are kept; the bubble may arrive a moment later. */
        markNew(id, now = Date.now()) {
            if (id === undefined || id === null || id === '') return;
            this.newUntil.set(String(id), now + NEW_HIGHLIGHT_MS);
        }

        _visible(app) {
            if (!app || !app.camera || !app.container || !app.spaces || !app.spaces.ideas) return false;
            if (app.currentSpace !== 'ideas' || app.isInsideBubble || root.isEnteringBubble) return false;
            const spaceView = this.doc.getElementById('space-view');
            return !(spaceView && !spaceView.classList.contains('hidden'));
        }

        _entry(id) {
            let entry = this.entries.get(id);
            if (!entry) {
                const label = this.doc.createElement('div');
                label.className = 'bubble-label';
                this.layer.appendChild(label);
                entry = { label, ring: null, arrow: null, text: null };
                this.entries.set(id, entry);
            }
            return entry;
        }

        _drop(id) {
            const entry = this.entries.get(id);
            if (!entry) return;
            for (const el of [entry.label, entry.ring, entry.arrow]) if (el) el.remove();
            this.entries.delete(id);
        }

        _tick() {
            root.requestAnimationFrame(this._tick);
            try {
                this._update(Date.now());
            } catch (err) {
                // Never let a label problem stop the frame loop; show it once.
                if (!this._warned) { this._warned = true; console.warn('[BubbleLabels]', err); }
            }
        }

        _update(now) {
            const app = this.getApp();
            const visible = this._visible(app);
            this.layer.classList.toggle('is-hidden', !visible);
            if (!visible) return;

            const rect = app.container.getBoundingClientRect();
            const s = this.layer.style;
            s.left = rect.left + 'px'; s.top = rect.top + 'px';
            s.width = rect.width + 'px'; s.height = rect.height + 'px';

            for (const [id, until] of this.newUntil) if (until <= now) this.newUntil.delete(id);

            const THREE = root.THREE;
            const seen = new Set();
            const placed = [];
            const centre = new THREE.Vector3();
            const top = new THREE.Vector3();
            const up = new THREE.Vector3();
            for (const bubble of app.spaces.ideas.objects || []) {
                const data = bubble.userData;
                if (!data || data.type !== 'bubble') continue;
                const id = String(data.db_id || data.id);
                if (seen.has(id)) continue;
                seen.add(id);

                bubble.getWorldPosition(centre);
                const distance = app.camera.position.distanceTo(centre);
                const radius = (bubble.geometry && bubble.geometry.parameters && bubble.geometry.parameters.radius) || 0.7;
                up.copy(app.camera.up).applyQuaternion(app.camera.quaternion).normalize();
                top.copy(centre).addScaledVector(up, radius * bubble.scale.y);

                const c = centre.clone().project(app.camera);
                const t = top.project(app.camera);
                const behind = c.z > 1;
                const x = (c.x * 0.5 + 0.5) * rect.width;
                const y = (-c.y * 0.5 + 0.5) * rect.height;
                const radiusPx = Math.max(6, Math.abs(((-t.y * 0.5 + 0.5) * rect.height) - y));

                const entry = this._entry(id);
                const isNew = this.newUntil.has(id);
                const text = truncateName(data.title);
                if (entry.text !== text) { entry.label.textContent = text; entry.text = text; }
                entry.label.classList.toggle('is-new', isNew);

                const onScreen = !behind && x > -100 && x < rect.width + 100 && y > -60 && y < rect.height + 60;
                if (!isNew) {
                    if (entry.ring) { entry.ring.remove(); entry.ring = null; }
                    if (entry.arrow) { entry.arrow.remove(); entry.arrow = null; }
                    entry.label.style.display = onScreen ? '' : 'none';
                    if (onScreen) {
                        const box = avoidOverlap(
                            { x, y: y + radiusPx + 4, w: Math.min(190, text.length * 7 + 16), h: 17 }, placed);
                        entry.label.style.opacity = String(labelOpacity(distance));
                        entry.label.style.transform = `translate(-50%, 0) translate(${box.x.toFixed(1)}px, ${box.y.toFixed(1)}px)`;
                    }
                    continue;
                }

                // New bubble: always shown, pinned to the edge when it is out of view.
                const marker = placeMarker({ x, y, behind }, rect.width, rect.height);
                if (!entry.ring) {
                    entry.ring = this.doc.createElement('div');
                    entry.ring.className = 'bubble-new-ring';
                    entry.arrow = this.doc.createElement('div');
                    entry.arrow.className = 'bubble-new-arrow';
                    this.layer.append(entry.ring, entry.arrow);
                }
                const size = marker.offscreen ? 34 : Math.min(260, radiusPx * 2 + 26);
                entry.ring.classList.toggle('is-offscreen', marker.offscreen);
                entry.ring.style.width = entry.ring.style.height = size.toFixed(1) + 'px';
                entry.ring.style.transform = `translate(${(marker.x - size / 2).toFixed(1)}px, ${(marker.y - size / 2).toFixed(1)}px)`;
                entry.arrow.style.display = marker.offscreen ? 'block' : 'none';
                if (marker.offscreen) {
                    entry.arrow.style.transform = `translate(${marker.x - 7}px, ${marker.y - 9}px) rotate(${marker.angle}deg) translate(26px, 0)`;
                }
                entry.label.style.display = '';
                entry.label.style.opacity = '1';
                const labelY = marker.offscreen
                    ? Math.min(Math.max(marker.y + 24, 8), rect.height - 30)
                    : marker.y + size / 2 + 2;
                const labelX = Math.min(Math.max(marker.x, 100), rect.width - 100);
                entry.label.style.transform = `translate(-50%, 0) translate(${labelX.toFixed(1)}px, ${labelY.toFixed(1)}px)`;
            }

            for (const id of [...this.entries.keys()]) if (!seen.has(id)) this._drop(id);
        }
    }

    const api = {
        NEW_HIGHLIGHT_MS, truncateName, placeMarker, labelOpacity, avoidOverlap,
        isLiveTopLevelIdea, bubbleDataFromIdea, BubbleLabelLayer,
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        root.BubbleLabels = api;
        const layer = new BubbleLabelLayer(() => root.multiverseApp);
        root.bubbleLabelLayer = layer;
        if (root.document.readyState === 'loading') {
            root.document.addEventListener('DOMContentLoaded', () => layer.start());
        } else {
            layer.start();
        }
    }
})(typeof window !== 'undefined' ? window : globalThis);
