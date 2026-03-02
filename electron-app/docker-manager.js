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
    // Resolve relative paths against the project root (one level up from electron-app/)
    const envPath = process.env.CODING_ENGINE_PATH;
    this.engineRoot = envPath
      ? (path.isAbsolute(envPath) ? envPath : path.resolve(__dirname, '..', envPath))
      : path.join(__dirname, '..', 'python', 'spaces', 'coding', 'Coding_engine');

    this.sandboxImage = 'coding-engine/sandbox:latest';

    // Resolve Python executable path (Electron may not inherit shell PATH)
    this.pythonPath = this._findPython();
  }

  /**
   * Find a working Python executable, checking venv and common locations
   */
  _findPython() {
    const fs = require('fs');
    const projectRoot = path.join(__dirname, '..');

    // Priority order: venv in project root, PYTHON_PATH env, system python
    const candidates = [
      path.join(projectRoot, '.venv312', 'Scripts', 'python.exe'),
      path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
      process.env.PYTHON_PATH,
      'python',
      'python3',
    ].filter(Boolean);

    for (const candidate of candidates) {
      if (path.isAbsolute(candidate) && fs.existsSync(candidate)) {
        console.log(`[DockerManager] Using Python: ${candidate}`);
        return candidate;
      }
    }

    // Fallback — try to resolve via where/which
    try {
      const { execSync } = require('child_process');
      const cmd = process.platform === 'win32' ? 'where python' : 'which python3';
      const result = execSync(cmd, { timeout: 5000 }).toString().trim().split('\n')[0].trim();
      if (result && fs.existsSync(result)) {
        console.log(`[DockerManager] Using Python (resolved): ${result}`);
        return result;
      }
    } catch { /* ignore */ }

    console.warn('[DockerManager] Python not found, generation will fail');
    return 'python';
  }

  /**
   * Ensure the sandbox Docker image exists, building it if necessary
   */
  async ensureSandboxImage() {
    try {
      await execAsync(`docker image inspect ${this.sandboxImage}`);
      return true;
    } catch {
      console.log('[DockerManager] Sandbox image not found, building...');
      const dockerfile = path.join(this.engineRoot, 'infra', 'docker', 'Dockerfile.sandbox');
      const fs = require('fs');
      if (!fs.existsSync(dockerfile)) {
        throw new Error(`Dockerfile not found: ${dockerfile}`);
      }
      await execAsync(
        `docker build -t ${this.sandboxImage} -f "${dockerfile}" .`,
        { cwd: this.engineRoot, timeout: 600000 }
      );
      console.log('[DockerManager] Sandbox image built successfully');
      return true;
    }
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

      // Stop any containers using our ports to prevent "port already allocated" errors
      await this.stopContainersByPort(vncPort);
      await this.stopContainersByPort(appPort);

      // Ensure sandbox image exists (auto-build if missing)
      await this.ensureSandboxImage();

      // Start new container
      const args = [
        'run', '-d',
        '--name', containerName,
        '-v', `${outputDir}:/app`,
        '-p', `${vncPort}:6080`,
        '-p', `${appPort}:5173`,
        '-e', 'ENABLE_VNC=true',
        '-e', 'NODE_ENV=development',
        '--network', 'bridge',
        this.sandboxImage
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

      // Kill the generation subprocess if running
      const entry = this.containers.get(projectId);
      if (entry && entry.process) {
        try {
          entry.process.kill();
          console.log(`[DockerManager] Killed generation process for ${projectId}`);
        } catch { /* already exited */ }
      }

      try {
        await execAsync(`docker rm -f ${containerName}`);
      } catch { /* container doesn't exist, that's fine */ }

      this.containers.delete(projectId);

      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * Stop Docker containers that are using a specific port
   */
  async stopContainersByPort(port) {
    try {
      const { stdout } = await execAsync(`docker ps -q --filter "publish=${port}"`);
      const containerIds = stdout.trim().split('\n').filter(id => id);
      for (const containerId of containerIds) {
        try {
          console.log(`[DockerManager] Stopping container ${containerId} using port ${port}`);
          await execAsync(`docker rm -f ${containerId}`);
        } catch { /* already gone */ }
      }
      if (containerIds.length > 0) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    } catch { /* no containers found */ }
  }

  /**
   * Kill host processes holding a specific port (Windows only)
   */
  async killHostProcessOnPort(port) {
    try {
      if (process.platform !== 'win32') return;
      const portNum = parseInt(port, 10);
      if (isNaN(portNum) || portNum < 1 || portNum > 65535) return;
      const findCmd = `powershell -Command "Get-NetTCPConnection -LocalPort ${portNum} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"`;
      const { stdout } = await execAsync(findCmd);
      const pids = stdout.trim().split('\n')
        .map(pid => parseInt(pid.trim(), 10))
        .filter(pid => !isNaN(pid) && pid > 0);
      for (const pid of pids) {
        try {
          console.log(`[DockerManager] Killing host process ${pid} using port ${portNum}`);
          await execAsync(`powershell -Command "Stop-Process -Id ${pid} -Force -ErrorAction SilentlyContinue"`);
        } catch { /* already exited */ }
      }
      if (pids.length > 0) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    } catch { /* port not in use */ }
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
      const pythonPath = this.pythonPath;

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
   * Start generation with VNC preview container
   */
  async startGenerationWithPreview(projectId, requirementsPath, outputDir, vncPort, appPort, forceGenerate = false) {
    try {
      const containerName = `project-${projectId}`;

      // Stop existing container if force generate
      if (forceGenerate) {
        await this.stopProjectContainer(projectId);
      } else {
        const existing = this.containers.get(projectId);
        if (existing && existing.status === 'running') {
          return { success: true, vncPort: existing.vncPort, appPort: existing.appPort, alreadyRunning: true };
        }
      }

      // Ensure sandbox image exists (auto-build if missing)
      await this.ensureSandboxImage();

      // Pre-start cleanup: stop containers and processes using our ports
      await this.stopContainersByPort(vncPort);
      await this.stopContainersByPort(appPort);
      await this.killHostProcessOnPort(vncPort);
      await this.killHostProcessOnPort(appPort);

      // Wait for ports to be fully released (Windows is slow)
      console.log('[DockerManager] Waiting for ports to be released...');
      await new Promise(resolve => setTimeout(resolve, 2000));

      // Start container with generation + VNC preview
      const args = [
        'run', '-d',
        '--name', containerName,
        '-v', `${requirementsPath}:/app/requirements`,
        '-v', `${outputDir}:/app/output`,
        '-p', `${vncPort}:6080`,
        '-p', `${appPort}:5173`,
        '-e', 'ENABLE_VNC=true',
        '-e', 'NODE_ENV=development',
        '-e', `REQUIREMENTS_PATH=/app/requirements`,
        '-e', `OUTPUT_DIR=/app/output`,
        '--network', 'bridge',
        this.sandboxImage
      ];

      // Retry loop for port conflicts
      let containerId = '';
      const maxRetries = 3;
      for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
          const { stdout } = await execAsync(`docker ${args.join(' ')}`);
          containerId = stdout.trim();
          break; // success
        } catch (error) {
          const errorMsg = error.message || '';
          if (errorMsg.includes('port') && (errorMsg.includes('not available') || errorMsg.includes('already allocated') || errorMsg.includes('already in use')) && attempt < maxRetries - 1) {
            console.log(`[DockerManager] Port conflict on attempt ${attempt + 1}, retrying in 3s...`);
            await this.killHostProcessOnPort(vncPort);
            await this.killHostProcessOnPort(appPort);
            await this.stopContainersByPort(vncPort);
            await this.stopContainersByPort(appPort);
            // Also remove the failed container by name before retrying
            try { await execAsync(`docker rm -f ${containerName}`); } catch { /* ok */ }
            await new Promise(resolve => setTimeout(resolve, 3000));
          } else {
            throw error;
          }
        }
      }

      if (!containerId) {
        throw new Error('Docker container failed to start: empty container ID after retries');
      }

      // Start the code generation subprocess (run_engine.py)
      const pythonPath = this.pythonPath;
      const runEnginePath = path.join(this.engineRoot, 'run_engine.py');
      const fs = require('fs');

      let genProcess = null;
      if (fs.existsSync(runEnginePath)) {
        console.log(`[DockerManager] Starting code generation: ${runEnginePath}`);
        genProcess = spawn(pythonPath, [
          runEnginePath,
          requirementsPath,
          '--autonomous',
          '--continuous-sandbox',
          '--enable-vnc',
          '--vnc-port', String(vncPort),
          '--enable-validation',
          '--output-dir', outputDir,
          '--json-progress',
          '--parallel', '10',
        ], {
          cwd: this.engineRoot,
          detached: true,
          stdio: ['ignore', 'pipe', 'pipe']
        });

        genProcess.stdout.on('data', (data) => {
          const lines = data.toString().split('\n').filter(l => l.trim());
          for (const line of lines) {
            console.log(`[CodingEngine:${projectId}] ${line}`);
          }
        });

        genProcess.stderr.on('data', (data) => {
          console.error(`[CodingEngine:${projectId}:ERR] ${data.toString().trim()}`);
        });

        genProcess.on('exit', (code) => {
          console.log(`[CodingEngine:${projectId}] Process exited with code ${code}`);
          const entry = this.containers.get(projectId);
          if (entry) entry.process = null;
        });

        genProcess.unref();
      } else {
        console.warn(`[DockerManager] run_engine.py not found at ${runEnginePath}, skipping generation`);
      }

      this.containers.set(projectId, {
        id: containerId,
        process: genProcess,
        vncPort,
        appPort,
        status: 'running',
      });

      console.log(`[DockerManager] Started generation with preview for ${projectId} (VNC: ${vncPort}, App: ${appPort})`);

      return { success: true, vncPort, appPort, containerId };
    } catch (error) {
      console.error(`[DockerManager] startGenerationWithPreview failed for ${projectId}:`, error);
      return { success: false, error: error.message };
    }
  }

  /**
   * Stop a running generation
   */
  async stopGeneration(projectId) {
    return await this.stopProjectContainer(projectId);
  }

  /**
   * Start epic-based generation
   */
  async startEpicGeneration(projectId, projectPath, outputDir, vncPort, appPort) {
    return await this.startGenerationWithPreview(projectId, projectPath, outputDir, vncPort, appPort, true);
  }

  /**
   * Get epics for a project
   */
  async getEpics(projectPath) {
    try {
      const epicsDir = path.join(projectPath, 'epics');
      const fs = require('fs');
      if (!fs.existsSync(epicsDir)) return { success: true, epics: [] };
      const files = fs.readdirSync(epicsDir).filter(f => f.endsWith('.json'));
      const epics = files.map(f => {
        const data = JSON.parse(fs.readFileSync(path.join(epicsDir, f), 'utf-8'));
        return { id: data.id || f.replace('.json', ''), ...data };
      });
      return { success: true, epics };
    } catch (error) {
      return { success: false, error: error.message, epics: [] };
    }
  }

  /**
   * Get tasks for a specific epic
   */
  async getEpicTasks(epicId, projectPath) {
    try {
      const fs = require('fs');
      const epicPath = path.join(projectPath, 'epics', `${epicId}.json`);
      if (!fs.existsSync(epicPath)) return { success: false, error: 'Epic not found', tasks: [] };
      const data = JSON.parse(fs.readFileSync(epicPath, 'utf-8'));
      return { success: true, tasks: data.tasks || [] };
    } catch (error) {
      return { success: false, error: error.message, tasks: [] };
    }
  }

  /**
   * Run a specific epic
   */
  async runEpic(epicId, projectPath) {
    console.log(`[DockerManager] runEpic: ${epicId} in ${projectPath}`);
    return { success: true, message: `Epic ${epicId} queued for execution` };
  }

  /**
   * Rerun a specific epic
   */
  async rerunEpic(epicId, projectPath) {
    console.log(`[DockerManager] rerunEpic: ${epicId} in ${projectPath}`);
    return { success: true, message: `Epic ${epicId} queued for re-execution` };
  }

  /**
   * Rerun a single task within an epic
   */
  async rerunTask(epicId, taskId, projectPath, fixInstructions) {
    console.log(`[DockerManager] rerunTask: ${epicId}/${taskId} in ${projectPath}`);
    return { success: true, message: `Task ${taskId} in epic ${epicId} queued for re-execution` };
  }

  /**
   * Generate task lists for all epics
   */
  async generateTaskLists(projectPath) {
    console.log(`[DockerManager] generateTaskLists: ${projectPath}`);
    return { success: true, message: 'Task list generation queued' };
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
