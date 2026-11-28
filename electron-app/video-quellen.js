/**
 * The Video space shows two sources: Laura (the editor) and "Aus dem Marketing", the reels the
 * marketing service built or was handed (its page /oberflaeche/reels: tabs Fertig, In Arbeit,
 * Fehlgeschlagen, Archiv; finished reels play in the card).
 *
 * The marketing page is the one the Marketing space already embeds (external-spaces.js): same
 * address (MARKETING_UI_URL), same key (MARKETING_UI_KEY as Bearer), added here in the main
 * process and only to requests of that page itself; the page never sees the key. It runs in its
 * own session (one request listener per session), stays on its own origin and opens anything else
 * in the browser. No new interface of the service is used.
 *
 * A bar of 28 px above the page (video-quellen.html, a file of the app) switches between the two.
 * Only the bar may switch (its webContents is checked); it gets yes/no, never an address.
 */
'use strict';

const path = require('node:path');
const { resolveSpaces, authFor, fromOwnPage, withAuthorization } = require('./external-spaces');
const { loadOverlay } = require('./overlay-status');

const BAR_HEIGHT = 28;
const QUELLEN = Object.freeze(['laura', 'marketing']);
const MARKETING_PARTITION = 'persist:video-marketing';
const MARKETING_PFAD = '/oberflaeche/reels';
const HINT = 'Die Videos kommen vom Marketing-Dienst, der außerhalb der App läuft. Sobald er gestartet ist, „Aus dem Marketing" erneut wählen.';

/** Where the reels of the marketing service are, with its key; null when no address is known. */
function marketingTarget(env = process.env) {
  const space = resolveSpaces(env).find((s) => s.id === 'marketing');
  if (!space || !space.url) return null;
  let url;
  try { url = new URL(MARKETING_PFAD, space.url); } catch (_) { return null; }
  return { url: url.href, origin: url.origin, auth: authFor(space, env) };
}

function quelleOf(value) {
  return QUELLEN.includes(value) ? value : 'laura';
}

class VideoQuellen {
  constructor({ mainWindow, BrowserView, shell, env = process.env, logger = console, overlayDeps = {}, topOffset = 75 } = {}) {
    this.mainWindow = mainWindow;
    this.BrowserView = BrowserView;
    this.shell = shell;
    this.env = env;
    this.logger = logger;
    this.overlayDeps = overlayDeps;
    this.topOffset = topOffset;
    this.quelle = 'laura';
    this.barView = null;
    this.marketingView = null;
    this.marketingResult = null;
    this.lauraView = null;
    this.visible = false;
  }

  /** Whether this window can show two views at once (a test window without it keeps the old way). */
  static supported(mainWindow) {
    return Boolean(mainWindow) && typeof mainWindow.addBrowserView === 'function' && typeof mainWindow.removeBrowserView === 'function';
  }

  _bar() {
    if (this.barView) return this.barView;
    this.barView = new this.BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'video-quellen-preload.js'),
        contextIsolation: true, nodeIntegration: false, sandbox: true,
      },
    });
    this.barView.webContents.on('did-finish-load', () => this._sendState());
    this.barView.webContents.on('will-navigate', (event) => event.preventDefault());
    this.barView.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
    Promise.resolve(this.barView.webContents.loadFile(path.join(__dirname, 'video-quellen.html')))
      .catch(() => this.logger.warn('[VideoQuellen] Leiste nicht geladen'));
    return this.barView;
  }

  _marketing() {
    if (this.marketingView) return this.marketingView;
    const target = marketingTarget(this.env);
    const view = new this.BrowserView({
      webPreferences: { partition: MARKETING_PARTITION, contextIsolation: true, nodeIntegration: false, sandbox: true },
    });
    this.marketingView = view;
    const auth = target && target.auth;
    if (auth) {
      view.webContents.session.webRequest.onBeforeSendHeaders({ urls: auth.urls }, (details, callback) => {
        callback({ requestHeaders: fromOwnPage(details, auth.origins)
          ? withAuthorization(details.requestHeaders, auth.header) : details.requestHeaders });
      });
    }
    const origins = auth ? auth.origins : (target ? [target.origin] : []);
    view.webContents.on('will-navigate', (event, url) => {
      let to;
      try { to = new URL(url); } catch (_) { event.preventDefault(); return; }
      if (origins.includes(to.origin)) return;
      event.preventDefault();
      if (to.protocol === 'http:' || to.protocol === 'https:') this.shell.openExternal(url);
    });
    view.webContents.setWindowOpenHandler(({ url }) => {
      if (/^https?:/i.test(String(url))) this.shell.openExternal(url);
      return { action: 'deny' };
    });
    this._loadMarketing();
    return view;
  }

  _loadMarketing() {
    const target = marketingTarget(this.env);
    const targets = target ? [{ kind: 'url', url: target.url,
      ...(target.auth ? { headers: { Authorization: target.auth.header } } : {}) }] : [];
    this.marketingResult = null;
    this.marketingReady = loadOverlay(this.marketingView.webContents, { space: 'Aus dem Marketing', targets, hint: HINT },
      { ...this.overlayDeps, onResult: (result) => { this.marketingResult = result; } });
  }

  _content() {
    return this.quelle === 'marketing' ? this._marketing() : this.lauraView;
  }

  /** Shows the bar and the chosen source; lauraView is the view of the Video manager. */
  show(lauraView) {
    this.lauraView = lauraView;
    this.mainWindow.setBrowserView(this._bar());
    if (this.quelle === 'marketing' && this.marketingResult && !this.marketingResult.ok) this._loadMarketing();
    const content = this._content();
    if (content) this.mainWindow.addBrowserView(content);
    this.visible = true;
    this.updateBounds();
    this._sendState();
  }

  hide() {
    this.visible = false;
  }

  /** Switch the source; only the bar of this manager may ask. Returns whether it switched. */
  choose(sender, wanted) {
    if (!this.barView || sender !== this.barView.webContents) return false;
    const next = quelleOf(wanted);
    if (next === this.quelle) { this._sendState(); return false; }
    const before = this.visible ? this._content() : null;
    this.quelle = next;
    if (this.visible) {
      if (before) this.mainWindow.removeBrowserView(before);
      if (next === 'marketing' && this.marketingView && this.marketingResult && !this.marketingResult.ok) this._loadMarketing();
      const content = this._content();
      if (content) this.mainWindow.addBrowserView(content);
      this.updateBounds();
    }
    this._sendState();
    this.logger.info(`[VideoQuellen] ${next === 'marketing' ? 'Aus dem Marketing' : 'Laura'} gezeigt`);
    return true;
  }

  updateBounds() {
    if (!this.visible || !this.mainWindow) return;
    const b = this.mainWindow.getContentBounds();
    if (this.barView) this.barView.setBounds({ x: 0, y: this.topOffset, width: b.width, height: BAR_HEIGHT });
    const content = this._content();
    const top = this.topOffset + BAR_HEIGHT;
    if (content) content.setBounds({ x: 0, y: top, width: b.width, height: Math.max(0, b.height - top) });
  }

  _sendState() {
    if (!this.barView || (this.barView.webContents.isDestroyed && this.barView.webContents.isDestroyed())) return;
    this.barView.webContents.send('video-quelle-stand', { quelle: this.quelle, marketing: Boolean(marketingTarget(this.env)) });
  }

  destroy() {
    for (const view of [this.barView, this.marketingView]) {
      if (view && view.webContents && typeof view.webContents.destroy === 'function') view.webContents.destroy();
    }
    this.barView = null;
    this.marketingView = null;
    this.visible = false;
  }
}

module.exports = { VideoQuellen, marketingTarget, quelleOf, BAR_HEIGHT, MARKETING_PARTITION, MARKETING_PFAD, QUELLEN };
