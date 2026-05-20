/**
 * Dashboard Manager for VibeMind
 *
 * Manages the Coding Engine Dashboard as a BrowserView overlay.
 * Shows the React-based dashboard when user navigates to Project Space.
 */

const { BrowserView } = require('electron');
const path = require('path');

const _DM_C = '\x1b[97m', _RST = '\x1b[0m'; // White Bold (Dashboard)
function _dmLog(...a) { process.stdout.write(`${_DM_C}[DashboardManager] ${a.join(' ')}${_RST}\n`); }

// 2026-05-21: the legacy file:// fallback targets a git submodule
// (python/spaces/coding/Coding_engine) that is uninstantiated in most
// checkouts — Chromium blocks with "Not allowed to load local resource".
// Default to the running Swarm-Stack frontend on :5173 instead; the
// file path is the ultimate fallback for offline-with-built-submodule.
const STACK_FRONTEND_URL = 'http://localhost:5173';

class DashboardManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.dashboardView = null;
    this.isVisible = false;

    // Dashboard source — precedence:
    //   1. DASHBOARD_DEV_URL env (explicit override from launcher / .env)
    //   2. Swarm-Stack coding-frontend on :5173 (the production path
    //      since the stack migration: vibemind_coding-frontend in
    //      infra/swarm/vibemind-stack.yml)
    //   3. file:// fallback into the uninstanced submodule (legacy)
    this.dashboardUrl = process.env.DASHBOARD_DEV_URL || STACK_FRONTEND_URL;
    this.dashboardPath = path.join(__dirname, '..', 'python', 'spaces',
      'coding', 'Coding_engine', 'web-app', 'front', 'dist', 'index.html');

    // We're "dev" (= load by URL) whenever any URL is configured —
    // which is now the default. file:// only happens if the URL can't
    // be reached, see createView() below.
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
   * Create the BrowserView for the dashboard
   */
  createView() {
    if (this.dashboardView) {
      return this.dashboardView;
    }

    this.dashboardView = new BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'dashboard-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    });

    // Load the dashboard — URL first, file:// only if URL fails.
    if (this.isDev) {
      _dmLog('Loading from URL:', this.dashboardUrl);
      this.dashboardView.webContents.loadURL(this.dashboardUrl).catch((err) => {
        _dmLog('URL load failed (' + err.message + '), trying file:// fallback:',
               this.dashboardPath);
        this.dashboardView.webContents.loadFile(this.dashboardPath).catch((err2) => {
          _dmLog('file:// fallback also failed:', err2.message);
          _dmLog('Hint: start the Swarm-Stack (scripts/vibemind-start.ps1) so '
                 + this.dashboardUrl + ' becomes reachable, OR init the '
                 + 'python/spaces/coding/Coding_engine submodule + build its web-app.');
        });
      });
    } else {
      _dmLog('Loading from file:', this.dashboardPath);
      this.dashboardView.webContents.loadFile(this.dashboardPath);
    }

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
      this.dashboardView.webContents.reload();
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
