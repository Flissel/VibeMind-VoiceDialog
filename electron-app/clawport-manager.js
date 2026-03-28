/**
 * ClawPort Dashboard Manager for VibeMind
 *
 * Manages the ClawPort Dashboard as a BrowserView overlay.
 * Shown when user navigates to the Dashboard space.
 *
 * Pattern: identical to rowboat-manager.js (Rowboat Space).
 */

const { BrowserView } = require('electron');
const path = require('path');
const fs = require('fs');

const _CP_C = '\x1b[97m', _RST = '\x1b[0m'; // White Bold (ClawPort/Dashboard)
function _cpLog(...a) { process.stdout.write(`${_CP_C}[ClawPortManager] ${a.join(' ')}${_RST}\n`); }

class ClawPortManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.clawportView = null;
    this.isVisible = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    // Renderer dist path (dev vs production)
    this.isDev = !!process.env.CLAWPORT_DEV_URL;

    // Listen for window resize
    if (this.mainWindow) {
      this.mainWindow.on('resize', () => {
        if (this.isVisible && this.clawportView) {
          this.updateBounds();
        }
      });
    }
  }

  /**
   * Resolve path to built dashboard dist/index.html
   */
  _resolveRendererPath() {
    // Development: built dashboard in dashboard/dist
    const devPath = path.join(__dirname, 'dashboard', 'dist', 'index.html');
    // Production: extraResources
    const prodPath = path.join(process.resourcesPath || '', 'clawport-dashboard', 'index.html');

    if (fs.existsSync(prodPath)) return prodPath;
    if (fs.existsSync(devPath)) return devPath;
    return devPath; // Will fail gracefully if missing
  }

  /**
   * Create the BrowserView for the ClawPort dashboard
   */
  createView() {
    if (this.clawportView) return this.clawportView;

    this.clawportView = new BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'clawport-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false, // Required for contextBridge + ipcRenderer
      },
    });

    // Load renderer
    if (this.isDev) {
      _cpLog('Loading from dev server:', process.env.CLAWPORT_DEV_URL);
      this.clawportView.webContents.loadURL(process.env.CLAWPORT_DEV_URL);
    } else {
      const rendererPath = this._resolveRendererPath();
      _cpLog('Loading from file:', rendererPath);
      this.clawportView.webContents.loadFile(rendererPath);
    }

    // Open DevTools in development
    if (process.env.NODE_ENV === 'development' || this.isDev) {
      this.clawportView.webContents.openDevTools({ mode: 'detach' });
    }

    // Handle external link navigation
    this.clawportView.webContents.setWindowOpenHandler(({ url }) => {
      require('electron').shell.openExternal(url);
      return { action: 'deny' };
    });

    // Notify VibeMind renderer of load status
    this.clawportView.webContents.on('did-finish-load', () => {
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'clawport_view_status',
          status: 'ready',
        });
      }
      _cpLog('Dashboard loaded');
    });

    this.clawportView.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'clawport_view_status',
          status: 'error',
          message: `Load failed: ${errorDescription} (${errorCode})`,
        });
      }
      console.error('[ClawPortManager] Load failed:', errorCode, errorDescription);
    });

    return this.clawportView;
  }

  /**
   * Show the ClawPort overlay
   */
  show() {
    if (!this.mainWindow) {
      console.error('[ClawPortManager] No main window available');
      return;
    }

    if (!this.clawportView) {
      this.createView();
    }

    this.mainWindow.setBrowserView(this.clawportView);
    this.updateBounds();
    this.isVisible = true;
    _cpLog('Dashboard shown');
  }

  /**
   * Hide the ClawPort overlay
   */
  hide() {
    if (!this.mainWindow || !this.clawportView) return;

    this.mainWindow.setBrowserView(null);
    this.isVisible = false;
    _cpLog('Dashboard hidden');
  }

  /**
   * Toggle visibility
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
    if (!this.mainWindow || !this.clawportView) return;

    const bounds = this.mainWindow.getContentBounds();
    this.clawportView.setBounds({
      x: 0,
      y: this.topOffset,
      width: bounds.width,
      height: bounds.height - this.topOffset,
    });
  }

  /**
   * Check if ClawPort is currently visible
   */
  getIsVisible() {
    return this.isVisible;
  }

  /**
   * Relay a push event to the ClawPort BrowserView.
   * Called from main.js to forward Python messages.
   */
  relayEvent(channel, payload) {
    if (this.clawportView && !this.clawportView.webContents.isDestroyed()) {
      this.clawportView.webContents.send(channel, payload);
    }
  }

  /**
   * Reload the ClawPort dashboard
   */
  reload() {
    if (this.clawportView) {
      this.clawportView.webContents.reload();
    }
  }

  /**
   * Destroy the ClawPort view
   */
  destroy() {
    if (this.clawportView) {
      this.hide();
      this.clawportView = null;
    }
  }
}

module.exports = ClawPortManager;
