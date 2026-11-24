const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { ExternalSpaceManager, barState, BAR_HEIGHT } = require('./external-spaces');
const { view } = require('./renderer/space-bar');

// The Sales case from the app: signed in at the start, then through inbox and post to the
// course notes inside the same view (same origin, no new window). Invented address.
const START = 'https://sales.example.test:8445/';

function fakeElectron() {
    const made = [];
    class BrowserView {
        constructor(options) {
            this.options = options;
            this.bounds = null;
            const handlers = {};
            const history = [];
            let index = -1;
            this.webContents = {
                session: { webRequest: { onBeforeSendHeaders() {} } },
                setWindowOpenHandler() {}, isDestroyed: () => false,
                on(name, handler) { handlers[name] = handler; },
                getURL: () => (index >= 0 ? history[index] : ''),
                canGoBack: () => index > 0,
                goBack() { index -= 1; handlers['did-navigate'] && handlers['did-navigate']({}, history[index]); },
                // what the page does when a link is followed
                follow(url, inPage = false) {
                    history.splice(index + 1);
                    history.push(url);
                    index = history.length - 1;
                    const name = inPage ? 'did-navigate-in-page' : 'did-navigate';
                    if (handlers[name]) handlers[name]({}, url);
                },
            };
            made.push(this);
        }
        setBounds(bounds) { this.bounds = bounds; }
    }
    const sent = [];
    const window = {
        view: undefined,
        on() {}, isDestroyed: () => false, webContents: { send: (channel, message) => sent.push({ channel, message }) },
        setBrowserView(v) { this.view = v; },
        getContentBounds: () => ({ width: 1400, height: 900 }),
    };
    return { BrowserView, window, made, sent };
}

function manager(env = { SALES_UI_URL: START }) {
    const electron = fakeElectron();
    const loads = [];
    const m = new ExternalSpaceManager(electron.window, {
        BrowserView: electron.BrowserView, shell: { openExternal() {} }, logger: { log() {} }, env,
    });
    // loading the start address = the page arrives there (the status check passed)
    m._load = (id) => {
        loads.push(id);
        const entry = m.views.get(id);
        entry.result = { ok: true };
        entry.view.webContents.follow(m.spaces.get(id).url);
    };
    const bars = () => electron.sent.filter((s) => s.message.type === 'external_space_nav').map((s) => s.message);
    return { m, electron, loads, bars };
}

test('the bar decides on yes/no only: away from the start address, and back where history allows', () => {
    assert.deepEqual(barState(START, START, true, false), { verlassen: false, zurueck: false }, 'at the start: no bar, even with a sign-in behind it');
    assert.deepEqual(barState(START, 'https://sales.example.test:8445', true, false), { verlassen: false, zurueck: false }, 'trailing slash');
    assert.deepEqual(barState(START, START + '?tab=2#x', true, false), { verlassen: false, zurueck: false }, 'query and fragment are the same page');
    assert.deepEqual(barState(START, 'https://sales.example.test:8445/mitschriften/kurs?id=7', true, false), { verlassen: true, zurueck: true });
    assert.deepEqual(barState(START, 'https://sales.example.test:8445/mitschriften/kurs', false, false), { verlassen: true, zurueck: false });
    // Lernen: the start sends the page to another origin (the course platform itself)
    assert.deepEqual(barState('https://lernen.example.test/lernen/', 'http://kurse.example.test:13000/login', true, false), { verlassen: true, zurueck: true });
    assert.deepEqual(barState(START, 'data:text/html,karte', true, false), { verlassen: false, zurueck: false }, 'status card');
    assert.deepEqual(barState(START, START + 'x', true, true), { verlassen: false, zurueck: false }, 'a card result: no bar');
});

test('Sales: follow links to the course notes, the bar appears; back and start bring the page home', () => {
    const { m, electron, loads, bars } = manager();
    m.show('sales');
    const page = electron.made[0].webContents;
    assert.equal(bars().at(-1).verlassen, false, 'opened at the start: no bar');
    assert.equal(electron.made[0].bounds.y, 75);

    page.follow('https://sales.example.test:8445/posteingang');
    page.follow('https://sales.example.test:8445/mitschriften/kurs?id=7');
    assert.deepEqual(bars().at(-1), { type: 'external_space_nav', space: 'sales', verlassen: true, zurueck: true });
    assert.deepEqual(electron.made[0].bounds, { x: 0, y: 75 + BAR_HEIGHT, width: 1400, height: 900 - 75 - BAR_HEIGHT }, 'the page moves below the bar');
    assert.doesNotMatch(JSON.stringify(bars()), /example\.test|mitschriften|posteingang/, 'no address reaches the renderer');

    assert.equal(m.back('sales'), true);
    assert.equal(page.getURL(), 'https://sales.example.test:8445/posteingang');
    assert.equal(bars().at(-1).verlassen, true);
    assert.equal(m.back('sales'), true);
    assert.equal(bars().at(-1).verlassen, false, 'back at the start: the bar goes');
    assert.equal(electron.made[0].bounds.y, 75);

    page.follow('https://sales.example.test:8445/mitschriften/kurs');
    assert.equal(m.home('sales'), true);
    assert.deepEqual(loads, ['sales', 'sales'], 'start = the first opening again (check, sign-in)');
    assert.equal(bars().at(-1).verlassen, false);
});

test('a link inside the page (only the fragment or history.pushState) counts too', () => {
    const { m, electron, bars } = manager();
    m.show('sales');
    electron.made[0].webContents.follow('https://sales.example.test:8445/freigaben', true);
    assert.equal(bars().at(-1).verlassen, true);
});

test('only the space on screen is driven; leaving it removes the bar', () => {
    const { m, electron, bars } = manager({ SALES_UI_URL: START, EVENT_UI_URL: 'https://events.example.test/' });
    m.show('sales');
    electron.made[0].webContents.follow('https://sales.example.test:8445/post');
    m.show('events');
    assert.deepEqual(bars().at(-1), { type: 'external_space_nav', space: 'events', verlassen: false, zurueck: false });
    assert.equal(m.back('sales'), false, 'Sales is not on screen');
    assert.equal(m.home('sales'), false);
    m.hideAll();
    assert.deepEqual(bars().at(-1), { type: 'external_space_nav', space: null, verlassen: false, zurueck: false });
    assert.equal(m.back('gibt-es-nicht'), false);
});

test('the renderer shows the bar only for a page away from its start, with a title and aria-label on each button', () => {
    const label = (id) => ({ sales: 'Sales' }[id] || id);
    assert.deepEqual(view({ space: 'sales', verlassen: false, zurueck: true }, label), { shown: false, space: 'sales', back: false, home: false, name: '' });
    assert.deepEqual(view({ space: 'sales', verlassen: true, zurueck: false }, label), { shown: true, space: 'sales', back: false, home: true, name: 'Sales' });
    assert.deepEqual(view({ space: 'sales', verlassen: true, zurueck: true }, label), { shown: true, space: 'sales', back: true, home: true, name: 'Sales' });
    assert.equal(view({ space: null, verlassen: true, zurueck: true }, label).shown, false);

    const source = fs.readFileSync(path.join(__dirname, 'renderer', 'space-bar.js'), 'utf8');
    assert.match(source, /back\.title = /);
    assert.match(source, /back\.setAttribute\('aria-label', /);
    assert.match(source, /home\.title = /);
    assert.match(source, /home\.setAttribute\('aria-label', /);
    assert.match(source, /top: 75px; height: 28px;/, 'the bar sits where the page made room');
});

test('main, preload and page are wired to the bar', () => {
    const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');
    const main = read('main.js');
    assert.match(main, /ipcMain\.on\('external-space-back', \(_event, id\) => \{\s*if \(externalSpaces && externalSpaces\.has\(id\)\) externalSpaces\.back\(id\);/);
    assert.match(main, /ipcMain\.on\('external-space-home', \(_event, id\) => \{\s*if \(externalSpaces && externalSpaces\.has\(id\)\) externalSpaces\.home\(id\);/);
    const preload = read('preload.js');
    assert.match(preload, /externalSpaceBack: \(id\) => ipcRenderer\.send\('external-space-back', id\)/);
    assert.match(preload, /externalSpaceHome: \(id\) => ipcRenderer\.send\('external-space-home', id\)/);
    assert.match(preload, /message\.type === 'external_space_nav'/);
    assert.match(read('renderer', 'index.html'), /<script defer src="space-bar\.js"><\/script>/);
});
