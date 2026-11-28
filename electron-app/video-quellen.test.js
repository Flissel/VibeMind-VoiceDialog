// The Video space shows Laura or "Aus dem Marketing" (the reels page of the marketing service). Invented
// addresses and keys, no real data.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { VideoQuellen, marketingTarget, quelleOf, BAR_HEIGHT, MARKETING_PARTITION } = require('./video-quellen');
const VideoManager = require('./video-manager');

const read = (...p) => fs.readFileSync(path.join(__dirname, ...p), 'utf8');
const ENV = { MARKETING_UI_URL: 'https://marketing.example.test/oberflaeche/newsletter', MARKETING_UI_KEY: 'test-marketing-ui-key' };
const quiet = { info() {}, warn() {}, log() {} };

function harness() {
  const views = [];
  const opened = [];
  class FakeBrowserView {
    constructor(options) {
      this.options = options;
      this.bounds = [];
      this.handlers = {};
      this.sent = [];
      this.loads = [];
      const self = this;
      this.webContents = {
        on: (event, fn) => { self.handlers[event] = fn; },
        send: (channel, data) => self.sent.push([channel, data]),
        loadFile: async (file) => { self.loads.push(['file', file]); },
        loadURL: async (url) => { self.loads.push(['url', url]); },
        setWindowOpenHandler: (fn) => { self.windowOpen = fn; },
        isDestroyed: () => false,
        destroy: () => {},
        openDevTools: () => {},
        session: { webRequest: { onBeforeSendHeaders: (filter, fn) => { self.headerFilter = filter; self.headerFn = fn; } } },
      };
      views.push(this);
    }
    setBounds(b) { this.bounds.push(b); }
  }
  let attached = [];
  const mainWindow = {
    on() {},
    getContentBounds: () => ({ width: 1200, height: 800 }),
    setBrowserView: (v) => { attached = v ? [v] : []; },
    addBrowserView: (v) => { attached.push(v); },
    removeBrowserView: (v) => { attached = attached.filter((x) => x !== v); },
    isDestroyed: () => false,
  };
  const overlayDeps = { logger: quiet, fetchImpl: async () => ({ ok: true, status: 200, text: async () => '<title>Reels</title>' }) };
  return { views, opened, mainWindow, FakeBrowserView, attached: () => attached, shell: { openExternal: async (u) => opened.push(u) }, overlayDeps };
}

function manager(h, env = ENV) {
  return new VideoManager(h.mainWindow, { BrowserView: h.FakeBrowserView, shell: h.shell, logger: quiet, env,
    rendererPath: 'C:\\Laura\\index.html', overlayDeps: h.overlayDeps });
}

const tick = () => new Promise((r) => setImmediate(r));

test('the reels page of the marketing service, at the address and with the key of the Marketing space', () => {
  const t = marketingTarget(ENV);
  assert.equal(t.url, 'https://marketing.example.test/oberflaeche/reels');
  assert.equal(t.auth.header, 'Bearer test-marketing-ui-key');
  assert.deepEqual(t.auth.origins, ['https://marketing.example.test']);
  assert.equal(marketingTarget({ MARKETING_UI_URL: 'http://127.0.0.1:5510/x/' }).auth, null, 'no key, no header');
  assert.equal(quelleOf('marketing'), 'marketing');
  assert.equal(quelleOf('../boese'), 'laura');
});

test('the Video space opens with the bar and Laura below it', () => {
  const h = harness();
  const v = manager(h);
  v.show();
  const [laura, bar] = h.views;
  assert.deepEqual(h.attached(), [bar, laura]);
  assert.match(bar.options.webPreferences.preload, /video-quellen-preload\.js$/);
  assert.equal(bar.options.webPreferences.sandbox, true);
  assert.deepEqual(bar.loads[0][0], 'file');
  assert.match(bar.loads[0][1], /video-quellen\.html$/);
  assert.deepEqual(bar.bounds.at(-1), { x: 0, y: 75, width: 1200, height: BAR_HEIGHT });
  assert.deepEqual(laura.bounds.at(-1), { x: 0, y: 75 + BAR_HEIGHT, width: 1200, height: 800 - 75 - BAR_HEIGHT });
  assert.deepEqual(bar.sent.at(-1), ['video-quelle-stand', { quelle: 'laura', marketing: true }]);
});

test('"Aus dem Marketing" shows the reels page in its own session, with the key only for its own requests', async () => {
  const h = harness();
  const v = manager(h);
  v.show();
  const [laura, bar] = h.views;
  assert.equal(v.chooseSource(bar.webContents, 'marketing'), true);
  const mk = h.views[2];
  await v.quellen.marketingReady;
  assert.equal(mk.options.webPreferences.partition, MARKETING_PARTITION);
  assert.equal(mk.options.webPreferences.preload, undefined, 'a remote page gets no bridge');
  assert.deepEqual(h.attached(), [bar, mk]);
  assert.deepEqual(mk.loads.at(-1), ['url', 'https://marketing.example.test/oberflaeche/reels']);
  assert.deepEqual(mk.bounds.at(-1), { x: 0, y: 75 + BAR_HEIGHT, width: 1200, height: 800 - 75 - BAR_HEIGHT });
  assert.deepEqual(bar.sent.at(-1), ['video-quelle-stand', { quelle: 'marketing', marketing: true }]);

  const own = await new Promise((r) => mk.headerFn({ resourceType: 'media', requestHeaders: {}, frame: { url: 'https://marketing.example.test/oberflaeche/reels' } }, r));
  assert.equal(own.requestHeaders.Authorization, 'Bearer test-marketing-ui-key');
  const foreign = await new Promise((r) => mk.headerFn({ resourceType: 'subFrame', requestHeaders: {}, frame: { url: 'https://fremd.example.test/' } }, r));
  assert.equal(foreign.requestHeaders.Authorization, undefined);

  let prevented = false;
  mk.handlers['will-navigate']({ preventDefault: () => { prevented = true; } }, 'https://fremd.example.test/x');
  assert.equal(prevented, true);
  assert.deepEqual(h.opened, ['https://fremd.example.test/x']);
  assert.deepEqual(mk.windowOpen({ url: 'https://fremd.example.test/y' }), { action: 'deny' });

  assert.equal(v.chooseSource(bar.webContents, 'laura'), true);
  assert.deepEqual(h.attached(), [bar, laura]);
});

test('only the bar may switch; leaving the space hides everything; the choice stays for the next visit', () => {
  const h = harness();
  const v = manager(h);
  v.show();
  const [, bar] = h.views;
  assert.equal(v.chooseSource({}, 'marketing'), false, 'another page may not switch');
  assert.equal(h.views.length, 2);
  v.chooseSource(bar.webContents, 'marketing');
  v.hide();
  assert.deepEqual(h.attached(), []);
  v.show();
  assert.deepEqual(h.attached(), [bar, h.views[2]]);
});

test('without MARKETING_UI_URL the page comes from the default address of the Marketing space', () => {
  const h = harness();
  const q = new VideoQuellen({ mainWindow: h.mainWindow, BrowserView: h.FakeBrowserView, shell: h.shell, env: {}, logger: quiet, overlayDeps: h.overlayDeps });
  // the Marketing space has a default address; without MARKETING_UI_URL the page comes from there
  assert.equal(marketingTarget({}).url, 'http://127.0.0.1:5510/oberflaeche/reels');
  q.show({ setBounds() {} });
  assert.deepEqual(h.views[0].sent.at(-1), ['video-quelle-stand', { quelle: 'laura', marketing: true }]);
});

test('a window without two views keeps the old way (Laura alone)', () => {
  assert.equal(VideoQuellen.supported({ setBrowserView() {} }), false);
  const h = harness();
  delete h.mainWindow.addBrowserView;
  const v = manager(h);
  assert.equal(v.quellen, null);
  v.show();
  assert.deepEqual(h.attached(), [h.views[0]]);
});

test('the bar page: two buttons, no inline script, the bridge has only waehlen and beiStand; main.js passes the sender', () => {
  const html = read('video-quellen.html');
  assert.match(html, />Laura</);
  assert.match(html, />Aus dem Marketing</);
  assert.match(html, /script-src 'self'/);
  assert.doesNotMatch(html, /<script>(?!<)/);
  const preload = read('video-quellen-preload.js');
  assert.match(preload, /exposeInMainWorld\('videoQuellen', \{/);
  assert.doesNotMatch(preload, /MARKETING|Bearer|http/);
  const main = read('main.js');
  assert.match(main, /ipcMain\.on\('video-quelle', \(event, quelle\) => \{\n\s+if \(videoManager\) videoManager\.chooseSource\(event\.sender, quelle\);/);
});
