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
