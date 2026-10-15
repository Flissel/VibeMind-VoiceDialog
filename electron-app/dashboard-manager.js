/**
 * Dashboard Manager for VibeMind
 *
 * Manages the Coding Engine Dashboard as a BrowserView overlay.
 * Shows the React-based dashboard when user navigates to Project Space.
 */

const { loadOverlay, resolveElectronParts } = require('./overlay-status');
const path = require('path');

const _DM_C = '\x1b[97m', _RST = '\x1b[0m'; // White Bold (Dashboard)
function _dmLog(...a) { process.stdout.write(`${_DM_C}[DashboardManager] ${a.join(' ')}${_RST}\n`); }

// Quelle: DASHBOARD_DEV_URL (muss die Coding-Engine-App "DaveLovable" sein) oder der
// gebaute Stand im Coding_engine-Submodul. Ohne beides: Statuskarte. Die fruehere
// Vorgabe :5173 entfaellt - dort laeuft inzwischen der Rowboat-Vite-Server.

class DashboardManager {
  constructor(mainWindow, dependencies = {}) {
    const { BrowserView } = resolveElectronParts(dependencies, ['BrowserView']);
    this.BrowserView = BrowserView;
    this._env = dependencies.env || process.env;
    this._overlayDeps = dependencies.overlayDeps || {};
    this.overlayReady = null;
    this.mainWindow = mainWindow;
    this.dashboardView = null;
    this.isVisible = false;

    // Dashboard source: DASHBOARD_DEV_URL (explizit) sonst gebauter Stand im Submodul;
    // ohne beides zeigt createView() die Statuskarte.
    this.dashboardUrl = this._env.DASHBOARD_DEV_URL || '';
    this.dashboardPath = dependencies.dashboardPath || path.join(__dirname, '..', 'python', 'spaces',
      'coding', 'Coding_engine', 'web-app', 'front', 'dist', 'index.html');

    this.isDev = !!this.dashboardUrl;

    // Titlebar (32px) + Space Nav Bar (42px) to offset the view
    this.titlebarHeight = 74;

    // Listen for window resize
    if (this.mainWindow) {
      this.mainWindow.on('resize', () => {
        if (this.isVisible && this.dashboardView) {
          this.updateBounds();
        }
      });
    }
  }

  /**
   * Prueft das Ziel und laedt es bzw. die Statuskarte. Wird beim Erzeugen der Ansicht,
   * bei reload() und bei show() nach einer Statuskarte erneut aufgerufen.
   */
  _startOverlay() {
    this.overlayResult = null;
    const targets = [];
    if (this.dashboardUrl) targets.push({ kind: 'url', url: this.dashboardUrl, expectTitle: /DaveLovable/i });
    targets.push({ kind: 'file', path: this.dashboardPath });
    _dmLog('Pruefe und lade:', targets.map((t) => t.url || t.path).join(' | '));
    this.overlayReady = loadOverlay(this.dashboardView.webContents, { space: 'Dashboard (Coding Engine)', targets }, { ...this._overlayDeps, onResult: (r) => { this.overlayResult = r; } });
    return this.overlayReady;
  }

  _recheckOverlay() {
    if (this.overlayResult && !this.overlayResult.ok && this.dashboardView) this._startOverlay();
  }

  /**
   * Create the BrowserView for the dashboard
   */
  createView() {
    if (this.dashboardView) {
      return this.dashboardView;
    }

    this.dashboardView = new this.BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'dashboard-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    });

    this._startOverlay();

    // Open DevTools always while debugging the embed
    this.dashboardView.webContents.openDevTools({ mode: 'detach' });

    // Log load failures explicitly
    this.dashboardView.webContents.on('did-fail-load', (_e, code, desc, url) => {
      _dmLog('did-fail-load', code, desc, url);
    });
    this.dashboardView.webContents.on('console-message', (_e, level, message, line, source) => {
      _dmLog(`[renderer:${level}] ${source}:${line} ${message}`);
    });

    return this.dashboardView;
  }

  /**
   * Show the dashboard overlay
   */
  show() {
    if (!this.mainWindow) {
      console.error('[DashboardManager] No main window available');
      return;
    }

    // Create view if not exists
    if (!this.dashboardView) {
      this.createView();
    } else {
      this._recheckOverlay();
    }

    // Add view to window
    this.mainWindow.setBrowserView(this.dashboardView);

    // Position the view
    this.updateBounds();

    this.isVisible = true;
    _dmLog('Dashboard shown');
  }

  /**
   * Hide the dashboard overlay
   */
  hide() {
    if (!this.mainWindow || !this.dashboardView) {
      return;
    }

    // Remove view from window
    this.mainWindow.setBrowserView(null);

    this.isVisible = false;
    _dmLog('Dashboard hidden');
  }

  /**
   * Toggle dashboard visibility
   */
  toggle() {
    if (this.isVisible) {
      this.hide();
    } else {
      this.show();
    }
  }

  /**
   * Update BrowserView bounds to match window size
   */
  updateBounds() {
    if (!this.mainWindow || !this.dashboardView) {
      return;
    }

    const bounds = this.mainWindow.getContentBounds();

    this.dashboardView.setBounds({
      x: 0,
      y: this.titlebarHeight,
      width: bounds.width,
      height: bounds.height - this.titlebarHeight,
    });
  }

  /**
   * Check if dashboard is currently visible
   */
  getIsVisible() {
    return this.isVisible;
  }

  /**
   * Reload the dashboard
   */
  reload() {
    if (this.dashboardView) {
      this._startOverlay();
    }
  }

  /**
   * Send message to dashboard
   */
  sendMessage(channel, data) {
    if (this.dashboardView) {
      this.dashboardView.webContents.send(channel, data);
    }
  }

  /**
   * Destroy the dashboard view
   */
  destroy() {
    if (this.dashboardView) {
      this.hide();
      // Note: BrowserView doesn't have a destroy method in newer Electron
      // Just remove reference
      this.dashboardView = null;
    }
  }
}

module.exports = DashboardManager;
