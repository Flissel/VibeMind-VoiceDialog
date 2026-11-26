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
const path = require('node:path');
const { loadOverlay, loadStatus, resolveElectronParts } = require('./overlay-status');
const { applyVibeMindLook, rgbOf, ORDERS_LOOK } = require('./vibemind-look');

const EXTERNAL_SPACES = Object.freeze([
  // OpenFang has no entry here: its dashboard is a tab of the Agent Farm; its key (OPENFANG_API_KEY)
  // goes only to the OpenFang page in that tab (openfang-access.js, agentfarm-manager.js).
  {
    id: 'sales', label: 'Sales', icon: '\u{1F91D}', color: 0x4fc3f7, position: [26, 0, 2],
    urlEnv: 'SALES_UI_URL',
    // Pages a finished task may send this space to (goTo): a comma-separated list in the
    // environment, like the address. The pages of a space are its own business and are not
    // written into this repository. Without the list no path is taken.
    pathsEnv: 'SALES_UI_PATHS',
    agent: { name: 'Sales', slug: 'sales', role: 'Kontakte, Post, Termine' },
  },
  {
    id: 'marketing', label: 'Marketing', icon: '\u{1F4E3}', color: 0xff7eb6, position: [24, 0, 20],
    urlEnv: 'MARKETING_UI_URL', defaultUrl: 'http://127.0.0.1:5510/mockup/', expectTitle: /Marketing/i,
    bearerEnv: 'MARKETING_UI_KEY', // the service answers 401 without it
    hint: 'Die Seite kommt vom Marketing-Dienst, der außerhalb der App läuft. Sobald er gestartet ist, den Reiter erneut öffnen.',
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
  {
    // Schedule, Research and Minibook have no page of their own; this local page shows all three.
    // Placed clear of Video (-10, 0, 24): at least 8 units from every space (space-models.test.js).
    id: 'orders', label: 'Aufträge', icon: '\u{1F4CB}', color: 0xb39ddb, position: [-3, 0, 29],
    localPage: 'auftraege/index.html', preload: 'auftraege-preload.js',
    look: ORDERS_LOOK, // H3: the VibeMind look, accent of its colour above (vibemind-look.js)
    agent: { name: 'Aufträge', slug: 'orders', role: 'Projektmanager, Termine, Recherche, Minibook' },
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

const PAGE = /^\/[A-Za-z0-9_\-.~\/]*$/;

/** The listed pages of a space from its environment value: "/, /seite, /liste/alt". */
function parsePaths(value) {
  if (typeof value !== 'string') return [];
  return value.split(',').map((entry) => entry.trim())
    .filter((entry) => PAGE.test(entry) && !entry.startsWith('//') && !entry.split('/').includes('..'));
}

/** The spaces with their resolved address ('' when none is configured). */
function resolveSpaces(env = process.env) {
  return EXTERNAL_SPACES.map((space) => ({
    ...space,
    url: space.urlEnv ? cleanUrl(env[space.urlEnv]) || cleanUrl(space.defaultUrl) : '',
    file: space.localPage ? path.join(__dirname, space.localPage) : '', // a page shipped with the app
    paths: space.pathsEnv ? parsePaths(env[space.pathsEnv]) : [],
  }));
}

/** What the renderer needs to draw the entry; no addresses, no key names. */
function describeForRenderer(env = process.env) {
  return resolveSpaces(env).map(({ id, label, icon, color, position, agent, url, file }) => ({
    id, label, icon, color, position, agent, configured: Boolean(url || file),
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
  const origins = hosts.map((host) => `${origin.protocol}//${host}${port}`);
  return { urls, origins, header: `Bearer ${key}` };
}

/**
 * The request comes from the space's own page, so its key may go with it. A page of another
 * origin (a site the view was led to, a foreign iframe inside the space) must not use the key:
 * the header is added by the main process, the page would get the user's access for free.
 * Navigations of the whole view count from the page being left; the first load (no page yet,
 * or the status card) is the app's own.
 */
function fromOwnPage(details, origins) {
  const contents = details && details.webContents;
  const current = contents && typeof contents.getURL === 'function' ? contents.getURL() : '';
  const page = details && details.resourceType !== 'mainFrame' && details.frame && details.frame.url
    ? details.frame.url : current;
  if (!page || page === 'about:blank' || page.startsWith('data:')) return Boolean(details) && details.resourceType === 'mainFrame';
  try {
    return origins.includes(new URL(page).origin);
  } catch (_) {
    return false;
  }
}

/**
 * The address of a path inside a space, or '' when the text is not a plain path of that space.
 * A task result names only the path ("/seite/7#anker"); the base address stays in the environment.
 * Anything that could leave the space (a scheme, "//host", a backslash) is refused.
 *
 * The path comes out of a task result, which an agent wrote: it is not trusted. The page is
 * signed in, so loading an arbitrary address of it could act in the user's name. Therefore only
 * the pages listed for the space (allowed: a page or anything below it) are taken, without a
 * query, without ".." and without escapes; a fragment ("#anker") may follow.
 */
function pathTarget(spaceUrl, pathText, allowed) {
  const text = typeof pathText === 'string' ? pathText.trim() : '';
  if (!spaceUrl || !Array.isArray(allowed) || !allowed.length) return '';
  if (!/^\/(?![\/\\])[A-Za-z0-9_\-.~\/]*(#[A-Za-z0-9_\-]*)?$/.test(text) || text.length > 256) return '';
  const page = text.split('#')[0];
  if (page.split('/').includes('..')) return '';
  if (!allowed.some((entry) => page === entry || (entry !== '/' && page.startsWith(entry + '/')))) return '';
  try {
    const base = new URL(spaceUrl);
    const target = new URL(text, base);
    return target.origin === base.origin && target.pathname === page ? target.href : '';
  } catch (_) {
    return '';
  }
}

/** Height of the bar with "Zurück" and "Start" above an embedded page (renderer/space-bar.js). */
const BAR_HEIGHT = 28;

/** Where an address points, without query and fragment: "https://host:port/pfad" (no trailing slash). */
function placeOf(text) {
  try {
    const url = new URL(text);
    if (!['http:', 'https:', 'file:'].includes(url.protocol)) return '';
    return `${url.protocol}//${url.host}${url.pathname.replace(/\/+$/, '')}`;
  } catch (_) {
    return '';
  }
}

/**
 * The bar of the space on screen: shown once the page has left its start address, with "Zurück"
 * when its history allows it. At the start address there is no bar: going back from there only
 * leads into the sign-in detour the page came through. A status card (service not there) gets
 * none either. Only yes/no reach the renderer, never an address.
 * landed: the places the page went to on its own right after loading (e.g. "/" -> "/anmelden");
 * they count as the start as well.
 */
function barState(startUrl, currentUrl, canGoBack, card, landed = []) {
  const here = placeOf(currentUrl);
  const start = placeOf(startUrl);
  const verlassen = Boolean(!card && here && start && here !== start && !landed.includes(here));
  return { verlassen, zurueck: verlassen && Boolean(canGoBack) };
}

/** How long after a load a navigation still counts as the page landing by itself (a redirect). */
const LANDING_MS = 5000;

/**
 * Where "Zurück" leads: the nearest earlier history entry that shows a different page. Entries
 * with the same address (a sign-in detour, a redirect, a reload) are skipped, so one press always
 * changes what is on screen. An entry whose address is not known counts as different.
 * places: index -> place (see placeOf), active: the index on screen. Returns the index, or -1.
 */
function backTarget(places, active) {
  const here = places[active];
  for (let i = active - 1; i >= 0; i--) {
    if (!places[i] || places[i] !== here) return i;
  }
  return -1;
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
    this._issued = new Map(); // id -> access cookie set for this space (main process only)
    this._pathOnOpen = new Map(); // id -> address inside the space to go to when it is opened next (goTo)
    this._wanted = new Map();     // id -> { target, detour } a path on its way, see _navigated
    this._places = new Map();     // id -> [place per history index], see _remember and backTarget
    this._landing = new Map();    // id -> { until, places } where the page went by itself after a load
    this._now = dependencies.now || Date.now;
    this.spaces = new Map(resolveSpaces(this._env).map((space) => [space.id, space]));
    this.views = new Map();   // id -> { view, result }
    this.visibleId = null;
    this.topOffset = 32 + 43; // titlebar + tab bar, as for the other overlays
    if (mainWindow) mainWindow.on('resize', () => this._updateBounds());
  }

  has(id) { return this.spaces.has(id); }

  /** True when `sender` is the page the app ships for this space (its own view, a local file). */
  ownsPage(id, sender) {
    const space = this.spaces.get(id);
    const entry = this.views.get(id);
    if (!space || !space.file || !entry || !sender || entry.view.webContents !== sender) return false;
    const url = typeof sender.getURL === 'function' ? sender.getURL() : '';
    return typeof url === 'string' && url.startsWith('file:');
  }

  /** Loads the start of a space; what the page does by itself in the next moments is its landing. */
  _startLoad(id) {
    this._landing.set(id, { until: this._now() + LANDING_MS, places: [] });
    return this._load(id);
  }

  _load(id) {
    const space = this.spaces.get(id);
    const entry = this.views.get(id);
    entry.result = null;
    return loadOverlay(entry.view.webContents, { space: space.label, targets: this._targets(space), hint: space.hint },
      { ...this._overlayDeps, onResult: (result) => { entry.result = result; } });
  }

  _targets(space) {
    if (space.file) return [{ kind: 'file', path: space.file }];
    if (!space.url) return [];
    const onOpen = this._pathOnOpen.get(space.id);
    this._pathOnOpen.delete(space.id);
    const target = { kind: 'url', url: onOpen || space.url, expectTitle: space.expectTitle };
    // The check before loading runs in the main process, outside the view's session: without
    // the access cookie it would see the refusal (403) that the signed-in page never gets.
    const cookie = this._issued.get(space.id);
    if (cookie) target.headers = { Cookie: `${cookie.name}=${cookie.value}` };
    // The same for a key: the view sends it (onBeforeSendHeaders), so the check sends it too.
    // The target is the space's own address or a page of it, never another origin.
    const auth = authFor(space, this._env);
    if (auth && new URL(target.url).origin === new URL(space.url).origin) {
      target.headers = { ...(target.headers || {}), Authorization: auth.header };
    }
    return [target];
  }

  _create(id) {
    const space = this.spaces.get(id);
    const webPreferences = {
      partition: `persist:space-${id}`, // each space keeps its own sign-in
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    };
    // Only a page shipped with the app gets a bridge; a remote page never does.
    if (space.file && space.preload) webPreferences.preload = path.join(__dirname, space.preload);
    const view = new this.BrowserView({ webPreferences });
    // H3: a space with a look block gets the VibeMind look after every load, accent = its scene colour.
    // Only our own pages have one so far; a service of another session is left as it is.
    if (space.look) {
      applyVibeMindLook(view.webContents, space.id, { extraCss: space.look, accentRgb: rgbOf(space.color),
        logger: { warn: (m) => this._log.log(m) } });
    }
    const auth = authFor(space, this._env);
    if (auth) {
      view.webContents.session.webRequest.onBeforeSendHeaders({ urls: auth.urls }, (details, callback) => {
        callback({ requestHeaders: fromOwnPage(details, auth.origins)
          ? withAuthorization(details.requestHeaders, auth.header) : details.requestHeaders });
      });
      // A view that carries a key stays on its own origin; another address opens in the browser.
      view.webContents.on('will-navigate', (event, url) => {
        let target;
        try { target = new URL(url); } catch (_) { event.preventDefault(); return; }
        if (auth.origins.includes(target.origin)) return;
        event.preventDefault();
        if (target.protocol === 'http:' || target.protocol === 'https:') this.shell.openExternal(url);
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
    view.webContents.on('did-navigate', (_event, url) => { this._remember(id); this._navigated(id, url); this._reportBar(id); });
    view.webContents.on('did-navigate-in-page', () => { this._remember(id); this._reportBar(id); });
    this.views.set(id, { view, result: null });
    if (space.access && space.url) {
      this._ready.set(id, this._signIn(space, view).then(() => { this._startLoad(id); }));
    } else {
      this._startLoad(id); // nothing to wait for
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
      this._issued.set(space.id, cookie);
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
    } else if ((entry.result && !entry.result.ok) || this._pathOnOpen.has(id)) {
      this._startLoad(id); // a status card: look again, the service may be up now; or a path is waiting
    }
    this.mainWindow.setBrowserView(entry.view);
    this.visibleId = id;
    this._reportBar(id);
    this._log.log(`[ExternalSpaces] ${this.spaces.get(id).label} shown`);
    return true;
  }

  /** The start address of a space: its configured address, or its page shipped with the app. */
  _startUrl(space) {
    if (space.url) return space.url;
    return space.file ? require('node:url').pathToFileURL(space.file).href : '';
  }

  /** Works out the bar for the space on screen, moves the page below it and tells the renderer. */
  _reportBar(id) {
    if (id !== this.visibleId) return;
    const entry = this.views.get(id);
    const space = this.spaces.get(id);
    const contents = entry && entry.view.webContents;
    const state = contents && typeof contents.getURL === 'function'
      ? barState(this._startUrl(space), contents.getURL(), this._backIndex(id) >= 0, Boolean(entry.result && !entry.result.ok),
        (this._landing.get(id) || { places: [] }).places)
      : { verlassen: false, zurueck: false };
    this.barShown = state.verlassen;
    this._updateBounds();
    this._sendBar({ space: id, ...state });
  }

  _sendBar(state) {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.webContents.send('python-message', { type: 'external_space_nav', ...state });
    }
  }

  /** Notes the address of the history entry now on screen (Electron 28 cannot list them). */
  _remember(id) {
    const entry = this.views.get(id);
    const contents = entry && entry.view.webContents;
    const landing = this._landing.get(id);
    if (landing && contents && typeof contents.getURL === 'function' && this._now() <= landing.until) {
      const place = placeOf(contents.getURL());
      if (place && !landing.places.includes(place)) landing.places.push(place);
    }
    if (!contents || typeof contents.getActiveIndex !== 'function') return;
    if (!this._places.has(id)) this._places.set(id, []);
    this._places.get(id)[contents.getActiveIndex()] = placeOf(contents.getURL());
  }

  /** The history index "Zurück" goes to, or -1 (see backTarget); plain canGoBack where indexes are missing. */
  _backIndex(id) {
    const entry = this.views.get(id);
    const contents = entry && entry.view.webContents;
    if (!contents || !contents.canGoBack || !contents.canGoBack()) return -1;
    if (typeof contents.getActiveIndex !== 'function' || typeof contents.goToIndex !== 'function') {
      return Number.MAX_SAFE_INTEGER;    // unknown: one plain step back
    }
    return backTarget(this._places.get(id) || [], contents.getActiveIndex());
  }

  /** "Zurück": to the previous page that looks different, skipping entries with the same address. */
  back(id) {
    const entry = id === this.visibleId && this.views.get(id);
    const contents = entry && entry.view.webContents;
    const target = entry ? this._backIndex(id) : -1;
    if (target < 0) return false;
    if (target === Number.MAX_SAFE_INTEGER) contents.goBack();
    else contents.goToIndex(target);
    return true;
  }

  /** "Start": the start address of the space again, with its check and sign-in as on first opening. */
  home(id) {
    if (id !== this.visibleId || !this.views.has(id)) return false;
    this._pathOnOpen.delete(id);
    this._wanted.delete(id);
    this._startLoad(id);
    return true;
  }

  /**
   * Sends the page of a space to one of its own paths, in the same session (the sign-in stays).
   * A space that is not open yet goes there when it is opened next. Returns whether the path was taken.
   */
  goTo(id, pathText) {
    const space = this.spaces.get(id);
    const target = space ? pathTarget(space.url, pathText, space.paths) : '';
    if (!target) return false;
    const entry = this.views.get(id);
    if (!entry) {
      this._pathOnOpen.set(id, target);
      return true;
    }
    // A status card means the service is not there; the next opening tries the path again.
    if (entry.result && !entry.result.ok) {
      this._pathOnOpen.set(id, target);
    } else {
      this._wanted.set(id, { target, detour: '' });
      entry.view.webContents.loadURL(target);
    }
    return true;
  }

  /**
   * The page of a space arrived somewhere. A sign-in that ran out sends a wanted path to the
   * sign-in page instead; the page does not come back by itself afterwards. So the path is
   * remembered and loaded once more as soon as the page leaves that detour (the user signed in).
   */
  _navigated(id, url) {
    const wanted = this._wanted.get(id);
    const entry = this.views.get(id);
    if (!wanted || !entry) return;
    let here;
    try { here = new URL(url); } catch (_) { return; }
    const goal = new URL(wanted.target);
    if (here.origin !== goal.origin) return;
    if (here.pathname === goal.pathname) {
      this._wanted.delete(id); // arrived
    } else if (!wanted.detour) {
      wanted.detour = here.pathname; // sent elsewhere: wait there
    } else if (here.pathname !== wanted.detour) {
      this._wanted.delete(id); // left the detour: try the path once more, and only once
      entry.view.webContents.loadURL(wanted.target);
    }
  }

  hideAll() {
    if (!this.visibleId) return;
    if (this.mainWindow) this.mainWindow.setBrowserView(null);
    this.visibleId = null;
    this.barShown = false;
    this._sendBar({ space: null, verlassen: false, zurueck: false });
  }

  getIsVisible() { return Boolean(this.visibleId); }

  _updateBounds() {
    const entry = this.visibleId && this.views.get(this.visibleId);
    if (!entry || !this.mainWindow) return;
    const bounds = this.mainWindow.getContentBounds();
    const top = this.topOffset + (this.barShown ? BAR_HEIGHT : 0);
    entry.view.setBounds({ x: 0, y: top, width: bounds.width, height: bounds.height - top });
  }

  destroy() {
    this.hideAll();
    this.views.clear();
  }
}

module.exports = {
  EXTERNAL_SPACES, resolveSpaces, describeForRenderer, authFor, fromOwnPage, withAuthorization, pathTarget, parsePaths, ExternalSpaceManager,
  barState, backTarget, BAR_HEIGHT, LANDING_MS,
};
