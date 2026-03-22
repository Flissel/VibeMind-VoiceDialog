/**
 * VibeMind Sentry Initialization (Main Process)
 *
 * Lazy-init pattern: Sentry.init() runs on first call to initSentry(),
 * which should happen after app.whenReady() in main.js.
 * This avoids the electron.app.getAppPath() crash during early require.
 */

let Sentry;
let sentryEnabled = false;

function initSentry() {
    if (sentryEnabled) return; // Already initialized

    const path = require('path');
    require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

    const dsn = process.env.SENTRY_DSN;
    if (!dsn) {
        console.log('[Sentry] No SENTRY_DSN configured, skipping');
        return;
    }

    try {
        Sentry = require('@sentry/electron/main');
        Sentry.init({
            dsn,
            environment: process.env.NODE_ENV || 'development',
            release: `vibemind@${require('./package.json').version}`,
            tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.2 : 1.0,
        });
        sentryEnabled = true;
        console.log('[Sentry] Initialized (main process)');
    } catch (err) {
        console.warn('[Sentry] Init failed:', err.message);
    }
}

function addBreadcrumb(crumb) {
    if (sentryEnabled && Sentry) {
        Sentry.addBreadcrumb(crumb);
    }
}

function setTag(key, value) {
    if (sentryEnabled && Sentry) {
        Sentry.setTag(key, value);
    }
}

function setContext(name, ctx) {
    if (sentryEnabled && Sentry) {
        Sentry.setContext(name, ctx);
    }
}

function captureMessage(msg, level) {
    if (sentryEnabled && Sentry) {
        Sentry.captureMessage(msg, level);
    }
}

module.exports = { initSentry, addBreadcrumb, setTag, setContext, captureMessage, get sentryEnabled() { return sentryEnabled; } };
