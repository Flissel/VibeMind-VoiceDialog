/**
 * OpenFang Daemon Manager for VibeMind
 *
 * Headless manager for the OpenFang Agent OS daemon.
 * Spawns the Rust binary on app start, kills on quit.
 *
 * Lifecycle:
 *   start()   → spawn openfang.exe start (or cargo run)
 *   stop()    → graceful shutdown via API, then kill
 *   destroy() → force kill process
 */

const path = require('path');
const fs = require('fs');
const http = require('http');
const { spawn, execFileSync } = require('child_process');

const FANG_COLOR = '[35m';  // Magenta
const RST = '[0m';

// Spec 2026-10-15: nur uebernehmen. Grosszuegige Probe (3 s x 3), damit ein langsam
// antwortendes, laufendes OpenFang nie ein zweites openfang.exe ausloest.
const DEFAULT_HEALTH_URL = 'http://127.0.0.1:4200/api/health';
const HEALTH_TIMEOUT_MS = 3000;
const HEALTH_ATTEMPTS = 3;
const HEALTH_RETRY_DELAY_MS = 500;

function probeHttpOk(url, timeoutMs) {
  return new Promise((resolve) => {
    let settled = false;
    const done = (value) => { if (!settled) { settled = true; resolve(value); } };
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      res.resume();
      done(res.statusCode === 200);
    });
    req.on('error', () => done(false));
    req.on('timeout', () => { req.destroy(); done(false); });
  });
}

class OpenFangManager {
  constructor(dependencies = {}) {
    this._process = null;
    this._ready = false;
    this._starting = false;
    this._adopted = false;
    this.port = null;
    this.status = { state: 'unbekannt', reason: '' };

    this._policy = dependencies.policy || null;
    this._spawn = dependencies.spawn || spawn;
    this._execFileSync = dependencies.execFileSync || execFileSync;
    this._probe = dependencies.probeHealth || probeHttpOk;
    this._healthUrl = dependencies.healthUrl || DEFAULT_HEALTH_URL;
    this._logger = dependencies.logger || console;
    this._sleep = dependencies.sleep || ((ms) => new Promise((r) => setTimeout(r, ms)));

    // Find binary: release → debug → PATH
    const projectRoot = path.resolve(__dirname, '..', '..'); // vibemind-os/
    const releaseBin = path.join(projectRoot, 'openfang', 'target', 'release', 'openfang.exe');
    const debugBin = path.join(projectRoot, 'openfang', 'target', 'debug', 'openfang.exe');

    if (fs.existsSync(releaseBin)) {
      this._binary = releaseBin;
    } else if (fs.existsSync(debugBin)) {
      this._binary = debugBin;
    } else {
      this._binary = 'openfang'; // hope it's in PATH
    }

    this._cwd = path.join(projectRoot, 'openfang');
  }

  async _isRunningExternally() {
    for (let attempt = 0; attempt < HEALTH_ATTEMPTS; attempt += 1) {
      if (await this._probe(this._healthUrl, HEALTH_TIMEOUT_MS)) return true;
      if (attempt < HEALTH_ATTEMPTS - 1) await this._sleep(HEALTH_RETRY_DELAY_MS);
    }
    return false;
  }

  _spawnAllowed() {
    return !!this._policy && this._policy.isAllowed('openfang-spawn');
  }

  /**
   * Start the OpenFang daemon. Resolves when the API is ready.
   */
  async start() {
    if (this._ready || this._starting) return;

    if (await this._isRunningExternally()) {
      this.port = Number(new URL(this._healthUrl).port) || 4200;
      this._ready = true;
      this._adopted = true;
      this.status = { state: 'uebernommen', reason: '' };
      this._logger.log(`${FANG_COLOR}[OpenFang]${RST} Laeuft bereits auf Port ${this.port} – uebernommen`);
      return;
    }

    if (!this._spawnAllowed()) {
      this.status = { state: 'fehlt', reason: `keine Antwort von ${this._healthUrl} (openfang-spawn aus)` };
      if (this._policy) this._policy.logSkipped('openfang-spawn', `${this._binary} start`);
      this._logger.warn(`${FANG_COLOR}[OpenFang]${RST} nicht verfuegbar – ${this.status.reason}`);
      return;
    }

    if (!fs.existsSync(this._binary) && this._binary !== 'openfang') {
      console.warn(`${FANG_COLOR}[OpenFang]${RST} Binary not found at ${this._binary}, skipping`);
      return;
    }

    this._starting = true;
    console.log(`${FANG_COLOR}[OpenFang]${RST} Starting daemon: ${this._binary}`);

    return new Promise((resolve) => {
      const _configFile = path.join(this._cwd, 'openfang.vibemind.toml');
      const _configArgs = fs.existsSync(_configFile) ? ['--config', _configFile] : [];
      const proc = this._spawn(this._binary, ['start', ..._configArgs], {
        cwd: this._cwd,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: { ...process.env },
        detached: false,
      });

      this._process = proc;
      this.status = { state: 'gestartet', reason: '' };
      let resolved = false;

      // Timeout: assume ready after 20s
      const timeout = setTimeout(() => {
        if (!resolved) {
          resolved = true;
          this._starting = false;
          this._ready = true;
          console.log(`${FANG_COLOR}[OpenFang]${RST} Startup timeout — assuming ready`);
          resolve();
        }
      }, 20000);

      proc.stdout.on('data', (data) => {
        const line = data.toString();
        for (const l of line.split('\n').filter(s => s.trim())) {
          // Strip ANSI codes for cleaner output
          const clean = l.replace(/\x1b\[[0-9;]*m/g, '').trim();
          if (clean) process.stdout.write(`${FANG_COLOR}[OpenFang] ${clean}${RST}\n`);
        }
        // Detect ready state
        if (!resolved && (
          line.includes('API server listening') ||
          line.includes('listening on http')
        )) {
          resolved = true;
          clearTimeout(timeout);
          this._starting = false;
          this._ready = true;
          // Extract port from log line
          const portMatch = line.match(/:(\d+)/);
          this.port = portMatch ? parseInt(portMatch[1]) : 4200;
          console.log(`${FANG_COLOR}[OpenFang]${RST} Daemon ready on port ${this.port}`);
          resolve();
        }
      });

      proc.stderr.on('data', (data) => {
        const line = data.toString();
        for (const l of line.split('\n').filter(s => s.trim())) {
          const clean = l.replace(/\x1b\[[0-9;]*m/g, '').trim();
          if (clean) process.stderr.write(`${FANG_COLOR}[OpenFang] ${clean}${RST}\n`);
        }
        // OpenFang may log ready state to stderr
        if (!resolved && (
          line.includes('API server listening') ||
          line.includes('listening on http')
        )) {
          resolved = true;
          clearTimeout(timeout);
          this._starting = false;
          this._ready = true;
          const portMatch = line.match(/:(\d+)/);
          this.port = portMatch ? parseInt(portMatch[1]) : 4200;
          console.log(`${FANG_COLOR}[OpenFang]${RST} Daemon ready on port ${this.port}`);
          resolve();
        }
      });

      proc.on('error', (err) => {
        clearTimeout(timeout);
        this._starting = false;
        console.warn(`${FANG_COLOR}[OpenFang]${RST} Failed to start: ${err.message}`);
        if (!resolved) { resolved = true; resolve(); }
      });

      proc.on('exit', (code) => {
        clearTimeout(timeout);
        this._process = null;
        this._ready = false;
        this._starting = false;
        console.log(`${FANG_COLOR}[OpenFang]${RST} Daemon exited with code ${code}`);
        if (!resolved) { resolved = true; resolve(); }
      });
    });
  }

  /**
   * Graceful shutdown: POST /api/shutdown, then kill.
   */
  async stop() {
    // Nie einen uebernommenen (fremden) Daemon herunterfahren – nur den eigenen.
    if (!this._process) return;

    // Try graceful shutdown via API
    if (this._ready && this.port) {
      try {
        const http = require('http');
        await new Promise((resolve) => {
          const req = http.request({
            hostname: '127.0.0.1',
            port: this.port,
            path: '/api/shutdown',
            method: 'POST',
            timeout: 3000,
          }, (res) => { res.resume(); resolve(); });
          req.on('error', () => resolve());
          req.on('timeout', () => { req.destroy(); resolve(); });
          req.end();
        });
        // Wait for graceful exit
        await new Promise(r => setTimeout(r, 2000));
      } catch { /* fall through to kill */ }
    }

    this._forceKill();
  }

  /**
   * Force kill the process.
   */
  destroy() {
    this._forceKill();
    console.log(`${FANG_COLOR}[OpenFang]${RST} Destroyed`);
  }

  isReady() {
    return this._ready;
  }

  getPort() {
    return this.port;
  }

  _forceKill() {
    if (!this._process) return;
    const pid = this._process.pid;
    try {
      if (process.platform === 'win32') {
        this._execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], { timeout: 5000 });
      } else {
        process.kill(-pid, 'SIGKILL');
      }
    } catch { /* already dead */ }
    this._process = null;
    this._ready = false;
  }
}

module.exports = OpenFangManager;
module.exports.probeHttpOk = probeHttpOk;
