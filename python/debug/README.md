# Electron Debug Agent

AutoGen 0.4 basierter Debug-Agent für Electron-Anwendungen.
Verbindet sich über das Chrome DevTools Protocol (CDP) und erstellt kontinuierliche Debug-Logs.

## Features

- 📝 **Console Logs** - Alle console.log/warn/error Ausgaben
- ❌ **Exceptions** - Runtime-Fehler mit Stack-Traces
- 🌐 **Network** - HTTP Requests und Responses
- 📊 **Statistiken** - Zähler für Errors, Warnings, etc.
- 🤖 **AI-Analyse** - Optional: AutoGen Agent für Log-Analyse

## Architektur

```
┌─────────────────────┐     WebSocket      ┌─────────────────────┐
│   Debug Agent       │◄──────────────────►│   Electron App      │
│   (Python)          │        CDP         │   (--inspect)       │
├─────────────────────┤                    └─────────────────────┘
│ - CDPClient         │
│ - DebugLogger       │
│ - AutoGen Agent     │
└─────────┬───────────┘
          │
          ▼
    logs/electron_debug/
    └── electron_debug_YYYYMMDD_HHMMSS.jsonl
```

## Installation

```bash
# Erforderliche Abhängigkeiten
pip install websockets aiohttp

# Optional für AI-Analyse
pip install autogen-agentchat autogen-ext
```

## Verwendung

### 1. Electron mit Debug-Port starten

```bash
# Windows (VibeMind)
set ELECTRON_RUN_AS_NODE=
electron --remote-debugging-port=9222 electron-app

# Oder via start_vibemind_debug.bat
```

### 2. Debug-Agent starten

```bash
cd python/debug
python electron_debug_agent.py
```

### 3. Output

Die Logs werden in `logs/electron_debug/` gespeichert:

```json
{"timestamp": "2024-12-02T18:15:00", "category": "console", "level": "info", "message": "App started"}
{"timestamp": "2024-12-02T18:15:01", "category": "exception", "level": "error", "message": "TypeError: ...", "data": {...}}
```

## Konfiguration

```python
config = DebugConfig(
    cdp_port=9222,              # CDP Port
    cdp_host="127.0.0.1",       # CDP Host
    log_dir=Path("logs/debug"), # Log-Verzeichnis
    log_console=True,           # Console.log abfangen
    log_network=True,           # Network Requests
    log_errors=True,            # Exceptions
    max_log_size_mb=50,         # Max Log-Größe vor Rotation
)
```

## API

### CDPClient

```python
# Verbinden
cdp = CDPClient(config)
await cdp.connect()

# Event Handler registrieren
cdp.on("Runtime.consoleAPICalled", my_handler)

# CDP Befehl senden
result = await cdp.send("Runtime.evaluate", {"expression": "1+1"})
```

### DebugLogger

```python
logger = DebugLogger(config)
logger.log("category", "error", "Message", {"extra": "data"})
```

### ElectronDebugAgent

```python
agent = ElectronDebugAgent()
await agent.start()
await agent.run_forever()

# Oder mit AutoGen Analyse
analysis = await agent.analyze("What errors occurred?")
```

## CDP Domains

Der Agent aktiviert folgende Chrome DevTools Protocol Domains:

| Domain | Zweck |
|--------|-------|
| Runtime | JavaScript Execution, Console |
| Console | Console API |
| Log | Browser Logs |
| Network | HTTP Requests (optional) |
| DOM | DOM Events (optional) |

## Integration mit VibeMind

Der Debug-Agent kann parallel zur VibeMind Voice-App laufen:

```bash
# Terminal 1: VibeMind mit Debug
electron --remote-debugging-port=9222 electron-app

# Terminal 2: Debug Agent
python python/debug/electron_debug_agent.py
```

Die Logs zeigen dann alle Voice-Dialog Events, Agent-Transfers und Fehler.

## Troubleshooting

### "Failed to connect to Electron"

Stellen Sie sicher, dass Electron läuft mit `--remote-debugging-port=9222`:
```bash
electron --remote-debugging-port=9222 electron-app
```

### "No targets found"

Die Electron-App muss mindestens ein Fenster geöffnet haben.

### Logs werden nicht geschrieben

Prüfen Sie die Schreibrechte im `logs/` Verzeichnis.