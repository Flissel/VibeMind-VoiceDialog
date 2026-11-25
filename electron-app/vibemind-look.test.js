// The VibeMind look for pages in a space view, first for Video (Laura).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { applyVibeMindLook, lookCss, SPACE_ACCENT_RGB, VM_TOKENS } = require('./vibemind-look');
const VideoManager = require('./video-manager');

const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');

test('the look has the values of the app itself: base.css and the accents of multiverse.js', () => {
    const base = read('renderer', 'styles', 'base.css');
    for (const [name, value] of Object.entries(VM_TOKENS)) {
        if (name === '--vm-font') continue;
        const found = base.match(new RegExp(`${name}:\\s*([^;]+);`));
        assert.ok(found, name);
        assert.equal(found[1].replace(/\s+/g, ''), value.replace(/\s+/g, ''), name);
    }
    assert.match(base, new RegExp(`font-family: ${VM_TOKENS['--vm-font'].replace(/[.*+?^${}()|[\]\\]/g, '\\$&')};`));

    const scene = read('renderer', 'multiverse.js');
    const block = scene.match(/const SPACE_ACCENT_RGB = \{([\s\S]*?)\};/)[1];
    const accents = Object.fromEntries([...block.matchAll(/(\w+):\s*'([\d,]+)'/g)].map((m) => [m[1], m[2]]));
    assert.deepEqual(accents, { ...SPACE_ACCENT_RGB });
});

test('the CSS of a space: tokens, its accent, dark scheme, weighing more than the page\'s own :root', () => {
    const css = lookCss('video', 'body { x: 1; }');
    assert.match(css, /^html:root \{/);
    assert.match(css, /--space-accent-rgb: 238,68,102;/);
    assert.match(css, /--vm-bg-deep: #0a0812;/);
    assert.match(css, /color-scheme: dark;/);
    assert.ok(css.endsWith('body { x: 1; }'));
    assert.match(lookCss('gibt-es-nicht'), /--space-accent-rgb: 68,136,255;/, 'an unknown space takes the Ideas accent');
});

function fakeContents() {
    const handlers = {};
    const inserted = [];
    return {
        handlers, inserted, destroyed: false,
        on(name, fn) { (handlers[name] = handlers[name] || []).push(fn); },
        insertCSS(css, options) { inserted.push({ css, options }); return Promise.resolve('k'); },
        isDestroyed() { return this.destroyed; },
        fire(name) { for (const fn of handlers[name] || []) fn(); },
    };
}

test('the look is put in after every load, not before, and not into a closed view', async () => {
    const contents = fakeContents();
    const css = applyVibeMindLook(contents, 'video', { extraCss: '.x{}' });
    assert.equal(contents.inserted.length, 0, 'nothing before the page is there');
    contents.fire('did-finish-load');
    contents.fire('did-finish-load');     // a reload
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(contents.inserted.length, 2);
    assert.equal(contents.inserted[0].css, css);
    assert.deepEqual(contents.inserted[0].options, { cssOrigin: 'author' });
    contents.destroyed = true;
    contents.fire('did-finish-load');
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(contents.inserted.length, 2);
});

test('a failed insert is logged and nothing else happens', async () => {
    const contents = fakeContents();
    contents.insertCSS = () => Promise.reject(new Error('weg'));
    const warned = [];
    applyVibeMindLook(contents, 'video', { logger: { warn: (m) => warned.push(m) } });
    contents.fire('did-finish-load');
    await new Promise((resolve) => setImmediate(resolve));
    assert.deepEqual(warned, ['[VibeMindLook] video: Aussehen nicht gesetzt']);
});

test('Video shows Laura in the look: the view gets the VibeMind CSS with Laura\'s variables, accent Video', async () => {
    const made = [];
    class BrowserView {
        constructor(options) { this.options = options; this.webContents = fakeContents(); this.webContents.setWindowOpenHandler = () => {}; this.webContents.loadFile = () => Promise.resolve(); made.push(this); }
    }
    const manager = new VideoManager(null, {
        BrowserView, shell: { openExternal() {} }, logger: { info() {}, warn() {} }, rendererPath: path.join(__dirname, 'nirgends', 'index.html'),
    });
    manager.createView();
    made[0].webContents.fire('did-finish-load');
    await new Promise((resolve) => setImmediate(resolve));
    const css = made[0].webContents.inserted.map((i) => i.css).join('\n');
    assert.match(css, /--space-accent-rgb: 238,68,102;/);
    assert.match(css, /--surface-0: var\(--vm-bg-deep\);/);
    assert.match(css, /--accent: rgb\(var\(--space-accent-rgb\)\);/);
});

test('the Laura block names exactly the 16 variables Laura draws with', () => {
    const names = [...VideoManager.LAURA_LOOK.matchAll(/^\s*(--[a-z0-9-]+):/gm)].map((m) => m[1]);
    assert.equal(names.length, 16);
    assert.equal(new Set(names).size, 16);
    // Laura's own list, when its source is next to this checkout (laura-embed-config.js); a renamed
    // variable there shows up here
    const lauraCss = process.env.LAURA_INDEX_CSS
        || path.resolve(__dirname, '..', '..', 'spaces', 'video', 'laura', 'apps', 'desktop', 'src', 'index.css');
    if (!fs.existsSync(lauraCss)) return;
    const root = fs.readFileSync(lauraCss, 'utf8').match(/:root\s*\{([\s\S]*?)\}/)[1];
    const theirs = [...root.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]);
    assert.deepEqual([...names].sort(), [...theirs].sort());
});
