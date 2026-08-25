/**
 * Video Space Manager for VibeMind
 *
 * Manages the Video Production UI as a BrowserView overlay.
 * Shown when user clicks the clapperboard in the 3D multiverse.
 *
 * Pattern: identical to agentfarm-manager.js
 */

const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const {
  LAURA_SESSION_PARTITION,
  resolveLauraRendererPath,
} = require('./laura-embed-config');

const _VD_C = '\x1b[36m', _RST = '\x1b[0m'; // Cyan (Video)
function _vdLog(...a) { process.stdout.write(`${_VD_C}[VideoManager] ${a.join(' ')}${_RST}\n`); }

class VideoManager {
  constructor(mainWindow, dependencies = {}) {
    let electron;
    if (!dependencies.BrowserView || !dependencies.shell) {
      electron = require('electron');
    }

    this.mainWindow = mainWindow;
    this.BrowserView = dependencies.BrowserView || electron.BrowserView;
    this.shell = dependencies.shell || electron.shell;
    this.logger = dependencies.logger || _vdLog;
    this.rendererPath = dependencies.rendererPath || resolveLauraRendererPath({
      dirname: __dirname,
      resourcesPath: process.resourcesPath || '',
      existsSync: fs.existsSync,
    });
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
   * Create the BrowserView for Video Production
   */
  createView() {
    if (this.videoView) return this.videoView;

    this.videoView = new this.BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'laura-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        webSecurity: true,
        partition: LAURA_SESSION_PARTITION,
      },
    });

    this.logger('Loading Laura renderer');
    this.videoView.webContents.loadFile(this.rendererPath);

    // Open DevTools in development
    if (process.env.NODE_ENV === 'development') {
      this.videoView.webContents.openDevTools({ mode: 'detach' });
    }

    // Handle external link navigation
    this.videoView.webContents.setWindowOpenHandler(({ url }) => {
      this.shell.openExternal(url);
      return { action: 'deny' };
    });

    const rendererUrl = pathToFileURL(this.rendererPath).href;
    this.videoView.webContents.on('will-navigate', (event, url) => {
      if (url !== rendererUrl) event.preventDefault();
    });

    this.videoView.webContents.on('did-finish-load', () => {
      this.logger('Laura renderer loaded');
    });

    this.videoView.webContents.on('did-fail-load', (_event, errorCode) => {
      this.logger('Laura renderer load failed:', errorCode);
    });

    return this.videoView;
  }

  show() {
    if (!this.mainWindow) return;
    if (!this.videoView) this.createView();

    this.mainWindow.setBrowserView(this.videoView);
    this.updateBounds();
    this.isVisible = true;
    this.logger('Video shown');
  }

  hide() {
    if (!this.mainWindow || !this.videoView) return;
    this.mainWindow.setBrowserView(null);
    this.isVisible = false;
    this.logger('Video hidden');
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
