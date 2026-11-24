/**
 * The Software Design tab shows the wizard of a promoted project: the shuttle wizard
 * (shuttle-wizard.js, panels in #shuttle-interior-view), not the stage view of the space (8162).
 *
 * The view sits below the title bar and the tabs (as the BrowserViews do), so the space tabs and
 * "← zurück zu Ideen" stay usable. The project comes from the ziel of the Brain after promoting
 * ({space: 'swedesign', projekt_id}, see result-target.js); the last one is remembered for the
 * next opening of the tab. Without a project the tab says so calmly.
 *
 * API (window.VibeSweWizard): show(), hide(), open(projektId), want(projektId), current().
 */
(function (root) {
    'use strict';

    const PLAIN_ID = /^[A-Za-z0-9-]{1,64}$/;
    const KEY = 'vibemind.swe-projekt';
    const NO_PROJECT = 'Noch kein Projekt hier. Befördere eine Bubble in Ideen, dann öffnet sich hier ihr Wizard.';

    let wanted = null;    // the project the tab should show
    let shown = null;     // the project the wizard was started for
    let isOpen = false;

    const doc = () => root.document;
    const view = () => doc().getElementById('shuttle-interior-view');

    function remembered() {
        try {
            const id = root.localStorage.getItem(KEY);
            return id && PLAIN_ID.test(id) ? id : null;
        } catch (_) { return null; }
    }

    /** The project the tab shows from now on (the wizard starts for it when the tab is open). */
    function want(projektId) {
        const id = typeof projektId === 'number' && Number.isInteger(projektId) ? String(projektId) : projektId;
        if (typeof id !== 'string' || !PLAIN_ID.test(id)) return false;
        wanted = id;
        try { root.localStorage.setItem(KEY, id); } catch (_) { /* not kept: the tab shows it until the next start */ }
        return true;
    }

    /** The calm line of a tab without a project; gone as soon as there is one. */
    function note(on) {
        const host = view();
        if (!host) return;
        let line = doc().getElementById('swe-wizard-leer');
        if (!line && on) {
            line = doc().createElement('div');
            line.id = 'swe-wizard-leer';
            line.className = 'swe-wizard-leer';
            line.textContent = NO_PROJECT;
            host.insertBefore(line, host.firstChild);
        }
        if (line) line.hidden = !on;
        host.classList.toggle('ohne-projekt', !!on);
    }

    /** Open the tab: the wizard of the wanted (or last) project, below the title bar. */
    function show() {
        const host = view();
        if (!host) return false;
        const projekt = wanted || remembered();
        host.classList.add('im-reiter');
        host.classList.remove('hidden');
        isOpen = true;
        note(!projekt);
        const title = doc().getElementById('shuttle-interior-name');
        if (title) title.textContent = 'Software Design';
        if (projekt && projekt !== shown && root.shuttleWizard && root.shuttleWizard.initWizard) {
            shown = projekt;
            root.shuttleWizard.initWizard({ projektId: projekt });
        }
        return true;
    }

    /** The wizard of this project; opens the tab's view when the tab is open. */
    function open(projektId) {
        if (!want(projektId)) return false;
        return isOpen ? show() : true;
    }

    /** Leave the tab: the view goes, the wizard keeps its state for the next opening. */
    function hide() {
        if (!isOpen) return;
        isOpen = false;
        const host = view();
        if (!host) return;
        host.classList.remove('im-reiter', 'ohne-projekt');
        host.classList.add('hidden');
    }

    const api = { show, hide, open, want, current: () => shown, isOpen: () => isOpen, NO_PROJECT };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    root.VibeSweWizard = api;
})(typeof window !== 'undefined' ? window : globalThis);
