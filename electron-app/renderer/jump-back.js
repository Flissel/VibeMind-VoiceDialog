/**
 * The way back after a jump a sentence asked for. Lauf 26: a sentence in the console took the app
 * to Desktop, Project Space, Rowboat or Aufträge; there was no way back but the tab of Ideas, which
 * at 1400 px had scrolled out of the tab strip. Now the title bar says "← zurück zu Ideen" (the space
 * the jump started in) until the person goes back or goes anywhere else.
 *
 * It sits in the title bar next to the status line, not in the bar below the tabs (#space-bar): the
 * pages of Rowboat, Project Space and the external spaces lie over everything below the tabs, the
 * title bar stays free above them.
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root && root.document) {
        root.VibeJumpBack = api.install(root, root.document);
    }
})(typeof window !== 'undefined' ? window : null, function () {
    'use strict';

    /** How the way back names a space: Ideas is "Ideen" (the word the person reads), else its tab. */
    const NAMES = Object.freeze({ ideas: 'Ideen' });

    /**
     * The offer after a switch: { from, to } when a jump of a sentence left `from`; null otherwise
     * (a switch by hand, a jump to where it already was, no space to come from).
     */
    function offerOf(from, to) {
        if (!from || !to || from === to) return null;
        return { from, to };
    }

    function nameOf(doc, space) {
        if (NAMES[space]) return NAMES[space];
        const tab = doc.getElementById('tab-' + space);
        const label = tab && tab.querySelector ? tab.querySelector('.space-name') : null;
        return label && label.textContent ? label.textContent.trim() : space;
    }

    function install(win, doc) {
        let offer = null;
        let el = null;

        function element() {
            if (el) return el;
            const anchor = doc.getElementById('titlebar-space');
            if (!anchor || !anchor.parentNode) return null;
            el = doc.createElement('button');
            el.id = 'jump-back';
            el.type = 'button';
            el.className = 'jump-back';
            el.hidden = true;
            anchor.parentNode.insertBefore(el, anchor.nextSibling);
            el.addEventListener('click', () => {
                const target = offer && offer.from;
                hide();
                if (!target) return;
                if (win.spaceNavigator && win.spaceNavigator.switchSpace) win.spaceNavigator.switchSpace(target, { quelle: 'rueckweg' });
                else if (win.multiverseApp) win.multiverseApp.navigateToSpace(target, { quelle: 'rueckweg' });
            });
            return el;
        }

        function hide() {
            offer = null;
            if (el) el.hidden = true;
        }

        function show() {
            const button = element();
            if (!button || !offer) return;
            const name = nameOf(doc, offer.from);
            button.textContent = '← zurück zu ' + name;
            button.title = 'Zurück zu ' + name + ', wo der Satz geschrieben wurde';
            button.setAttribute('aria-label', 'Zurück zu ' + name);
            button.hidden = false;
        }

        /** A switch of space started: `from` is set when a sentence asked for it, '' when not. */
        function jumped(from, to) {
            offer = offerOf(from, to);
            if (offer) show();
            else hide();
        }

        // Anywhere else than the target of the jump (a tab, the arrow keys, a click in the scene):
        // the way back has done its part.
        if (typeof win.addEventListener === 'function') {
            win.addEventListener('vibemind:space-arrived', (event) => {
                const space = event && event.detail ? event.detail.space : '';
                if (offer && space && space !== offer.to) hide();
            });
        }

        return { jumped, hide, offer: () => offer, element };
    }

    return { offerOf, install, NAMES };
});
