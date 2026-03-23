/**
 * Flowzen Diary Manager for VibeMind
 *
 * Manages the Flowzen Journal (Blue Rose diary) as a BrowserView overlay.
 * Loads a local HTML page with a page-flip book UI for diary entries.
 * Shown when user navigates to the Flowzen space.
 *
 * Pattern: similar to mirofish-manager.js but loads a local file.
 */

const { BrowserView } = require('electron');
const path = require('path');

class FlowzenManager {
  constructor(mainWindow, sendToPythonFn) {
    this.mainWindow = mainWindow;
    this.sendToPython = sendToPythonFn || null;
    this.flowzenView = null;
    this.isVisible = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    // Listen for window resize
    if (this.mainWindow) {
      this.mainWindow.on('resize', () => {
        if (this.isVisible && this.flowzenView) {
          this.updateBounds();
        }
      });
    }
  }

  /**
   * Create the BrowserView for the Flowzen diary
   */
  createView() {
    if (this.flowzenView) return this.flowzenView;

    this.flowzenView = new BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'flowzen-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    });

    // Load the local diary HTML page
    const diaryPath = path.join(__dirname, 'flowzen-diary.html');
    console.log('[FlowzenManager] Loading diary from:', diaryPath);
    this.flowzenView.webContents.loadFile(diaryPath);

    // Handle external link navigation
    this.flowzenView.webContents.setWindowOpenHandler(({ url }) => {
      require('electron').shell.openExternal(url);
      return { action: 'deny' };
    });

    // Forward 'to-python' IPC from the diary BrowserView to the Python backend
    const { ipcMain } = require('electron');
    ipcMain.on('to-python', (_event, message) => {
      if (this.sendToPython) {
        this.sendToPython(message);
      }
    });

    this._loaded = false;

    // Notify VibeMind renderer of load status
    this.flowzenView.webContents.on('did-finish-load', () => {
      this._loaded = true;
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'flowzen_view_status',
          status: 'ready',
        });
      }
      console.log('[FlowzenManager] Diary loaded');

      // Send pending data request now that page is ready
      if (this.isVisible && this.sendToPython) {
        this.sendToPython({ type: 'flowzen_status' });
        this.sendToPython({ type: 'flowzen_diary_entries' });
      }
    });

    this.flowzenView.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'flowzen_view_status',
          status: 'error',
          message: `Load failed: ${errorDescription} (${errorCode})`,
        });
      }
      console.error('[FlowzenManager] Load failed:', errorCode, errorDescription);
    });

    return this.flowzenView;
  }

  /**
   * Show the Flowzen diary overlay.
   * Requests fresh data from Python backend on show.
   */
  show() {
    if (!this.mainWindow) {
      console.error('[FlowzenManager] No main window available');
      return;
    }

    if (!this.flowzenView) {
      this.createView();
    }

    this.mainWindow.addBrowserView(this.flowzenView);
    this.updateBounds();
    this.isVisible = true;
    console.log('[FlowzenManager] Diary shown');

    // Request fresh diary data (only if page already loaded, otherwise did-finish-load handles it)
    if (this._loaded && this.sendToPython) {
      this.sendToPython({ type: 'flowzen_status' });
      this.sendToPython({ type: 'flowzen_diary_entries' });
    }
  }

  /**
   * Hide the Flowzen diary overlay
   */
  hide() {
    if (!this.mainWindow || !this.flowzenView) return;

    this.mainWindow.removeBrowserView(this.flowzenView);
    this.isVisible = false;
    console.log('[FlowzenManager] Diary hidden');
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
    if (!this.mainWindow || !this.flowzenView) return;

    const bounds = this.mainWindow.getContentBounds();
    this.flowzenView.setBounds({
      x: 0,
      y: this.topOffset,
      width: bounds.width,
      height: bounds.height - this.topOffset,
    });
  }

  /**
   * Check if Flowzen diary is currently visible
   */
  getIsVisible() {
    return this.isVisible;
  }

  /**
   * Relay a push event to the Flowzen diary BrowserView.
   */
  send(channel, payload) {
    if (this.flowzenView && !this.flowzenView.webContents.isDestroyed()) {
      this.flowzenView.webContents.send(channel, payload);
    }
  }

  /**
   * Reload the diary page
   */
  reload() {
    if (this.flowzenView && !this.flowzenView.webContents.isDestroyed()) {
      this.flowzenView.webContents.reload();
    }
  }

  /**
   * Destroy the Flowzen diary view
   */
  destroy() {
    if (this.flowzenView) {
      this.hide();
      this.flowzenView = null;
    }
  }
}

module.exports = FlowzenManager;
