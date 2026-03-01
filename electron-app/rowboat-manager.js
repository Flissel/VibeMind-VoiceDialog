/**
 * Rowboat Manager for VibeMind
 *
 * Manages the Rowboat Electron app renderer as a BrowserView overlay.
 * Shown when user navigates to the Roarboot space.
 *
 * Pattern: identical to dashboard-manager.js (Coding Engine Dashboard).
 * Addition: relayEvent() for pushing runs/workspace/service events to
 * the BrowserView (since BrowserView is not a BrowserWindow and thus
 * not reached by BrowserWindow.getAllWindows()).
 */

const { BrowserView } = require('electron');
const path = require('path');
const fs = require('fs');

class RowboatManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.rowboatView = null;
    this.isVisible = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    // Renderer dist path (dev vs production)
    this.isDev = !!process.env.ROWBOAT_DEV_URL;

    // Listen for window resize
    if (this.mainWindow) {
      this.mainWindow.on('resize', () => {
        if (this.isVisible && this.rowboatView) {
          this.updateBounds();
        }
      });
    }
  }

  /**
   * Resolve path to built renderer dist/index.html
   */
  _resolveRendererPath() {
    // Development: built renderer in submodule
    const devPath = path.join(
      __dirname, '..', 'python', 'spaces', 'rowboat', 'rowboat',
      'apps', 'x', 'apps', 'renderer', 'dist', 'index.html'
    );
    // Production: extraResources
    const prodPath = path.join(process.resourcesPath || '', 'rowboat-renderer', 'index.html');

    if (fs.existsSync(prodPath)) return prodPath;
    if (fs.existsSync(devPath)) return devPath;
    return devPath; // Will fail gracefully if missing
  }

  /**
   * Create the BrowserView for the Rowboat renderer
   */
  createView() {
    if (this.rowboatView) return this.rowboatView;

    this.rowboatView = new BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'rowboat-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false, // Required for contextBridge + ipcRenderer
      },
    });

    // Load renderer
    if (this.isDev) {
      console.log('[RowboatManager] Loading from dev server:', process.env.ROWBOAT_DEV_URL);
      this.rowboatView.webContents.loadURL(process.env.ROWBOAT_DEV_URL);
    } else {
      const rendererPath = this._resolveRendererPath();
      console.log('[RowboatManager] Loading from file:', rendererPath);
      this.rowboatView.webContents.loadFile(rendererPath);
    }

    // Open DevTools in development
    if (process.env.NODE_ENV === 'development' || this.isDev) {
      this.rowboatView.webContents.openDevTools({ mode: 'detach' });
    }

    // Handle external link navigation
    this.rowboatView.webContents.setWindowOpenHandler(({ url }) => {
      require('electron').shell.openExternal(url);
      return { action: 'deny' };
    });

    // CSS injection: remove Rowboat's macOS traffic-light reservation
    // (VibeMind handles its own titlebar at 32px)
    this.rowboatView.webContents.on('dom-ready', () => {
      this.rowboatView.webContents.insertCSS(`
        .titlebar-drag-region {
          -webkit-app-region: no-drag !important;
        }
      `);
    });

    // Notify VibeMind renderer of load status
    this.rowboatView.webContents.on('did-finish-load', () => {
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'rowboat_view_status',
          status: 'ready',
        });
      }
      console.log('[RowboatManager] Renderer loaded');
    });

    this.rowboatView.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'rowboat_view_status',
          status: 'error',
          message: `Load failed: ${errorDescription} (${errorCode})`,
        });
      }
      console.error('[RowboatManager] Load failed:', errorCode, errorDescription);
    });

    return this.rowboatView;
  }

  /**
   * Show the Rowboat overlay
   */
  show() {
    if (!this.mainWindow) {
      console.error('[RowboatManager] No main window available');
      return;
    }

    if (!this.rowboatView) {
      this.createView();
    }

    this.mainWindow.setBrowserView(this.rowboatView);
    this.updateBounds();
    this.isVisible = true;
    console.log('[RowboatManager] Rowboat shown');
  }

  /**
   * Hide the Rowboat overlay
   */
  hide() {
    if (!this.mainWindow || !this.rowboatView) return;

    this.mainWindow.setBrowserView(null);
    this.isVisible = false;
    console.log('[RowboatManager] Rowboat hidden');
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
    if (!this.mainWindow || !this.rowboatView) return;

    const bounds = this.mainWindow.getContentBounds();
    this.rowboatView.setBounds({
      x: 0,
      y: this.topOffset,
      width: bounds.width,
      height: bounds.height - this.topOffset,
    });
  }

  /**
   * Check if Rowboat is currently visible
   */
  getIsVisible() {
    return this.isVisible;
  }

  /**
   * Relay a push event to the Rowboat BrowserView.
   * Called from main.js after subscribing to bus/serviceBus.
   */
  relayEvent(channel, payload) {
    if (this.rowboatView && !this.rowboatView.webContents.isDestroyed()) {
      this.rowboatView.webContents.send(channel, payload);
    }
  }

  /**
   * Reload the Rowboat renderer
   */
  reload() {
    if (this.rowboatView) {
      this.rowboatView.webContents.reload();
    }
  }

  /**
   * Destroy the Rowboat view
   */
  destroy() {
    if (this.rowboatView) {
      this.hide();
      this.rowboatView = null;
    }
  }
}

module.exports = RowboatManager;
