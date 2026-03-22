/**
 * MiroFish Manager for VibeMind
 *
 * Manages the MiroFish-Offline web app (Flask+Vue on port 5001)
 * as a BrowserView overlay. Shown when user navigates to MiroFish space.
 *
 * Pattern: identical to agentfarm-manager.js.
 */

const { BrowserView } = require('electron');
const path = require('path');

class MiroFishManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.mirofishView = null;
    this.isVisible = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    // MiroFish Flask+Vue app URL
    this.mirofishUrl = process.env.MIROFISH_URL || 'http://localhost:3001';

    // Retry state for connection-refused errors
    this.retryCount = 0;
    this.maxRetries = 10;
    this.retryTimer = null;

    // Listen for window resize
    if (this.mainWindow) {
      this.mainWindow.on('resize', () => {
        if (this.isVisible && this.mirofishView) {
          this.updateBounds();
        }
      });
    }
  }

  /**
   * Create the BrowserView for MiroFish
   */
  createView() {
    if (this.mirofishView) return this.mirofishView;

    this.mirofishView = new BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'mirofish-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    });

    // Load MiroFish web app
    console.log('[MiroFishManager] Loading from:', this.mirofishUrl);
    this.mirofishView.webContents.loadURL(this.mirofishUrl);

    // Open DevTools in development
    if (process.env.NODE_ENV === 'development') {
      this.mirofishView.webContents.openDevTools({ mode: 'detach' });
    }

    // Handle external link navigation
    this.mirofishView.webContents.setWindowOpenHandler(({ url }) => {
      require('electron').shell.openExternal(url);
      return { action: 'deny' };
    });

    // Notify VibeMind renderer of load status
    this.mirofishView.webContents.on('did-finish-load', () => {
      this.retryCount = 0;
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'mirofish_view_status',
          status: 'ready',
        });
      }
      console.log('[MiroFishManager] MiroFish loaded');
    });

    this.mirofishView.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
      // ERR_CONNECTION_REFUSED (-102): server not up yet — retry with backoff
      if (errorCode === -102 && this.retryCount < this.maxRetries) {
        this.retryCount++;
        const delay = Math.min(1000 * this.retryCount, 5000);
        console.log(`[MiroFishManager] Server not ready, retry ${this.retryCount}/${this.maxRetries} in ${delay}ms`);
        this.retryTimer = setTimeout(() => {
          if (this.mirofishView && !this.mirofishView.webContents.isDestroyed()) {
            this.mirofishView.webContents.loadURL(this.mirofishUrl);
          }
        }, delay);
        return;
      }

      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'mirofish_view_status',
          status: 'error',
          message: `Load failed: ${errorDescription} (${errorCode})`,
        });
      }
      console.error('[MiroFishManager] Load failed:', errorCode, errorDescription);
    });

    return this.mirofishView;
  }

  /**
   * Show the MiroFish overlay
   */
  show() {
    if (!this.mainWindow) {
      console.error('[MiroFishManager] No main window available');
      return;
    }

    if (!this.mirofishView) {
      this.createView();
    }

    this.mainWindow.setBrowserView(this.mirofishView);
    this.updateBounds();
    this.isVisible = true;
    console.log('[MiroFishManager] MiroFish shown');
  }

  /**
   * Hide the MiroFish overlay
   */
  hide() {
    if (!this.mainWindow || !this.mirofishView) return;

    this.mainWindow.setBrowserView(null);
    this.isVisible = false;
    console.log('[MiroFishManager] MiroFish hidden');
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
    if (!this.mainWindow || !this.mirofishView) return;

    const bounds = this.mainWindow.getContentBounds();
    this.mirofishView.setBounds({
      x: 0,
      y: this.topOffset,
      width: bounds.width,
      height: bounds.height - this.topOffset,
    });
  }

  /**
   * Check if MiroFish is currently visible
   */
  getIsVisible() {
    return this.isVisible;
  }

  /**
   * Relay a push event to the MiroFish BrowserView.
   */
  relayEvent(channel, payload) {
    if (this.mirofishView && !this.mirofishView.webContents.isDestroyed()) {
      this.mirofishView.webContents.send(channel, payload);
    }
  }

  /**
   * Reload MiroFish
   */
  reload() {
    if (this.mirofishView) {
      this.mirofishView.webContents.reload();
    }
  }

  /**
   * Destroy the MiroFish view
   */
  destroy() {
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    if (this.mirofishView) {
      this.hide();
      this.mirofishView = null;
    }
  }
}

module.exports = MiroFishManager;
