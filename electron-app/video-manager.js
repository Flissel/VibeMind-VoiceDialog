/**
 * Video Space Manager for VibeMind
 *
 * Manages the Video Production UI as a BrowserView overlay.
 * Shown when user clicks the clapperboard in the 3D multiverse.
 *
 * Pattern: identical to agentfarm-manager.js
 */

const { BrowserView } = require('electron');
const path = require('path');
const fs = require('fs');

const _VD_C = '\x1b[36m', _RST = '\x1b[0m'; // Cyan (Video)
function _vdLog(...a) { process.stdout.write(`${_VD_C}[VideoManager] ${a.join(' ')}${_RST}\n`); }

class VideoManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.videoView = null;
    this.isVisible = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    // Listen for window resize
    if (this.mainWindow) {
      this.mainWindow.on('resize', () => {
        if (this.isVisible && this.videoView) {
          this.updateBounds();
        }
      });
    }
  }

  /**
   * Resolve path to built video-ui dist/index.html
   */
  _resolveRendererPath() {
    const devPath = path.join(__dirname, 'video-ui', 'dist', 'index.html');
    const prodPath = path.join(process.resourcesPath || '', 'video-ui', 'index.html');

    if (fs.existsSync(prodPath)) return prodPath;
    if (fs.existsSync(devPath)) return devPath;
    return devPath;
  }

  /**
   * Create the BrowserView for Video Production
   */
  createView() {
    if (this.videoView) return this.videoView;

    this.videoView = new BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'video-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
        webSecurity: false,  // Allow file:// URLs for local video playback
      },
    });

    const rendererPath = this._resolveRendererPath();
    _vdLog('Loading from file:', rendererPath);
    this.videoView.webContents.loadFile(rendererPath);

    // Open DevTools in development
    if (process.env.NODE_ENV === 'development') {
      this.videoView.webContents.openDevTools({ mode: 'detach' });
    }

    // Handle external link navigation
    this.videoView.webContents.setWindowOpenHandler(({ url }) => {
      require('electron').shell.openExternal(url);
      return { action: 'deny' };
    });

    this.videoView.webContents.on('did-finish-load', () => {
      _vdLog('Video UI loaded');
    });

    this.videoView.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
      console.error('[VideoManager] Load failed:', errorCode, errorDescription);
    });

    return this.videoView;
  }

  show() {
    if (!this.mainWindow) return;
    if (!this.videoView) this.createView();

    this.mainWindow.setBrowserView(this.videoView);
    this.updateBounds();
    this.isVisible = true;
    _vdLog('Video shown');
  }

  hide() {
    if (!this.mainWindow || !this.videoView) return;
    this.mainWindow.setBrowserView(null);
    this.isVisible = false;
    _vdLog('Video hidden');
  }

  toggle() {
    if (this.isVisible) {
      this.hide();
    } else {
      this.show();
    }
  }

  updateBounds() {
    if (!this.mainWindow || !this.videoView) return;
    const bounds = this.mainWindow.getContentBounds();
    this.videoView.setBounds({
      x: 0,
      y: this.topOffset,
      width: bounds.width,
      height: bounds.height - this.topOffset,
    });
  }

  getIsVisible() {
    return this.isVisible;
  }

  destroy() {
    if (this.videoView) {
      this.videoView.webContents.close();
      this.videoView = null;
    }
    this.isVisible = false;
  }
}

module.exports = VideoManager;