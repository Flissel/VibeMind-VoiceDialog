/**
 * SWE Design Manager for VibeMind
 *
 * Self-contained manager for the SWE Design (Requirements Engineer) dashboard.
 * Spawns the Python aiohttp server and creates a BrowserView overlay.
 *
 * Server lifecycle:
 *   show()    → start server (if needed) + create BrowserView
 *   hide()    → remove BrowserView (server stays alive for fast re-show)
 *   destroy() → stop server + kill Python process
 */

const { BrowserView } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

// ANSI colors for SWE Design space logs
const SWE_COLOR = '\x1b[96m';     // Bright Cyan
const SWE_MGR_COLOR = '\x1b[96m'; // Bright Cyan
const RST = '\x1b[0m';

class SweDesignManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.view = null;
    this.isVisible = false;
    this._starting = false;
    this._serverProcess = null;
    this._serverReady = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    // Python path: prefer .venv312 from project root
    const projectRoot = path.resolve(__dirname, '..');
    const venv312 = path.join(projectRoot, '.venv312', 'Scripts', 'python.exe');
    this.pythonPath = fs.existsSync(venv312) ? venv312 : 'python';

    // RE project root (where start_dashboard.py lives)
    this.reProjectRoot = path.join(
      projectRoot, 'python', 'spaces', 'shuttles', 'swe_desgine'
    );

    this.port = 8086; // 8085 often held by zombie; use 8086 as default

    // Resize handler
    if (this.mainWindow) {
      this.mainWindow.on('resize', () => {
        if (this.isVisible && this.view) {
          this._updateBounds();
        }
      });
    }
  }

  /**
   * Start the Python dashboard server with port retry.
   * Tries up to 3 consecutive ports if the default is in use.
   * Returns a promise that resolves with the actual port when the server is ready.
   */
  async _startServer() {
    if (this._serverReady) return this.port;

    const scriptPath = path.join(this.reProjectRoot, 'start_dashboard.py');
    if (!fs.existsSync(scriptPath)) {
      throw new Error(`SWE Design dashboard script not found: ${scriptPath}`);
    }

    // Try up to 3 ports
    const maxRetries = 3;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      const tryPort = this.port + attempt;
      try {
        await this._tryStartOnPort(scriptPath, tryPort);
        this.port = tryPort;
        return this.port;
      } catch (err) {
        const isPortConflict = err.message.includes('10048') ||
                               err.message.includes('address already in use') ||
                               err.message.includes('EADDRINUSE');
        if (isPortConflict && attempt < maxRetries - 1) {
          console.log(`[SweDesignManager] Port ${tryPort} busy, trying ${tryPort + 1}...`);
          continue;
        }
        throw err;
      }
    }
  }

  /**
   * Try to start the server on a specific port.
   */
  _tryStartOnPort(scriptPath, port) {
    return new Promise((resolve, reject) => {
      console.log(`[SweDesignManager] Starting server on port ${port}...`);

      const proc = spawn(this.pythonPath, [
        scriptPath,
        '--port', String(port),
        '--no-browser',
      ], {
        cwd: this.reProjectRoot,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: { ...process.env },
      });

      this._serverProcess = proc;

      let resolved = false;
      let stderrBuf = '';

      const timeout = setTimeout(() => {
        if (!resolved) {
          resolved = true;
          this._serverReady = true;
          console.log('[SweDesignManager] Server start timeout — assuming ready on port', port);
          resolve(port);
        }
      }, 10000);

      proc.stdout.on('data', (data) => {
        const line = data.toString();
        for (const l of line.split('\n').filter(s => s.trim())) {
          process.stdout.write(`${SWE_COLOR}[SWE-Server] ${l.trim()}${RST}\n`);
        }
        if (!resolved && (line.includes('Dashboard running') || line.includes('localhost'))) {
          resolved = true;
          clearTimeout(timeout);
          this._serverReady = true;
          console.log('[SweDesignManager] Server ready on port', port);
          resolve(port);
        }
      });

      proc.stderr.on('data', (data) => {
        const line = data.toString();
        stderrBuf += line;
        for (const l of line.split('\n').filter(s => s.trim())) {
          process.stderr.write(`${SWE_COLOR}[SWE-Server] ${l.trim()}${RST}\n`);
        }
        if (!resolved && (line.includes('Running on') || line.includes('localhost'))) {
          resolved = true;
          clearTimeout(timeout);
          this._serverReady = true;
          resolve(port);
        }
      });

      proc.on('error', (err) => {
        clearTimeout(timeout);
        if (!resolved) {
          resolved = true;
          reject(new Error(`Failed to start server: ${err.message}`));
        }
      });

      proc.on('exit', (code) => {
        console.log(`[SweDesignManager] Server exited with code ${code}`);
        this._serverProcess = null;
        this._serverReady = false;
        if (!resolved) {
          resolved = true;
          clearTimeout(timeout);
          // Include stderr in error for port-conflict detection
          reject(new Error(`Server exited with code ${code}: ${stderrBuf.slice(-300)}`));
        }
      });
    });
  }

  /**
   * Show the SWE Design wizard BrowserView.
   * Starts the Python dashboard server on first call.
   */
  async show() {
    if (!this.mainWindow) {
      console.error('[SweDesignManager] No main window available');
      return;
    }

    // Prevent concurrent start attempts
    if (this._starting) {
      console.log('[SweDesignManager] Already starting, please wait...');
      return;
    }

    try {
      // Start server if not running
      if (!this._serverReady) {
        this._starting = true;
        console.log('[SweDesignManager] Starting RE dashboard server...');
        this.port = await this._startServer();
        this._starting = false;
      }

      // Create BrowserView if needed
      if (!this.view) {
        this.view = new BrowserView({
          webPreferences: {
            contextIsolation: true,
            nodeIntegration: false,
            sandbox: false,
          },
        });

        // Position and attach
        this.mainWindow.setBrowserView(this.view);
        this._updateBounds();

        // Load the server URL (cache-bust to avoid stale Chromium cache)
        const url = `http://localhost:${this.port}?_t=${Date.now()}`;
        console.log('[SweDesignManager] Loading:', url);
        this.view.webContents.session.clearCache().then(() => {
          this.view.webContents.loadURL(url);
        });

        // Handle external links
        this.view.webContents.setWindowOpenHandler(({ url }) => {
          require('electron').shell.openExternal(url);
          return { action: 'deny' };
        });

        // Notify renderer of load status
        this.view.webContents.on('did-finish-load', () => {
          if (this.mainWindow && !this.mainWindow.isDestroyed()) {
            this.mainWindow.webContents.send('python-message', {
              type: 'swedesign_view_status',
              status: 'ready',
            });
          }
          console.log('[SweDesignManager] Dashboard loaded');
        });

        this.view.webContents.on('did-fail-load', (_ev, code, desc) => {
          if (this.mainWindow && !this.mainWindow.isDestroyed()) {
            this.mainWindow.webContents.send('python-message', {
              type: 'swedesign_view_status',
              status: 'error',
              message: `Load failed: ${desc} (${code})`,
            });
          }
          console.error('[SweDesignManager] Load failed:', code, desc);
        });
      } else {
        // Re-attach existing view
        this.mainWindow.setBrowserView(this.view);
        this._updateBounds();
      }

      this.isVisible = true;
      console.log('[SweDesignManager] Shown');
    } catch (err) {
      this._starting = false;
      console.error('[SweDesignManager] Failed to show:', err.message);
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'swedesign_view_status',
          status: 'error',
          message: err.message,
        });
      }
    }
  }

  /**
   * Hide the BrowserView (server stays alive for fast re-show).
   */
  hide() {
    if (!this.mainWindow || !this.view) return;
    this.mainWindow.setBrowserView(null);
    this.isVisible = false;
    console.log('[SweDesignManager] Hidden');
  }

  /**
   * Relay a push event to the SWE Design BrowserView
   */
  relayEvent(channel, payload) {
    if (this.view && !this.view.webContents.isDestroyed()) {
      this.view.webContents.send(channel, payload);
    }
  }

  /**
   * Reload the wizard content
   */
  reload() {
    if (this.view && !this.view.webContents.isDestroyed()) {
      this.view.webContents.reload();
    }
  }

  /**
   * Check visibility
   */
  getIsVisible() {
    return this.isVisible;
  }

  /**
   * Destroy the view and stop the server.
   */
  destroy() {
    if (this.view) {
      this.hide();
      this.view = null;
    }
    // Kill Python server process
    if (this._serverProcess) {
      try {
        this._serverProcess.kill();
      } catch (e) {
        // ignore
      }
      this._serverProcess = null;
    }
    this._serverReady = false;
    console.log('[SweDesignManager] Destroyed');
  }

  // -- Private helpers --

  _getBounds() {
    const wb = this.mainWindow.getContentBounds();
    return {
      x: 0,
      y: this.topOffset,
      width: wb.width,
      height: wb.height - this.topOffset,
    };
  }

  _updateBounds() {
    if (!this.mainWindow || !this.view) return;
    this.view.setBounds(this._getBounds());
  }
}

module.exports = SweDesignManager;
