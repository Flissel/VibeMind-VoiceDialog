/**
 * Rowboat Manager for VibeMind (Spec vibemind-os 2026-10-17-rowboat-einbettung, Abschnitt 4).
 *
 * Zeigt die echte Rowboat-Oberflaeche als BrowserView im Roarboot-Space. Rowboat laeuft als eigener
 * Prozess (start_desktop.py --embed); diese Ansicht laedt Rowboats eigenen Preload, ihre Aufrufe
 * beantwortet Rowboats Hauptprozess ueber RowboatEmbedClient. Ohne Verbindung: Statuskarte.
 */
const { loadOverlay, loadStatus, resolveElectronParts } = require('./overlay-status');
const { APP_PARTITION, BROWSER_PANE_NOTE, attachEmbedIpc } = require('./rowboat-embed-view');

const APP_URL = 'app://-/index.html';
const _RB_C = '\x1b[94m', _RST = '\x1b[0m'; // Blue (Rowboat)
function _rbLog(...args) { process.stdout.write(`${_RB_C}[RowboatManager] ${args.join(' ')}${_RST}\n`); }

class RowboatManager {
  constructor(mainWindow, dependencies = {}) {
    const { BrowserView, shell, dialog } = resolveElectronParts(dependencies, ['BrowserView', 'shell', 'dialog']);
    if (!dependencies.client) throw new TypeError('RowboatManager braucht dependencies.client (RowboatEmbedClient)');
    this.BrowserView = BrowserView;
    this.shell = shell;
    this.dialog = dialog;
    this.client = dependencies.client;
    this._onNavigate = dependencies.onNavigate || null;
    this._pendingUrl = null;
    this._overlayDeps = dependencies.overlayDeps || {};
    this.mainWindow = mainWindow;
    this.rowboatView = null;
    this.isVisible = false;
    this.overlayReady = null;
    this.overlayResult = null;
    this._viewPreload = null;
    this._detachIpc = null;
    this._browserNoteShown = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    this.client.on('connected', () => this._onConnected());
    this.client.on('disconnected', () => { if (this.rowboatView) this._load(); });
    this.client.on('push', (channel, payload) => this._onPush(channel, payload));

    if (this.mainWindow) {
      this.mainWindow.on('resize', () => {
        if (this.isVisible && this.rowboatView) this.updateBounds();
      });
    }
  }

  _createView() {
    const preload = this.client.connected && this.client.info ? this.client.info.preloadPath : null;
    const view = new this.BrowserView({
      webPreferences: {
        ...(preload ? { preload } : {}),
        partition: APP_PARTITION,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        // PDFs in <iframe> wie in Rowboats eigenem Fenster
        plugins: true,
      },
    });
    this.rowboatView = view;
    this._viewPreload = preload;

    view.webContents.setWindowOpenHandler(({ url }) => {
      this.shell.openExternal(url);
      return { action: 'deny' };
    });
    // Wie in Rowboats Fenster: was nicht app:// ist, geht in den System-Browser.
    view.webContents.on('will-navigate', (event, url) => {
      if (url.startsWith('app://')) return;
      event.preventDefault();
      this.shell.openExternal(url);
    });
    // Rowboats macOS-Titelleisten-Reservierung entfernen (VibeMind hat eine eigene Titelleiste)
    view.webContents.on('dom-ready', () => {
      view.webContents.insertCSS('.titlebar-drag-region { -webkit-app-region: no-drag !important; }');
    });
    view.webContents.on('did-finish-load', () => {
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', { type: 'rowboat_view_status', ...loadStatus(this.overlayResult) });
      }
      _rbLog('Renderer loaded');
    });
    view.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'rowboat_view_status', status: 'error', message: `Load failed: ${errorDescription} (${errorCode})`,
        });
      }
      console.error('[RowboatManager] Load failed:', errorCode, errorDescription);
    });

    this._load();
    return view;
  }

  /** Laedt Rowboat (verbunden + Preload passt) oder die Statuskarte. */
  _load() {
    const view = this.rowboatView;
    if (this._detachIpc) { this._detachIpc(); this._detachIpc = null; }
    if (this.client.connected && this._viewPreload) {
      this._detachIpc = attachEmbedIpc(view.webContents, this.client, this.client.invokeChannels, {
        onBrowserPane: () => this._browserPaneNote(),
        consumePendingUrl: () => this.consumePendingUrl(),
      });
      this.overlayResult = { ok: true, target: APP_URL };
      this.overlayReady = view.webContents.loadURL(APP_URL).then(
        () => this.overlayResult,
        (err) => {
          _rbLog(`Laden fehlgeschlagen – ${err.message}`);
          return this.overlayResult;
        },
      );
      return this.overlayReady;
    }
    const reason = this.client.reason || 'Rowboat nicht verbunden';
    this.overlayReady = loadOverlay(view.webContents,
      { space: 'Rowboat', targets: [{ kind: 'unavailable', reason, target: 'Rowboat-Einbettung' }] },
      { ...this._overlayDeps, onResult: (r) => { this.overlayResult = r; } });
    return this.overlayReady;
  }

  /**
   * Rowboat-Navigation (rowboat://open?...) kommt als Push app:openUrl. Ist die Ansicht geladen, hoert sie
   * den Push selbst (attachEmbedIpc); sonst merken wir die URL, bis die Oberflaeche sie abholt.
   */
  _onPush(channel, payload) {
    if (channel !== 'app:openUrl') return;
    const url = payload && typeof payload.url === 'string' ? payload.url : null;
    if (!url) return;
    if (!this._detachIpc) this._pendingUrl = url;
    if (this._onNavigate) {
      try { this._onNavigate(url); } catch (err) { _rbLog(`onNavigate fehlgeschlagen – ${err.message}`); }
    }
  }

  /** Gibt die gemerkte Navigations-URL genau einmal zurueck. */
  consumePendingUrl() {
    const url = this._pendingUrl;
    this._pendingUrl = null;
    return url;
  }

  _onConnected() {
    if (!this.rowboatView) return;
    if (this._viewPreload === this.client.info.preloadPath) this._load();
    else this._rebuildView();
  }

  /** Der Preload steht beim Erzeugen fest: Ansicht ohne (oder mit anderem) Preload neu bauen. */
  _rebuildView() {
    const wasVisible = this.isVisible;
    this._disposeView();
    this._createView();
    if (wasVisible) {
      this.mainWindow.setBrowserView(this.rowboatView);
      this.updateBounds();
    }
  }

  _disposeView() {
    if (this._detachIpc) { this._detachIpc(); this._detachIpc = null; }
    if (!this.rowboatView) return;
    if (this.isVisible && this.mainWindow) this.mainWindow.setBrowserView(null);
    try { this.rowboatView.webContents.close(); } catch { /* schon zu */ }
    this.rowboatView = null;
  }

  _browserPaneNote() {
    if (this._browserNoteShown) return;
    this._browserNoteShown = true;
    this.dialog.showMessageBox(this.mainWindow, {
      type: 'info', message: BROWSER_PANE_NOTE, buttons: ['In Rowboat öffnen', 'Abbrechen'], defaultId: 0, cancelId: 1,
    }).then(({ response }) => {
      if (response === 0) this.openInRowboat();
    }).catch(() => {});
  }

  /** Holt Rowboats eigenes (verstecktes) Fenster nach vorn. */
  openInRowboat() {
    return this.client.showApp();
  }

  show() {
    if (!this.mainWindow) {
      console.error('[RowboatManager] No main window available');
      return;
    }
    if (!this.rowboatView) this._createView();
    else if (this.overlayResult && !this.overlayResult.ok) this._onConnectedOrCard();
    this.mainWindow.setBrowserView(this.rowboatView);
    this.updateBounds();
    this.isVisible = true;
    _rbLog('Rowboat shown');
  }

  /** show() nach einer Statuskarte: verbunden → Rowboat laden, sonst Karte mit aktuellem Grund. */
  _onConnectedOrCard() {
    if (this.client.connected) this._onConnected();
    else this._load();
  }

  hide() {
    if (!this.mainWindow || !this.rowboatView) return;
    this.mainWindow.setBrowserView(null);
    this.isVisible = false;
    _rbLog('Rowboat hidden');
  }

  toggle() {
    if (this.isVisible) this.hide();
    else this.show();
  }

  updateBounds() {
    if (!this.mainWindow || !this.rowboatView) return;
    const bounds = this.mainWindow.getContentBounds();
    this.rowboatView.setBounds({ x: 0, y: this.topOffset, width: bounds.width, height: bounds.height - this.topOffset });
  }

  getIsVisible() {
    return this.isVisible;
  }

  reload() {
    if (this.rowboatView) this._load();
  }

  destroy() {
    this._disposeView();
    this.isVisible = false;
  }
}

module.exports = RowboatManager;
