/**
 * The n8n editor window (Agent Farm -> "open in n8n").
 *
 * Signing in happens here in the main process: a POST to n8n's /rest/login with the window's own
 * session, so the session cookie lands where the window needs it. The account never enters the
 * page's JavaScript. It comes only from the environment (N8N_UI_EMAIL, N8N_UI_PASSWORD), never
 * from the code. Without it the window opens at n8n's sign-in page and the user signs in there.
 *
 * The window stays on n8n: a link or a new window to any other origin goes to the system browser.
 */

/** The account from the environment, or null when either half is missing. */
function editorLogin(env = process.env) {
  const email = typeof env.N8N_UI_EMAIL === 'string' ? env.N8N_UI_EMAIL.trim() : '';
  const password = typeof env.N8N_UI_PASSWORD === 'string' ? env.N8N_UI_PASSWORD : '';
  return email && password ? { email, password } : null;
}

/** Whether an address belongs to the n8n at `base` (same origin). */
function isN8nPage(address, base) {
  try {
    return new URL(address).origin === new URL(base).origin;
  } catch (_) {
    return false;
  }
}

/** Where the editor should show: a workflow of its own, or the start page. */
function targetPath(workflowId) {
  const id = workflowId === undefined || workflowId === null ? '' : String(workflowId).trim();
  return id ? `/workflow/${encodeURIComponent(id)}` : '/';
}

/**
 * Signs in at n8n with the window's session. Resolves { ok, status }; never rejects and never
 * reports the account. `net` is Electron's net module (injected for the tests).
 */
function signIn({ net, session, base, login, timeoutMs = 10000 }) {
  return new Promise((resolve) => {
    let done = false;
    const finish = (result) => { if (!done) { done = true; clearTimeout(timer); resolve(result); } };
    const timer = setTimeout(() => finish({ ok: false, status: 0, reason: 'timeout' }), timeoutMs);
    let request;
    try {
      request = net.request({ method: 'POST', url: `${base}/rest/login`, session, useSessionCookies: true });
    } catch (_) {
      finish({ ok: false, status: 0, reason: 'request' });
      return;
    }
    request.setHeader('Content-Type', 'application/json');
    request.on('response', (response) => {
      const status = response.statusCode;
      response.on('data', () => {});
      response.on('end', () => finish({ ok: status >= 200 && status < 300, status }));
      response.on('error', () => finish({ ok: false, status, reason: 'response' }));
    });
    request.on('error', () => finish({ ok: false, status: 0, reason: 'network' }));
    request.write(JSON.stringify({ emailOrLdapLoginId: login.email, password: login.password }));
    request.end();
  });
}

/** Keeps the window on n8n; everything else opens in the system browser (http/https only). */
function limitToN8n(contents, base, shell) {
  const outside = (url) => {
    try {
      const { protocol } = new URL(url);
      if (protocol === 'http:' || protocol === 'https:') shell.openExternal(url);
    } catch (_) { /* not an address: drop it */ }
  };
  contents.on('will-navigate', (event, url) => {
    if (isN8nPage(url, base)) return;
    event.preventDefault();
    outside(url);
  });
  contents.setWindowOpenHandler(({ url }) => {
    if (isN8nPage(url, base)) contents.loadURL(url);   // n8n's own pages stay in this one window
    else outside(url);
    return { action: 'deny' };
  });
}

const NO_ACCOUNT = 'n8n-Editor ist offen. Bitte dort anmelden – fuer die automatische Anmeldung fehlen N8N_UI_EMAIL und N8N_UI_PASSWORD.';
const REFUSED = 'n8n-Editor ist offen. Die automatische Anmeldung hat nicht geklappt – bitte dort anmelden.';

/**
 * Opens the editor in `win`: signs in first when an account is set, then shows the target.
 * Resolves what the IPC handler returns. Nothing here logs or returns the account.
 */
async function openEditor({ win, base, workflowId, env = process.env, net, shell, log = () => {} }) {
  limitToN8n(win.webContents, base, shell);
  const login = editorLogin(env);
  if (!login) {
    log('[n8n] Editor ohne automatische Anmeldung geoeffnet (N8N_UI_EMAIL/N8N_UI_PASSWORD nicht gesetzt)');
    win.loadURL(`${base}/signin`);
    return { success: true, autoLogin: false, message: NO_ACCOUNT };
  }
  const result = await signIn({ net, session: win.webContents.session, base, login });
  if (win.isDestroyed()) return { success: false, autoLogin: false, message: 'n8n-Editor wurde geschlossen.' };
  if (!result.ok) {
    log(`[n8n] Automatische Anmeldung abgelehnt (Status ${result.status || result.reason})`);
    win.loadURL(`${base}/signin`);
    return { success: true, autoLogin: false, message: REFUSED };
  }
  win.loadURL(`${base}${targetPath(workflowId)}`);
  return { success: true, autoLogin: true };
}

module.exports = { editorLogin, isN8nPage, targetPath, signIn, limitToN8n, openEditor };
