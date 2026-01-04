/**
 * Docker Manager for VibeMind
 *
 * Manages Docker containers for project previews and the Coding Engine stack.
 * Adapted from Coding Engine dashboard-app for VibeMind integration.
 */

const { spawn, exec } = require('child_process');
const { promisify } = require('util');
const path = require('path');

const execAsync = promisify(exec);

class DockerManager {
  constructor() {
    this.containers = new Map();
    this.engineProcess = null;
    this.engineRunning = false;

    // Path to Coding Engine - configurable via environment
    this.engineRoot = process.env.CODING_ENGINE_PATH ||
      path.join(__dirname, '..', '..', '..', 'Coding_engine');
  }

  /**
   * Start the Coding Engine Docker stack
   */
  async startEngine() {
    try {
      const composeFile = path.join(this.engineRoot, 'infra', 'docker', 'docker-compose.dashboard.yml');

      const { stdout, stderr } = await execAsync(
        `docker-compose -f "${composeFile}" up -d`,
        { cwd: this.engineRoot }
      );

      this.engineRunning = true;
      console.log('[DockerManager] Engine started:', stdout);

      return { success: true };
    } catch (error) {
      console.error('[DockerManager] Failed to start engine:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * Stop the Coding Engine Docker stack
   */
  async stopEngine() {
    try {
      const composeFile = path.join(this.engineRoot, 'infra', 'docker', 'docker-compose.dashboard.yml');

      await execAsync(
        `docker-compose -f "${composeFile}" down`,
        { cwd: this.engineRoot }
      );

      this.engineRunning = false;
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Get Engine status
   */
  async getEngineStatus() {
    try {
      const { stdout } = await execAsync('docker ps --format "{{.Names}}"');
      const services = stdout.trim().split('\n').filter(name =>
        name.includes('coding-engine') || name.includes('postgres') || name.includes('redis')
      );

      return { running: services.length > 0, services };
    } catch {
      return { running: false, services: [] };
    }
  }

  /**
   * Start a project container with VNC for live preview
   */
  async startProjectContainer(projectId, outputDir, vncPort, appPort) {
    try {
      const containerName = `project-${projectId}`;

      // Check if container already exists
      const existing = this.containers.get(projectId);
      if (existing && existing.status === 'running') {
        return { success: true, vncPort: existing.vncPort, appPort: existing.appPort };
      }

      // Stop any existing container with same name
      await this.stopProjectContainer(projectId);

      // Start new container
      const args = [
        'run', '-d',
        '--name', containerName,
        '-v', `${outputDir}:/app`,
        '-p', `${vncPort}:6080`,
        '-p', `${appPort}:5173`,
        '-e', 'ENABLE_VNC=true',
        '-e', 'NODE_ENV=development',
        '--network', 'host-gateway',
        'coding-engine/sandbox:latest'
      ];

      const { stdout } = await execAsync(`docker ${args.join(' ')}`);
      const containerId = stdout.trim();

      this.containers.set(projectId, {
        id: containerId,
        process: null,
        vncPort,
        appPort,
        status: 'running'
      });

      console.log(`[DockerManager] Started container ${containerName} with VNC on port ${vncPort}`);

      return { success: true, vncPort, appPort };
    } catch (error) {
      console.error(`[DockerManager] Failed to start container for ${projectId}:`, error);
      return { success: false, error: error.message };
    }
  }

  /**
   * Stop a project container
   */
  async stopProjectContainer(projectId) {
    try {
      const containerName = `project-${projectId}`;

      // Stop and remove container (Windows compatible)
      await execAsync(`docker stop ${containerName} 2>nul || echo ""`);
      await execAsync(`docker rm ${containerName} 2>nul || echo ""`);

      this.containers.delete(projectId);

      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Get project container status
   */
  async getProjectStatus(projectId) {
    const containerName = `project-${projectId}`;

    try {
      const { stdout } = await execAsync(
        `docker inspect --format="{{.State.Status}}" ${containerName}`
      );

      const status = stdout.trim();
      const info = this.containers.get(projectId);

      return {
        running: status === 'running',
        vncPort: info?.vncPort,
        appPort: info?.appPort,
        health: status
      };
    } catch {
      return { running: false };
    }
  }

  /**
   * Get container logs
   */
  async getProjectLogs(projectId, tail = 100) {
    const containerName = `project-${projectId}`;

    try {
      const { stdout } = await execAsync(`docker logs --tail ${tail} ${containerName}`);
      return stdout;
    } catch (error) {
      return `Error fetching logs: ${error.message}`;
    }
  }

  /**
   * Start a code generation job
   */
  async startGeneration(requirementsPath, outputDir) {
    try {
      const pythonPath = process.platform === 'win32' ? 'python' : 'python3';

      const genProcess = spawn(pythonPath, [
        'run_society_hybrid.py',
        requirementsPath,
        '--output-dir', outputDir,
        '--fast'
      ], {
        cwd: this.engineRoot,
        detached: true,
        stdio: 'ignore'
      });

      genProcess.unref();

      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Stop all containers on app quit
   */
  async stopAllContainers() {
    const stopPromises = Array.from(this.containers.keys()).map(id =>
      this.stopProjectContainer(id)
    );
    await Promise.all(stopPromises);
  }

  /**
   * Get the API URL for the Coding Engine
   */
  getApiUrl() {
    return process.env.CODING_ENGINE_API_URL || 'http://localhost:8000';
  }
}

module.exports = DockerManager;
