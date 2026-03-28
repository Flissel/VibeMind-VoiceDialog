# Systembeschreibung

## VibeMind Voice Dialog — Voice-controlled Multiverse Workspace

**Version:** 1.0.0
**Status:** Phase 17+ (Post-Modular-Migration)
**Datum:** Maerz 2026
**Lizenz:** MIT

---

## Projektsteckbrief

| Eigenschaft | Wert |
|------------|------|
| Projektname | VibeMind Voice Dialog |
| Typ | Voice-controlled Multi-Space Workspace |
| Team | Solo-Entwickler + Claude Code Co-Pilot |
| Entwicklungsphase | Production-Ready Core, Active Feature Expansion |
| Plattform | Windows 11 (Electron Desktop App) |
| Sprache | Deutsch (Primaer), Englisch (Sekundaer) |

---

## Systemueberblick

VibeMind ist ein sprachgesteuertes Multiverse-Workspace, das natuerliche Spracheingabe in strukturierte Aktionen uebersetzt und ueber eine 3D-Electron-Oberflaeche visualisiert.

```
Nutzer spricht
    |
    v
+---------------------------+
| Voice Layer               |
| OpenAI Realtime API       |
| (+ ElevenLabs Fallback)   |
+---------------------------+
    |
    v
+---------------------------+
| Intent Orchestrator       |
| LLM-basierte Klassifikation|
| 100+ Event Types          |
+---------------------------+
    |
    v
+---------------------------+
| Event Router              |
| Sync Mode (Redis optional)|
+---------------------------+
    |
    +--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
    |        |        |        |        |        |        |        |        |        |        |
    v        v        v        v        v        v        v        v        v        v        v
 IDEAS   CODING  DESKTOP ROARBOOT RESEARCH MINIBOOK SHUTTLES  N8N   AGENTFARM VIDEO  MIROFISH
 Space   Space   Space   Space    Space    Space    Space    Space   Space   Space   Space
    |        |        |        |        |        |        |        |        |        |        |
    +--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
    |
    v
+---------------------------+
| Electron UI               |
| Three.js 3D Multiverse    |
| Bubbles, Canvas, Shuttles |
+---------------------------+
```

---

## Schluesselmetriken

| Metrik | Wert |
|--------|------|
| Aktive Spaces | 15 (13 Domains + 1 Pipeline + 1 Standalone) |
| Intent Types | 100+ (ueber alle Spaces) |
| Orchestrator-Code | 7.500+ Zeilen |
| Backend Agents | 13 Domain-Agents |
| Tool-Module | 30+ |
| Event Streams | 13 Task-Streams + 4 System-Streams (optional via Redis) |
| Testdateien | 62 |
| ENV-Variablen | 50+ konfigurierbare Optionen |
| DB-Schema | Version 13 (SQLite WAL) |
| Voice Provider | OpenAI Realtime API (gpt-4o-realtime) |
| Git Submodule | 4 (Coding_engine, Automation_ui, Rowboat, SWE Design) |

---

## Kernkomponenten

### 1. Voice Layer
OpenAI Realtime API als einziger Voice Provider. Unterstuetzt Speech-to-Speech, Voice Activity Detection und native Function Calling.

### 2. Intent Pipeline
LLM-basierte Klassifikation von natuerlicher Sprache in strukturierte Event-Types. Optionale Erweiterungen: CollectorAgent (Fragmentakkumulation), IntentEnhancer (ASR-Fehlerkorrektur), DroPE Resolver (Referenzaufloesung), RAG Classifier (Semantische Klassifikation).

### 3. Multiverse Spaces
15 modulare Spaces mit eigenstaendigen Agents, Tools und Workers. Jeder Space verarbeitet seine eigenen Event-Types im Sync-Modus (optional async via Redis Streams).

### 4. Electron 3D UI
Three.js-basierte 3D-Visualisierung mit Bubbles (Ideen), Canvas (Verbindungen), Shuttles (Requirements Pipeline) und Space-spezifischen Visualisierungen (Nebula, Planet, Portal, Factory).

### 5. Swarm Backend
BaseBackendAgent-Pattern mit TOOL_MAP und PARAM_MAPPING fuer konsistente Tool-Ausfuehrung. Standard: Synchrone Direktausfuehrung (optional async via Redis Streams).

---

## Entwicklungsgeschichte (Meilensteine)

| Phase | Beschreibung |
|-------|-------------|
| Phase 1-3 | Modular Filesystem Migration |
| Phase 11 | Tool Orchestrator (Multi-Step Requests) |
| Phase 13 | Multi-Agent Intent Analysis |
| Phase 15 | OpenAI Realtime API Integration |
| Phase 16 | ZeroClaw Research Space |
| Phase 17 | Minibook Inter-Space Collaboration |
| Phase 17+ | Messaging Pipeline, Roarboot Space, Dead Code Cleanup |

---

## Einstiegspunkte

| Datei | Zweck |
|-------|-------|
| `electron-app/main.js` | Electron Hauptprozess (Python Spawning, IPC, Manager) |
| `python/electron_backend.py` | Python Backend (Stdin/Stdout JSON Protokoll) |
| `python/voice/openai_realtime.py` | OpenAI Realtime Voice Session |
| `python/swarm/orchestrator/intent_orchestrator.py` | Intent-Orchestrierung (Gehirn) |

---

## Konfiguration

Alle Einstellungen ueber `.env`-Datei (siehe `.env.example`):

```bash
# Minimal-Setup
OPENAI_API_KEY=xxx
FORCE_SYNC_MODE=true               # Kein Redis erforderlich

# Voll-Setup
USE_TOOL_ORCHESTRATOR=true
USE_TASK_MEMORY=true
MINIBOOK_ENABLED=true
```
