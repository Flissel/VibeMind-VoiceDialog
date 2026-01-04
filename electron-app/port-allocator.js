/**
 * Port Allocator for VibeMind
 *
 * Manages port allocation for VNC viewers and app previews.
 * Adapted from Coding Engine dashboard-app.
 *
 * VNC Ports: 6081, 6082, 6083, ...
 * App Ports: 3001, 3002, 3003, ...
 */

class PortAllocator {
  constructor() {
    this.vncBasePort = 6081;
    this.appBasePort = 3001;
    this.maxPorts = 20;

    this.allocations = new Map();
    this.usedVncPorts = new Set();
    this.usedAppPorts = new Set();
  }

  /**
   * Allocate a VNC port for a project
   */
  allocate(projectId) {
    // Return existing allocation if exists
    const existing = this.allocations.get(projectId);
    if (existing) {
      return existing.vncPort;
    }

    // Find next available VNC port
    const vncPort = this.findNextPort(this.vncBasePort, this.usedVncPorts);
    this.usedVncPorts.add(vncPort);

    // Initialize allocation (app port allocated separately)
    this.allocations.set(projectId, { vncPort, appPort: 0 });

    return vncPort;
  }

  /**
   * Allocate an app port for a project
   */
  allocateAppPort(projectId) {
    const existing = this.allocations.get(projectId);
    if (existing && existing.appPort > 0) {
      return existing.appPort;
    }

    // Find next available app port
    const appPort = this.findNextPort(this.appBasePort, this.usedAppPorts);
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
   * Find next available port
   */
  findNextPort(basePort, usedPorts) {
    for (let i = 0; i < this.maxPorts; i++) {
      const port = basePort + i;
      if (!usedPorts.has(port)) {
        return port;
      }
    }
    throw new Error(`No available ports in range ${basePort}-${basePort + this.maxPorts}`);
  }

  /**
   * Check if a specific port is available
   */
  isPortAvailable(port) {
    return !this.usedVncPorts.has(port) && !this.usedAppPorts.has(port);
  }
}

module.exports = PortAllocator;
