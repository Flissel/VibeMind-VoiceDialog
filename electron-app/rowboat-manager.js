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

      // Inject Claude Code Max badge into Settings dialog when token is available
      this._injectClaudeCodeBadge();
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
   * Check if Claude Code OAuth token is available.
   * Reads credentials directly (we are in the main process).
   */
  _isClaudeCodeAvailable() {
    try {
      const os = require('os');
      const credPath = path.join(os.homedir(), '.claude', '.credentials.json');
      if (!fs.existsSync(credPath)) return false;
      const creds = JSON.parse(fs.readFileSync(credPath, 'utf-8'));
      const oauth = creds?.claudeAiOauth;
      if (!oauth?.accessToken) return false;
      if (oauth.expiresAt && oauth.expiresAt < Date.now() + 300000) return false;
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Inject a "Connected via Claude Code Max" badge into the Rowboat
   * Settings dialog. Uses a MutationObserver to detect when the dialog
   * opens and prepends a status banner — no submodule files are modified.
   * All DOM construction uses safe createElement/textContent methods.
   */
  _injectClaudeCodeBadge() {
    if (!this.rowboatView || this.rowboatView.webContents.isDestroyed()) return;

    if (!this._isClaudeCodeAvailable()) {
      console.log('[RowboatManager] No Claude Code token — skipping badge injection');
      return;
    }

    this.rowboatView.webContents.executeJavaScript(`
      (function() {
        if (window.__claudeCodeBadgeObserver) return;

        var BADGE_ID = 'claude-code-badge';

        function injectBadge() {
          var dialog = document.querySelector('[role="dialog"], [data-testid="settings-dialog"], .settings-modal');
          if (!dialog) return;
          if (document.getElementById(BADGE_ID)) return;

          var badge = document.createElement('div');
          badge.id = BADGE_ID;
          badge.style.cssText = [
            'background: linear-gradient(135deg, #7c3aed 0%, #2563eb 100%)',
            'color: white',
            'padding: 10px 16px',
            'border-radius: 8px',
            'margin: 0 0 16px 0',
            'font-size: 13px',
            'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            'display: flex',
            'align-items: center',
            'gap: 10px',
            'box-shadow: 0 2px 8px rgba(124, 58, 237, 0.3)',
            'line-height: 1.4'
          ].join(';');

          var checkmark = document.createElement('span');
          checkmark.style.cssText = 'font-size: 18px; flex-shrink: 0;';
          checkmark.textContent = String.fromCharCode(0x2713);

          var textWrap = document.createElement('span');

          var titleLine = document.createElement('strong');
          titleLine.textContent = 'Claude Code Max';

          var connText = document.createTextNode(' connected');

          var br = document.createElement('br');

          var subLine = document.createElement('span');
          subLine.style.cssText = 'opacity: 0.85; font-size: 12px;';
          subLine.textContent = 'OAuth token auto-injected \\u2014 no API key needed';

          textWrap.appendChild(titleLine);
          textWrap.appendChild(connText);
          textWrap.appendChild(br);
          textWrap.appendChild(subLine);

          badge.appendChild(checkmark);
          badge.appendChild(textWrap);

          var content = dialog.querySelector('.space-y-6, .space-y-4, .overflow-y-auto, form')
                     || dialog.firstElementChild;
          if (content) {
            content.prepend(badge);
            console.log('[VibeMind] Claude Code Max badge injected into Settings');
          }
        }

        var observer = new MutationObserver(function() {
          injectBadge();
        });
        observer.observe(document.body, { childList: true, subtree: true });
        window.__claudeCodeBadgeObserver = observer;

        injectBadge();
      })();
    `).catch(function(err) {
      console.warn('[RowboatManager] Badge injection failed:', err.message);
    });

    console.log('[RowboatManager] Claude Code Max badge observer injected');
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
