/**
 * Marks of the clicks on the desktop pictures (Desktop space).
 *
 * The clicks come from the task book of the Brain (window.vibemind.desktopKlicks, every
 * POLL_MS while the pictures are shown) and from the answer to a click on the picture
 * (add). Each is a ring at its place on the right monitor that fades over FADE_S:
 *   agent  cyan, filled      hand  white, filled      trocken (dry run)  outline, dashed
 *   refused (ok false)  red, with a short line for the reason
 * A click still running (ok null) is drawn in its colour, half strong.
 * Marks are drawn on their own canvas per monitor (.klick-marken-canvas), so the eyeTerm dots
 * on .click-dot-canvas, which clear their canvas on every message, do not wipe them out.
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.VibeKlickMarken = api;
})(typeof self !== 'undefined' ? self : this, function () {
    const POLL_MS = 1500;
    const DRAW_MS = 250;
    const FADE_S = 30;
    const RING = 14;
    const MAX_MARKS = 300;

    const COLORS = Object.freeze({ agent: '103, 232, 249', hand: '255, 255, 255', trocken: '200, 190, 220', abgelehnt: '255, 90, 110' });

    /** The reasons as the picture says them; anything else reads "abgelehnt". No window title ever. */
    const REASONS = Object.freeze({
        gesperrt: 'gesperrtes Fenster',
        not_aus: 'Not-Aus',
        aufgabe_laeuft: 'Agent arbeitet',
        fenster_unlesbar: 'Fenster unklar',
        freigabe_ausstehend: 'wartet auf Freigabe',
        nicht_freigegeben: 'nicht freigegeben',
        nicht_gebunden: 'nicht gebunden',
        werkzeug_aus: 'Werkzeug aus',
        dienst_fehler: 'Dienst-Fehler',
        dienst_nicht_erreichbar: 'Dienst fehlt',
        werkzeug_fehler: 'Werkzeug-Fehler',
        nicht_belegt: 'nicht freigeschaltet',
        klick_laeuft: 'Klick läuft noch',
        gehirn_nicht_erreichbar: 'Gehirn fehlt',
        keine_antwort: 'keine Antwort',
        eingabe_ungueltig: 'ungültige Stelle',
    });

    function reasonText(grund) {
        return Object.prototype.hasOwnProperty.call(REASONS, grund) ? REASONS[grund] : 'abgelehnt';
    }

    const num = (v) => typeof v === 'number' && Number.isFinite(v);

    /** A click of the Brain as a mark, or null when it has no place. */
    function markOf(klick) {
        if (!klick || !num(klick.x) || !num(klick.y)) return null;
        const quelle = klick.quelle === 'agent' || klick.quelle === 'hand' || klick.quelle === 'trocken' ? klick.quelle
            : (klick.trocken ? 'trocken' : (klick.hand ? 'hand' : 'agent'));
        const refused = klick.ok === false;
        return {
            key: `${klick.task_id || ''}|${klick.zeit || ''}|${klick.x},${klick.y}`,
            x: klick.x, y: klick.y, zeit: num(klick.zeit) ? klick.zeit : 0,
            quelle, refused, running: klick.ok === null || klick.ok === undefined,
            text: refused ? reasonText(klick.grund) : '',
        };
    }

    /** How a mark looks at `now` (seconds), or null once faded. */
    function styleOf(mark, now) {
        const age = Math.max(0, now - mark.zeit);
        if (age >= FADE_S) return null;
        const fade = 1 - age / FADE_S;
        const rgb = mark.refused ? COLORS.abgelehnt : COLORS[mark.quelle];
        return {
            rgb, alpha: fade * (mark.running ? 0.5 : 1),
            filled: !mark.refused && mark.quelle !== 'trocken',
            dashed: mark.quelle === 'trocken',
            text: mark.text,
        };
    }

    /**
     * The monitor of a desktop point and its place on that monitor's canvas.
     * monitors: [{ offsetX, offsetY, width, height, boxW, boxH }] (box = canvas size, picture
     * drawn with object-fit: contain inside it).
     */
    function placeOf(monitors, x, y) {
        for (const m of monitors) {
            if (x < m.offsetX || x >= m.offsetX + m.width || y < m.offsetY || y >= m.offsetY + m.height) continue;
            const imgAspect = m.width / m.height;
            const boxAspect = m.boxW / m.boxH;
            let renderW, renderH, padX, padY;
            if (imgAspect > boxAspect) { renderW = m.boxW; renderH = m.boxW / imgAspect; padX = 0; padY = (m.boxH - renderH) / 2; }
            else { renderH = m.boxH; renderW = m.boxH * imgAspect; padX = (m.boxW - renderW) / 2; padY = 0; }
            return { monitor: m, cx: padX + ((x - m.offsetX) / m.width) * renderW, cy: padY + ((y - m.offsetY) / m.height) * renderH };
        }
        return null;
    }

    function create(win, doc) {
        const marks = new Map();
        let grid = null;
        let active = false;
        let pollTimer = null;
        let drawTimer = null;
        let newest = 0;        // `zeit` of the newest click known: the next `seit`
        let stopped = false;   // STOP lies (emergency stop)
        const nowS = () => (win.Date ? win.Date.now() : Date.now()) / 1000;

        function remember(mark, klick) {
            if (!mark) return;
            // the book entry of a click made here replaces the mark of its answer
            if (klick && klick.hand && klick.task_id) marks.delete(`antwort|${klick.task_id}`);
            marks.set(mark.key, mark);
            if (mark.zeit > newest) newest = mark.zeit;
            if (marks.size > MAX_MARKS) marks.delete(marks.keys().next().value);
        }

        async function poll() {
            pollTimer = null;
            if (!active) return;
            const ask = win.vibemind && win.vibemind.desktopKlicks;
            if (ask) {
                try {
                    const answer = await ask(newest || undefined);
                    if (answer && Array.isArray(answer.klicks)) {
                        for (const k of answer.klicks) remember(markOf(k), k);
                        stopped = answer.stopped === true;
                    }
                } catch (_) { /* the next round asks again */ }
            }
            if (active) pollTimer = win.setTimeout(poll, POLL_MS);
        }

        function monitorsOf() {
            if (!grid) return [];
            const out = [];
            grid.querySelectorAll('.monitor-panel').forEach((p) => {
                const canvas = p.querySelector('.klick-marken-canvas');
                const img = p.querySelector('.desktop-stream-img');
                if (!canvas || !img || !img.naturalWidth) return;
                const rect = p.getBoundingClientRect();
                out.push({
                    offsetX: parseInt(p.dataset.offsetX || '0', 10), offsetY: parseInt(p.dataset.offsetY || '0', 10),
                    width: img.naturalWidth, height: img.naturalHeight, boxW: rect.width, boxH: rect.height, canvas,
                });
            });
            return out;
        }

        function draw() {
            const monitors = monitorsOf();
            const now = nowS();
            for (const m of monitors) {
                m.canvas.width = m.boxW;
                m.canvas.height = m.boxH;
                m.ctx = m.canvas.getContext('2d');
                m.ctx.clearRect(0, 0, m.boxW, m.boxH);
            }
            for (const [key, mark] of marks) {
                const look = styleOf(mark, now);
                if (!look) { marks.delete(key); continue; }
                const place = placeOf(monitors, mark.x, mark.y);
                if (!place) continue;
                const ctx = place.monitor.ctx;
                ctx.save();
                ctx.lineWidth = 2;
                ctx.strokeStyle = `rgba(${look.rgb}, ${look.alpha})`;
                ctx.setLineDash(look.dashed ? [4, 3] : []);
                ctx.beginPath();
                ctx.arc(place.cx, place.cy, RING, 0, Math.PI * 2);
                ctx.stroke();
                if (look.filled) {
                    ctx.fillStyle = `rgba(${look.rgb}, ${look.alpha * 0.35})`;
                    ctx.fill();
                }
                if (look.text) {
                    ctx.setLineDash([]);
                    ctx.font = '11px "Segoe UI", sans-serif';
                    ctx.fillStyle = `rgba(${look.rgb}, ${look.alpha})`;
                    ctx.fillText(look.text, place.cx + RING + 4, place.cy + 4);
                }
                ctx.restore();
            }
            const hint = doc.getElementById('klick-not-aus');
            if (hint) hint.hidden = !stopped;
        }

        /** Start asking and drawing for the pictures in `gridEl`. */
        function start(gridEl) {
            grid = gridEl || grid;
            if (active) return;
            active = true;
            poll();
            drawTimer = win.setInterval(draw, DRAW_MS);
        }

        /** Stop asking and drawing (the space is left); the marks stay for the next start. */
        function stop() {
            active = false;
            if (pollTimer) { win.clearTimeout(pollTimer); pollTimer = null; }
            if (drawTimer) { win.clearInterval(drawTimer); drawTimer = null; }
        }

        /** The answer to a click on the picture, shown at once (a refusal "Not-Aus" is only here). */
        function add(answer) {
            if (!answer || typeof answer !== 'object') return null;
            const mark = markOf({ ...answer, quelle: answer.trocken ? 'trocken' : 'hand', hand: true, zeit: num(answer.zeit) ? answer.zeit : nowS() });
            if (mark) {
                if (answer.task_id) mark.key = `antwort|${answer.task_id}`;
                marks.set(mark.key, mark);   // not `newest`: the book may write its own entry a little later
            }
            return mark;
        }

        return { start, stop, add, draw, isActive: () => active, marks, stopped: () => stopped };
    }

    return { create, markOf, styleOf, placeOf, reasonText, POLL_MS, FADE_S, RING, COLORS };
});
