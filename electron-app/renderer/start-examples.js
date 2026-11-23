/**
 * Start view of the console: "Sag zum Beispiel: …" with a few sentences per space, until the first
 * sentence stands in the list (game-console.css hides it then).
 *
 * Only sentences the brain really answers (measured run 7, 2026-11-23). A space without a sentence
 * of its own shows the ones that work from every tab. None of them leads to the Desktop space: that
 * stays no navigation target. A sentence ending in "…" is a start: the click puts it into the field
 * and the person writes the rest; every click only fills the field, the person sends.
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.VibeStartExamples = api;
    if (typeof document !== 'undefined' && typeof window !== 'undefined' && !(typeof module === 'object' && module.exports)) {
        api.mount(window, document);
    }
})(typeof self !== 'undefined' ? self : this, function () {
    const EVERYWHERE = ['Woran denkt das Gehirn gerade?', 'Welche Bubbles gibt es?'];
    const OWN = {
        ideas: ['Welche Bubbles gibt es?', 'Halte fest: … in der Bubble …'],
        thebrain: ['Woran denkt das Gehirn gerade?'],
        orders: ['Welche geplanten Aufgaben gibt es?'],
        // since Lauf 8 the sentence stays in the Dashboard (before, it jumped to Aufträge)
        clawport: ['Welche geplanten Aufgaben gibt es?'],
    };
    const MAX = 3;

    /** The sentences for a space: its own first, then those from every tab, without repeats. */
    function examplesFor(space) {
        const list = [];
        for (const sentence of (OWN[space] || []).concat(EVERYWHERE)) {
            if (!list.includes(sentence)) list.push(sentence);
        }
        return list.slice(0, MAX);
    }

    /** What a click puts into the field: a start ("… in der Bubble …") only up to its first gap. */
    function fieldText(sentence) {
        const gap = sentence.indexOf('…');
        return gap < 0 ? sentence : sentence.slice(0, gap);
    }

    function render(doc, box, space) {
        box.replaceChildren();
        const label = doc.createElement('span');
        label.className = 'gc-start-label';
        label.textContent = 'Sag zum Beispiel:';
        box.appendChild(label);
        for (const sentence of examplesFor(space)) {
            const button = doc.createElement('button');
            button.type = 'button';
            button.className = 'gc-start-example';
            button.textContent = '„' + sentence + '“';
            button.addEventListener('click', () => {
                const input = doc.getElementById('gc-input');
                if (!input) return;
                input.value = fieldText(sentence);
                input.focus();
            });
            box.appendChild(button);
        }
    }

    function mount(win, doc) {
        const start = () => {
            const messages = doc.getElementById('gc-messages');
            if (!messages) return;
            const box = doc.createElement('div');
            box.className = 'gc-start';
            messages.insertBefore(box, messages.firstChild);
            const app = win.multiverseApp;
            render(doc, box, app && app.currentSpace ? app.currentSpace : 'ideas');
            win.addEventListener('vibemind:space-arrived', (event) => {
                render(doc, box, event && event.detail ? event.detail.space : 'ideas');
            });
        };
        if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', start);
        else start();
    }

    return { examplesFor, fieldText, mount, EVERYWHERE, OWN };
});
