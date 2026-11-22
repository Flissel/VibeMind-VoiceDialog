/**
 * Where n8n is and how the Agent Farm signs in.
 *
 * n8n may run on this machine or elsewhere (N8N_API_URL). The Agent Farm shows the n8n
 * editor in a frame and signs in for the user. The address was hardcoded to
 * localhost:15678 in three places and the sign-in always used the account that a
 * freshly started local n8n gets; against any other n8n that was refused six times in
 * a row (401, then 429).
 *
 * Sign-in data come from the environment (N8N_UI_EMAIL, N8N_UI_PASSWORD). The built-in
 * account is only tried against an n8n on this machine.
 */

const LOCAL_URL = 'http://localhost:15678';
// The owner that local-startup.js creates on a fresh local n8n. Not a secret of any real system.
const LOCAL_OWNER = Object.freeze({ email: 'admin@vibemind.local', password: 'Vibemind1' });

function n8nBaseUrl(env = process.env) {
  const raw = typeof env.N8N_API_URL === 'string' ? env.N8N_API_URL.trim() : '';
  try {
    const url = new URL(raw || LOCAL_URL);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return LOCAL_URL;
    return url.origin;
  } catch (_) {
    return LOCAL_URL;
  }
}

function isLocal(baseUrl) {
  const host = new URL(baseUrl).hostname;
  return host === 'localhost' || host === '127.0.0.1' || host === '[::1]';
}

/** The account to sign in with, or null when none is known for this n8n. */
function n8nLogin(env = process.env) {
  const email = typeof env.N8N_UI_EMAIL === 'string' ? env.N8N_UI_EMAIL.trim() : '';
  const password = typeof env.N8N_UI_PASSWORD === 'string' ? env.N8N_UI_PASSWORD : '';
  if (email && password) return { email, password, source: 'environment' };
  if (isLocal(n8nBaseUrl(env))) return { ...LOCAL_OWNER, source: 'local default' };
  return null;
}

/**
 * A refused sign-in does not get better by repeating it, and n8n starts locking out
 * (429). Only "not there yet" is worth another try.
 */
function shouldRetryLogin(statusCode) {
  return ![400, 401, 403, 404, 422, 429].includes(statusCode);
}

/** Addresses whose framing headers the Agent Farm removes so they can be shown in a frame. */
function frameHeaderUrls(env = process.env) {
  const urls = new Set(['http://localhost:15678/*', 'http://localhost:4200/*']);
  urls.add(`${n8nBaseUrl(env)}/*`);
  return [...urls];
}

module.exports = { LOCAL_URL, n8nBaseUrl, n8nLogin, shouldRetryLogin, frameHeaderUrls };
