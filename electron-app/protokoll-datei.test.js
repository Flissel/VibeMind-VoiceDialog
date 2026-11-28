// Lauf 43: Zeilen des Hauptprozesses (VibeCoder) landen in logs/renderer.log, im Format der Renderer-Zeilen.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { protokollZeile, RENDERER_LOG } = require('./protokoll-datei');

const jetzt = () => new Date('2026-01-02T03:04:05.000Z');

test('eine Zeile im Format der Renderer-Zeilen, Zeilenumbrueche werden zu Leerzeichen', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'protokoll-'));
  const datei = path.join(dir, 'logs', 'renderer.log');
  protokollZeile('info', '[VibeCoder] OpenFang antwortet mit 200 nach 250 ms', { datei, jetzt });
  protokollZeile('info', 'zwei\nZeilen', { datei, jetzt });
  assert.equal(fs.readFileSync(datei, 'utf8'),
    '[2026-01-02T03:04:05.000Z] [info] [VibeCoder] OpenFang antwortet mit 200 nach 250 ms\n'
    + '[2026-01-02T03:04:05.000Z] [info] zwei Zeilen\n');
  fs.rmSync(dir, { recursive: true, force: true });
});

test('ein Schreibfehler stoert den Ablauf nicht', () => {
  assert.doesNotThrow(() => protokollZeile('info', 'x', { datei: path.join(os.tmpdir(), 'egal.log'), anhaengen: () => { throw new Error('EACCES'); } }));
});

test('dieselbe Datei wie die Renderer-Zeilen, und der VibeCoder schreibt hinein', () => {
  assert.equal(RENDERER_LOG, path.join(__dirname, '..', 'logs', 'renderer.log'));
  const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
  assert.match(main, /path'\)\.join\(__dirname, '\.\.', 'logs', 'renderer\.log'\)/);
  assert.match(main, /const vibecoderLog = \(line\) => \{ console\.log\(line\); require\('\.\/protokoll-datei'\)\.protokollZeile\('info', line\); \};/);
  assert.match(main, /createVibeCoderChat\(\{ env: process\.env, log: vibecoderLog \}\)/);
});
