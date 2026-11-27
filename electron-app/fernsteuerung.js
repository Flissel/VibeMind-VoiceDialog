/**
 * K9: the remote-control port (CDP) only in a test run, and approvals outside the page.
 *
 * With the port open, any local program can type and click in the window as if it were the person
 * (CDP input is isTrusted and gives user activation) and can call the preload directly. So nothing
 * decided in the page proves a person then (port-9223-plan.md).
 *
 * Part 1 – test mode: the port opens only with VIBEMIND_ENABLE_CDP=1 (main.js). Whether it is open is
 * read from the command line of this process, so a port from a start line counts too. While it is
 * open: a fixed strip "Prüfmodus: Fernsteuerung offen" in the window, no sentence counts as typed, the
 * Brain is told `fernsteuerung_offen: true`, no click on the desktop picture is signed, and Sales
 * approvals are refused. All of that lives in this process, not in the page.
 *
 * Part 2 – native confirmation: when the Brain asks for a Sales approval (an answer with
 * `bestaetigung: { art: "sales_freigabe", frage_id, frage }`), the person answers in a dialog of this
 * process, which CDP cannot reach. Only that answer goes to the Brain as `bestaetigt_nativ`, with the
 * proof of this main process (chat-input.js).
 */
'use strict';

const BANNER = 'Prüfmodus: Fernsteuerung offen';
/** Kinds of questions the person answers only in the native dialog. */
const NATIVE_ARTS = Object.freeze(['sales_freigabe']);
const ID = /^[A-Za-z0-9_.:-]{1,128}$/;

const TEXT = Object.freeze({
  gesperrt: 'Im Prüfmodus (Fernsteuerung offen) sind Sales-Freigaben gesperrt. Bitte die App ohne Prüfmodus starten.',
  ja: 'Ja, freigeben',
  nein: 'Nein',
});

/** Whether this process has a remote-control port, whoever asked for it. */
function remoteControlOpen(commandLine) {
  if (!commandLine || typeof commandLine.hasSwitch !== 'function') return false;
  return commandLine.hasSwitch('remote-debugging-port') || commandLine.hasSwitch('remote-debugging-pipe');
}

/** Height of the strip; the page reads it as --vm-pruefstreifen to keep panels at the top below it (Lauf 39). */
const BANNER_HEIGHT_PX = 22;

/**
 * The strip at the top of the window, as CSS only (no script in the page).
 * pushDown (Lauf 42): for a page that is not ours (the n8n editor), which does not read --vm-pruefstreifen and
 * lost half of its top line under the strip: the whole page starts below the strip and keeps its height.
 */
function bannerCss({ pushDown = false } = {}) {
  const push = pushDown
    ? `html { margin-top: ${BANNER_HEIGHT_PX}px !important; height: calc(100% - ${BANNER_HEIGHT_PX}px) !important; overflow: hidden !important; }
html body { height: 100% !important; }
`
    : '';
  return `html { --vm-pruefstreifen: ${BANNER_HEIGHT_PX}px; }
${push}html body::before {
  content: '${BANNER}';
  position: fixed; top: 0; left: 0; right: 0; z-index: 2147483647;
  height: ${BANNER_HEIGHT_PX}px; box-sizing: border-box; line-height: 16px;
  padding: 3px 12px; text-align: center; pointer-events: none;
  font: 600 12px 'Segoe UI', Tahoma, sans-serif; letter-spacing: 0.3px;
  color: #1a1000; background: #ffc145; box-shadow: 0 1px 6px rgba(0, 0, 0, 0.5);
}
`;
}

/** Put the strip into the window after every load. */
function showBanner(webContents, logger = console, { pushDown = false } = {}) {
  const css = bannerCss({ pushDown });
  webContents.on('did-finish-load', () => {
    Promise.resolve()
      .then(() => webContents.insertCSS(css, { cssOrigin: 'author' }))
      .catch(() => logger.warn('[Fernsteuerung] Streifen nicht gesetzt'));
  });
  return css;
}

/** The question of an answer that the person must answer natively, or null. */
function nativeQuestion(answer) {
  const b = answer && typeof answer === 'object' ? answer.bestaetigung : null;
  if (!b || typeof b !== 'object' || Array.isArray(b)) return null;
  if (!NATIVE_ARTS.includes(b.art)) return null;
  if (typeof b.frage_id !== 'string' || !ID.test(b.frage_id)) return null;
  const frage = typeof b.frage === 'string' && b.frage.trim() ? b.frage.trim().slice(0, 600) : 'Diesen Entwurf freigeben?';
  return { art: b.art, frage_id: b.frage_id, frage };
}

/**
 * Ask the person in a dialog of the main process. Refused without a dialog while the port is open.
 * Returns { ja, gesperrt }.
 */
async function askNatively(question, { dialog, window, remoteOpen }) {
  if (remoteOpen) return { ja: false, gesperrt: true };
  const options = {
    type: 'question',
    title: 'Sales-Freigabe',
    message: question.frage,
    detail: 'Erst mit „Ja, freigeben" geht der Entwurf raus.',
    buttons: [TEXT.nein, TEXT.ja],
    defaultId: 0,
    cancelId: 0,
    noLink: true,
  };
  const result = window ? await dialog.showMessageBox(window, options) : await dialog.showMessageBox(options);
  return { ja: !!result && result.response === 1, gesperrt: false };
}

module.exports = { remoteControlOpen, bannerCss, showBanner, nativeQuestion, askNatively, BANNER, BANNER_HEIGHT_PX, NATIVE_ARTS, TEXT };
