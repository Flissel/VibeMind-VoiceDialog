/**
 * Agent Farm Manager for VibeMind
 *
 * Manages the Agent Farm as a BrowserView overlay.
 * Shown when user clicks the barn in the 3D multiverse.
 *
 * Pattern: identical to clawport-manager.js (ClawPort Dashboard).
 */

const { BrowserView } = require('electron');
const path = require('path');
const fs = require('fs');

class AgentFarmManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.agentfarmView = null;
    this.isVisible = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    // Renderer dist path (dev vs production)
    this.isDev = !!process.env.AGENTFARM_DEV_URL;

    // Listen for window resize
    if (this.mainWindow) {
      this.mainWindow.on('resize', () => {
        if (this.isVisible && this.agentfarmView) {
          this.updateBounds();
        }
      });
    }
  }

  /**
   * Resolve path to built agentfarm dist/index.html
   */
  _resolveRendererPath() {
    // Development: built agentfarm in agentfarm/dist
    const devPath = path.join(__dirname, 'agentfarm', 'dist', 'index.html');
    // Production: extraResources
    const prodPath = path.join(process.resourcesPath || '', 'agentfarm', 'index.html');

    if (fs.existsSync(prodPath)) return prodPath;
    if (fs.existsSync(devPath)) return devPath;
    return devPath; // Will fail gracefully if missing
  }

  /**
   * Create the BrowserView for the Agent Farm
   */
  createView() {
    if (this.agentfarmView) return this.agentfarmView;

    this.agentfarmView = new BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'agentfarm-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false, // Required for contextBridge + ipcRenderer
      },
    });

    // Load renderer
    if (this.isDev) {
      console.log('[AgentFarmManager] Loading from dev server:', process.env.AGENTFARM_DEV_URL);
      this.agentfarmView.webContents.loadURL(process.env.AGENTFARM_DEV_URL);
    } else {
      const rendererPath = this._resolveRendererPath();
      console.log('[AgentFarmManager] Loading from file:', rendererPath);
      this.agentfarmView.webContents.loadFile(rendererPath);
    }

    // Open DevTools in development
    if (process.env.NODE_ENV === 'development' || this.isDev) {
      this.agentfarmView.webContents.openDevTools({ mode: 'detach' });
    }

    // Handle external link navigation
    this.agentfarmView.webContents.setWindowOpenHandler(({ url }) => {
      require('electron').shell.openExternal(url);
      return { action: 'deny' };
    });

    // Notify VibeMind renderer of load status
    this.agentfarmView.webContents.on('did-finish-load', () => {
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'agentfarm_view_status',
          status: 'ready',
        });
      }
      console.log('[AgentFarmManager] Agent Farm loaded');
    });

    this.agentfarmView.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'agentfarm_view_status',
          status: 'error',
          message: `Load failed: ${errorDescription} (${errorCode})`,
        });
      }
      console.error('[AgentFarmManager] Load failed:', errorCode, errorDescription);
    });

    return this.agentfarmView;
  }

  /**
   * Show the Agent Farm overlay
   */
  show() {
    if (!this.mainWindow) {
      console.error('[AgentFarmManager] No main window available');
      return;
    }

    if (!this.agentfarmView) {
      this.createView();
    }

    this.mainWindow.setBrowserView(this.agentfarmView);
    this.updateBounds();
    this.isVisible = true;
    console.log('[AgentFarmManager] Agent Farm shown');
  }

  /**
   * Hide the Agent Farm overlay
   */
  hide() {
    if (!this.mainWindow || !this.agentfarmView) return;

    this.mainWindow.setBrowserView(null);
    this.isVisible = false;
    console.log('[AgentFarmManager] Agent Farm hidden');
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
    if (!this.mainWindow || !this.agentfarmView) return;

    const bounds = this.mainWindow.getContentBounds();
    this.agentfarmView.setBounds({
      x: 0,
      y: this.topOffset,
      width: bounds.width,
      height: bounds.height - this.topOffset,
    });
  }

  /**
   * Check if Agent Farm is currently visible
   */
  getIsVisible() {
    return this.isVisible;
  }

  /**
   * Relay a push event to the Agent Farm BrowserView.
   * Called from main.js to forward Python messages.
   */
  relayEvent(channel, payload) {
    if (this.agentfarmView && !this.agentfarmView.webContents.isDestroyed()) {
      this.agentfarmView.webContents.send(channel, payload);
    }
  }

  /**
   * Reload the Agent Farm
   */
  reload() {
    if (this.agentfarmView) {
      this.agentfarmView.webContents.reload();
    }
  }

  /**
   * Destroy the Agent Farm view
   */
  destroy() {
    if (this.agentfarmView) {
      this.hide();
      this.agentfarmView = null;
    }
  }
}

module.exports = AgentFarmManager;
