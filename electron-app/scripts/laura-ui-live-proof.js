#!/usr/bin/env node

const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const { mkdtemp, rm } = require('node:fs/promises');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');

const API_ARGUMENTS = Object.freeze(['run', '--directory', 'services/local-api', 'laura-api']);
const API_URL = 'http://127.0.0.1:8765';
const HELP = `Usage: npm run laura:live-proof -- [--help]

Runs the Laura Local API in an isolated temporary workspace, then proves the
authenticated and fail-closed Laura BrowserView states in real Electron launches.
The probe prints only allowlisted result fields; tokens and filesystem paths are omitted.
`;

function parseArguments(argumentsList) {
  if (argumentsList.length === 0) return { help: false };
  if (argumentsList.length === 1 && ['--help', '-h'].includes(argumentsList[0])) {
    return { help: true };
  }
  throw new Error('unsupported argument; use --help');
}

function createEphemeralToken() {
  return randomBytes(32).toString('base64url');
}

function buildElectronEnvironment(baseEnvironment, token, authenticated, workspacePath = '') {
  const environment = {
    ...baseEnvironment,
    LAURA_TOKEN: authenticated ? token : '',
    LAURA_URL: API_URL,
    LAURA_WORKSPACE: workspacePath,
    NODE_ENV: 'test',
    FORCE_SYNC_MODE: 'true',
    FAST_STARTUP: 'true',
    USE_TASK_MEMORY: 'false',
    USE_CONVERSATION_MEMORY: 'false',
    USE_USER_PROFILES: 'false',
    USE_RAG_CLASSIFIER: 'false',
    SCHEDULE_ENABLED: 'false',
    MINIBOOK_ENABLED: 'false',
    USE_ZEROCLAW: 'false',
    N8N_ENABLED: 'false',
    MIROFISH_ENABLED: 'false',
    SKIP_BRAIN_SPAWN: 'true',
    EYETERM_ENABLED: 'false',
  };
  delete environment.ELECTRON_RUN_AS_NODE;
  return environment;
}

function formatPublicResult(result) {
  const allowedKeys = new Set([
    'apiHealthStatus',
    'apiAuthorizedProjectsStatus',
    'apiAuthorizedProjectCount',
    'apiUnauthorizedProjectsStatus',
    'healthStatus',
    'projectCount',
    'positive',
    'negative',
    'header',
    'navRailEntries',
    'chatInput',
    'projectSelector',
    'projectSelectorDisabled',
    'projectOptionCount',
    'jobCenter',
    'legacyBridge',
    'rendererApiStatus',
    'dialogCanceled',
    'dialogCallCount',
    'pickedFileCount',
    'browserViewReused',
    'rendererTimeOriginPreserved',
    'navStateAfterReturn',
    'serviceInfoUnavailable',
    'serviceOffline',
    'projectControlsAbsent',
    'mediaAssetsAbsent',
    'port8765Free',
  ]);

  function copyAllowed(value) {
    if (Array.isArray(value)) return value.map(copyAllowed);
    if (!value || typeof value !== 'object') return value;
    return Object.fromEntries(Object.entries(value)
      .filter(([key]) => allowedKeys.has(key))
      .map(([key, nested]) => [key, copyAllowed(nested)]));
  }

  return JSON.stringify(copyAllowed(result));
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function withTimeout(promise, milliseconds, label) {
  let timer;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error(`${label} timed out`)), milliseconds);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

async function assertPortAvailable() {
  await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', () => reject(new Error('port 8765 is already in use')));
    server.listen(8765, '127.0.0.1', () => server.close(resolve));
  });
}

function captureBounded(stream) {
  let captured = '';
  stream?.on('data', (chunk) => {
    captured = `${captured}${String(chunk)}`.slice(-4096);
  });
  return () => captured;
}

function startApi(lauraRoot, workspacePath, token) {
  const child = spawn('uv', API_ARGUMENTS, {
    cwd: lauraRoot,
    env: {
      ...process.env,
      LAURA_TOKEN: token,
      LAURA_WORKSPACE: workspacePath,
      LAURA_HOST: '127.0.0.1',
      LAURA_PORT: '8765',
      LAURA_WORKERS: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });
  return {
    child,
    readStdout: captureBounded(child.stdout),
    readStderr: captureBounded(child.stderr),
  };
}

async function waitForApi(child) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    if (child.exitCode !== null) throw new Error('Laura API exited before readiness');
    try {
      const response = await fetch(`${API_URL}/healthz`, { signal: AbortSignal.timeout(750) });
      if (response.status === 200) return response;
    } catch {
      // Readiness is bounded by the loop; connection refusal before startup is expected.
    }
    await delay(250);
  }
  throw new Error('Laura API readiness timed out');
}

async function stopOwnedProcessTree(child) {
  if (!child || child.exitCode !== null || !child.pid) return;
  if (process.platform === 'win32') {
    await new Promise((resolve) => {
      const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], {
        stdio: 'ignore',
        windowsHide: true,
      });
      killer.once('error', resolve);
      killer.once('exit', resolve);
    });
  } else {
    child.kill('SIGTERM');
    await Promise.race([new Promise((resolve) => child.once('exit', resolve)), delay(3000)]);
    if (child.exitCode === null) child.kill('SIGKILL');
  }
}

async function findMainPage(electronApp) {
  await electronApp.firstWindow();
  for (let attempt = 0; attempt < 100; attempt += 1) {
    for (const page of electronApp.windows()) {
      const isMain = await page.evaluate(() => typeof window.vibemind?.showVideo === 'function')
        .catch(() => false);
      if (isMain) return page;
    }
    await delay(100);
  }
  throw new Error('VibeMind main window readiness timed out');
}

async function showVideo(mainPage) {
  await mainPage.evaluate(() => window.vibemind.showVideo());
}

async function inspectBrowserView(electronApp, expression) {
  return electronApp.evaluate(async ({ BrowserWindow }, source) => {
    const view = BrowserWindow.getAllWindows()
      .map((window) => window.getBrowserView())
      .find((candidate) => candidate && !candidate.webContents.isDestroyed());
    if (!view) return null;
    return {
      viewId: view.webContents.id,
      payload: await view.webContents.executeJavaScript(source, true),
    };
  }, expression);
}

async function waitForBrowserView(electronApp, expression, predicate, label) {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    const state = await inspectBrowserView(electronApp, expression).catch(() => null);
    if (state && predicate(state.payload)) return state;
    await delay(100);
  }
  throw new Error(`${label} timed out`);
}

async function launchElectron(electronRoot, environment) {
  const { _electron: electron } = require('@playwright/test');
  return electron.launch({ args: [electronRoot], env: environment, timeout: 60_000 });
}

async function closeElectron(electronApp) {
  if (!electronApp) return;
  const ownedProcess = electronApp.process();
  try {
    await withTimeout(electronApp.close(), 30_000, 'Electron app.close');
  } catch (error) {
    await stopOwnedProcessTree(ownedProcess);
    throw error;
  }
}

async function runPositiveElectron(electronRoot, workspacePath, token) {
  const electronApp = await launchElectron(
    electronRoot,
    buildElectronEnvironment(process.env, token, true, workspacePath),
  );
  try {
    const mainPage = await findMainPage(electronApp);
    await electronApp.evaluate(({ dialog }) => {
      global.__lauraLiveProofDialogCalls = 0;
      dialog.showOpenDialog = async () => {
        global.__lauraLiveProofDialogCalls += 1;
        return { canceled: true, filePaths: [] };
      };
    });
    await showVideo(mainPage);

    const initial = await waitForBrowserView(electronApp, `
      (async () => {
        const service = await window.laura?.getServiceInfo();
        const heading = Array.from(document.querySelectorAll('h1'))
          .find((element) => element.textContent?.trim() === 'Laura');
        const selector = document.querySelector('select[aria-label="Choose a project"]');
        return {
          ready: Boolean(heading && service && selector),
          header: Boolean(heading),
          navRailEntries: document.querySelectorAll('nav button').length,
          chatInput: Boolean(document.querySelector('[aria-label="Nachricht"]')),
          projectSelector: Boolean(selector),
          projectSelectorDisabled: Boolean(selector?.disabled),
          projectOptionCount: selector?.querySelectorAll('option').length ?? 0,
          legacyBridge: typeof window.vibemindVideo !== 'undefined',
          timeOrigin: performance.timeOrigin,
        };
      })()
    `, (state) => state.ready === true, 'positive Laura renderer readiness');

    const action = await inspectBrowserView(electronApp, `
      (async () => {
        const service = await window.laura.getServiceInfo();
        const response = await fetch(service.baseUrl + '/projects', {
          headers: { 'X-Laura-Token': service.token },
        });
        const picked = await window.laura.pickMediaFiles();
        const jobsButton = Array.from(document.querySelectorAll('button'))
          .find((button) => button.textContent?.trim().startsWith('Jobs'));
        jobsButton?.click();
        const mediaButton = Array.from(document.querySelectorAll('nav button'))
          .find((button) => button.textContent?.trim().endsWith('Media'));
        mediaButton?.click();
        return { rendererApiStatus: response.status, pickedFileCount: picked.length };
      })()
    `);
    if (!action) throw new Error('positive Laura BrowserView disappeared');

    const ready = await waitForBrowserView(electronApp, `
      (() => {
        const selector = document.querySelector('select[aria-label="Choose a project"]');
        const active = document.querySelector('nav button[aria-current="page"]');
        return {
          jobCenter: document.body.innerText.includes('Job-Zentrale'),
          navState: active?.textContent?.trim() ?? null,
          timeOrigin: performance.timeOrigin,
        };
      })()
    `, (state) => state.jobCenter === true && state.navState?.endsWith('Media'),
    'positive component readiness');

    const dialogCallCount = await electronApp.evaluate(() => global.__lauraLiveProofDialogCalls);
    await mainPage.evaluate(() => window.vibemind.hideVideo());
    await delay(250);
    await showVideo(mainPage);
    const restored = await waitForBrowserView(electronApp, `
      (() => ({
        timeOrigin: performance.timeOrigin,
        navState: document.querySelector('nav button[aria-current="page"]')?.textContent?.trim() ?? null,
      }))()
    `, (state) => state.navState?.endsWith('Media'), 'restored Laura BrowserView');

    const result = {
      header: initial.payload.header === true ? 'Laura' : null,
      navRailEntries: initial.payload.navRailEntries,
      chatInput: initial.payload.chatInput,
      projectSelector: initial.payload.projectSelector,
      projectSelectorDisabled: initial.payload.projectSelectorDisabled,
      projectOptionCount: initial.payload.projectOptionCount,
      jobCenter: ready.payload.jobCenter ? 'Job-Zentrale' : null,
      legacyBridge: initial.payload.legacyBridge,
      rendererApiStatus: action.payload.rendererApiStatus,
      dialogCanceled: action.payload.pickedFileCount === 0 && dialogCallCount === 1,
      dialogCallCount,
      pickedFileCount: action.payload.pickedFileCount,
      browserViewReused: initial.viewId === restored.viewId,
      rendererTimeOriginPreserved: initial.payload.timeOrigin === restored.payload.timeOrigin,
      navStateAfterReturn: restored.payload.navState?.replace(/^\d+\s*/, '') ?? null,
    };
    if (
      result.header !== 'Laura'
      || result.navRailEntries !== 7
      || !result.chatInput
      || !result.projectSelector
      || !result.projectSelectorDisabled
      || result.projectOptionCount !== 1
      || result.jobCenter !== 'Job-Zentrale'
      || result.legacyBridge
      || result.rendererApiStatus !== 200
      || !result.dialogCanceled
      || !result.browserViewReused
      || !result.rendererTimeOriginPreserved
      || result.navStateAfterReturn !== 'Media'
    ) throw new Error('positive Electron assertions failed');
    return result;
  } finally {
    await closeElectron(electronApp);
  }
}

async function runNegativeElectron(electronRoot, workspacePath, token) {
  const electronApp = await launchElectron(
    electronRoot,
    buildElectronEnvironment(process.env, token, false, workspacePath),
  );
  try {
    const mainPage = await findMainPage(electronApp);
    await showVideo(mainPage);
    const state = await waitForBrowserView(electronApp, `
      (async () => {
        const serviceInfoUnavailable = await window.laura?.getServiceInfo() === null;
        const text = document.body.innerText;
        return {
          header: Array.from(document.querySelectorAll('h1'))
            .some((element) => element.textContent?.trim() === 'Laura'),
          serviceInfoUnavailable,
          serviceOffline: text.includes('Service offline'),
          projectControlsAbsent:
            !document.querySelector('select[aria-label="Choose a project"]')
            && !document.querySelector('[aria-label="Neuer Projektname"]'),
          mediaAssetsAbsent: !text.includes('Project media'),
          legacyBridge: typeof window.vibemindVideo !== 'undefined',
        };
      })()
    `, (candidate) => candidate.header && candidate.serviceInfoUnavailable
      && candidate.serviceOffline, 'negative Laura renderer readiness');
    const result = state.payload;
    if (
      !result.header
      || !result.serviceInfoUnavailable
      || !result.serviceOffline
      || !result.projectControlsAbsent
      || !result.mediaAssetsAbsent
      || result.legacyBridge
    ) throw new Error('negative Electron assertions failed');
    return { ...result, header: result.header ? 'Laura' : null };
  } finally {
    await closeElectron(electronApp);
  }
}

async function runLiveProof() {
  const electronRoot = path.resolve(__dirname, '..');
  const lauraRoot = path.resolve(electronRoot, '..', '..', 'spaces', 'video', 'laura');
  const workspacePath = await mkdtemp(path.join(os.tmpdir(), 'vibemind-laura-live-proof-'));
  const token = createEphemeralToken();
  let api;
  try {
    await assertPortAvailable();
    api = startApi(lauraRoot, workspacePath, token);
    const health = await waitForApi(api.child);
    const authorized = await fetch(`${API_URL}/projects`, {
      headers: { 'X-Laura-Token': token },
      signal: AbortSignal.timeout(5000),
    });
    const projects = await authorized.json();
    const unauthorized = await fetch(`${API_URL}/projects`, {
      signal: AbortSignal.timeout(5000),
    });
    if (health.status !== 200 || authorized.status !== 200
      || !Array.isArray(projects) || projects.length !== 0 || unauthorized.status !== 401) {
      throw new Error('Laura API assertions failed');
    }

    const positive = await runPositiveElectron(electronRoot, workspacePath, token);
    const negative = await runNegativeElectron(electronRoot, workspacePath, token);
    return {
      apiHealthStatus: health.status,
      apiAuthorizedProjectsStatus: authorized.status,
      apiAuthorizedProjectCount: projects.length,
      apiUnauthorizedProjectsStatus: unauthorized.status,
      positive,
      negative,
      port8765Free: false,
    };
  } finally {
    await stopOwnedProcessTree(api?.child);
    await rm(workspacePath, { recursive: true, force: true });
  }
}

async function main() {
  let options;
  try {
    options = parseArguments(process.argv.slice(2));
  } catch {
    process.stderr.write('Unsupported arguments. Use --help.\n');
    process.exitCode = 2;
    return;
  }
  if (options.help) {
    process.stdout.write(HELP);
    return;
  }

  try {
    const result = await runLiveProof();
    await assertPortAvailable();
    result.port8765Free = true;
    process.stdout.write(`${formatPublicResult(result)}\n`);
  } catch {
    process.stderr.write('Laura UI live proof failed; no PASS result was emitted.\n');
    process.exitCode = 1;
  }
}

module.exports = {
  API_ARGUMENTS,
  buildElectronEnvironment,
  createEphemeralToken,
  formatPublicResult,
  parseArguments,
  runLiveProof,
};

if (require.main === module) {
  void main();
}
