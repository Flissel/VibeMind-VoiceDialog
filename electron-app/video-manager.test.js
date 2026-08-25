const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const { describe, test } = require('node:test');

const { LAURA_SESSION_PARTITION } = require('./laura-embed-config');
const VideoManager = require('./video-manager');

const RENDERER_PATH = 'C:\\Laura Renderer\\index.html';

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function flushPromises() {
  return new Promise((resolve) => setImmediate(resolve));
}

function createHarness({ loadFileImpl, openExternalImpl } = {}) {
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
        loadFile: (file) => {
          this.loadFiles.push(file);
          return loadFileImpl ? loadFileImpl(file, this.loadFiles.length) : Promise.resolve();
        },
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

  let currentBrowserView = null;
  const mainWindow = {
    on: (event, handler) => windowHandlers.set(event, handler),
    setBrowserView: (view) => {
      currentBrowserView = view;
      attachedViews.push(view);
    },
    getBrowserView: () => currentBrowserView,
    getContentBounds: () => ({ width: 1280, height: 900 }),
  };
  const shell = {
    openExternal: (url) => {
      openedUrls.push(url);
      return openExternalImpl ? openExternalImpl(url) : Promise.resolve();
    },
  };
  const logger = (...parts) => logs.push(['info', ...parts]);
  logger.info = (...parts) => logs.push(['info', ...parts]);
  logger.warn = (...parts) => logs.push(['warn', ...parts]);
  const manager = new VideoManager(mainWindow, {
    BrowserView: FakeBrowserView,
    shell,
    rendererPath: RENDERER_PATH,
    logger,
  });

  return {
    attachedViews,
    instances,
    logs,
    manager,
    openedUrls,
    setCurrentView: (view) => { currentBrowserView = view; },
    windowHandlers,
  };
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
    const { attachedViews, instances, manager } = createHarness();
    manager.show();

    manager.destroy();

    assert.deepEqual(attachedViews, [instances[0], null]);
    assert.equal(instances[0].closeCalls, 1);
    assert.equal(manager.videoView, null);
    assert.equal(manager.getIsVisible(), false);
  });

  test('destroy never detaches a BrowserView owned by another manager', () => {
    const { attachedViews, instances, manager, setCurrentView } = createHarness();
    manager.show();
    setCurrentView({ owner: 'other-manager' });

    manager.destroy();

    assert.deepEqual(attachedViews, [instances[0]]);
    assert.equal(instances[0].closeCalls, 1);
    assert.equal(manager.videoView, null);
  });

  test('new windows open only HTTP(S) URLs externally and are always denied inside', () => {
    const { instances, manager, openedUrls } = createHarness();
    manager.show();

    const results = [
      'https://example.com/help',
      'http://example.com/help',
      'file:///private/customer.html',
      'javascript:alert(1)',
      'custom:command',
      'not a URL',
    ].map((url) => instances[0].windowOpenHandler({ url }));

    assert.deepEqual(openedUrls, ['https://example.com/help', 'http://example.com/help']);
    assert.deepEqual(results, Array(results.length).fill({ action: 'deny' }));
  });

  test('external open rejection is handled without logging URL or error details', async () => {
    const { instances, logs, manager } = createHarness({
      openExternalImpl: () => Promise.reject(new Error('token=super-secret')),
    });
    manager.show();

    instances[0].windowOpenHandler({ url: 'https://private.example/customer' });
    await flushPromises();

    const serialized = JSON.stringify(logs);
    assert.match(serialized, /external link failed/);
    assert.doesNotMatch(serialized, /super-secret|private\.example|customer/);
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

  test('same-document main-frame restoration is single-flight and ignores subframes', async () => {
    const restore = deferred();
    const { instances, manager } = createHarness({
      loadFileImpl: (_file, callNumber) => callNumber === 2 ? restore.promise : Promise.resolve(),
    });
    manager.show();
    const rendererUrl = pathToFileURL(RENDERER_PATH).href;
    const handler = instances[0].handlers.get('did-navigate-in-page');

    assert.equal(typeof handler, 'function');
    handler({}, `${rendererUrl}#subframe`, false);
    assert.deepEqual(instances[0].loadFiles, [RENDERER_PATH]);

    handler({}, `${rendererUrl}#fragment`, true);
    handler({}, `${rendererUrl}#second`, true);
    assert.deepEqual(instances[0].loadFiles, [RENDERER_PATH, RENDERER_PATH]);

    restore.resolve();
    await flushPromises();
    handler({}, rendererUrl, true);
    assert.deepEqual(instances[0].loadFiles, [RENDERER_PATH, RENDERER_PATH]);
  });

  test('failed same-document restoration is logged safely and can retry', async () => {
    const failedRestore = deferred();
    const { instances, logs, manager } = createHarness({
      loadFileImpl: (_file, callNumber) => callNumber === 2
        ? failedRestore.promise
        : Promise.resolve(),
    });
    manager.show();
    const rendererUrl = pathToFileURL(RENDERER_PATH).href;
    const handler = instances[0].handlers.get('did-navigate-in-page');

    handler({}, `${rendererUrl}#fragment`, true);
    failedRestore.reject(new Error('file:///private/customer-token'));
    await flushPromises();
    handler({}, `${rendererUrl}#retry`, true);

    assert.deepEqual(instances[0].loadFiles, [RENDERER_PATH, RENDERER_PATH, RENDERER_PATH]);
    const serialized = JSON.stringify(logs);
    assert.match(serialized, /renderer restore failed/);
    assert.doesNotMatch(serialized, /private|customer-token/);
  });

  test('initial renderer load rejection is handled without sensitive logging', async () => {
    const { logs, manager } = createHarness({
      loadFileImpl: () => Promise.reject(new Error('file:///private/customer-token')),
    });

    manager.show();
    await flushPromises();

    const serialized = JSON.stringify(logs);
    assert.match(serialized, /initial renderer load failed/);
    assert.doesNotMatch(serialized, /private|customer-token/);
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
