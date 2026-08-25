const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const { describe, test } = require('node:test');

const { LAURA_SESSION_PARTITION } = require('./laura-embed-config');
const VideoManager = require('./video-manager');

const RENDERER_PATH = 'C:\\Laura Renderer\\index.html';

function createHarness() {
  const instances = [];
  const openedUrls = [];
  const logs = [];
  const windowHandlers = new Map();
  const attachedViews = [];

  class FakeBrowserView {
    constructor(options) {
      this.options = options;
      this.bounds = [];
      this.handlers = new Map();
      this.loadFiles = [];
      this.closeCalls = 0;
      this.webContents = {
        loadFile: (file) => this.loadFiles.push(file),
        setWindowOpenHandler: (handler) => { this.windowOpenHandler = handler; },
        on: (event, handler) => this.handlers.set(event, handler),
        close: () => { this.closeCalls += 1; },
        openDevTools: () => {},
      };
      instances.push(this);
    }

    setBounds(bounds) {
      this.bounds.push(bounds);
    }
  }

  const mainWindow = {
    on: (event, handler) => windowHandlers.set(event, handler),
    setBrowserView: (view) => attachedViews.push(view),
    getContentBounds: () => ({ width: 1280, height: 900 }),
  };
  const shell = {
    openExternal: (url) => {
      openedUrls.push(url);
      return Promise.resolve();
    },
  };
  const logger = (...parts) => logs.push(parts);
  const manager = new VideoManager(mainWindow, {
    BrowserView: FakeBrowserView,
    shell,
    rendererPath: RENDERER_PATH,
    logger,
  });

  return { attachedViews, instances, logs, manager, openedUrls, windowHandlers };
}

describe('VideoManager Laura embed', () => {
  test('show creates one secure Laura BrowserView and loads the injected renderer', () => {
    const { instances, manager } = createHarness();

    manager.show();
    manager.show();

    assert.equal(instances.length, 1);
    assert.deepEqual(instances[0].options, {
      webPreferences: {
        preload: require('node:path').join(__dirname, 'laura-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        webSecurity: true,
        partition: LAURA_SESSION_PARTITION,
      },
    });
    assert.deepEqual(instances[0].loadFiles, [RENDERER_PATH]);
  });

  test('show, hide, resize, and reuse preserve bounds and visibility semantics', () => {
    const { attachedViews, instances, manager, windowHandlers } = createHarness();

    manager.show();
    assert.equal(manager.getIsVisible(), true);
    assert.deepEqual(instances[0].bounds, [{ x: 0, y: 75, width: 1280, height: 825 }]);

    manager.updateBounds();
    assert.equal(instances[0].bounds.length, 2);

    windowHandlers.get('resize')();
    assert.equal(instances[0].bounds.length, 3);

    manager.toggle();
    assert.equal(manager.getIsVisible(), false);
    manager.toggle();

    assert.equal(instances.length, 1);
    assert.deepEqual(attachedViews, [instances[0], null, instances[0]]);
    assert.equal(instances[0].bounds.length, 4);
  });

  test('destroy closes the view, clears it, and resets visibility', () => {
    const { instances, manager } = createHarness();
    manager.show();

    manager.destroy();

    assert.equal(instances[0].closeCalls, 1);
    assert.equal(manager.videoView, null);
    assert.equal(manager.getIsVisible(), false);
  });

  test('new windows open externally and are denied inside the embed', () => {
    const { instances, manager, openedUrls } = createHarness();
    manager.show();

    const result = instances[0].windowOpenHandler({ url: 'https://example.com/help' });

    assert.deepEqual(openedUrls, ['https://example.com/help']);
    assert.deepEqual(result, { action: 'deny' });
  });

  test('navigation allows only the exact renderer file URL', () => {
    const { instances, manager } = createHarness();
    manager.show();
    const handler = instances[0].handlers.get('will-navigate');
    const rendererUrl = pathToFileURL(RENDERER_PATH).href;
    const allowedEvent = { preventDefaultCalls: 0, preventDefault() { this.preventDefaultCalls += 1; } };

    handler(allowedEvent, rendererUrl);

    assert.equal(allowedEvent.preventDefaultCalls, 0);

    for (const blockedUrl of [
      'https://example.com/',
      pathToFileURL('C:\\Laura Renderer\\other.html').href,
      `${rendererUrl}?token=secret`,
      `${rendererUrl}#fragment`,
    ]) {
      const event = { preventDefaultCalls: 0, preventDefault() { this.preventDefaultCalls += 1; } };
      handler(event, blockedUrl);
      assert.equal(event.preventDefaultCalls, 1, blockedUrl);
    }
  });

  test('same-document fragment navigation resets to the exact renderer without a reload loop', () => {
    const { instances, manager } = createHarness();
    manager.show();
    const rendererUrl = pathToFileURL(RENDERER_PATH).href;
    const handler = instances[0].handlers.get('did-navigate-in-page');

    assert.equal(typeof handler, 'function');
    handler({}, rendererUrl);
    assert.deepEqual(instances[0].loadFiles, [RENDERER_PATH]);

    handler({}, `${rendererUrl}#fragment`);
    assert.deepEqual(instances[0].loadFiles, [RENDERER_PATH, RENDERER_PATH]);

    handler({}, rendererUrl);
    assert.deepEqual(instances[0].loadFiles, [RENDERER_PATH, RENDERER_PATH]);
  });

  test('failed loads log only a safe code without description or URL', () => {
    const { instances, logs, manager } = createHarness();
    manager.show();
    const handler = instances[0].handlers.get('did-fail-load');

    handler({}, -105, 'token=super-secret', 'file:///private/customer.html');

    const serialized = JSON.stringify(logs);
    assert.match(serialized, /-105/);
    assert.doesNotMatch(serialized, /super-secret|customer\.html/);
  });
});
