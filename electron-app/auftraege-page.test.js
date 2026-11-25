// The page "Auftraege" (auftraege/index.html) stays loaded between showings. Lauf 10: "Zeig meine
// Auftraege" jumped there, the answer stood in the chat, the page did not show it. It reads again when shown.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { summarize } = require('./orders-data');

const html = fs.readFileSync(path.join(__dirname, 'auftraege', 'index.html'), 'utf8');
const script = /<script>([\s\S]*?)<\/script>/.exec(html)[1];

function element(tag) {
    const el = { tag, children: [], textContent: '', disabled: false, className: '', listeners: {}, dataset: {}, parent: null,
        append(...c) { for (const x of c) { if (x && typeof x === 'object') x.parent = el; } el.children.push(...c); },
        replaceChildren(...c) { el.children = []; el.append(...c); },
        replaceWith(other) { const list = el.parent.children; list[list.indexOf(el)] = other; other.parent = el.parent; },
        remove() { if (el.parent) el.parent.children = el.parent.children.filter((x) => x !== el); },
        contains(x) { return el.children.includes(x); },
        querySelector(selector) { const id = /data-id="([^"]+)"/.exec(selector); return el.children.find((x) => x.dataset && x.dataset.id === (id && id[1])) || null; },
        focus() {},
        addEventListener(type, fn) { el.listeners[type] = fn; } };
    return el;
}

/** The page in a stand-in document; the read answers as the brain does (orders-data.summarize). */
function page(views, pmViews = []) {
    const byId = { bereiche: element(), stand: element(), neu: element() };
    const listeners = {};
    const reads = [];
    const pmReads = [];
    const timers = [];
    const document = {
        visibilityState: 'visible',
        getElementById: (id) => byId[id],
        createElement: (tag) => element(tag),
        createTextNode: (text) => ({ textContent: text }),
        addEventListener(type, fn) { listeners[type] = fn; },
    };
    const window = { auftraege: {
        lesen: (teil) => (teil === 'pm'
            ? new Promise((resolve) => pmReads.push(() => resolve(pmViews.shift())))
            : new Promise((resolve) => reads.push(() => resolve(views.shift())))),
        pmChatStand: async () => ({ aktiv: false, text: 'Chat nicht eingerichtet.' }),
        pmChatSenden: async () => ({ ok: false, text: 'nicht' }),
    } };
    vm.runInNewContext(script, { document, window, Date, setInterval: (fn, ms) => timers.push({ fn, ms }) });
    const titles = () => byId.bereiche.children.flatMap((s) => s.children.filter((c) => c.tag === 'ul')
        .flatMap((ul) => ul.children.map((li) => li.textContent)));
    return {
        reads, pmReads, timers, titles, stand: byId.stand, bereiche: byId.bereiche,
        show() { document.visibilityState = 'visible'; listeners.visibilitychange(); },
        hide() { document.visibilityState = 'hidden'; listeners.visibilitychange(); },
    };
}

const flush = () => new Promise((resolve) => setImmediate(resolve));
const empty = summarize({ schedule: { executed: { s1: { ok: true, result: { tasks: [] } } } }, research: { ok: true, components: {} }, minibook: { online: false } });
const one = summarize({ schedule: { executed: { s1: { ok: true, result: { tasks: [{ title: 'Termin A', next_run: 'morgen 9:00' }] } } } },
    research: { ok: true, components: {} }, minibook: { online: false } });

test('shown again, the page reads again and shows the new list', async () => {
    const p = page([empty, one]);
    assert.equal(p.reads.length, 1, 'the first read on load');
    p.reads[0](); await flush();
    assert.deepEqual(p.titles(), []);
    p.hide();
    assert.equal(p.reads.length, 1, 'hidden: no read');
    p.show();
    assert.equal(p.reads.length, 2, 'shown: read again');
    p.reads[1](); await flush();
    assert.deepEqual(p.titles(), ['Termin A']);
    assert.match(p.stand.textContent, /^Stand: /);
});

test('one read at a time: shown while the first read runs does not start a second', async () => {
    const p = page([empty, one]);
    p.show();
    assert.equal(p.reads.length, 1);
    p.reads[0](); await flush();
    p.show();
    assert.equal(p.reads.length, 2);
});

const pmCard = (text, items = []) => ({ id: 'pm', title: 'Projektmanager', state: 'ok', text, items: [], groups: [{ title: 'Projekte', items }] });

test('the project manager stands on top; every minute only its card is read again', async () => {
    const first = { sections: [pmCard('1 aktives Projekt.', [{ title: 'gartenhaus', detail: 'Phase aufnahme' }]), ...one.sections] };
    const p = page([first], [{ sections: [pmCard('2 aktive Projekte.')] }]);
    p.reads[0](); await flush();
    assert.equal(p.bereiche.children[0].dataset.id, 'pm');
    assert.equal(p.bereiche.children[0].children[1].textContent, '1 aktives Projekt.');
    assert.deepEqual(p.timers.map((t) => t.ms), [60000]);

    p.timers[0].fn();
    assert.equal(p.reads.length, 1, 'the brain is not asked every minute');
    assert.equal(p.pmReads.length, 1);
    p.pmReads[0](); await flush();
    assert.equal(p.bereiche.children[0].children[1].textContent, '2 aktive Projekte.');
    assert.equal(p.bereiche.children.length, 4, 'the other cards stay');
    assert.deepEqual(p.titles(), ['Termin A']);
});
