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
const { spawn, execFileSync } = require('child_process');

const FANG_COLOR = '\x1b[35m';  // Magenta
const RST = '\x1b[0m';

class OpenFangManager {
  constructor() {
    this._process = null;
    this._ready = false;
    this._starting = false;
    this.port = null;

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

  /**
   * Start the OpenFang daemon. Resolves when the API is ready.
   */
  async start() {
    if (this._ready || this._starting) return;

    // Check if already running externally
    try {
      const http = require('http');
      const running = await new Promise((resolve) => {
        const req = http.get('http://127.0.0.1:4200/api/health', { timeout: 1000 }, (res) => {
          resolve(res.statusCode === 200);
          res.resume();
        });
        req.on('error', () => resolve(false));
        req.on('timeout', () => { req.destroy(); resolve(false); });
      });
      if (running) {
        console.log(`${FANG_COLOR}[OpenFang]${RST} Already running externally on port 4200`);
        this.port = 4200;
        this._ready = true;
        return;
      }
    } catch { /* continue to spawn */ }

    if (!fs.existsSync(this._binary) && this._binary !== 'openfang') {
      console.warn(`${FANG_COLOR}[OpenFang]${RST} Binary not found at ${this._binary}, skipping`);
      return;
    }

    this._starting = true;
    console.log(`${FANG_COLOR}[OpenFang]${RST} Starting daemon: ${this._binary}`);

    return new Promise((resolve) => {
      const _configFile = path.join(this._cwd, 'openfang.vibemind.toml');
      const _configArgs = fs.existsSync(_configFile) ? ['--config', _configFile] : [];
      const proc = spawn(this._binary, ['start', ..._configArgs], {
        cwd: this._cwd,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: { ...process.env },
        detached: false,
      });

      this._process = proc;
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
    if (!this._process && !this._ready) return;

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
        execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], { timeout: 5000 });
      } else {
        process.kill(-pid, 'SIGKILL');
      }
    } catch { /* already dead */ }
    this._process = null;
    this._ready = false;
  }
}

module.exports = OpenFangManager;
