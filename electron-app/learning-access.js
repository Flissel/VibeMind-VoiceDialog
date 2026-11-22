/**
 * Access to the learning space ("Lern-Huelle") for the owner's own app.
 *
 * The learning page answers 403 unless the request carries the access cookie `huelle_zugang`.
 * That cookie is normally set by opening an access link that the learning space sends by
 * Telegram. The app runs on the machine that holds the signing key, so it issues the same
 * cookie itself: the entry "Lernen" then opens signed in, with nothing to type or click.
 *
 * Same construction as spaces/learning/huelle/zugang.py (HMAC-SHA256 over the expiry, 30 days).
 * The key is read in the main process only; it is never logged and never reaches a page.
 */
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const COOKIE = 'huelle_zugang';
const VALID_SECONDS = 30 * 24 * 3600;
const OWN_KEY = 'LEARNING_HUELLE_ZUGANG_SCHLUESSEL';
const SERVICE_KEY = 'LEARNHOUSE_LEARNING_SERVICE_KEY'; // what the learning space signs with when it has no own key

function keyFile(env = process.env) {
  const named = typeof env.LEARNING_HUELLE_ENV === 'string' ? env.LEARNING_HUELLE_ENV.trim() : '';
  if (named) return named;
  return env.LOCALAPPDATA ? path.join(env.LOCALAPPDATA, 'VibeMind', 'learning-huelle', 'huelle.env') : '';
}

function readAccessKey(file, readFile = (name) => fs.readFileSync(name, 'utf8')) {
  if (!file) return '';
  let text;
  try {
    text = readFile(file);
  } catch (_) {
    return '';
  }
  const values = {};
  for (const line of String(text).split(/\r?\n/)) {
    const match = /^\s*([A-Z0-9_]+)\s*=(.*)$/.exec(line);
    if (match) values[match[1]] = match[2].trim().replace(/^(["'])(.*)\1$/, '$2').trim();
  }
  return values[OWN_KEY] || values[SERVICE_KEY] || '';
}

function mintToken(key, nowMs = Date.now()) {
  const expiry = Math.floor(nowMs / 1000 + VALID_SECONDS);
  const hmacKey = crypto.createHash('sha256').update(`huelle:${key}`, 'utf8').digest();
  const signature = crypto.createHmac('sha256', hmacKey).update(String(expiry), 'ascii').digest('hex');
  return Buffer.from(`${expiry}.${signature}`, 'ascii').toString('base64url');
}

/** The cookie for Electron's `session.cookies.set`, or null when there is no key or no https address. */
function accessCookie(spaceUrl, key, nowMs = Date.now()) {
  if (!key) return null;
  let url;
  try {
    url = new URL(spaceUrl);
  } catch (_) {
    return null;
  }
  if (url.protocol !== 'https:') return null; // the learning space sets the cookie as Secure
  return {
    url: `${url.origin}/`,
    name: COOKIE,
    value: mintToken(key, nowMs),
    path: '/',
    httpOnly: true,
    secure: true,
    sameSite: 'strict',
    expirationDate: Math.floor(nowMs / 1000 + VALID_SECONDS),
  };
}

/** What the external-space manager calls for an entry with `access: 'learning-huelle'`. */
function learningAccessCookie(spaceUrl, env = process.env) {
  return accessCookie(spaceUrl, readAccessKey(keyFile(env)));
}

module.exports = { COOKIE, keyFile, readAccessKey, mintToken, accessCookie, learningAccessCookie };
