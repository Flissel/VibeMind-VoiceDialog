// The Software Design tab shows the wizard of a promoted project (shuttle-wizard.js in the shuttle
// panel), not the stage view on 8162. Invented ids and words only.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const PROJEKT = 'p1a2b3c4';
const SHUTTLE = 'shuttle-projekt-p1a2b3c4';
const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');

function element(tag, id, placed) {
    const classes = new Set();
    const el = {
        tag, id: id || '', children: [], hidden: false, disabled: false, title: '', value: '', style: {}, dataset: {},
        _text: '',
        get textContent() { return el._text + el.children.map((c) => c.textContent).join(' '); },
        set textContent(v) { el._text = String(v); el.children = []; },
        get className() { return [...classes].join(' '); },
        set className(v) { classes.clear(); String(v).split(/\s+/).filter(Boolean).forEach((c) => classes.add(c)); },
        classList: {
            add: (...c) => c.forEach((x) => classes.add(x)), remove: (...c) => c.forEach((x) => classes.delete(x)),
            contains: (c) => classes.has(c), toggle: (c, on) => { if (on === undefined ? !classes.has(c) : on) classes.add(c); else classes.delete(c); },
        },
        appendChild(c) { el.children.push(c); if (placed) placed(c); return c; },
        insertBefore(c) { el.children.unshift(c); if (placed) placed(c); return c; },
        get firstChild() { return el.children[0] || null; },
        _on: {},
        addEventListener(type, fn) { (el._on[type] = el._on[type] || []).push(fn); },
        click() { (el._on.click || []).forEach((fn) => fn({})); },
        querySelector: () => null, querySelectorAll: () => [],
    };
    return el;
}

/** The page as the wizard and the tab see it: every id answers, the messages to Python are kept. */
function page() {
    const byId = new Map();
    // the lines the scripts make themselves are found only once they stand on the page
    const MADE = new Set(['wizard-sinnpruefung', 'swe-wizard-leer', 'wizard-white-paper']);
    const placed = (c) => { if (c.id && !byId.has(c.id)) byId.set(c.id, c); };
    const get = (id) => { if (!byId.has(id)) { if (MADE.has(id)) return null; byId.set(id, element('div', id, placed)); } return byId.get(id); };
    const listeners = {};
    const sent = [];
    const store = new Map();
    const window = {
        document: { getElementById: get, createElement: (tag) => element(tag, '', placed), querySelectorAll: () => [] },
        localStorage: { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)) },
        vibemind: { sendToPython: (m) => sent.push(JSON.parse(JSON.stringify(m))) },   // as over IPC
        addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
        dispatchEvent(e) { for (const fn of listeners[e.type] || []) fn(e); return true; },
        console: { log() {} },
    };
    const context = { window, document: window.document, console: window.console, globalThis: window, module: undefined };
    vm.runInNewContext(read('renderer', 'shuttle-wizard.js'), context);
    vm.runInNewContext(read('renderer', 'swe-wizard-tab.js'), context);
    const fromPython = (detail) => window.dispatchEvent({ type: 'message-from-python', detail });
    return { window, get, sent, store, fromPython };
}

const VERDICT_OK = { bestanden: true, text: 'Sinncheck bestanden · 12 Karten · White Paper deckt 83 %', gruende: [], gruende_text: '', pruefsumme: 'stimmt' };
const VERDICT_NO = { bestanden: false, text: 'Sinncheck nicht bestanden · 5 Karten · White Paper deckt 40 %', gruende: ['leer'], gruende_text: 'leere Karten: 2, lose Karten: 1', pruefsumme: 'falsch' };

test('a promoted project: the wizard asks for it by its id, the agent teams stay off', () => {
    const p = page();
    p.window.shuttleWizard.initWizard({ projektId: PROJEKT });
    assert.deepEqual(p.sent, [{ type: 'wizard_init_from_project', projekt_id: PROJEKT, shuttle_id: null }]);
    for (const id of ['wizard-generate-context', 'wizard-generate-stakeholders', 'wizard-run-gap-analysis', 'wizard-extract-constraints']) {
        assert.equal(p.get(id).disabled, true, id);
        assert.match(p.get(id).title, /Modellzugang/);
    }
    // a shuttle of a bubble works as before: its message, the agents on
    p.sent.length = 0;
    p.window.shuttleWizard.initWizard({ id: 'shuttle-7', bubbleId: 'b-7' });
    assert.deepEqual(p.sent, [{ type: 'wizard_init_from_bubble', shuttle_id: 'shuttle-7', bubble_id: 'b-7' }]);
    assert.equal(p.get('wizard-generate-context').disabled, false);
});

test('the answer: its shuttle, name and description filled, the verdict above the project panel, then the stand', () => {
    const p = page();
    p.window.shuttleWizard.initWizard({ projektId: PROJEKT });
    p.sent.length = 0;
    p.fromPython({ type: 'wizard_initialized', quelle: 'projekt', success: true, shuttle_id: SHUTTLE, projekt_id: PROJEKT,
        project: { name: 'Ladeplaner', description: 'Plant das Laden', domain: '', target_users: '' }, requirements_count: 12, kopfzeile: VERDICT_OK });
    assert.equal(p.get('wizard-project-name').value, 'Ladeplaner');
    assert.equal(p.get('wizard-project-desc').value, 'Plant das Laden');
    const line = p.get('checkpoint-mining').children.find((c) => c.id === 'wizard-sinnpruefung');
    assert.ok(line, 'the line stands in the project panel');
    assert.equal(line.hidden, false);
    assert.equal(line.className, 'wizard-sinnpruefung', 'green');
    assert.match(line.textContent, /Sinncheck bestanden · 12 Karten · White Paper deckt 83 %/);
    assert.deepEqual(p.sent, [{ type: 'wizard_get_state', shuttle_id: SHUTTLE }]);
});

test('not passed: yellow with its reasons, it does not block; a changed stand is said in red', () => {
    const p = page();
    p.window.shuttleWizard.initWizard({ projektId: PROJEKT });
    p.fromPython({ type: 'wizard_initialized', quelle: 'projekt', success: true, shuttle_id: SHUTTLE, projekt_id: PROJEKT,
        project: { name: 'Ladeplaner' }, kopfzeile: VERDICT_NO });
    const shown = p.get('checkpoint-mining').children.find((c) => c.id === 'wizard-sinnpruefung');
    assert.equal(shown.className, 'wizard-sinnpruefung nicht-bestanden');
    assert.match(shown.textContent, /leere Karten: 2, lose Karten: 1/);
    assert.match(shown.textContent, /Der Stand wurde nach dem Befördern verändert\./);
    assert.ok(p.sent.some((m) => m.type === 'wizard_get_state'), 'the wizard opens anyway');
    assert.equal(p.get('wizard-sinnpruefung'), shown, 'one line, found by its id');
});

test('a project that cannot be opened: a calm sentence, no stand asked; an older answer is left alone', () => {
    const p = page();
    p.window.shuttleWizard.initWizard({ projektId: PROJEKT });
    p.sent.length = 0;
    p.fromPython({ type: 'wizard_initialized', quelle: 'projekt', success: false, error: 'kein_stand', projekt_id: PROJEKT });
    const line = p.get('checkpoint-mining').children.find((c) => c.id === 'wizard-sinnpruefung');
    assert.equal(line.textContent, 'Dieses Projekt wurde ohne festen Stand befördert.');
    assert.deepEqual(p.sent, []);
    p.fromPython({ type: 'wizard_initialized', quelle: 'projekt', success: true, shuttle_id: 'shuttle-alt', projekt_id: 'p-alt', project: { name: 'Alt' } });
    assert.deepEqual(p.sent, [], 'an answer for another project');
    assert.notEqual(p.get('wizard-project-name').value, 'Alt');
});

const REQS = [
    { id: 'REQ-001', title: 'Laden planen', description: 'x', priority: 'medium', status: 'pending', category: 'Laden', source_card_id: 'a' },
    { id: 'REQ-002', title: 'Ohne Gruppe', description: '', priority: 'medium', status: 'pending', category: null, source_card_id: 'b' },
    { id: 'REQ-003', title: 'Tarif', description: '', priority: 'medium', status: 'gestrichen', category: 'Laden', source_card_id: 'c' },
];

function opened(context) {
    const p = page();
    p.window.shuttleWizard.initWizard({ projektId: PROJEKT });
    p.fromPython({ type: 'wizard_initialized', quelle: 'projekt', success: true, shuttle_id: SHUTTLE, projekt_id: PROJEKT, project: {}, kopfzeile: VERDICT_OK });
    p.fromPython({ type: 'wizard_state', shuttle_id: SHUTTLE, current_step: 'mining', project: {},
        context: Object.assign({ sinnpruefung: VERDICT_OK }, context || {}), requirements: JSON.parse(JSON.stringify(REQS)) });
    p.sent.length = 0;
    return p;
}

test('the stand of a promoted project: cards are requirements, grouped by their card group, struck ones greyed out', () => {
    const p = opened();
    const grid = p.get('wizard-requirements-grid');
    const parts = grid.children.map((c) => (c.className === 'req-group-head' ? '# ' + c.textContent : c.children[0].children[0].textContent));
    assert.deepEqual(parts, ['# Laden', 'REQ-001', 'REQ-003', '# Ungrouped', 'REQ-002']);
    const card1 = grid.children[1];
    assert.deepEqual(card1.children[0].children.map((c) => c.textContent), ['REQ-001', 'medium', 'Strike'], 'no candidate badge');
    assert.equal(grid.children[2].className, 'req-card req-struck');
    assert.equal(grid.children[2].children[0].children[2].textContent, 'Restore');
    assert.equal(p.get('validation-count').textContent, '2 requirements · 1 struck');
});

test('strike and restore: greyed at once, saved by the space; a failed save shows the old state with a note', () => {
    const p = opened();
    const grid = p.get('wizard-requirements-grid');
    grid.children[1].children[0].children[2].click();   // Strike REQ-001
    assert.deepEqual(p.sent, [{ type: 'wizard_set_requirement_status', shuttle_id: SHUTTLE, req_id: 'REQ-001', status: 'gestrichen' }]);
    assert.equal(grid.children[1].className, 'req-card req-struck');
    assert.equal(p.get('validation-count').textContent, '1 requirements · 2 struck');

    p.fromPython({ type: 'wizard_requirement_status', success: false, error: 'speichern_fehlgeschlagen', shuttle_id: SHUTTLE, req_id: 'REQ-001' });
    assert.equal(grid.children[1].className, 'req-card');
    assert.match(grid.children[1].textContent, /Not saved, please try again\./);

    p.sent.length = 0;
    grid.children[2].children[0].children[2].click();   // Restore REQ-003
    assert.deepEqual(p.sent, [{ type: 'wizard_set_requirement_status', shuttle_id: SHUTTLE, req_id: 'REQ-003', status: 'pending' }]);
    p.fromPython({ type: 'wizard_requirement_status', success: true, shuttle_id: SHUTTLE, req_id: 'REQ-003', status: 'pending', aktiv: 3, gestrichen: 0 });
    assert.equal(p.get('validation-count').textContent, '3 requirements');
});

test('the white paper: readable in full and collapsible in step Project, as text', () => {
    const p = opened({ white_paper: { node_id: 'w1', titel: 'Ladeplaner', text: '# Ziel\n<b>nicht fett</b>' } });
    const box = p.get('wizard-form-mining').children.find((c) => c.id === 'wizard-white-paper');
    assert.ok(box, 'in the project form');
    assert.equal(box.tag, 'details');
    assert.equal(box.children[0].textContent, 'White paper: Ladeplaner');
    assert.equal(box.children[1].textContent, '# Ziel\n<b>nicht fett</b>', 'text, never HTML');
    const none = opened({ white_paper: null });
    assert.equal(none.get('wizard-form-mining').children.find((c) => c.id === 'wizard-white-paper'), undefined);
});

test('the tab: the wanted project opens below the title bar, once; leaving hides it; without a project a calm line', () => {
    const p = page();
    const tab = p.window.VibeSweWizard;
    const view = p.get('shuttle-interior-view');
    view.classList.add('hidden');
    assert.equal(tab.show(), true);
    assert.equal(view.classList.contains('im-reiter'), true);
    assert.equal(view.classList.contains('hidden'), false);
    assert.equal(view.classList.contains('ohne-projekt'), true);
    assert.equal(p.get('swe-wizard-leer').textContent, tab.NO_PROJECT);
    assert.deepEqual(p.sent, [], 'nothing asked without a project');

    tab.open(PROJEKT);
    assert.deepEqual(p.sent, [{ type: 'wizard_init_from_project', projekt_id: PROJEKT, shuttle_id: null }]);
    assert.equal(view.classList.contains('ohne-projekt'), false);
    assert.equal(p.get('swe-wizard-leer').hidden, true);
    tab.show();
    tab.open(PROJEKT);
    assert.equal(p.sent.length, 1, 'the same project is not started anew');

    tab.hide();
    assert.equal(view.classList.contains('hidden'), true);
    assert.equal(view.classList.contains('im-reiter'), false);
    assert.equal(p.store.get('vibemind.swe-projekt'), PROJEKT, 'remembered for the next opening');
    assert.equal(tab.open('../x y'), false, 'plain ids only');
});

test('a ziel naming a project: the app goes to Software Design and opens that project\'s wizard', () => {
    const RT = require('./renderer/result-target');
    assert.equal(RT.zielOf({ space: 'swedesign', projekt_id: PROJEKT }).projekt_id, PROJEKT);
    assert.equal('projekt_id' in RT.zielOf({ space: 'swedesign', projekt_id: '../x' }), false);
    assert.equal('projekt_id' in RT.zielOf({ space: 'ideas' }), false);

    let now = 0;
    let timers = [];
    const calls = [];
    const app = { currentSpace: 'ideas', isNavigating: false, isInsideBubble: false, spaces: { ideas: {}, swedesign: { name: 'SWE Design' } } };
    const win = {
        multiverseApp: app,
        spaceNavigator: { switchSpace: (s, how) => { calls.push('switch ' + s + ' ' + JSON.stringify(how)); } },
        VibeSweWizard: { want: (id) => calls.push('want ' + id), open: (id) => calls.push('open ' + id) },
        setTimeout(fn, ms) { const t = { fn, at: now + ms }; timers.push(t); return t; },
        clearTimeout(t) { timers = timers.filter((x) => x !== t); },
    };
    const follower = RT.create(win, { querySelector: () => null });
    assert.equal(follower.follow({ space: 'swedesign', projekt_id: PROJEKT }, { quick: true, back: true }), true);
    assert.deepEqual(calls, ['want ' + PROJEKT, 'switch swedesign {"quick":true,"back":true,"quelle":"ziel"}'], 'the project first, then the short flight with the way back');
    app.currentSpace = 'swedesign';
    now += RT.STEP_MS;
    for (const t of timers.filter((x) => x.at <= now)) { timers = timers.filter((x) => x !== t); t.fn(); }
    assert.deepEqual(calls.slice(-1), ['open ' + PROJEKT]);
    assert.equal(follower.pending(), null);
});

test('the main process keeps projekt_id in a ziel, plain only', () => {
    const { zielOf } = require('./task-navigation');
    assert.deepEqual(zielOf({ space: 'swedesign', projekt_id: PROJEKT }), { space: 'swedesign', bubble_id: null, node_id: null, projekt_id: PROJEKT });
    assert.deepEqual(zielOf({ space: 'swedesign', projekt_id: 'a b' }), { space: 'swedesign', bubble_id: null, node_id: null });
    assert.equal(zielOf({ space: 'Swe!', projekt_id: PROJEKT }), null);
});

test('the tab shows the wizard, not the stage view; the page loads the tab after the wizard; Python answers the message', () => {
    const scene = read('renderer', 'multiverse.js');
    assert.match(scene, /if \(targetSpace === 'swedesign'\) \{\s*if \(window\.VibeSweWizard\) window\.VibeSweWizard\.show\(\);/);
    assert.match(scene, /targetSpace !== 'swedesign'\) \{\s*if \(window\.VibeSweWizard\) window\.VibeSweWizard\.hide\(\);/);
    assert.doesNotMatch(scene, /showSweDesign/);
    const html = read('renderer', 'index.html');
    assert.ok(html.indexOf('src="swe-wizard-tab.js"') > html.indexOf('src="shuttle-wizard.js"'));
    const css = read('renderer', 'styles', 'shuttle.css');
    assert.match(css, /#shuttle-interior-view\.im-reiter \{\s*top: 75px;/);
    const backend = fs.readFileSync(path.join(__dirname, '..', 'python', 'electron_backend.py'), 'utf8');
    assert.match(backend, /elif msg_type == "wizard_init_from_project":/);
    assert.match(backend, /handler\.init_from_project\(shuttle_id, projekt_id\)/);
    assert.match(backend, /"type": "wizard_initialized", "quelle": "projekt", \*\*result/);
    assert.match(backend, /elif msg_type == "wizard_set_requirement_status":/);
    assert.match(backend, /handler\.set_requirement_status\(shuttle_id, req_id, status\)/);
    assert.match(backend, /"type": "wizard_requirement_status", \*\*result/);
});
