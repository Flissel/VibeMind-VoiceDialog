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
const { spawn } = require('child_process');
const readline = require('readline');
const path = require('path');
const fs = require('fs');

const _RB_C = '\x1b[94m', _RST = '\x1b[0m'; // Blue (Rowboat)
function _rbLog(...args) { process.stdout.write(`${_RB_C}[RowboatManager] ${args.join(' ')}${_RST}\n`); }

class RowboatManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.rowboatView = null;
    this.isVisible = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    // Renderer dist path (dev vs production)
    this.isDev = !!process.env.ROWBOAT_DEV_URL;

    // Bridge (child process) state
    this.bridgeProcess = null;
    this.bridgeReady = false;
    this.pendingRpc = new Map();
    this.rpcCounter = 0;
    this.bridgeRestartCount = 0;
    this._bridgeReadyResolve = null;

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
      _rbLog('Loading from dev server:', process.env.ROWBOAT_DEV_URL);
      this.rowboatView.webContents.loadURL(process.env.ROWBOAT_DEV_URL);
    } else {
      const rendererPath = this._resolveRendererPath();
      _rbLog('Loading from file:', rendererPath);
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
      _rbLog('Renderer loaded');

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
    _rbLog('Rowboat shown');
  }

  /**
   * Hide the Rowboat overlay
   */
  hide() {
    if (!this.mainWindow || !this.rowboatView) return;

    this.mainWindow.setBrowserView(null);
    this.isVisible = false;
    _rbLog('Rowboat hidden');
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

  // ═══════════════════════════════════════════════════════
  // Bridge (Child Process) — runs @x/core in a separate
  // Node.js process, communicates via JSON-RPC on stdio.
  // ═══════════════════════════════════════════════════════

  /**
   * Start the core bridge process.
   * Returns a promise that resolves when bridge:ready is received.
   */
  startBridge() {
    if (this.bridgeProcess) return Promise.resolve();

    // CWD must be apps/x/apps/main/ where pnpm workspace symlinks resolve @x/core, @x/shared
    const coreDir = path.join(
      __dirname, '..', 'python', 'spaces', 'rowboat', 'rowboat', 'apps', 'x', 'apps', 'main'
    );
    const bridgeScript = path.join(__dirname, 'rowboat-core-bridge.mjs');

    if (!fs.existsSync(bridgeScript)) {
      _rbLog('Bridge script not found:', bridgeScript);
      return Promise.reject(new Error('Bridge script not found'));
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Bridge startup timed out (15s)'));
      }, 15000);

      this._bridgeReadyResolve = () => {
        clearTimeout(timeout);
        resolve();
      };

      // Use the system Node.js (not Electron's, which may lack ESM support in packaged builds)
      const nodeBin = process.env.ROWBOAT_NODE_BIN || 'node';

      this.bridgeProcess = spawn(nodeBin, [bridgeScript], {
        cwd: coreDir,
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env, NODE_NO_WARNINGS: '1' },
      });

      // Parse stdout line by line (JSON-RPC messages)
      const rl = readline.createInterface({ input: this.bridgeProcess.stdout });
      rl.on('line', (line) => this._onBridgeLine(line));

      // Forward stderr to console (bridge logging)
      this.bridgeProcess.stderr.on('data', (chunk) => {
        const text = chunk.toString().trimEnd();
        if (text) _rbLog(text);
      });

      // Handle unexpected exit
      this.bridgeProcess.on('close', (code) => {
        this.bridgeProcess = null;
        this.bridgeReady = false;

        // Reject all pending RPCs
        for (const [id, { reject: rej, timer }] of this.pendingRpc) {
          clearTimeout(timer);
          rej(new Error('Bridge process exited'));
        }
        this.pendingRpc.clear();

        if (code !== 0 && code !== null) {
          _rbLog(`Bridge exited with code ${code}`);
          this._handleBridgeRestart();
        }
      });

      this.bridgeProcess.on('error', (err) => {
        clearTimeout(timeout);
        _rbLog('Bridge spawn error:', err.message);
        reject(err);
      });
    });
  }

  /**
   * Stop the bridge process gracefully.
   */
  stopBridge() {
    if (!this.bridgeProcess) return;

    _rbLog('Stopping bridge...');
    this.bridgeReady = false;

    try {
      this.bridgeProcess.stdin.end();
    } catch { /* stdin may already be closed */ }

    const proc = this.bridgeProcess;
    setTimeout(() => {
      try { proc.kill('SIGTERM'); } catch { /* already dead */ }
    }, 3000);

    this.bridgeProcess = null;
  }

  /**
   * Send a JSON-RPC request to the bridge and wait for the response.
   */
  sendRpc(method, params, timeoutMs = 30000) {
    if (!this.bridgeProcess || !this.bridgeReady) {
      return Promise.reject(new Error('Rowboat bridge not ready'));
    }

    const id = String(++this.rpcCounter);

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRpc.delete(id);
        reject(new Error(`RPC timeout for ${method} (${timeoutMs}ms)`));
      }, timeoutMs);

      this.pendingRpc.set(id, { resolve, reject, timer });

      const msg = JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n';
      try {
        this.bridgeProcess.stdin.write(msg);
      } catch (err) {
        clearTimeout(timer);
        this.pendingRpc.delete(id);
        reject(err);
      }
    });
  }

  /**
   * Parse a JSON line from bridge stdout.
   * RPC responses have an `id`, push events have a `method`.
   */
  _onBridgeLine(line) {
    if (!line.trim()) return;

    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      _rbLog('Malformed bridge output:', line.slice(0, 120));
      return;
    }

    // RPC response (has id)
    if (msg.id !== undefined) {
      const pending = this.pendingRpc.get(msg.id);
      if (pending) {
        this.pendingRpc.delete(msg.id);
        clearTimeout(pending.timer);
        if (msg.error) {
          pending.reject(new Error(msg.error.message || 'Bridge RPC error'));
        } else {
          pending.resolve(msg.result);
        }
      }
      return;
    }

    // Push event (notification)
    if (msg.method === 'bridge:ready') {
      this.bridgeReady = true;
      this.bridgeRestartCount = 0;
      _rbLog('Bridge ready');
      if (this._bridgeReadyResolve) {
        this._bridgeReadyResolve();
        this._bridgeReadyResolve = null;
      }
      return;
    }

    if (msg.method === 'runs:events') {
      this.relayEvent('runs:events', msg.params);
      return;
    }

    if (msg.method === 'services:events') {
      this.relayEvent('services:events', msg.params);
      return;
    }
  }

  /**
   * Auto-restart bridge with exponential backoff (max 3 attempts).
   */
  _handleBridgeRestart() {
    if (this.bridgeRestartCount >= 3) {
      _rbLog('Bridge restart limit reached (3) — giving up');
      return;
    }

    const delay = Math.pow(2, this.bridgeRestartCount) * 1000; // 1s, 2s, 4s
    this.bridgeRestartCount++;
    _rbLog(`Restarting bridge in ${delay}ms (attempt ${this.bridgeRestartCount}/3)`);

    setTimeout(() => {
      this.startBridge().catch((err) => {
        _rbLog('Bridge restart failed:', err.message);
      });
    }, delay);
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
   * Destroy the Rowboat view and stop the bridge.
   */
  destroy() {
    this.stopBridge();
    if (this.rowboatView) {
      this.hide();
      this.rowboatView = null;
    }
  }
}

module.exports = RowboatManager;
