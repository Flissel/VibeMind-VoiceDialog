/**
 * Zeilen des Hauptprozesses in voice/logs/renderer.log, im selben Format wie die Zeilen des Renderers
 * (ipcMain 'renderer-log' in main.js): `[ISO-Zeit] [stufe] text`. Fehler beim Schreiben werden geschluckt:
 * ein Protokoll darf nie den Ablauf stoeren. Wer hier schreibt, schreibt nur Status und Dauer, nie Inhalte.
 */
const fs = require('node:fs');
const path = require('node:path');

const RENDERER_LOG = path.join(__dirname, '..', 'logs', 'renderer.log');

function protokollZeile(stufe, text, { datei = RENDERER_LOG, anhaengen = fs.appendFileSync, jetzt = () => new Date() } = {}) {
  const zeile = `[${jetzt().toISOString()}] [${stufe}] ${String(text).replace(/[\r\n]+/g, ' ')}\n`;
  try {
    fs.mkdirSync(path.dirname(datei), { recursive: true });
    anhaengen(datei, zeile);
  } catch (_) { /* Protokoll ist Beiwerk */ }
  return zeile;
}

module.exports = { protokollZeile, RENDERER_LOG };
