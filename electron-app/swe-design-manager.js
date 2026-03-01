/**
 * SWE Design Manager for VibeMind
 *
 * Delegates to the RE Dashboard embed module from swe_desgine to manage
 * the Requirements Wizard BrowserView. The wizard (6 steps) maps to
 * shuttle checkpoints in the factory pipeline.
 *
 * Server lifecycle:
 *   show()    → start server (if needed) + create BrowserView
 *   hide()    → remove BrowserView (server stays alive for fast re-show)
 *   destroy() → stop server + kill Python process
 */

const path = require('path');
const {
  startREServer,
  stopREServer,
  createREDashboardView,
  removeREDashboardView,
  isServerRunning,
  getServerPort,
} = require('../python/spaces/shuttles/swe_desgine/requirements_engineer/electron/embed');

class SweDesignManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.view = null;
    this.isVisible = false;
    this._starting = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    // Python path: prefer .venv312 from project root
    const projectRoot = path.resolve(__dirname, '..');
    const venv312 = path.join(projectRoot, '.venv312', 'Scripts', 'python.exe');
    const fs = require('fs');
    this.pythonPath = fs.existsSync(venv312) ? venv312 : 'python';

    // RE project root (where `requirements_engineer` package lives)
    this.reProjectRoot = path.join(
      projectRoot, 'python', 'spaces', 'shuttles', 'swe_desgine'
    );

    this.port = 8085;

    // Resize handler
    if (this.mainWindow) {
      this.mainWindow.on('resize', () => {
        if (this.isVisible && this.view) {
          this._updateBounds();
        }
      });
    }
  }

  /**
   * Show the SWE Design wizard BrowserView.
   * Starts the Python dashboard server on first call.
   */
  async show() {
    if (!this.mainWindow) {
      console.error('[SweDesignManager] No main window available');
      return;
    }

    // Prevent concurrent start attempts
    if (this._starting) {
      console.log('[SweDesignManager] Already starting, please wait...');
      return;
    }

    try {
      // Start server if not running
      if (!isServerRunning()) {
        this._starting = true;
        console.log('[SweDesignManager] Starting RE dashboard server...');
        this.port = await startREServer({
          pythonPath: this.pythonPath,
          projectRoot: this.reProjectRoot,
          port: this.port,
        });
        this._starting = false;
      }

      // Create BrowserView if needed
      if (!this.view) {
        const bounds = this._getBounds();
        this.view = createREDashboardView(this.mainWindow, this.port, {
          bounds,
          autoResize: true,
        });

        // Handle external links
        this.view.webContents.setWindowOpenHandler(({ url }) => {
          require('electron').shell.openExternal(url);
          return { action: 'deny' };
        });

        // Notify renderer of load status
        this.view.webContents.on('did-finish-load', () => {
          if (this.mainWindow && !this.mainWindow.isDestroyed()) {
            this.mainWindow.webContents.send('python-message', {
              type: 'swedesign_view_status',
              status: 'ready',
            });
          }
          console.log('[SweDesignManager] Wizard loaded');
        });

        this.view.webContents.on('did-fail-load', (_ev, code, desc) => {
          if (this.mainWindow && !this.mainWindow.isDestroyed()) {
            this.mainWindow.webContents.send('python-message', {
              type: 'swedesign_view_status',
              status: 'error',
              message: `Load failed: ${desc} (${code})`,
            });
          }
          console.error('[SweDesignManager] Load failed:', code, desc);
        });
      } else {
        // Re-attach existing view
        this.mainWindow.setBrowserView(this.view);
        this._updateBounds();
      }

      this.isVisible = true;
      console.log('[SweDesignManager] Shown');
    } catch (err) {
      this._starting = false;
      console.error('[SweDesignManager] Failed to show:', err.message);
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'swedesign_view_status',
          status: 'error',
          message: err.message,
        });
      }
    }
  }

  /**
   * Hide the BrowserView (server stays alive for fast re-show).
   */
  hide() {
    if (!this.mainWindow || !this.view) return;
    removeREDashboardView(this.mainWindow, this.view);
    this.isVisible = false;
    console.log('[SweDesignManager] Hidden');
  }

  /**
   * Relay a push event to the SWE Design BrowserView
   */
  relayEvent(channel, payload) {
    if (this.view && !this.view.webContents.isDestroyed()) {
      this.view.webContents.send(channel, payload);
    }
  }

  /**
   * Reload the wizard content
   */
  reload() {
    if (this.view && !this.view.webContents.isDestroyed()) {
      this.view.webContents.reload();
    }
  }

  /**
   * Check visibility
   */
  getIsVisible() {
    return this.isVisible;
  }

  /**
   * Destroy the view and stop the server.
   */
  destroy() {
    if (this.view) {
      this.hide();
      this.view = null;
    }
    stopREServer();
    console.log('[SweDesignManager] Destroyed');
  }

  // -- Private helpers --

  _getBounds() {
    const wb = this.mainWindow.getContentBounds();
    return {
      x: 0,
      y: this.topOffset,
      width: wb.width,
      height: wb.height - this.topOffset,
    };
  }

  _updateBounds() {
    if (!this.mainWindow || !this.view) return;
    this.view.setBounds(this._getBounds());
  }
}

module.exports = SweDesignManager;
