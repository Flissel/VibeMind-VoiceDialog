/**
 * Agent Farm Manager for VibeMind
 *
 * Manages the Agent Farm as a BrowserView overlay.
 * Shown when user clicks the barn in the 3D multiverse.
 *
 * Pattern: identical to clawport-manager.js (ClawPort Dashboard).
 */

const { resolveElectronParts } = require('./overlay-status');
const getElectronSession = () => require('electron').session;
const path = require('path');
const fs = require('fs');
const { loadOverlay, loadStatus } = require('./overlay-status');

const _AF_C = '\x1b[93m', _RST = '\x1b[0m'; // Yellow (AgentFarm)
function _afLog(...a) { process.stdout.write(`${_AF_C}[AgentFarmManager] ${a.join(' ')}${_RST}\n`); }

class AgentFarmManager {
  constructor(mainWindow, dependencies = {}) {
    const { BrowserView, shell } = resolveElectronParts(dependencies, ['BrowserView', 'shell']);
    this.BrowserView = BrowserView;
    this.shell = shell;
    this._env = dependencies.env || process.env;
    this._n8nLoginEnabled = dependencies.n8nLogin !== false;
    this._overlayDeps = dependencies.overlayDeps || {};
    this.overlayReady = null;
    this.overlayResult = null;
    this.mainWindow = mainWindow;
    this.agentfarmView = null;
    this.isVisible = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    // Renderer dist path (dev vs production)
    this.isDev = !!this._env.AGENTFARM_DEV_URL;

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
    const prodPath = path.join(process.resourcesPath || '', 'agentfarm-ui', 'index.html');

    if (fs.existsSync(prodPath)) return prodPath;
    if (fs.existsSync(devPath)) return devPath;
    return devPath; // Will fail gracefully if missing
  }

  /**
   * Prueft das Ziel und laedt es bzw. die Statuskarte. Wird beim Erzeugen der Ansicht,
   * bei reload() und bei show() nach einer Statuskarte erneut aufgerufen.
   */
  _startOverlay() {
    this.overlayResult = null;
    const targets = this.isDev
      ? [{ kind: 'url', url: this._env.AGENTFARM_DEV_URL }]
      : [{ kind: 'file', path: this._resolveRendererPath() }];
    _afLog('Pruefe und lade:', targets.map((t) => t.url || t.path).join(' | '));
    this.overlayReady = loadOverlay(this.agentfarmView.webContents, { space: 'AgentFarm', targets }, { ...this._overlayDeps, onResult: (r) => { this.overlayResult = r; } });
    return this.overlayReady;
  }

  _recheckOverlay() {
    if (this.overlayResult && !this.overlayResult.ok && this.agentfarmView) this._startOverlay();
  }

  /**
   * Create the BrowserView for the Agent Farm
   */
  createView() {
    if (this.agentfarmView) return this.agentfarmView;

    this.agentfarmView = new this.BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'agentfarm-preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false, // Required for contextBridge + ipcRenderer
      },
    });

    this._startOverlay();

    // Strip X-Frame-Options / CSP from embedded iframe targets so their UIs
    // can load inside AgentFarm:
    //  - n8n (:15678) sends restrictive CSP frame-ancestors
    //  - OpenFang (:4200) sends X-Frame-Options: DENY (Rust server)
    // Rowboat (:3100) needs no stripping (Next.js sends no such headers).
    this.agentfarmView.webContents.session.webRequest.onHeadersReceived(
      { urls: ['http://localhost:15678/*', 'http://localhost:4200/*'] },
      (details, callback) => {
        const headers = { ...details.responseHeaders };
        // Remove headers that block iframe embedding (case-insensitive keys)
        for (const key of Object.keys(headers)) {
          const lower = key.toLowerCase();
          if (lower === 'x-frame-options' || lower === 'content-security-policy') {
            delete headers[key];
          }
        }
        callback({ responseHeaders: headers });
      },
    );

    // Open DevTools in development
    if (process.env.NODE_ENV === 'development' || this.isDev) {
      this.agentfarmView.webContents.openDevTools({ mode: 'detach' });
    }

    // Handle external link navigation
    this.agentfarmView.webContents.setWindowOpenHandler(({ url }) => {
      this.shell.openExternal(url);
      return { action: 'deny' };
    });

    // Notify VibeMind renderer of load status
    this.agentfarmView.webContents.on('did-finish-load', () => {
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'agentfarm_view_status',
          ...loadStatus(this.overlayResult),
        });
      }
      _afLog('Agent Farm loaded');
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

    // Auto-login to n8n so the embedded iframe is authenticated
    if (this._n8nLoginEnabled) this._loginToN8n();

    return this.agentfarmView;
  }

  /**
   * Login to n8n and set session cookie so iframe loads authenticated.
   * Retries up to 6 times (n8n may still be booting).
   */
  _loginToN8n(attempt = 1) {
    const n8nUrl = process.env.N8N_API_URL || 'http://localhost:15678';
    const http = require('http');
    const url = new URL(`${n8nUrl}/rest/login`);
    const body = JSON.stringify({
      emailOrLdapLoginId: 'admin@vibemind.local',
      password: 'Vibemind1',
    });

    const req = http.request({
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        if (res.statusCode === 200) {
          // Extract set-cookie header and inject into Electron session
          const cookies = res.headers['set-cookie'];
          if (cookies && this.agentfarmView) {
            // Set cookie on BOTH the BrowserView session AND the default session,
            // because the embedded n8n <iframe> may use a different partition.
            const sessions = [
              this.agentfarmView.webContents.session,
              getElectronSession().defaultSession,
            ];
            for (const raw of cookies) {
              // Parse cookie name=value from "n8n-auth=xxx; Path=/; ..."
              const [nameValue] = raw.split(';');
              const eqIdx = nameValue.indexOf('=');
              if (eqIdx === -1) continue;
              const name = nameValue.substring(0, eqIdx).trim();
              const value = nameValue.substring(eqIdx + 1).trim();
              for (const sess of sessions) {
                sess.cookies.remove(n8nUrl, name)
                  .catch(() => {})
                  .then(() => sess.cookies.set({
                    url: n8nUrl,
                    name,
                    value,
                    path: '/',
                    httpOnly: true,
                    sameSite: 'no_restriction',
                  }))
                  .then(() => {
                    _afLog(`n8n cookie "${name}" set in ${sess === getElectronSession().defaultSession ? 'default' : 'view'} session`);
                  })
                  .catch((err) => {
                    console.warn('[AgentFarmManager] Failed to set n8n cookie:', err.message);
                  });
              }
            }
          }
          _afLog('n8n auto-login successful');
          // Notify the Agent Farm renderer so it can remount the n8n iframe
          // with the cookie now present in the session.
          setTimeout(() => {
            if (this.agentfarmView && !this.agentfarmView.webContents.isDestroyed()) {
              this.agentfarmView.webContents.send('n8n-auth-ready');
            }
          }, 300);
        } else {
          _afLog(`n8n login returned status ${res.statusCode}, attempt ${attempt}/6`);
          if (attempt < 6) setTimeout(() => this._loginToN8n(attempt + 1), 5000);
        }
      });
    });

    req.on('error', () => {
      if (attempt < 6) {
        _afLog(`n8n not ready for login, retry ${attempt}/6...`);
        setTimeout(() => this._loginToN8n(attempt + 1), 5000);
      } else {
        console.warn('[AgentFarmManager] n8n auto-login gave up after 6 attempts');
      }
    });

    req.write(body);
    req.end();
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
    } else {
      this._recheckOverlay();
    }

    this.mainWindow.setBrowserView(this.agentfarmView);
    this.updateBounds();
    this.isVisible = true;
    _afLog('Agent Farm shown');
  }

  /**
   * Hide the Agent Farm overlay
   */
  hide() {
    if (!this.mainWindow || !this.agentfarmView) return;

    this.mainWindow.setBrowserView(null);
    this.isVisible = false;
    _afLog('Agent Farm hidden');
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
      this._startOverlay();
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
