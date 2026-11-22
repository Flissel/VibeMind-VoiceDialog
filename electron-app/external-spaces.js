/**
 * External spaces: one manager for every space that is simply another web UI.
 *
 * A space listed in EXTERNAL_SPACES gets a nav entry, a place in the 3D scene and an
 * overlay that loads its address, with the usual status card when the service is not
 * there (overlay-status.js). Adding a space means adding one entry to the list below;
 * no further handler, preload line or hide list is needed.
 *
 * Addresses come from the environment, so nothing about a private network is written
 * into this repository. Without an address the entry shows the card
 * "kein Ziel konfiguriert".
 *
 * Keys stay in the main process: a space may name an environment variable (earerEnv) whose value
 * is added as `Authorization: Bearer …` to requests to that space's own address, and
 * only there. The page never sees the value.
 */
const { loadOverlay, loadStatus, resolveElectronParts } = require('./overlay-status');

const EXTERNAL_SPACES = Object.freeze([
  // OpenFang has no entry here: its dashboard is a tab of the Agent Farm and needs no key
  // on this machine (GET /api/auth/check -> mode "none").
  {
    id: 'sales', label: 'Sales', icon: '\u{1F91D}', color: 0x4fc3f7, position: [26, 0, 2],
    urlEnv: 'SALES_UI_URL',
    agent: { name: 'Sales', slug: 'sales', role: 'Kontakte, Post, Termine' },
  },
  {
    id: 'marketing', label: 'Marketing', icon: '\u{1F4E3}', color: 0xff7eb6, position: [24, 0, 20],
    urlEnv: 'MARKETING_UI_URL', defaultUrl: 'http://127.0.0.1:5510/mockup/', expectTitle: /Marketing/i,
    agent: { name: 'Marketing', slug: 'marketing', role: 'Kampagnen und Inhalte' },
  },
  {
    id: 'learning', label: 'Lernen', icon: '\u{1F393}', color: 0x9ccc65, position: [8, 0, 26],
    urlEnv: 'LEARNING_UI_URL',
    access: 'learning-huelle', // the page wants an access cookie; the app issues it (learning-access.js)
    agent: { name: 'Lernen', slug: 'learning', role: 'Kurse und Aufgaben' },
  },
  {
    id: 'events', label: 'Events', icon: '\u{1F3AA}', color: 0xffb74d, position: [-22, 0, 6],
    urlEnv: 'EVENT_UI_URL', expectTitle: /Events/i,
    agent: { name: 'Events', slug: 'events', role: 'Veranstaltungen' },
  },
]);

function cleanUrl(value) {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!text) return '';
  try {
    const url = new URL(text);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : '';
  } catch (_) {
    return '';
  }
}

/** The spaces with their resolved address ('' when none is configured). */
function resolveSpaces(env = process.env) {
  return EXTERNAL_SPACES.map((space) => ({
    ...space,
    url: cleanUrl(env[space.urlEnv]) || cleanUrl(space.defaultUrl),
  }));
}

/** What the renderer needs to draw the entry; no addresses, no key names. */
function describeForRenderer(env = process.env) {
  return resolveSpaces(env).map(({ id, label, icon, color, position, agent, url }) => ({
    id, label, icon, color, position, agent, configured: Boolean(url),
  }));
}

/**
 * URL patterns and header for the key of a space, or null when it has none.
 * The patterns cover only the origin of the space's own address (http and websocket).
 */
function authFor(space, env = process.env) {
  if (!space.bearerEnv || !space.url) return null;
  const key = typeof env[space.bearerEnv] === 'string' ? env[space.bearerEnv].trim() : '';
  if (!key) return null;
  const origin = new URL(space.url);
  const hosts = origin.hostname === '127.0.0.1' || origin.hostname === 'localhost'
    ? ['127.0.0.1', 'localhost'] : [origin.hostname];
  const port = origin.port ? `:${origin.port}` : '';
  const ws = origin.protocol === 'https:' ? 'wss:' : 'ws:';
  const urls = hosts.flatMap((host) => [`${origin.protocol}//${host}${port}/*`, `${ws}//${host}${port}/*`]);
  return { urls, header: `Bearer ${key}` };
}

/** Adds the key unless the page already sent its own Authorization header. */
function withAuthorization(requestHeaders, header) {
  const has = Object.keys(requestHeaders || {}).some((name) => name.toLowerCase() === 'authorization');
  return has ? requestHeaders : { ...requestHeaders, Authorization: header };
}

class ExternalSpaceManager {
  constructor(mainWindow, dependencies = {}) {
    const { BrowserView, shell } = resolveElectronParts(dependencies, ['BrowserView', 'shell']);
    this.BrowserView = BrowserView;
    this.shell = shell;
    this.mainWindow = mainWindow;
    this._env = dependencies.env || process.env;
    this._overlayDeps = dependencies.overlayDeps || {};
    this._log = dependencies.logger || console;
    // access kind -> (spaceUrl, env) => cookie for session.cookies.set, or null
    this._accessCookies = dependencies.accessCookies
      || { 'learning-huelle': require('./learning-access').learningAccessCookie };
    this._ready = new Map();  // id -> promise that settles once the first load was started
    this.spaces = new Map(resolveSpaces(this._env).map((space) => [space.id, space]));
    this.views = new Map();   // id -> { view, result }
    this.visibleId = null;
    this.topOffset = 32 + 43; // titlebar + tab bar, as for the other overlays
    if (mainWindow) mainWindow.on('resize', () => this._updateBounds());
  }

  has(id) { return this.spaces.has(id); }

  _load(id) {
    const space = this.spaces.get(id);
    const entry = this.views.get(id);
    entry.result = null;
    const targets = space.url ? [{ kind: 'url', url: space.url, expectTitle: space.expectTitle }] : [];
    return loadOverlay(entry.view.webContents, { space: space.label, targets },
      { ...this._overlayDeps, onResult: (result) => { entry.result = result; } });
  }

  _create(id) {
    const space = this.spaces.get(id);
    const view = new this.BrowserView({
      webPreferences: {
        partition: `persist:space-${id}`, // each space keeps its own sign-in
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    });
    const auth = authFor(space, this._env);
    if (auth) {
      view.webContents.session.webRequest.onBeforeSendHeaders({ urls: auth.urls }, (details, callback) => {
        callback({ requestHeaders: withAuthorization(details.requestHeaders, auth.header) });
      });
      this._log.log(`[ExternalSpaces] ${space.label}: Schluessel aus ${space.bearerEnv} wird mitgegeben`);
    }
    view.webContents.setWindowOpenHandler(({ url }) => {
      this.shell.openExternal(url);
      return { action: 'deny' };
    });
    view.webContents.on('did-finish-load', () => {
      const entry = this.views.get(id);
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'external_space_status', space: id, ...loadStatus(entry && entry.result),
        });
      }
    });
    this.views.set(id, { view, result: null });
    if (space.access && space.url) {
      this._ready.set(id, this._signIn(space, view).then(() => { this._load(id); }));
    } else {
      this._load(id); // nothing to wait for
    }
    return view;
  }

  /** Resolves once the first load of this space was started (after its sign-in, if it has one). */
  ready(id) { return this._ready.get(id) || Promise.resolve(); }

  /** Sets the access cookie of a space that wants one. Never throws: without it the page shows its own refusal. */
  async _signIn(space, view) {
    const make = space.access && this._accessCookies[space.access];
    if (!make || !space.url) return;
    try {
      const cookie = make(space.url, this._env);
      if (!cookie) {
        this._log.log(`[ExternalSpaces] ${space.label}: kein Zugang ausgestellt (Schluessel oder https fehlt)`);
        return;
      }
      await view.webContents.session.cookies.set(cookie);
      this._log.log(`[ExternalSpaces] ${space.label}: Zugang ausgestellt`);
    } catch (error) {
      this._log.log(`[ExternalSpaces] ${space.label}: Zugang nicht gesetzt (${error && error.name})`);
    }
  }

  show(id) {
    if (!this.mainWindow || !this.spaces.has(id)) return false;
    let entry = this.views.get(id);
    if (!entry) {
      this._create(id);
      entry = this.views.get(id);
    } else if (entry.result && !entry.result.ok) {
      this._load(id); // a status card: look again, the service may be up now
    }
    this.mainWindow.setBrowserView(entry.view);
    this.visibleId = id;
    this._updateBounds();
    this._log.log(`[ExternalSpaces] ${this.spaces.get(id).label} shown`);
    return true;
  }

  hideAll() {
    if (!this.visibleId) return;
    if (this.mainWindow) this.mainWindow.setBrowserView(null);
    this.visibleId = null;
  }

  getIsVisible() { return Boolean(this.visibleId); }

  _updateBounds() {
    const entry = this.visibleId && this.views.get(this.visibleId);
    if (!entry || !this.mainWindow) return;
    const bounds = this.mainWindow.getContentBounds();
    entry.view.setBounds({ x: 0, y: this.topOffset, width: bounds.width, height: bounds.height - this.topOffset });
  }

  destroy() {
    this.hideAll();
    this.views.clear();
  }
}

module.exports = {
  EXTERNAL_SPACES, resolveSpaces, describeForRenderer, authFor, withAuthorization, ExternalSpaceManager,
};
