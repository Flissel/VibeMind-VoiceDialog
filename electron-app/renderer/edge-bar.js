/**
 * With a bubble open the area belongs to the cards and the chat. Whatever else floated over it
 * (voice panel, Summaries, White Paper, the EVAL tab) moves into a bar at the edge, in the header
 * of the bubble; leaving the bubble puts every element back where it was.
 *
 * Elements are moved, not copied: their click handlers keep working.
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root) root.VibeEdgeBar = api;
})(typeof window !== 'undefined' ? window : null, function () {
    'use strict';

    const IDS = ['summaries-toggle', 'whitepaper-toggle', 'eval-toggle', 'voice-panel'];
    const BAR_ID = 'space-edge-bar';

    function create() {
        const homes = new Map(); // id -> { parent, next }

        function bar(doc) {
            let el = doc.getElementById(BAR_ID);
            if (!el) {
                const header = doc.getElementById('space-header');
                if (!header) return null;
                el = doc.createElement('div');
                el.id = BAR_ID;
                el.setAttribute('aria-label', 'Werkzeuge');
                header.appendChild(el);
            }
            return el;
        }

        /** Bubble opened: everything over the cards into the bar. */
        function dock(doc) {
            const target = bar(doc);
            if (!target) return 0;
            // every place first, then move: a neighbour that moves first would falsify the place
            const loose = IDS.map((id) => doc.getElementById(id)).filter((el) => el && el.parentNode !== target);
            for (const el of loose) homes.set(el.id, { parent: el.parentNode, next: el.nextSibling });
            for (const el of loose) target.appendChild(el);
            const moved = loose.length;
            if (doc.body && doc.body.classList) doc.body.classList.add('bubble-open');
            return moved;
        }

        /** Bubble left: every element back to its place. */
        function undock(doc) {
            for (const id of IDS.slice().reverse()) {   // last moved first: its neighbours are home again
                const home = homes.get(id);
                const el = doc.getElementById(id);
                if (!home || !el || !home.parent) continue;
                const next = home.next && home.next.parentNode === home.parent ? home.next : null;
                home.parent.insertBefore(el, next);
            }
            homes.clear();
            if (doc.body && doc.body.classList) doc.body.classList.remove('bubble-open');
        }

        /** Follow #space-view: every way into a bubble (button, key, voice, Python) shows it. */
        function sync(doc) {
            const view = doc.getElementById('space-view');
            if (view && !view.classList.contains('hidden')) dock(doc);
            else undock(doc);
        }

        function watch(doc, Observer) {
            const view = doc.getElementById('space-view');
            if (!view || typeof Observer !== 'function') return null;
            const observer = new Observer(() => sync(doc));
            observer.observe(view, { attributes: true, attributeFilter: ['class'] });
            sync(doc);
            return observer;
        }

        return { dock, undock, sync, watch };
    }

    const shared = create();
    if (typeof document !== 'undefined' && typeof MutationObserver === 'function') {
        const start = () => shared.watch(document, MutationObserver);
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
        else start();
    }
    return { IDS, BAR_ID, create, dock: shared.dock, undock: shared.undock };
});
