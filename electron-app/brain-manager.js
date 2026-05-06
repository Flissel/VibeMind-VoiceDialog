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

    // Python path: prefer repo-root .venv (Python 3.11 — verified working)
    // over voice/.venv312 (Python 3.12 — has qdrant_kg init bug).
    // Falls back to system 'python' as last resort.
    const projectRoot = path.resolve(__dirname, '..');
    const repoRoot = path.resolve(projectRoot, '..', '..');  // .../Vibemind_V1
    const candidates = [
      path.join(repoRoot, '.venv', 'Scripts', 'python.exe'),       // repo .venv (3.11) — preferred
      path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),    // voice/.venv if any
      path.join(projectRoot, '.venv312', 'Scripts', 'python.exe'), // voice/.venv312 (3.12) — fallback
    ];
    this.pythonPath = candidates.find(p => fs.existsSync(p)) || 'python';
    console.log(`[BrainManager] Using python: ${this.pythonPath}`);

    // Brain project root — try root-level brain/ first, then legacy submodule, then standalone
    const rootBrainPath = path.join(projectRoot, '..', 'brain', 'the_brain');
    const submodulePath = path.join(projectRoot, 'python', 'spaces', 'brain', 'the_brain');
    const standalonePath = path.join('C:', 'Users', 'User', 'Desktop', 'the_brain', 'the_brain');

    if (fs.existsSync(path.join(rootBrainPath, 'web', 'brain_server.py'))) {
      this.brainProjectRoot = rootBrainPath;
    } else if (fs.existsSync(path.join(submodulePath, 'web', 'brain_server.py'))) {
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
   * Start the Brain FastAPI server. Stays on port 5000 (the canonical Brain
   * port that everything else points at) and retries up to 6 times with
   * 3-second back-off when the port is busy. Only falls back to the next
   * port as a last resort. This avoids the race where a previous brain
   * shutdown is still cleaning up TCP state and a fresh-spawn fails.
   */
  async _startServer() {
    if (this._serverReady) return this.port;

    const serverModule = 'web.brain_server';
    const basePort = this.port;
    const portRetries = 6;            // retries on basePort
    const backoffMs = 3000;
    const fallbackPorts = [basePort + 1, basePort + 2];

    // First: keep trying basePort with back-off
    for (let attempt = 0; attempt < portRetries; attempt++) {
      try {
        await this._tryStartOnPort(serverModule, basePort);
        this.port = basePort;
        return basePort;
      } catch (err) {
        const isPortConflict = err.message.includes('10048') ||
                               err.message.includes('address already in use') ||
                               err.message.includes('EADDRINUSE');
        if (isPortConflict) {
          console.log(`[BrainManager] Port ${basePort} busy (attempt ${attempt + 1}/${portRetries}), waiting ${backoffMs}ms...`);
          // Probe: maybe an earlier brain is already running on this port
          // (race-condition where vibemind starts twice). If health check
          // says yes, skip spawn entirely and adopt the existing instance.
          try {
            const ok = await this._probeHealth(basePort);
            if (ok) {
              console.log(`[BrainManager] Existing brain detected on ${basePort} — adopting`);
              this.port = basePort;
              this._serverReady = true;
              return basePort;
            }
          } catch (_) {}
          await new Promise(r => setTimeout(r, backoffMs));
          continue;
        }
        // Non-port error — propagate
        throw err;
      }
    }

    // Last resort — try next port
    for (const tryPort of fallbackPorts) {
      try {
        await this._tryStartOnPort(serverModule, tryPort);
        this.port = tryPort;
        console.log(`[BrainManager] Fell back to port ${tryPort}`);
        return tryPort;
      } catch (_) {}
    }
    throw new Error(`Brain server could not start on ${basePort} after ${portRetries} retries`);
  }

  async _probeHealth(port) {
    return new Promise((resolve) => {
      const http = require('http');
      const req = http.get({
        host: '127.0.0.1', port, path: '/api/health', timeout: 2000,
      }, (res) => {
        resolve(res.statusCode === 200);
        res.resume();
      });
      req.on('error', () => resolve(false));
      req.on('timeout', () => { req.destroy(); resolve(false); });
    });
  }

  /**
   * Try to start the server on a specific port.
   */
  _tryStartOnPort(serverModule, port) {
    return new Promise((resolve, reject) => {
      console.log(`[BrainManager] Starting brain server on port ${port}...`);
      console.log(`[BrainManager] CWD: ${this.brainProjectRoot}`);

      // Phase 11 — ensure brain has the right env defaults so KG init,
      // ollama fallback, and PYTHONPATH-driven imports all work.
      const repoRoot = path.resolve(this.brainProjectRoot, '..', '..', '..');
      const envOverrides = {
        // Default Qdrant to the docker-mapped port (16333 is the python-default
        // but the project uses 6340; keep what's already in env if set)
        QDRANT_URL: process.env.QDRANT_URL || 'http://127.0.0.1:6340',
        // Phase 10 — local Ollama as last-resort planner when cloud LLMs fail
        PLANNER_OLLAMA_FALLBACK: process.env.PLANNER_OLLAMA_FALLBACK || 'llama3.1:latest',
        // Make sure brain.the_brain package + spaces siblings are importable
        PYTHONPATH: process.env.PYTHONPATH || this.brainProjectRoot,
      };
      const proc = spawn(this.pythonPath, [
        '-m', serverModule,
        '--port', String(port),
      ], {
        cwd: this.brainProjectRoot,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: { ...process.env, ...envOverrides },
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
        } else if (!this._shuttingDown) {
          // Auto-restart on unexpected exit (e.g. crash mid-execution).
          // Schedule with back-off; user can stop it via this._shuttingDown=true.
          console.log(`[BrainManager] Auto-restart in 5s (exit code ${code})`);
          setTimeout(() => {
            if (!this._shuttingDown) {
              this._startServer().catch(e =>
                console.warn('[BrainManager] Auto-restart failed:', e.message)
              );
            }
          }, 5000);
        }
      });
    });
  }

  /**
   * Start the Brain server without UI (headless mode).
   * Called at app startup so routing + shadow training are available immediately.
   */
  async startHeadless() {
    if (this._serverReady || this._starting) return;
    this._starting = true;
    try {
      console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Starting brain server (headless)...`);
      this.port = await this._startServer();
      this._starting = false;
      console.log(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Brain server ready on port ${this.port} (headless)`);
    } catch (err) {
      this._starting = false;
      console.warn(`${BRAIN_MGR_COLOR}[BrainManager]${RST} Headless start failed: ${err.message}`);
    }
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
