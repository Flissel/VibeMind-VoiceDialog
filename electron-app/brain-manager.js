/**
 * Brain Dashboard Manager for VibeMind
 *
 * Self-contained manager for the Brain (Tahlamus) dashboard.
 * Spawns the Python FastAPI brain_server and creates a BrowserView overlay.
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

// ANSI colors for Brain space logs
const BRAIN_COLOR = '\x1b[32m';   // Dark Green (matches SpaceLogger)
const BRAIN_MGR_COLOR = '\x1b[32m'; // Dark Green
const RST = '\x1b[0m';

class BrainManager {
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

    // Brain project root — try submodule first, then standalone Desktop location
    const submodulePath = path.join(projectRoot, 'python', 'spaces', 'brain', 'the_brain');
    const standalonePath = path.join('C:', 'Users', 'User', 'Desktop', 'the_brain', 'the_brain');

    if (fs.existsSync(path.join(submodulePath, 'web', 'brain_server.py'))) {
      this.brainProjectRoot = submodulePath;
    } else if (fs.existsSync(path.join(standalonePath, 'web', 'brain_server.py'))) {
      this.brainProjectRoot = standalonePath;
    } else {
      this.brainProjectRoot = standalonePath; // fallback
    }

    this.port = 5000;
    this._loadRetries = 0;
    this._maxLoadRetries = 10;

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
   * Start the Brain FastAPI server with port retry.
   */
  async _startServer() {
    if (this._serverReady) return this.port;

    const serverModule = 'web.brain_server';

    // Try up to 3 ports
    const maxRetries = 3;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      const tryPort = this.port + attempt;
      try {
        await this._tryStartOnPort(serverModule, tryPort);
        this.port = tryPort;
        return this.port;
      } catch (err) {
        const isPortConflict = err.message.includes('10048') ||
                               err.message.includes('address already in use') ||
                               err.message.includes('EADDRINUSE');
        if (isPortConflict && attempt < maxRetries - 1) {
          console.log(`[BrainManager] Port ${tryPort} busy, trying ${tryPort + 1}...`);
          continue;
        }
        throw err;
      }
    }
  }

  /**
   * Try to start the server on a specific port.
   */
  _tryStartOnPort(serverModule, port) {
    return new Promise((resolve, reject) => {
      console.log(`[BrainManager] Starting brain server on port ${port}...`);
      console.log(`[BrainManager] CWD: ${this.brainProjectRoot}`);

      const proc = spawn(this.pythonPath, [
        '-m', serverModule,
        '--port', String(port),
      ], {
        cwd: this.brainProjectRoot,
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
          console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Server start timeout — assuming ready on port`, port);
          resolve(port);
        }
      }, 15000);

      proc.stdout.on('data', (data) => {
        const line = data.toString();
        // Colored output — one write per line to avoid duplicates
        for (const l of line.split('\n').filter(s => s.trim())) {
          process.stdout.write(`${BRAIN_COLOR}[Brain-Server] ${l.trim()}${RST}\n`);
        }
        if (!resolved && (
          line.includes('Uvicorn running') ||
          line.includes('Application startup complete')
        )) {
          resolved = true;
          clearTimeout(timeout);
          this._serverReady = true;
          console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Server ready on port`, port);
          resolve(port);
        }
      });

      proc.stderr.on('data', (data) => {
        const line = data.toString();
        stderrBuf += line;
        // Colored output — one write per line to avoid duplicates
        for (const l of line.split('\n').filter(s => s.trim())) {
          process.stderr.write(`${BRAIN_COLOR}[Brain-Server] ${l.trim()}${RST}\n`);
        }
        if (!resolved && (
          line.includes('Uvicorn running') ||
          line.includes('Application startup complete') ||
          line.includes('Running on http')
        )) {
          resolved = true;
          clearTimeout(timeout);
          this._serverReady = true;
          console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Server ready on port`, port);
          resolve(port);
        }
      });

      proc.on('error', (err) => {
        clearTimeout(timeout);
        if (!resolved) {
          resolved = true;
          reject(new Error(`Failed to start brain server: ${err.message}`));
        }
      });

      proc.on('exit', (code) => {
        console.log(`[BrainManager] Server exited with code ${code}`);
        this._serverProcess = null;
        this._serverReady = false;
        if (!resolved) {
          resolved = true;
          clearTimeout(timeout);
          reject(new Error(`Brain server exited with code ${code}: ${stderrBuf.slice(-300)}`));
        }
      });
    });
  }

  /**
   * Show the Brain dashboard BrowserView.
   * Starts the Python server on first call.
   */
  async show() {
    if (!this.mainWindow) {
      console.error('[BrainManager] No main window available');
      return;
    }

    // Prevent concurrent start attempts
    if (this._starting) {
      console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Already starting, please wait...`);
      return;
    }

    try {
      // Start server if not running
      if (!this._serverReady) {
        this._starting = true;
        console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Starting brain dashboard server...`);
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

        // Load the Unified Brain Dashboard (dark theme, thought stream, chat)
        const url = `http://localhost:${this.port}/brain`;
        console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Loading:`, url);
        this.view.webContents.loadURL(url);

        // Handle external links
        this.view.webContents.setWindowOpenHandler(({ url }) => {
          require('electron').shell.openExternal(url);
          return { action: 'deny' };
        });

        // Notify renderer of load status
        this.view.webContents.on('did-finish-load', () => {
          this._loadRetries = 0; // Reset on success
          if (this.mainWindow && !this.mainWindow.isDestroyed()) {
            this.mainWindow.webContents.send('python-message', {
              type: 'brain_view_status',
              status: 'ready',
            });
          }
          console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Dashboard loaded successfully`);
        });

        this.view.webContents.on('did-fail-load', (_ev, code, desc) => {
          console.error(`[BrainManager] Load failed (attempt ${this._loadRetries + 1}/${this._maxLoadRetries}):`, code, desc);
          // Retry on connection refused (server still starting)
          if (code === -102 && this._serverProcess && this._loadRetries < this._maxLoadRetries) {
            this._loadRetries++;
            const delay = Math.min(2000 * this._loadRetries, 5000);
            console.log(`[BrainManager] Server not ready yet, retrying in ${delay}ms...`);
            setTimeout(() => {
              if (this.view && !this.view.webContents.isDestroyed()) {
                const retryUrl = `http://localhost:${this.port}/brain`;
                console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Retrying:`, retryUrl);
                this.view.webContents.loadURL(retryUrl);
              }
            }, delay);
          } else if (this.mainWindow && !this.mainWindow.isDestroyed()) {
            this.mainWindow.webContents.send('python-message', {
              type: 'brain_view_status',
              status: 'error',
              message: `Load failed: ${desc} (${code})`,
            });
          }
        });
      } else {
        // Re-attach existing view
        this.mainWindow.setBrowserView(this.view);
        this._updateBounds();
        // Reload if previous load failed
        if (this._loadRetries > 0) {
          const url = `http://localhost:${this.port}/brain`;
          console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Reloading after previous failure:`, url);
          this._loadRetries = 0;
          this.view.webContents.loadURL(url);
        }
      }

      this.isVisible = true;
      console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Shown`);
    } catch (err) {
      this._starting = false;
      console.error('[BrainManager] Failed to show:', err.message);
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('python-message', {
          type: 'brain_view_status',
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
    console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Hidden`);
  }

  /**
   * Relay a push event to the Brain BrowserView
   */
  relayEvent(channel, payload) {
    if (this.view && !this.view.webContents.isDestroyed()) {
      this.view.webContents.send(channel, payload);
    }
  }

  /**
   * Reload the dashboard
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
    console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Destroyed`);
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

module.exports = BrainManager;
