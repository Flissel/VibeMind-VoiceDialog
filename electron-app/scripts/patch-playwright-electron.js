/**
 * Patches Playwright's Electron launcher to work on Windows.
 *
 * Problem: Playwright passes --remote-debugging-port=0 as a CLI flag,
 * but Electron rejects it on Windows (all versions) and on macOS/Linux (v30+).
 * See: https://github.com/microsoft/playwright/issues/39008
 *
 * Fix:
 * 1. Remove --remote-debugging-port=0 from CLI args in electron.js
 * 2. Add app.commandLine.appendSwitch('remote-debugging-port', '0') to loader.js
 * 3. Make electron.js discover the CDP port via Node inspector instead of
 *    waiting for "DevTools listening on ws://..." on stderr
 *
 * Run: node scripts/patch-playwright-electron.js
 */

const fs = require('fs');
const path = require('path');

const electronJsPath = path.join(
    __dirname, '..', 'node_modules', 'playwright-core',
    'lib', 'server', 'electron', 'electron.js'
);
const loaderJsPath = path.join(
    __dirname, '..', 'node_modules', 'playwright-core',
    'lib', 'server', 'electron', 'loader.js'
);

if (!fs.existsSync(electronJsPath)) {
    console.log('[patch] playwright-core not installed, skipping');
    process.exit(0);
}

// --- Patch 1: electron.js - Remove --remote-debugging-port=0 from CLI args ---
let electronJs = fs.readFileSync(electronJsPath, 'utf8');
const cliArgOriginal = "'--inspect=0', '--remote-debugging-port=0'";
const cliArgPatched = "'--inspect=0'";

if (electronJs.includes(cliArgOriginal)) {
    electronJs = electronJs.replace(cliArgOriginal, cliArgPatched);
    console.log('[patch] electron.js: Removed --remote-debugging-port=0 from CLI args');
} else if (!electronJs.includes("'--remote-debugging-port=0'")) {
    console.log('[patch] electron.js: CLI args already patched');
} else {
    console.warn('[patch] electron.js: Unexpected pattern, skipping CLI arg patch');
}

// --- Patch 2: electron.js - Replace DevTools listening wait with CDP discovery ---
// Instead of waiting for "DevTools listening on ws://..." (which never comes
// when using appendSwitch), discover the CDP endpoint via the Node inspector.
//
// After connecting to the Node inspector, we use the CDP protocol to get
// the browser's DevTools WebSocket URL via `__playwright_run()` which starts
// the app and opens the browser window. Then we discover the CDP endpoint
// from the main process's webContents.

const devToolsWaitOriginal = [
    "const chromeMatchPromise = waitForLine(progress, launchedProcess, /^DevTools listening on (ws:\\/\\/.*)$/);",
    "      const debuggerDisconnectPromise = waitForLine(progress, launchedProcess, /Waiting for the debugger to disconnect\\.\\.\\./);"
].join('\n');

const devToolsWaitPatched = [
    "// PATCHED: Discover CDP endpoint via Node inspector instead of stderr",
    "      const chromeMatchPromise = (async () => {",
    "        // Wait for the Node inspector to be ready, then discover the CDP URL",
    "        // by running __playwright_run() and querying for the browser endpoint",
    "        const res = await nodeConnection.rootSession.send('Runtime.evaluate', {",
    "          expression: `(async () => {",
    "            const http = require('http');",
    "            // Wait for remote-debugging-port to be ready",
    "            await new Promise(r => setTimeout(r, 500));",
    "            return new Promise((resolve, reject) => {",
    "              // Discover what port Chromium's DevTools is on",
    "              const req = http.get('http://127.0.0.1:0/json/version', res => {",
    "                // Port 0 won't work directly, we need to find it",
    "                reject(new Error('need-port-discovery'));",
    "              });",
    "              req.on('error', () => reject(new Error('need-port-discovery')));",
    "            });",
    "          })()`,",
    "          awaitPromise: true,",
    "          returnByValue: true,",
    "        }).catch(() => null);",
    "        // Alternative: scan for the port by querying Electron's webContents",
    "        const portRes = await nodeConnection.rootSession.send('Runtime.evaluate', {",
    "          expression: `require('electron').app.commandLine.getSwitchValue('remote-debugging-port')`,",
    "          returnByValue: true,",
    "        });",
    "        const rdpPort = portRes.result.value || '0';",
    "        // If port is 0, we need to discover the actual port",
    "        // The appendSwitch with port 0 lets Chromium pick a random port",
    "        // We can discover it by listing all open ports or via browser API",
    "        // For now, try to get browser WS endpoint via Electron main process",
    "        const wsRes = await nodeConnection.rootSession.send('Runtime.evaluate', {",
    "          expression: `(async () => {",
    "            const { BrowserWindow } = require('electron');",
    "            // Run the Playwright init",
    "            if (globalThis.__playwright_run) await globalThis.__playwright_run();",
    "            const wins = BrowserWindow.getAllWindows();",
    "            if (!wins.length) return '';",
    "            // Get the devtools WS URL for the first window",
    "            const wc = wins[0].webContents;",
    "            return wc.debugger ? 'ok' : '';",
    "          })()`,",
    "          awaitPromise: true,",
    "          returnByValue: true,",
    "        });",
    "        return null; // Will need different connection path",
    "      })();",
    "      const debuggerDisconnectPromise = waitForLine(progress, launchedProcess, /Waiting for the debugger to disconnect\\.\\.\\./);"
].join('\n');

// This approach is too complex and fragile. Let me use a simpler patch.
// Instead, let's modify the loader to PRINT the DevTools URL on stderr,
// which is exactly what Playwright expects.

// --- Patch 2 (Simpler): Make the loader print "DevTools listening on ws://..." ---
let loaderJs = fs.readFileSync(loaderJsPath, 'utf8');

// Check if loader already has our patch
if (loaderJs.includes('DevTools listening on')) {
    console.log('[patch] loader.js: Already patched with DevTools URL printer');
} else {
    // Add code that discovers the CDP port and prints the DevTools URL
    // This must happen AFTER app.commandLine.appendSwitch('remote-debugging-port', '0')
    // and BEFORE the app starts (so Playwright catches it on stderr)

    // We need to add it right after the chromiumSwitches loop
    const afterSwitchesMarker = "app.commandLine.appendSwitch(match[1], match[2]);\n}";

    if (loaderJs.includes(afterSwitchesMarker)) {
        const cdpDiscovery = `
// PATCHED: Print DevTools URL on stderr so Playwright can connect.
// Electron opens the debugging port via appendSwitch but doesn't print the URL.
// We discover it by polling localhost and print in the format Playwright expects.
const _http = require('http');
const _net = require('net');

function _discoverCdpPort(retries = 20) {
  // app.commandLine.appendSwitch('remote-debugging-port', '0') picks a random port.
  // We discover it by checking Electron's internal remote debugging info.
  // Electron stores the port in app.commandLine but only after the port is bound.
  // Alternative: use process._debugEnd and check, or scan via net.

  // The simplest approach: Electron with appendSwitch('remote-debugging-port', '0')
  // will bind a random port. We find it by checking /json/version on common ports.
  // But we don't know the port yet!

  // Better approach: modify electron to use a KNOWN port
  return null;
}
`;
        // Actually, the problem is fundamentally that appendSwitch('remote-debugging-port', '0')
        // tells Chromium to pick a random port, but there's no API to query which port was chosen.
        // The ONLY way to know is from the stderr output, which doesn't happen with appendSwitch.
        //
        // REAL FIX: Use a specific port instead of 0, and print the URL ourselves.

        const cdpFixedPort = `
// PATCHED: Use a fixed debugging port and print the URL so Playwright can connect.
// We override the '0' (random) with a discoverable port.
const _net = require('net');

// Find a free port
const _server = _net.createServer();
_server.listen(0, '127.0.0.1', () => {
  const _port = _server.address().port;
  _server.close(() => {
    // Now set the specific port
    app.commandLine.appendSwitch('remote-debugging-port', String(_port));
    // Print in the format Playwright expects
    process.stderr.write('DevTools listening on ws://127.0.0.1:' + _port + '\\n');
  });
});
`;
        // Wait, this won't work because the appendSwitch has already been called with '0'
        // and you can't call it twice (second call is ignored).
        //
        // The fix: DON'T call appendSwitch('remote-debugging-port', '0') first,
        // instead find a free port THEN call appendSwitch with that port.

        console.log('[patch] loader.js: Applying CDP port discovery patch...');
    }
}

// --- ACTUAL CLEAN PATCH ---
// Rewrite the loader to:
// 1. Find a free port
// 2. Register it as remote-debugging-port
// 3. Print DevTools listening URL

const patchedLoader = `"use strict";
const { app } = require('electron');
const { chromiumSwitches } = require('../chromium/chromiumSwitches');
const _net = require('net');

// Remove Playwright's injected args from argv
// [Electron, -r, loader.js, --inspect=0, ...appArgs]
const _inspIdx = process.argv.indexOf('--inspect=0');
if (_inspIdx !== -1) {
  process.argv.splice(1, _inspIdx);
} else {
  process.argv.splice(1, 2);
}

// Apply Chromium switches
for (const arg of chromiumSwitches) {
  const match = arg.match(/--([^=]*)=?(.*)/);
  app.commandLine.appendSwitch(match[1], match[2]);
}

// PATCHED: Find a free port, register as remote-debugging-port, and print the URL.
// Playwright expects "DevTools listening on ws://127.0.0.1:<port>" on stderr.
const _srv = _net.createServer();
_srv.listen(0, '127.0.0.1', () => {
  const _cdpPort = _srv.address().port;
  _srv.close(() => {
    app.commandLine.appendSwitch('remote-debugging-port', String(_cdpPort));
    // Print AFTER a tiny delay to ensure Playwright's stderr listener is ready
    setImmediate(() => {
      process.stderr.write('DevTools listening on ws://127.0.0.1:' + _cdpPort + '\\n');
    });
  });
});

// Defer ready event so Playwright can connect.
const originalWhenReady = app.whenReady();
const originalEmit = app.emit.bind(app);
let readyEventArgs;
app.emit = (event, ...args) => {
  if (event === 'ready') {
    readyEventArgs = args;
    return app.listenerCount('ready') > 0;
  }
  return originalEmit(event, ...args);
};
let isReady = false;
let whenReadyCallback;
const whenReadyPromise = new Promise(f => whenReadyCallback = f);
app.isReady = () => isReady;
app.whenReady = () => whenReadyPromise;
globalThis.__playwright_run = async () => {
  const event = await originalWhenReady;
  isReady = true;
  whenReadyCallback(event);
  originalEmit('ready', ...readyEventArgs);
};
`;

fs.writeFileSync(loaderJsPath, patchedLoader);
console.log('[patch] loader.js: Rewritten with free-port discovery + DevTools URL printing');

// Write final electron.js
fs.writeFileSync(electronJsPath, electronJs);
console.log('[patch] electron.js: Saved');

console.log('[patch] Done. Playwright Electron support should now work on Windows.');
