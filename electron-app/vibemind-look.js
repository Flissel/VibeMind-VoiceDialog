/**
 * The VibeMind look for a page shown in a space view (BrowserView).
 *
 * The values are those of the app itself (renderer/styles/base.css, the accent of each space
 * from renderer/multiverse.js). applyVibeMindLook puts them into the page as CSS after every
 * load: the `--vm-*` variables, the accent of the space, a dark color scheme, and whatever a
 * space adds to fit its page onto them (for Laura: its own variables, see video-manager.js).
 * The page keeps its code; nothing is written into the app shown.
 */

/** The accent of each space (renderer/multiverse.js, SPACE_ACCENT_RGB). */
const SPACE_ACCENT_RGB = Object.freeze({
  ideas: '68,136,255',
  projects: '68,255,136',
  desktop: '255,136,68',
  roarboot: '34,204,170',
  swedesign: '255,102,51',
  clawport: '136,102,255',
  agentfarm: '136,170,68',
  video: '238,68,102',
  thebrain: '255,102,170',
  flowzen: '51,102,204',
  mirofish: '0,204,187',
});

/** The look of the app (renderer/styles/base.css :root). */
const VM_TOKENS = Object.freeze({
  '--vm-bg-deep': '#0a0812',
  '--vm-bg-mid': '#12101e',
  '--vm-bg-surface': 'rgba(20, 18, 32, 0.92)',
  '--vm-bg-elevated': 'rgba(30, 27, 48, 0.88)',
  '--vm-text-primary': '#f0e8ff',
  '--vm-text-secondary': 'rgba(230, 220, 245, 0.65)',
  '--vm-text-muted': 'rgba(200, 190, 220, 0.40)',
  '--vm-panel-bg': 'rgba(16, 14, 28, 0.85)',
  '--vm-status-ok': '#5eff8a',
  '--vm-status-warn': '#ffc145',
  '--vm-status-error': '#ff5a6e',
  '--vm-status-info': '#6eb8ff',
  '--vm-font': "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
});

/**
 * The CSS for a space: the tokens, its accent and the extra block of the space.
 * `html:root` weighs more than a page's own `:root`, so the values hold whatever the order.
 */
function lookCss(space, extraCss = '') {
  const rgb = SPACE_ACCENT_RGB[space] || SPACE_ACCENT_RGB.ideas;
  const lines = Object.entries(VM_TOKENS).map(([name, value]) => `  ${name}: ${value};`);
  lines.push(`  --space-accent-rgb: ${rgb};`);
  lines.push(`  --space-accent: rgb(${rgb});`);
  lines.push('  --vm-panel-border: rgba(var(--space-accent-rgb), 0.20);');
  lines.push('  color-scheme: dark;');
  return `html:root {\n${lines.join('\n')}\n}\n${extraCss || ''}`;
}

/**
 * Give the page of a view the VibeMind look, now and after every load (a reload, the status
 * card). Returns the CSS it puts in. A failed insert is logged and changes nothing else.
 */
function applyVibeMindLook(webContents, space, options = {}) {
  const css = lookCss(space, options.extraCss);
  const logger = options.logger || console;
  const put = () => {
    if (typeof webContents.isDestroyed === 'function' && webContents.isDestroyed()) return;
    Promise.resolve()
      .then(() => webContents.insertCSS(css, { cssOrigin: 'author' }))
      .catch(() => logger.warn(`[VibeMindLook] ${space}: Aussehen nicht gesetzt`));
  };
  webContents.on('did-finish-load', put);
  return css;
}

module.exports = { applyVibeMindLook, lookCss, SPACE_ACCENT_RGB, VM_TOKENS };
