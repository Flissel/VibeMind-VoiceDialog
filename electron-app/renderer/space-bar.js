/**
 * The bar above an embedded page (Sales, Marketing, Lernen, Events, Aufträge).
 *
 * An embedded page has no browser bar of its own: once it has followed a link, there was no way
 * back to where the space started. The main process (external-spaces.js) reports whether the page
 * has left its start address and whether its history allows a step back; this draws "← Zurück"
 * and "⌂ Start" in the 28 px it keeps free above the page. No address reaches this side.
 */
(function (root) {
    'use strict';

    const STYLE = `
#space-bar { position: fixed; left: 0; right: 0; top: 75px; height: 28px; z-index: 900;
  display: flex; align-items: center; gap: 6px; padding: 0 10px; box-sizing: border-box;
  background: #0f0d1a; border-bottom: 1px solid rgba(136, 102, 255, 0.25); font: 12px system-ui, "Segoe UI", sans-serif; }
#space-bar[hidden] { display: none; }
#space-bar button { height: 22px; padding: 0 10px; border-radius: 6px; cursor: pointer;
  border: 1px solid rgba(136, 102, 255, 0.35); background: rgba(136, 102, 255, 0.12); color: #dde3f0; font: inherit; }
#space-bar button:hover { background: rgba(136, 102, 255, 0.25); }
#space-bar button[hidden] { display: none; }
#space-bar .space-bar-name { color: rgba(200, 210, 235, 0.6); margin-left: 4px; }
/* the space sign top right (space-nav.css: top 80px) moves below the bar while it is shown */
body.space-bar-open #space-indicator { top: 111px; }`;

    /** What the bar shows for a report of the main process. */
    function view(state, labelOf) {
        const space = state && typeof state.space === 'string' ? state.space : '';
        const shown = Boolean(space && state.verlassen);
        return {
            shown,
            space,
            back: shown && Boolean(state.zurueck),
            home: shown,
            name: shown ? labelOf(space) : '',
        };
    }

    function create(doc, bridge, labelOf) {
        const style = doc.createElement('style');
        style.textContent = STYLE;
        doc.head.appendChild(style);
        const bar = doc.createElement('div');
        bar.id = 'space-bar';
        bar.hidden = true;
        bar.setAttribute('role', 'toolbar');
        const back = doc.createElement('button');
        back.type = 'button';
        back.textContent = '← Zurück';
        const home = doc.createElement('button');
        home.type = 'button';
        home.textContent = '⌂ Start';
        const name = doc.createElement('span');
        name.className = 'space-bar-name';
        bar.append(back, home, name);
        doc.body.appendChild(bar);

        let current = '';
        back.addEventListener('click', () => { if (current) bridge.externalSpaceBack(current); });
        home.addEventListener('click', () => { if (current) bridge.externalSpaceHome(current); });

        function render(state) {
            const v = view(state, labelOf);
            current = v.space;
            bar.hidden = !v.shown;
            if (doc.body.classList) doc.body.classList.toggle('space-bar-open', v.shown);
            back.hidden = !v.back;
            home.hidden = !v.home;
            const label = v.name || 'Bereich';
            back.title = 'Eine Seite zurück';
            back.setAttribute('aria-label', 'Eine Seite zurück in ' + label);
            home.title = 'Zur Startseite von ' + label;
            home.setAttribute('aria-label', 'Zur Startseite von ' + label);
            bar.setAttribute('aria-label', 'Navigation in ' + label);
            name.textContent = v.name;
        }
        return { bar, back, home, render };
    }

    function install() {
        const bridge = root.vibemind;
        if (!bridge || !bridge.onExternalSpaceNav) return null;
        const labelOf = (id) => {
            const tab = root.document.getElementById('tab-' + id);
            const label = tab && tab.querySelector('.space-name');
            return label ? label.textContent : id;
        };
        const made = create(root.document, bridge, labelOf);
        bridge.onExternalSpaceNav(made.render);
        return made;
    }

    const api = { view, create, install };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        root.VibeSpaceBar = api;
        if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', install);
        else install();
    }
})(typeof window !== 'undefined' ? window : globalThis);
