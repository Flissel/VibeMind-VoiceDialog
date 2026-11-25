// The Project Space view opens its DevTools only when asked for (DASHBOARD_DEVTOOLS).
const test = require('node:test');
const assert = require('node:assert/strict');

const DashboardManager = require('./dashboard-manager');
const { dashboardDevTools } = DashboardManager;

function viewWith(env) {
    const opened = [];
    class FakeBrowserView {
        constructor() {
            this.webContents = {
                loadURL: async () => {}, loadFile: async () => {}, on() {}, setWindowOpenHandler() {}, insertCSS() {},
                isDestroyed: () => false, send() {}, openDevTools: (options) => opened.push(options),
            };
        }
        setBounds() {}
    }
    const mainWindow = { on() {}, setBrowserView() {}, getContentBounds: () => ({ x: 0, y: 0, width: 800, height: 600 }), isDestroyed: () => false, webContents: { send() {} } };
    const quiet = { log() {}, info() {}, warn() {}, error() {} };
    new DashboardManager(mainWindow, { BrowserView: FakeBrowserView, env, dashboardPath: 'C:/nirgends/index.html', overlayDeps: { existsSync: () => false, logger: quiet } }).createView();
    return opened;
}

test('DASHBOARD_DEVTOOLS is off unless it says 1 or true', () => {
    assert.equal(dashboardDevTools({}), false);
    assert.equal(dashboardDevTools({ DASHBOARD_DEVTOOLS: '0' }), false);
    assert.equal(dashboardDevTools({ DASHBOARD_DEVTOOLS: 'ja' }), false);
    assert.equal(dashboardDevTools({ DASHBOARD_DEVTOOLS: '1' }), true);
    assert.equal(dashboardDevTools({ DASHBOARD_DEVTOOLS: ' TRUE ' }), true);
});

test('the view opens no DevTools by itself; with the variable it does', () => {
    assert.deepEqual(viewWith({}), []);
    assert.deepEqual(viewWith({ DASHBOARD_DEVTOOLS: '1' }), [{ mode: 'detach' }]);
});
