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

const { resolveElectronParts, statusCardUrl, loadOverlay } = require('./overlay-status');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

const SPACE_NAME = 'SWE Design';
/** What the status card says when the stage view does not answer (the app does not start it). */
const SWE_HINT = 'Die Ansicht kommt vom SWE-Design-Dienst, der außerhalb der App läuft. '
  + 'Sobald er gestartet ist, den Reiter erneut öffnen.';
const MAX_REASON_STDERR = 160;

// ANSI colors for SWE Design space logs
const SWE_COLOR = '\x1b[96m';     // Bright Cyan
const SWE_MGR_COLOR = '\x1b[96m'; // Bright Cyan
const RST = '\x1b[0m';

/**
 * Resolve a path inside python/spaces/<subdir...>, working around the
 * broken-symlink-on-Windows case. python/spaces is git-committed as a
 * symlink to ../../spaces (= vibemind-os/spaces). On Linux/Mac and
 * Win-with-symlink-rights this just works via path.join + fs. On
 * Windows without symlink rights, git stores it as a plain 12-byte
 * file with the literal text "../../spaces"; fs.existsSync on inner
 * paths returns false. We try both candidates and return the first
 * one that exists. Cross-platform safe.
 *
 * @param {string} projectRoot — typically `path.resolve(__dirname, '..')`
 *                                (= voice/ root, so `voice/`).
 * @param {...string} parts — path segments under spaces/, e.g. 'shuttles', 'swe_desgine'.
 * @returns {string} — the resolved absolute path (first existing candidate),
 *                     falling back to the symlink-style path so the caller
 *                     still gets a deterministic value to log on failure.
 */
function resolveSpacesPath(projectRoot, ...parts) {
  // Candidate 1: through python/spaces (works if symlink resolves)
  const viaSymlink = path.join(projectRoot, 'python', 'spaces', ...parts);
  if (fs.existsSync(viaSymlink)) return viaSymlink;

  // Candidate 2: directly to vibemind-os/spaces (symlink target)
  const viaDirect = path.join(projectRoot, '..', 'spaces', ...parts);
  if (fs.existsSync(viaDirect)) return viaDirect;

  // Candidate 3: read the "symlink" file content explicitly. Some
  // setups stash the relative target inside that text file —
  // safety net if naming ever diverges from `../../spaces`.
  try {
    const linkFile = path.join(projectRoot, 'python', 'spaces');
    if (fs.existsSync(linkFile) && fs.statSync(linkFile).isFile()) {
      const target = fs.readFileSync(linkFile, 'utf8').trim();
      if (target) {
        const candidate = path.join(path.dirname(linkFile), target, ...parts);
        if (fs.existsSync(candidate)) return candidate;
      }
    }
  } catch (_) { /* ignore — fall through */ }

  // No candidate exists: return the symlink-style path so the caller
  // logs a sensible error like "ENOENT: .../python/spaces/...".
  return viaSymlink;
}

/**
 * Python fuer den SWE-Design-Server. Bevorzugt die eigene venv des Space
 * (<reProjectRoot>\.venv, vom Update-Skript angelegt), weil dessen requirements.txt
 * (openai, anthropic, transformers, ...) die voice-venv nicht beruehren darf.
 * Rueckfall: voice/.venv312, dann 'python'.
 */
function resolvePythonPath(projectRoot, reProjectRoot, existsSync = fs.existsSync) {
  const sweVenv = path.join(reProjectRoot, '.venv', 'Scripts', 'python.exe');
  if (existsSync(sweVenv)) return sweVenv;
  const venv312 = path.join(projectRoot, '.venv312', 'Scripts', 'python.exe');
  return existsSync(venv312) ? venv312 : 'python';
}

/** Kurzgrund fuer die Statuskarte: "Server beendet (Exit N): <Zeile aus stderr>". */
const DEFAULT_STAGE_URL = 'http://127.0.0.1:8162/';

/** Address of the stage view: SWE_DESIGN_UI_URL when it is a valid http(s) address, else this machine. */
function stageViewUrl(env = process.env) {
  const text = typeof env.SWE_DESIGN_UI_URL === 'string' ? env.SWE_DESIGN_UI_URL.trim() : '';
  try {
    const url = new URL(text);
    if (url.protocol === 'http:' || url.protocol === 'https:') return url.href;
  } catch (_) { /* not set or not an address */ }
  return DEFAULT_STAGE_URL;
}

function exitReason(code, stderr) {
  const lines = String(stderr || '').split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  // Python-Traceback: die aussagekraeftige Zeile (Exception) steht am Ende, sonst die erste.
  const line = lines.length === 0 ? '' : (lines[0].startsWith('Traceback') ? lines[lines.length - 1] : lines[0]);
  const short = line.length > MAX_REASON_STDERR ? `${line.slice(0, MAX_REASON_STDERR - 1)}…` : line;
  return `Server beendet (Exit ${code})${short ? `: ${short}` : ''}`;
}

class SweDesignManager {
  constructor(mainWindow, dependencies = {}) {
    const { BrowserView, shell } = resolveElectronParts(dependencies, ['BrowserView', 'shell']);
    this.BrowserView = BrowserView;
    this.shell = shell;
    this._existsSync = dependencies.existsSync || fs.existsSync;
    this._spawn = dependencies.spawn || spawn;
    this._overlayDeps = dependencies.overlayDeps || {};
    this._cardShown = false;
    this.mainWindow = mainWindow;
    this.view = null;
    this.isVisible = false;
    this._starting = false;
    this._serverProcess = null;
    this._serverReady = false;

    // Titlebar (32px) + space-nav tab bar (42px + 1px border)
    this.topOffset = 32 + 43;

    const projectRoot = dependencies.projectRoot || path.resolve(__dirname, '..');

    // RE project root (where start_dashboard.py lives).
    //
    // Cross-platform path-resolution: `python/spaces` is committed in git
    // as a symlink to `../../spaces` (= vibemind-os/spaces). On Linux/Mac
    // and Win-with-Developer-Mode the symlink resolves automatically. On
    // Windows without symlink rights git materialises it as a 12-byte
    // text file containing "../../spaces" — `fs.existsSync` on any inner
    // path returns false ("Not a directory"). We probe both candidates.
    this.reProjectRoot = resolveSpacesPath(
      projectRoot, 'shuttles', 'swe_desgine'
    );

    // Python path: own swe_desgine/.venv first, then voice/.venv312, then 'python'
    this.pythonPath = resolvePythonPath(projectRoot, this.reProjectRoot, this._existsSync);

    this.port = 8086; // old dashboard (wizard); 8085 often held by zombie

    // Stage view of the space. The service accepts the host name 127.0.0.1 only (anything else: 403),
    // so never "localhost" here.
    this.stageUrl = stageViewUrl(dependencies.env || process.env);

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

      const proc = this._spawn(this.pythonPath, [
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
          const err = new Error(`Server exited with code ${code}: ${stderrBuf.slice(-300)}`);
          err.exitCode = code;
          err.stderr = stderrBuf;
          reject(err);
        }
      });
    });
  }

  /**
   * Show the SWE Design BrowserView: the stage view of the space (run, six stages, results).
   *
   * The page is served by the space itself on this machine; the app only embeds it. It replaced
   * the old "RE System Dashboard" as the main view: that page reads the projects of a pipeline
   * that no longer runs and stayed empty whatever the stage run did. The app therefore no longer
   * starts the old server here (_startServer stays for the wizard, which is not linked yet).
   * When the service is not there, the usual status card says so.
   */
  async show() {
    if (!this.mainWindow) {
      console.error('[SweDesignManager] No main window available');
      return;
    }
    const first = !this.view;
    if (first) {
      this._createView();
    } else {
      this.mainWindow.setBrowserView(this.view);
      this._updateBounds();
    }
    this.isVisible = true;
    // A status card is checked again on every opening: the service may be up now.
    if (first || this._cardShown) await this._loadStageView();
    console.log('[SweDesignManager] Shown');
  }

  /** Load the stage view, or the status card when its service does not answer. */
  async _loadStageView() {
    const result = await loadOverlay(
      this.view.webContents,
      { space: SPACE_NAME, targets: [{ kind: 'url', url: this.stageUrl }], hint: SWE_HINT },
      this._overlayDeps,
    );
    this._cardShown = !result.ok;
    if (!result.ok && this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.webContents.send('python-message', {
        type: 'swedesign_view_status', status: 'error', message: result.reason,
      });
    }
    return result;
  }

  /** Create the BrowserView, attach it and wire the status events. */
  _createView() {
    this.view = new this.BrowserView({
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    });

    // Position and attach
    this.mainWindow.setBrowserView(this.view);
    this._updateBounds();

    // Handle external links
    this.view.webContents.setWindowOpenHandler(({ url }) => {
      this.shell.openExternal(url);
      return { action: 'deny' };
    });

    // Notify renderer of load status
    this.view.webContents.on('did-finish-load', () => {
      if (this._cardShown) return;
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
  }

  /** Load the running dashboard into the view (cache-bust to avoid stale Chromium cache). */
  _loadDashboard() {
    this._cardShown = false;
    const url = `http://localhost:${this.port}?_t=${Date.now()}`;
    console.log('[SweDesignManager] Loading:', url);
    this.view.webContents.session.clearCache().then(() => {
      this.view.webContents.loadURL(url);
    });
  }

  /** Statuskarte statt leerer Flaeche, wenn der Server nicht startet. */
  _showCard(reason) {
    try {
      if (!this.view) this._createView();
      else this.mainWindow.setBrowserView(this.view);
      this._updateBounds();
      this._cardShown = true;
      this.isVisible = true;
      const target = path.join(this.reProjectRoot, 'start_dashboard.py');
      this.view.webContents.loadURL(statusCardUrl({ space: SPACE_NAME, reason, target }));
    } catch (cardErr) {
      console.error('[SweDesignManager] Statuskarte fehlgeschlagen:', cardErr.message);
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
module.exports.resolvePythonPath = resolvePythonPath;
module.exports.exitReason = exitReason;
module.exports.stageViewUrl = stageViewUrl;
