/**
 * Start view of the console: "Sag zum Beispiel: …" with a few sentences per space, until the first
 * sentence stands in the list (game-console.css hides it then).
 *
 * Only sentences the brain really answers (measured run 7, 2026-11-23). A space without a sentence
 * of its own shows the ones that work from every tab. None of them leads to the Desktop space: that
 * stays no navigation target. A sentence ending in "…" is a start: the click puts it into the field
 * and the person writes the rest; every click only fills the field, the person sends.
 *
 * Later the "?" button at the input shows the sentences again, at the end of the list (Lauf 9: the
 * list was never empty, so they could not be seen); a click on a sentence or on "?" hides them.
 *
 * The Brain names its own sentences per space (GET /api/beispielsaetze, read by the main process,
 * window.vibemind.examples). They replace the built-in ones of that space; an empty list or a Brain
 * that does not answer leaves the built-in ones.
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
        // the sentence answers from the Dashboard too; its result lies in Aufträge, the app goes there
        clawport: ['Welche geplanten Aufgaben gibt es?'],
    };
    // In an open bubble (its own chat): sentences measured there (Lauf 10), none that starts an order
    // of a model (those cost the budget of the Brain).
    const BUBBLE = ['Wie viele Karten hat diese Bubble?', 'Halte fest: …'];
    const MAX = 3;
    const BRAIN_MAX = 5;
    const SHOWN = 'gc-start-shown';

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

    /** The sentences of the Brain for a space, as the main process gives them; [] on any trouble. */
    function brainExamples(win, space) {
        const api = win && win.vibemind;
        if (!api || typeof api.examples !== 'function') return Promise.resolve([]);
        return Promise.resolve()
            .then(() => api.examples(space))
            .then((list) => (Array.isArray(list) ? list.filter((x) => typeof x === 'string' && x.trim()).slice(0, BRAIN_MAX) : []))
            .catch(() => []);
    }

    function render(doc, box, sentences) {
        box.replaceChildren();
        const label = doc.createElement('span');
        label.className = 'gc-start-label';
        label.textContent = 'Sag zum Beispiel:';
        box.appendChild(label);
        for (const sentence of sentences) {
            const button = doc.createElement('button');
            button.type = 'button';
            button.className = 'gc-start-example';
            button.textContent = '„' + sentence + '“';
            button.addEventListener('click', () => {
                const input = doc.getElementById('gc-input');
                if (!input) return;
                input.value = fieldText(sentence);
                input.focus();
                show(doc, box, false);
            });
            box.appendChild(button);
        }
    }

    /** The sentences asked for by "?": on or off, at the end of the list where the person reads. */
    function show(doc, box, on) {
        box.classList.toggle(SHOWN, on);
        const help = doc.getElementById('gc-help-btn');
        if (help) help.setAttribute('aria-expanded', on ? 'true' : 'false');
        const messages = box.parentNode;
        if (!on || !messages) return;
        messages.appendChild(box);
        messages.scrollTop = messages.scrollHeight;
    }

    function mount(win, doc) {
        const start = () => {
            const messages = doc.getElementById('gc-messages');
            if (!messages) return;
            const box = doc.createElement('div');
            box.className = 'gc-start';
            messages.insertBefore(box, messages.firstChild);
            const app = win.multiverseApp;
            // The built-in sentences at once; those of the Brain when it names some for the space
            // the console still stands in. "?" asks again while the built-in ones stand.
            let space = null;
            let fromBrain = false;
            const paint = (next) => {
                space = next;
                fromBrain = false;
                render(doc, box, examplesFor(next));
                ask();
            };
            const ask = () => {
                const asked = space;
                brainExamples(win, asked).then((list) => {
                    if (asked !== space || !list.length) return;
                    fromBrain = true;
                    render(doc, box, list);
                });
            };
            paint(app && app.currentSpace ? app.currentSpace : 'ideas');
            const send = doc.getElementById('gc-send-btn');
            if (send && send.parentNode) {
                const help = doc.createElement('button');
                help.type = 'button';
                help.id = 'gc-help-btn';
                help.className = 'gc-help-btn';
                help.textContent = '?';
                help.title = 'Beispielsätze zeigen';
                help.setAttribute('aria-expanded', 'false');
                help.addEventListener('click', () => {
                    const on = !box.classList.contains(SHOWN);
                    if (on && !fromBrain) ask();
                    show(doc, box, on);
                });
                send.parentNode.insertBefore(help, send);
            }
            // A bubble chat built before this script (another order of the scripts): its "?" now.
            const chatInput = doc.getElementById('ideas-chat-input');
            if (chatInput && chatInput.parentNode) {
                const row = chatInput.parentNode;
                attachChat(doc, { row, input: chatInput, send: row.querySelector ? row.querySelector('.ideas-chat-send') : null,
                    log: doc.getElementById('ideas-chat-log') });
            }
            win.addEventListener('vibemind:space-arrived', (event) => {
                paint(event && event.detail ? event.detail.space : 'ideas');
            });
        };
        if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', start);
        else start();
    }

    /**
     * The "?" of the chat in an open bubble (ideas-chat.js): before its send button, the sentences
     * at the end of its log; a click fills its field, the person sends. Lauf 11: the bubble chat had none.
     */
    function attachChat(doc, { row, input, send, log }) {
        if (!row || !input || !send || !log) return null;
        if (doc.getElementById && doc.getElementById('ideas-chat-help')) return null;   // there already
        const box = doc.createElement('div');
        box.className = 'gc-start ideas-chat-start';
        const help = doc.createElement('button');
        help.type = 'button';
        help.id = 'ideas-chat-help';
        help.className = 'gc-help-btn ideas-chat-help';
        help.textContent = '?';
        help.title = 'Beispielsätze zeigen';
        help.setAttribute('aria-expanded', 'false');
        const toggle = (on) => {
            box.classList.toggle(SHOWN, on);
            help.setAttribute('aria-expanded', on ? 'true' : 'false');
            if (!on) return;
            log.appendChild(box);          // at the end, where the person reads
            log.scrollTop = log.scrollHeight;
        };
        const label = doc.createElement('span');
        label.className = 'gc-start-label';
        label.textContent = 'Sag zum Beispiel:';
        box.appendChild(label);
        for (const sentence of BUBBLE) {
            const button = doc.createElement('button');
            button.type = 'button';
            button.className = 'gc-start-example';
            button.textContent = '„' + sentence + '“';
            button.addEventListener('click', () => {
                input.value = fieldText(sentence);
                input.focus();
                toggle(false);
            });
            box.appendChild(button);
        }
        help.addEventListener('click', () => toggle(!box.classList.contains(SHOWN)));
        row.insertBefore(help, send);
        return { help, box };
    }

    return { examplesFor, fieldText, mount, attachChat, brainExamples, EVERYWHERE, OWN, BUBBLE, BRAIN_MAX };
});
