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
const { loadOverlay } = require('./overlay-status');
const { applyVibeMindLook } = require('./vibemind-look');

/**
 * Laura in the VibeMind look: its own variables (laura/apps/desktop/src/index.css, the
 * light green theme its parts are drawn with) set to the values of the app, accent Video.
 * Laura itself stays as it is; only this view shows it dark.
 */
const LAURA_LOOK = `html:root {
  --surface-0: var(--vm-bg-deep);
  --surface-1: var(--vm-bg-surface);
  --surface-1-5: var(--vm-bg-mid);
  --surface-2: var(--vm-bg-elevated);
  --text-strong: var(--vm-text-primary);
  --text-muted: var(--vm-text-secondary);
  --text-faint: rgba(200, 190, 220, 0.55);
  --accent: rgb(var(--space-accent-rgb));
  --accent-glow: rgb(255, 102, 136);
  --accent-press: rgb(200, 50, 85);
  --accent-ink: #ffffff;
  --status-ok: var(--vm-status-ok);
  --status-warn: var(--vm-status-warn);
  --status-err: var(--vm-status-error);
  --bezel: rgba(var(--space-accent-rgb), 0.20);
  --playhead: #c8bedc;
}
body { font-family: var(--vm-font); background: var(--vm-bg-deep); color: var(--vm-text-primary); }
`;

class VideoManager {
  constructor(mainWindow, dependencies = {}) {
    let electron;
    if (!dependencies.BrowserView || !dependencies.shell) {
      electron = require('electron');
    }

    this.mainWindow = mainWindow;
    this.BrowserView = dependencies.BrowserView || electron.BrowserView;
    this.shell = dependencies.shell || electron.shell;
    this.logger = dependencies.logger || console;
    this.rendererPath = null;
    this.rendererMissing = '';
    if (dependencies.rendererPath) {
      this.rendererPath = dependencies.rendererPath;
    } else {
      const resolveRendererPath = dependencies.resolveRendererPath || (() => resolveLauraRendererPath({
        dirname: __dirname,
        resourcesPath: process.resourcesPath || '',
        existsSync: fs.existsSync,
      }));
      try {
        this.rendererPath = resolveRendererPath();
      } catch (err) {
        this.rendererMissing = err.message;
        this.logger.warn('[VideoManager] Laura-Renderer fehlt - Statuskarte statt Abbruch');
      }
    }
    this._overlayDeps = dependencies.overlayDeps || { logger: this.logger };
    this.overlayReady = null;
    this.videoView = null;
    this.isVisible = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    // Laura or "Aus dem Marketing" (video-quellen.js): a bar above the view switches. Only a window that
    // can hold two views at once gets it; otherwise the space shows Laura as before.
    const { VideoQuellen } = require('./video-quellen');
    this.quellen = dependencies.quellen !== false && VideoQuellen.supported(this.mainWindow)
      ? new VideoQuellen({
        mainWindow: this.mainWindow, BrowserView: this.BrowserView, shell: this.shell,
        env: dependencies.env || process.env, logger: this.logger, overlayDeps: this._overlayDeps, topOffset: this.topOffset,
      })
      : null;

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
    applyVibeMindLook(this.videoView.webContents, 'video', { extraCss: LAURA_LOOK, logger: this.logger });

    if (!this.rendererPath) {
      this.overlayReady = loadOverlay(this.videoView.webContents, {
        space: 'Video/Laura',
        targets: [{ kind: 'unavailable', reason: 'Renderer fehlt (pnpm laura:build)', target: this.rendererMissing }],
      }, this._overlayDeps);
      return this.videoView;
    }

    this.logger.info('[VideoManager] Loading Laura renderer');
    this._loadRenderer('[VideoManager] initial renderer load failed');

    // Open DevTools in development
    if (process.env.NODE_ENV === 'development') {
      this.videoView.webContents.openDevTools({ mode: 'detach' });
    }

    // Handle external link navigation
    this.videoView.webContents.setWindowOpenHandler(({ url }) => {
      let parsedUrl;
      try {
        parsedUrl = new URL(url);
      } catch {
        return { action: 'deny' };
      }
      if (parsedUrl.protocol === 'http:' || parsedUrl.protocol === 'https:') {
        try {
          Promise.resolve(this.shell.openExternal(url)).catch(() => {
            this.logger.warn('[VideoManager] external link failed');
          });
        } catch {
          this.logger.warn('[VideoManager] external link failed');
        }
      }
      return { action: 'deny' };
    });

    const rendererUrl = pathToFileURL(this.rendererPath).href;
    this.videoView.webContents.on('will-navigate', (event, url) => {
      if (url !== rendererUrl) event.preventDefault();
    });
    this.videoView.webContents.on('did-navigate-in-page', (_event, url, isMainFrame) => {
      if (!isMainFrame || url === rendererUrl || this.isRestoringRenderer) return;
      this.isRestoringRenderer = true;
      this._loadRenderer('[VideoManager] renderer restore failed').finally(() => {
        this.isRestoringRenderer = false;
      });
    });

    this.videoView.webContents.on('did-finish-load', () => {
      this.logger.info('[VideoManager] Laura renderer loaded');
    });

    this.videoView.webContents.on('did-fail-load', (_event, errorCode) => {
      this.logger.warn('[VideoManager] Laura renderer load failed:', errorCode);
    });

    return this.videoView;
  }

  show() {
    if (!this.mainWindow) return;
    if (!this.videoView) this.createView();

    this.isVisible = true;
    if (this.quellen) {
      this.quellen.show(this.videoView);
    } else {
      this.mainWindow.setBrowserView(this.videoView);
      this.updateBounds();
    }
    this.logger.info('[VideoManager] Video shown');
  }

  hide() {
    if (!this.mainWindow || !this.videoView) return;
    this.mainWindow.setBrowserView(null);
    this.isVisible = false;
    if (this.quellen) this.quellen.hide();
    this.logger.info('[VideoManager] Video hidden');
  }

  toggle() {
    if (this.isVisible) {
      this.hide();
    } else {
      this.show();
    }
  }

  /** The bar of the space asks for a source (main.js, ipc 'video-quelle'); only that bar may. */
  chooseSource(sender, quelle) {
    return this.quellen ? this.quellen.choose(sender, quelle) : false;
  }

  updateBounds() {
    if (!this.mainWindow || !this.videoView) return;
    if (this.quellen) { this.quellen.updateBounds(); return; }
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

  _loadRenderer(failureMessage) {
    try {
      return Promise.resolve(this.videoView.webContents.loadFile(this.rendererPath)).catch(() => {
        this.logger.warn(failureMessage);
      });
    } catch {
      this.logger.warn(failureMessage);
      return Promise.resolve();
    }
  }

  destroy() {
    if (this.videoView) {
      const view = this.videoView;
      // getBrowserView throws while two views are attached (the bar of video-quellen.js and the source)
      let shown = null;
      try { shown = this.mainWindow?.getBrowserView?.(); } catch { shown = view; }
      if (shown === view || (this.quellen && this.isVisible)) {
        this.mainWindow.setBrowserView(null);
      }
      view.webContents.destroy();
      this.videoView = null;
    }
    if (this.quellen) this.quellen.destroy();
    this.isVisible = false;
  }
}

module.exports = VideoManager;
module.exports.LAURA_LOOK = LAURA_LOOK;
