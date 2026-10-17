/**
 * Verbindung zum Einbettungszugang der laufenden Rowboat-Instanz
 * (Spec vibemind-os 2026-10-17-rowboat-einbettung, Abschnitt 4).
 *
 * Liest <ROWBOAT_WORKDIR | ~/.rowboat>/embed.json, meldet sich mit dem Token an und reicht
 * invoke weiter. Das Token bleibt in diesem Hauptprozess; die Rowboat-Ansicht sieht es nie.
 * Die voice-App startet Rowboat nicht – sie verbindet sich nur und versucht es mit Backoff erneut.
 */
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const BACKOFF_MS = [1000, 2000, 5000, 10000]; // Obergrenze 10 s: Rowboat-Neustart soll schnell sichtbar werden
const PROTOCOL_VERSION = 1;
const HELLO_TIMEOUT_MS = 5000;
const MAX_MESSAGE_BYTES = 64 * 1024 * 1024;
const NOT_RUNNING = 'Rowboat laeuft nicht (start_desktop.py --embed)';

function defaultEmbedFile(env = process.env) {
  return path.join(env.ROWBOAT_WORKDIR || path.join(os.homedir(), '.rowboat'), 'embed.json');
}

function defaultPidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return err.code === 'EPERM';
  }
}

function readEmbedInfo(file, { readFileSync = fs.readFileSync, isPidAlive = defaultPidAlive } = {}) {
  let raw;
  try {
    raw = JSON.parse(readFileSync(file, 'utf8'));
  } catch {
    return { ok: false, reason: NOT_RUNNING };
  }
  const valid = raw && raw.v === 1 && Number.isInteger(raw.port) && raw.port > 0
    && typeof raw.token === 'string' && raw.token.length > 0
    && Number.isInteger(raw.pid) && raw.pid > 0 && typeof raw.preloadPath === 'string';
  if (!valid) return { ok: false, reason: 'embed.json unvollstaendig' };
  if (!isPidAlive(raw.pid)) return { ok: false, reason: NOT_RUNNING };
  return { ok: true, info: { port: raw.port, token: raw.token, pid: raw.pid, preloadPath: raw.preloadPath } };
}

class RowboatEmbedClient extends EventEmitter {
  constructor(deps = {}) {
    super();
    this.embedFile = deps.embedFile || defaultEmbedFile();
    this.WebSocket = deps.WebSocket || require('ws');
    this.readFileSync = deps.readFileSync || fs.readFileSync;
    this.isPidAlive = deps.isPidAlive || defaultPidAlive;
    this.backoffMs = deps.backoffMs || BACKOFF_MS;
    this.helloTimeoutMs = deps.helloTimeoutMs || HELLO_TIMEOUT_MS;
    this.logger = deps.logger || console;
    this.state = 'disconnected';
    this.reason = NOT_RUNNING;
    this.info = null;
    this.invokeChannels = [];
    this._ws = null;
    this._pending = new Map();
    this._nextId = 1;
    this._attempt = 0;
    this._timer = null;
    this._stopped = true;
  }

  get connected() {
    return this.state === 'connected';
  }

  start() {
    if (!this._stopped) return;
    this._stopped = false;
    this._connect();
  }

  stop() {
    this._stopped = true;
    clearTimeout(this._timer);
    this._timer = null;
    if (this._ws) this._ws.terminate();
  }

  invoke(channel, args) {
    if (!this.connected || !this._ws) return Promise.reject(new Error('Rowboat nicht verbunden'));
    const id = this._nextId++;
    let text;
    try {
      text = JSON.stringify({ type: 'invoke', id, channel, args });
    } catch (err) {
      return Promise.reject(err);
    }
    // Rowboat schliesst bei Ueberschreitung von maxPayload die ganze Verbindung (alle Ansichten).
    // Darum nur diesen Aufruf ablehnen, ohne zu senden.
    if (Buffer.byteLength(text) > MAX_MESSAGE_BYTES) {
      const err = new Error(`embed_too_large: Aufruf ${channel} ist groesser als ${MAX_MESSAGE_BYTES} Bytes`);
      err.code = 'embed_too_large';
      return Promise.reject(err);
    }
    const ws = this._ws;
    return new Promise((resolve, reject) => {
      this._pending.set(id, { resolve, reject });
      try {
        ws.send(text);
      } catch (err) {
        this._pending.delete(id);
        reject(err);
      }
    });
  }

  /** Holt Rowboats eigenes Fenster nach vorn („In Rowboat öffnen“). */
  showApp() {
    if (!this.connected || !this._ws) return false;
    this._ws.send(JSON.stringify({ type: 'show-app' }));
    return true;
  }

  _schedule() {
    if (this._stopped || this._timer) return;
    const delay = this.backoffMs[Math.min(this._attempt, this.backoffMs.length - 1)];
    this._attempt += 1;
    this._timer = setTimeout(() => {
      this._timer = null;
      this._connect();
    }, delay);
  }

  _down(reason) {
    const was = this.connected;
    this.state = 'disconnected';
    this.reason = reason;
    this.info = null;
    this.invokeChannels = [];
    if (was) {
      this.logger.warn(`[RowboatEmbed] getrennt – ${reason}`);
      this.emit('disconnected', reason);
    }
  }

  _connect() {
    if (this._stopped) return;
    const read = readEmbedInfo(this.embedFile, { readFileSync: this.readFileSync, isPidAlive: this.isPidAlive });
    if (!read.ok) {
      this._down(read.reason);
      this._schedule();
      return;
    }
    const info = read.info;
    this.state = 'connecting';
    const ws = new this.WebSocket(`ws://127.0.0.1:${info.port}/embed`, { maxPayload: MAX_MESSAGE_BYTES });
    this._ws = ws;
    const helloTimer = setTimeout(() => ws.terminate(), this.helloTimeoutMs);
    let closeReason = null;
    ws.on('open', () => ws.send(JSON.stringify({ type: 'hello', v: PROTOCOL_VERSION, token: info.token })));
    ws.on('message', (data) => {
      let msg;
      if (this._ws !== ws) return;
      try { msg = JSON.parse(String(data)); } catch { return; }
      if (!msg || typeof msg !== 'object') return;
      if (msg.type === 'welcome' && msg.v !== PROTOCOL_VERSION) {
        clearTimeout(helloTimer);
        closeReason = `Rowboat-Protokoll unbekannt (v=${msg.v})`;
        ws.terminate();
      } else if (msg.type === 'welcome') {
        clearTimeout(helloTimer);
        this.info = info;
        this.invokeChannels = Array.isArray(msg.invokeChannels) ? msg.invokeChannels : [];
        this.state = 'connected';
        this.reason = '';
        this._attempt = 0;
        this.logger.info(`[RowboatEmbed] verbunden (127.0.0.1:${info.port}, ${this.invokeChannels.length} Kanaele)`);
        this.emit('connected', { invokeChannels: this.invokeChannels, preloadPath: info.preloadPath });
      } else if (msg.type === 'result') {
        const pending = this._pending.get(msg.id);
        if (!pending) return;
        this._pending.delete(msg.id);
        if (msg.ok) {
          pending.resolve(msg.result);
        } else {
          const err = new Error((msg.error && msg.error.message) || 'Rowboat-Fehler');
          if (msg.error && msg.error.code) err.code = msg.error.code;
          pending.reject(err);
        }
      } else if (msg.type === 'push') {
        this.emit('push', msg.channel, msg.payload);
      }
    });
    ws.on('error', (err) => this.logger.warn(`[RowboatEmbed] ${err.code || err.message}`));
    ws.on('close', (code) => {
      clearTimeout(helloTimer);
      if (this._ws !== ws) return; // veralteter Socket (stop()/start()): nicht den neuen stoeren
      this._ws = null;
      for (const pending of this._pending.values()) pending.reject(new Error('Verbindung zu Rowboat getrennt'));
      this._pending.clear();
      this._down(closeReason || (code === 4401 ? 'Anmeldung bei Rowboat abgelehnt' : 'Verbindung zu Rowboat getrennt'));
      this._schedule();
    });
  }
}

module.exports = { RowboatEmbedClient, readEmbedInfo, defaultEmbedFile, NOT_RUNNING, BACKOFF_MS, MAX_MESSAGE_BYTES };
