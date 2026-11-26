// H3: our own pages in the VibeMind look. Values = base.css, accent = multiverse.js (vibemind-look.test.js
// checks both tables against their sources); here: each page gets them, with its own variables set onto them.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { lookCss, SPACE_ACCENT_RGB, TOKEN_PAGE_LOOK } = require('./vibemind-look');

const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');
const quiet = { log() {}, warn() {}, error() {}, info() {} };

/** The variables a block sets ("--name: …;" inside html:root). */
const namesIn = (css) => [...css.match(/html:root \{([\s\S]*?)\}/)[1].matchAll(/(--[a-z0-9-]+):/g)].map((m) => m[1]);
/** The variables a page declares in its :root. */
const rootNames = (css) => new Set([...css.match(/:root\s*\{([\s\S]*?)\n\}/)[1].matchAll(/(--[a-z0-9-]+):/g)].map((m) => m[1]));

/** The accent of a space as multiverse.js has it. */
function sceneAccent(space) {
  const block = read('renderer', 'multiverse.js').match(/const SPACE_ACCENT_RGB = \{([\s\S]*?)\};/)[1];
  return Object.fromEntries([...block.matchAll(/(\w+):\s*'([\d,]+)'/g)].map((m) => [m[1], m[2]]))[space];
}

/** A view whose contents collect did-finish-load handlers and inserted CSS. */
function fakeView() {
  const handlers = {};
  const inserted = [];
  const contents = {
    on(event, fn) { (handlers[event] = handlers[event] || []).push(fn); },
    insertCSS: async (css, options) => { inserted.push({ css, options }); return 'key'; },
    isDestroyed: () => false,
    session: { webRequest: { onHeadersReceived() {}, onBeforeSendHeaders() {} }, clearCache: async () => {} },
    setWindowOpenHandler() {}, loadURL: async () => {}, loadFile: async () => {}, getURL: () => '', openDevTools() {},
  };
  const load = async () => { for (const fn of handlers['did-finish-load'] || []) fn(); await new Promise((r) => setImmediate(r)); };
  return { contents, inserted, load };
}

/** Run fn with stdout quiet (the managers log in colour). */
function silent(fn) {
  const write = process.stdout.write;
  process.stdout.write = () => true;
  try { return fn(); } finally { process.stdout.write = write; }
}

test('the token block of our React pages: every name it sets is a variable of the page, onto --vm values', () => {
  const names = namesIn(TOKEN_PAGE_LOOK);
  const page = rootNames(read('agentfarm', 'src', 'styles', 'globals.css'));
  for (const name of names) assert.ok(page.has(name), `${name} is a variable of the Agent Farm page`);
  for (const name of ['--bg', '--text-primary', '--accent', '--accent-fill', '--space-accent']) assert.ok(names.includes(name), name);
  assert.match(TOKEN_PAGE_LOOK, /--accent: rgb\(var\(--space-accent-rgb\)\);/, 'the accent is that of the space, no fixed blue');
  assert.doesNotMatch(TOKEN_PAGE_LOOK, /#4488ff|68,\s*136,\s*255/i);
  assert.match(TOKEN_PAGE_LOOK, /--bg: var\(--vm-bg-deep\);/);
  assert.match(TOKEN_PAGE_LOOK, /font-family: var\(--vm-font\)/);
});

test('Agent Farm: after every load the page gets the look, accent of its space (green, as multiverse.js)', async () => {
  const AgentFarmManager = require('./agentfarm-manager');
  const view = fakeView();
  class FakeBrowserView { constructor() { this.webContents = view.contents; } setBounds() {} setAutoResize() {} }
  const m = silent(() => {
    const made = new AgentFarmManager(null, { BrowserView: FakeBrowserView, shell: { openExternal() {} }, env: {}, n8nLogin: false,
      overlayDeps: { existsSync: () => true, logger: quiet } });
    made.createView();
    return made;
  });
  assert.ok(m.agentfarmView);
  await view.load();
  await view.load();                                   // a reload: put again
  assert.equal(view.inserted.length, 2);
  const { css, options } = view.inserted[0];
  assert.equal(css, lookCss('agentfarm', TOKEN_PAGE_LOOK));
  assert.equal(SPACE_ACCENT_RGB.agentfarm, sceneAccent('agentfarm'));
  assert.match(css, new RegExp(`--space-accent-rgb: ${sceneAccent('agentfarm')};`));
  assert.match(css, /--vm-bg-deep: #0a0812;/);
  assert.deepEqual(options, { cssOrigin: 'author' });
});

test('Agent Farm: the embedded pages (n8n, Rowboat, OpenFang) keep their own look, nothing is written into them', () => {
  const manager = read('agentfarm-manager.js');
  assert.match(manager, /applyVibeMindLook\(this\.agentfarmView\.webContents, 'agentfarm'/);
  assert.equal((manager.match(/applyVibeMindLook\(/g) || []).length, 1, 'only the view of the Agent Farm page');
  for (const file of ['WorkflowBuilder.tsx', 'RowboatWorkflow.tsx', 'OpenFangWorkflow.tsx']) {
    assert.doesNotMatch(read('agentfarm', 'src', 'features', file), /--vm-|vibemind-look/, file);
  }
});

test('ClawPort: same token names as the Agent Farm page, so the same block fits', () => {
  const page = rootNames(read('dashboard', 'src', 'styles', 'globals.css'));
  for (const name of namesIn(TOKEN_PAGE_LOOK)) assert.ok(page.has(name), `${name} is a variable of the ClawPort page`);
});

test('ClawPort: after every load the page gets the look, accent of its space (violet, as multiverse.js)', async () => {
  const ClawPortManager = require('./clawport-manager');
  const view = fakeView();
  class FakeBrowserView { constructor() { this.webContents = view.contents; } setBounds() {} setAutoResize() {} }
  silent(() => {
    const m = new ClawPortManager(null, { BrowserView: FakeBrowserView, shell: { openExternal() {} }, env: {},
      rendererPath: 'C:/x/index.html', overlayDeps: { existsSync: () => true, logger: quiet } });
    m.createView();
  });
  await view.load();
  assert.equal(view.inserted.length, 1);
  assert.equal(view.inserted[0].css, lookCss('clawport', TOKEN_PAGE_LOOK));
  assert.equal(SPACE_ACCENT_RGB.clawport, sceneAccent('clawport'));
  assert.match(view.inserted[0].css, new RegExp(`--space-accent-rgb: ${sceneAccent('clawport')};`));
});

test('Aufträge: every name of its block is a variable of the page; the accent is its scene colour', () => {
  const { ORDERS_LOOK, rgbOf } = require('./vibemind-look');
  const page = read('auftraege', 'index.html');
  const declared = new Set([...page.match(/:root \{([^}]*)\}/)[1].matchAll(/(--[a-z0-9-]+):/g)].map((m) => m[1]));
  for (const name of namesIn(ORDERS_LOOK)) assert.ok(declared.has(name), `${name} is a variable of the Aufträge page`);
  const { EXTERNAL_SPACES } = require('./external-spaces');
  const orders = EXTERNAL_SPACES.find((s) => s.id === 'orders');
  assert.equal(orders.look, ORDERS_LOOK);
  assert.equal(rgbOf(orders.color), '179,157,219', 'the colour the scene draws the space with');
  assert.match(lookCss('orders', ORDERS_LOOK, rgbOf(orders.color)), /--space-accent-rgb: 179,157,219;/);
  assert.match(lookCss('orders', '', 'kein,rgb'), /--space-accent-rgb: 68,136,255;/, 'a malformed accent falls back');
});

test('Aufträge: its view gets the look after every load; services of other sessions (Sales, Marketing) do not', async () => {
  const { ExternalSpaceManager } = require('./external-spaces');
  const { ORDERS_LOOK, rgbOf } = require('./vibemind-look');
  const views = {};
  class View {
    constructor() {
      const v = fakeView();
      this.fake = v;
      this.webContents = { ...v.contents, getURL: () => '' };
    }
    setBounds() {}
  }
  const manager = new ExternalSpaceManager(null, { BrowserView: View, shell: {}, logger: { log() {} }, env: {} });
  manager._load = () => {};
  for (const id of ['orders', 'sales', 'marketing']) { manager._create(id); views[id] = manager.views.get(id).view.fake; }
  for (const v of Object.values(views)) await v.load();
  assert.equal(views.orders.inserted.length, 1);
  assert.equal(views.orders.inserted[0].css, lookCss('orders', ORDERS_LOOK, rgbOf(0xb39ddb)));
  assert.equal(views.sales.inserted.length, 0, 'Sales stays as it is');
  assert.equal(views.marketing.inserted.length, 0, 'Marketing stays as it is');
});
