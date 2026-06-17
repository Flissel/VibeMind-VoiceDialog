/**
 * Rowboat Core Bridge for VibeMind
 *
 * Runs @x/core in a separate Node.js process (ESM).
 * Communicates with VibeMind's Electron main process via
 * JSON-RPC 2.0 on stdin/stdout.
 *
 * Spawn with cwd = spaces/rowboat/rowboat/apps/x/
 * so that @x/core resolves from the local node_modules.
 */

// Resolve @x/core from the pnpm workspace via absolute paths.
// Dynamic import() needs file:// URLs on Windows.
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';
import readline from 'node:readline';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Core dist lives at: spaces/rowboat/rowboat/apps/x/packages/core/dist/
// electron-app -> voice -> vibemind-os -> spaces/rowboat/rowboat (NOT
// voice/python, which has no rowboat checkout — same path bug that broke
// rowboat-manager._resolveRendererPath / startBridge.coreDir).
const CORE_BASE = join(__dirname, '..', '..', 'spaces', 'rowboat', 'rowboat',
  'apps', 'x', 'packages', 'core', 'dist');

function coreModule(subpath) {
  return pathToFileURL(join(CORE_BASE, subpath)).href;
}

const { initConfigs } = await import(coreModule('config/initConfigs.js'));
const runsCore = await import(coreModule('runs/runs.js'));
const { bus } = await import(coreModule('runs/bus.js'));
const { serviceBus } = await import(coreModule('services/service_bus.js'));

// ── Helpers ──────────────────────────────────────────────

function writeJsonLine(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}

function log(...args) {
  process.stderr.write(`[RowboatBridge] ${args.join(' ')}\n`);
}

// ── Startup ──────────────────────────────────────────────

log('Initializing configs...');
await initConfigs();
log('Configs ready');

// Subscribe to all run events (push to VibeMind)
await bus.subscribe('*', (event) => {
  writeJsonLine({ jsonrpc: '2.0', method: 'runs:events', params: event });
});

// Subscribe to service events
serviceBus.subscribe((event) => {
  writeJsonLine({ jsonrpc: '2.0', method: 'services:events', params: event });
});

// Signal readiness
writeJsonLine({ jsonrpc: '2.0', method: 'bridge:ready', params: {} });
log('Bridge ready — listening on stdin');

// ── RPC Dispatch ─────────────────────────────────────────

async function dispatch(method, params) {
  switch (method) {
    case 'runs:create':
      return await runsCore.createRun(params);

    case 'runs:createMessage': {
      const messageId = await runsCore.createMessage(
        params.runId,
        params.message,
        params.voiceInput,
        params.voiceOutput,
        params.searchEnabled,
      );
      return { messageId };
    }

    case 'runs:list':
      return await runsCore.listRuns(params?.cursor);

    case 'runs:fetch':
      return await runsCore.fetchRun(params.runId);

    case 'runs:stop':
      await runsCore.stop(params.runId, params.force);
      return { success: true };

    case 'runs:delete':
      await runsCore.deleteRun(params.runId);
      return { success: true };

    case 'runs:authorizePermission':
      await runsCore.authorizePermission(params.runId, params.authorization);
      return { success: true };

    case 'runs:provideHumanInput':
      await runsCore.replyToHumanInputRequest(params.runId, params.reply);
      return { success: true };

    default:
      throw new Error(`Unknown method: ${method}`);
  }
}

// ── stdin reader ─────────────────────────────────────────

const rl = readline.createInterface({ input: process.stdin });

for await (const line of rl) {
  if (!line.trim()) continue;

  let req;
  try {
    req = JSON.parse(line);
  } catch {
    log('Malformed JSON on stdin:', line.slice(0, 120));
    continue;
  }

  const { id, method, params } = req;

  try {
    const result = await dispatch(method, params || {});
    writeJsonLine({ jsonrpc: '2.0', id, result });
  } catch (err) {
    log(`Error in ${method}:`, err.message);
    writeJsonLine({
      jsonrpc: '2.0',
      id,
      error: { code: -1, message: err.message },
    });
  }
}

// stdin closed — main process is shutting down
log('stdin closed, exiting');
process.exit(0);
