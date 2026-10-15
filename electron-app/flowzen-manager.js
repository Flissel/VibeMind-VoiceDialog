/**
 * Flowzen Diary Manager for VibeMind
 *
 * Manages the Flowzen Journal (Blue Rose diary) as a BrowserView overlay.
 * Loads a local HTML page with a page-flip book UI for diary entries.
 * Shown when user navigates to the Flowzen space.
 *
 * Pattern: similar to mirofish-manager.js but loads a local file.
 */

const path = require('path');
const { loadOverlay, loadStatus, resolveElectronParts } = require('./overlay-status');

const _FZ_C = '\x1b[92m', _RST = '\x1b[0m'; // Bright Green (Flowzen)
function _fzLog(...a) { process.stdout.write(`${_FZ_C}[FlowzenManager] ${a.join(' ')}${_RST}\n`); }

class FlowzenManager {
  constructor(mainWindow, sendToPythonFn, dependencies = {}) {
    const { BrowserView, shell } = resolveElectronParts(dependencies, ['BrowserView', 'shell']);
    this.BrowserView = BrowserView;
    this.shell = shell;
    this._ipcMain = dependencies.ipcMain || null;
    this._overlayDeps = dependencies.overlayDeps || {};
    this.overlayReady = null;
    this.overlayResult = null;
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
   * Prueft das Ziel und laedt es bzw. die Statuskarte. Wird beim Erzeugen der Ansicht,
   * bei reload() und bei show() nach einer Statuskarte erneut aufgerufen.
   */
  _startOverlay() {
    this.overlayResult = null;
    const diaryPath = path.join(__dirname, 'flowzen-diary.html');
    _fzLog('Pruefe und lade:', diaryPath);
    const targets = [{ kind: 'file', path: diaryPath }];
    this.overlayReady = loadOverlay(this.flowzenView.webContents, { space: 'Flowzen', targets }, { ...this._overlayDeps, onResult: (r) => { this.overlayResult = r; } });
    return this.overlayReady;
  }

  _recheckOverlay() {
    if (this.overlayResult && !this.overlayResult.ok && this.flowzenView) this._startOverlay();
  }

  /**
   * Create the BrowserView for the Flowzen diary
   */
  createView() {
    if (this.flowzenView) return this.flowzenView;

    this.flowzenView = new this.BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'flowzen-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    });

    this._startOverlay();

    // Handle external link navigation
    this.flowzenView.webContents.setWindowOpenHandler(({ url }) => {
      this.shell.openExternal(url);
      return { action: 'deny' };
    });

    // Forward 'to-python' IPC from the diary BrowserView to the Python backend
    const ipcMain = this._ipcMain || require('electron').ipcMain;
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
          ...loadStatus(this.overlayResult),
        });
      }
      _fzLog('Diary loaded');

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
    } else {
      this._recheckOverlay();
    }

    this.mainWindow.addBrowserView(this.flowzenView);
    this.updateBounds();
    this.isVisible = true;
    _fzLog('Diary shown');

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
    _fzLog('Diary hidden');
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
      _fzLog(`send(${channel}) -> BrowserView`);
      this.flowzenView.webContents.send(channel, payload);
    } else {
      _fzLog(`send(${channel}) FAILED - view not ready`);
    }
  }

  /**
   * Reload the diary page
   */
  reload() {
    if (this.flowzenView && !this.flowzenView.webContents.isDestroyed()) {
      this._startOverlay();
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
