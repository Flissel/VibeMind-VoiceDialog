/**
 * Port Allocator for VibeMind
 *
 * Manages port allocation for VNC viewers and app previews.
 * Adapted from Coding Engine dashboard-app.
 *
 * VNC Ports: 6081, 6082, 6083, ...
 * App Ports: 3001, 3002, 3003, ...
 */

const net = require('net');
const { exec } = require('child_process');
const { promisify } = require('util');

const execAsync = promisify(exec);

class PortAllocator {
  constructor(options = {}) {
    // VNC ports start at 6200 to avoid Windows/Hyper-V TCP exclusion range
    // (Hyper-V often reserves 5940-6139 on Windows 11 + Docker Desktop)
    this.vncBasePort = 6200;
    this.appBasePort = 3001;
    this.maxPorts = 20;

    this.allocations = new Map();
    this.usedVncPorts = new Set();
    this.usedAppPorts = new Set();

    // Startprofil (Spec 2026-10-15): Aufraeumen nur mit "docker-cleanup".
    this._policy = options.policy || null;
    this._exec = options.execAsync || execAsync;
    this._logger = options.logger || console;
  }

  /**
   * Allocate a VNC port for a project
   */
  async allocate(projectId) {
    // Return existing allocation if exists
    const existing = this.allocations.get(projectId);
    if (existing) {
      return existing.vncPort;
    }

    // Find next available VNC port (checks OS-level availability)
    const vncPort = await this.findNextPort(this.vncBasePort, this.usedVncPorts);
    this.usedVncPorts.add(vncPort);

    // Initialize allocation (app port allocated separately)
    this.allocations.set(projectId, { vncPort, appPort: 0 });

    return vncPort;
  }

  /**
   * Allocate an app port for a project
   */
  async allocateAppPort(projectId) {
    const existing = this.allocations.get(projectId);
    if (existing && existing.appPort > 0) {
      return existing.appPort;
    }

    // Find next available app port (checks OS-level availability)
    const appPort = await this.findNextPort(this.appBasePort, this.usedAppPorts);
    this.usedAppPorts.add(appPort);

    if (existing) {
      existing.appPort = appPort;
    } else {
      this.allocations.set(projectId, { vncPort: 0, appPort });
    }

    return appPort;
  }

  /**
   * Release ports for a project
   */
  release(projectId) {
    const allocation = this.allocations.get(projectId);
    if (allocation) {
      this.usedVncPorts.delete(allocation.vncPort);
      this.usedAppPorts.delete(allocation.appPort);
      this.allocations.delete(projectId);
    }
  }

  /**
   * Get VNC port for a project
   */
  getVncPort(projectId) {
    return this.allocations.get(projectId)?.vncPort;
  }

  /**
   * Get app port for a project
   */
  getAppPort(projectId) {
    return this.allocations.get(projectId)?.appPort;
  }

  /**
   * Get all port allocations
   */
  getAllAllocations() {
    const result = {};
    for (const [projectId, allocation] of this.allocations) {
      result[projectId] = allocation;
    }
    return result;
  }

  /**
   * Check if a port is actually free on the OS by attempting to bind to it.
   */
  isPortFreeOnOS(port) {
    return new Promise((resolve) => {
      const server = net.createServer();
      server.once('error', () => resolve(false));
      server.once('listening', () => {
        server.close(() => resolve(true));
      });
      server.listen(port, '0.0.0.0');
    });
  }

  /**
   * Find next available port (checks both internal tracking and OS-level availability)
   */
  async findNextPort(basePort, usedPorts) {
    for (let i = 0; i < this.maxPorts; i++) {
      const port = basePort + i;
      if (usedPorts.has(port)) continue;
      if (await this.isPortFreeOnOS(port)) {
        return port;
      }
      console.log(`[PortAllocator] Port ${port} is in use on OS, skipping`);
    }
    throw new Error(`No available ports in range ${basePort}-${basePort + this.maxPorts}`);
  }

  /**
   * Check if a specific port is available
   */
  isPortAvailable(port) {
    return !this.usedVncPorts.has(port) && !this.usedAppPorts.has(port);
  }

  /**
   * Sync port allocations with running Docker containers.
   * Call this on app startup to detect containers from previous sessions.
   */
  async syncWithDocker() {
    try {
      const { stdout } = await execAsync('docker ps --format "{{.Names}}|{{.Ports}}"');

      for (const line of stdout.split('\n').filter(Boolean)) {
        const [name, ports] = line.split('|');

        if (!name.startsWith('generation-') && !name.startsWith('project-')) {
          continue;
        }

        const vncMatch = ports?.match(/0\.0\.0\.0:(\d+)->6080/);
        const appMatch = ports?.match(/0\.0\.0\.0:(\d+)->5173/);

        if (vncMatch) {
          this.usedVncPorts.add(parseInt(vncMatch[1]));
        }
        if (appMatch) {
          this.usedAppPorts.add(parseInt(appMatch[1]));
        }

        const projectId = name.replace(/^(generation-|project-)/, '');
        if (vncMatch || appMatch) {
          this.allocations.set(projectId, {
            vncPort: vncMatch ? parseInt(vncMatch[1]) : 0,
            appPort: appMatch ? parseInt(appMatch[1]) : 0
          });
        }
      }

      console.log(`[PortAllocator] Synced with Docker: ${this.usedVncPorts.size} VNC ports, ${this.usedAppPorts.size} app ports in use`);
    } catch (error) {
      if (error.code === 'ENOENT' || error.message?.includes('not found')) {
        console.log('[PortAllocator] Docker not available, skipping sync');
      } else {
        console.warn('[PortAllocator] syncWithDocker error:', error.message);
      }
    }
  }

  /**
   * Entfernt generation-/project-Container frueherer Sitzungen – nur mit
   * Startprofil "docker-cleanup". Sonst wird nur geloggt, was entfernt worden waere.
   */
  async cleanupStaleContainers() {
    let names;
    try {
      const { stdout } = await this._exec('docker ps -a --format "{{.Names}}"');
      names = String(stdout)
        .split(/\r?\n/)
        .map((name) => name.trim())
        .filter((name) => name.startsWith('generation-') || name.startsWith('project-'));
    } catch {
      this._logger.log('[PortAllocator] No stale containers to clean');
      return { removed: [], skipped: [] };
    }

    if (!this._policy || !this._policy.isAllowed('docker-cleanup')) {
      const would = names.length > 0
        ? `docker rm -f ${names.join(' ')}`
        : 'keine generation-/project-Container vorhanden';
      if (this._policy) this._policy.logSkipped('docker-cleanup', would);
      else this._logger.warn(`[PortAllocator] kein Startprofil – nichts entfernt (${would})`);
      return { removed: [], skipped: names };
    }

    for (const name of names) {
      this._logger.log(`[PortAllocator] Removing stale container: ${name}`);
      try {
        await this._exec(`docker rm -f ${name}`);
      } catch { /* already gone */ }
    }
    this.allocations.clear();
    this.usedVncPorts.clear();
    this.usedAppPorts.clear();
    this._logger.log(`[PortAllocator] Cleaned up ${names.length} stale containers`);
    return { removed: names, skipped: [] };
  }
}

module.exports = PortAllocator;
