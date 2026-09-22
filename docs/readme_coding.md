# Coding.Space

**Autonome Code-Produktions-Pipeline und Vibe-Coding-Plattform für alle Sprachen — von Web-Apps bis C++ und Simulationen.**

## Overview

Coding.Space ist Vibeminds Software-Entwicklungsplattform mit zwei Modi:

1. **Autonome Pipeline**: Basierend auf einem Requirements-Stack generiert die Coding_engine (Society of Mind mit 40+ Agents) vollständige Projekte autonom — inklusive Docker-Sandbox, Testing und VNC-Preview.
2. **Vibe-Coding**: Ähnlich wie Lovable, aber sprachunabhängig — User beschreiben per Voice was sie wollen und sehen den Code in Echtzeit entstehen. Unterstützt nicht nur Web-Technologien, sondern auch C++, Simulationen und andere Software-Sprachen.

Die Architektur trennt klar: VibeMind steuert und überwacht, der externe Coding_engine generiert den Code.

## Architektur

```
Voice → IntentClassifier → code.* Event
                              ↓
                      CodingAgent (Backend)
                              ↓
                      CodingEngineRunner
                              ↓ (Subprocess)
                      Coding_engine (extern)
                        ├── 3-Layer Hybrid Pipeline
                        ├── Docker Sandbox
                        ├── VNC Preview Server
                        └── BDD Testing
                              ↓
                      Status-Updates → Electron UI
```

> **Hinweis (2026-09-22):** Die im Folgenden beschriebene Implementierung
> (`python/spaces/coding/agents/`, `engine/`, `tools/`, `broadcast/`) wurde am
> 2026-06-16 vollständig aus dem Repo entfernt (Commit `ec98a0c6`, u. a.
> `agents/coding_agent.py` [117 Zeilen], `engine/coding_engine_runner.py`
> [689 Zeilen — nahe an den unten genannten 690], `tools/coding_tools.py`
> [595 Zeilen — nahe an den unten genannten 587], `tools/adapted_coding_tools.py`,
> `tools/voice_coding_tools.py`, `broadcast/coding_broadcast_agent.py`,
> `engine/project_discovery.py`; insgesamt 3056 Dateien / 923.402 Zeilen allein
> in diesem Commit unter `spaces/coding/`). `spaces/coding/` existiert im
> aktuellen Code nicht mehr — auch nicht als leeres Verzeichnis. Der
> lazy-Import `CodingAgent` in `python/swarm/backend_agents/__init__.py` zeigt
> auf einen nicht mehr vorhandenen Pfad. Ob und wie die externe
> `Coding_engine`-Submodule (heute als Top-Level-Submodul `coding-engine/`
> registriert, nicht mehr unter `spaces/coding/Coding_engine/`) die
> beschriebene Funktionalität ersetzt, wurde nicht geprüft — der aktuell
> gepinnte Commit dieser Submodule ist vom hiesigen Remote nicht abrufbar.

## Backend-Agent

**Datei (nicht mehr vorhanden):** `python/spaces/coding/agents/coding_agent.py`

| Event | Tool-Funktion | Beschreibung |
|-------|--------------|-------------|
| `code.generate` | `generate_code` | Code-Generierung starten |
| `code.status` | `get_generation_status` | Generierungs-Status abfragen |
| `code.cancel` | `cancel_generation` | Generierung abbrechen |
| `code.list` | `list_generated_projects` | Projekte auflisten |
| `code.preview.start` | `start_preview` | VNC-Preview starten |
| `code.preview.stop` | `stop_preview` | Preview beenden |
| `idea.to_project` | `idea_to_project_sync` | Bubble-Idee zu Projekt konvertieren |
| `code.modify` | `modify_code_sync` | Code per Voice modifizieren |

## Key Components

| Komponente | Datei | Zweck |
|-----------|-------|-------|
| Backend-Agent | `agents/coding_agent.py` | Event-Routing zu Tools |
| Engine Runner | `engine/coding_engine_runner.py` (690 Zeilen) | Subprocess-Bridge zum Coding_engine |
| Project Discovery | `engine/project_discovery.py` | Projekt-Erkennung |
| Coding Tools | `tools/coding_tools.py` (587 Zeilen) | Haupt-Tool-Implementierungen |
| Adapted Tools | `tools/adapted_coding_tools.py` | Typisierte Wrapper |
| Voice Tools | `tools/voice_coding_tools.py` | Async Voice-Wrapper |
| Broadcast Agent | `broadcast/coding_broadcast_agent.py` | Electron-UI-Updates |
| Coding_engine | `Coding_engine/` (Git-Submodul) | Externer Code-Generator |

## CodingEngineRunner

Der Runner (`engine/coding_engine_runner.py`) verwaltet den externen Coding_engine als Subprocess:

- **VNC-Port-Allokation**: Unique Ports pro Job ab BASE_VNC_PORT (6080)
- **Requirements-Generierung**: Erstellt `requirements.json` aus Voice-Input
- **Echtzeit-Status-Streaming**: Parsed JSON + Text Progress-Updates
- **Quality-Monitoring**: Pollt `self_critique_report.json` während Generierung
- **4 Convergence-Modes**: `autonomous`, `strict`, `relaxed`, `fast`
- **Job-Lifecycle**: pending → generating → converging → testing → completed/failed

**Subprocess-Flags:**
```
python run_engine.py <requirements.json> \
  --autonomous --continuous-sandbox --external-sandbox \
  --enable-vnc --vnc-port 6080 --enable-validation \
  --output-dir <path> --json-progress --parallel 10
```

## VNC-Preview-System

Voll implementiert mit Port-Management:

- `start_preview()` — Allokiert Port, startet VNC-Server, speichert URL in DB
- `stop_preview()` — Terminiert Server, gibt Port frei
- `_find_available_port()` — Verhindert Port-Kollisionen
- DB-Felder: `vnc_port INTEGER`, `preview_url TEXT` in `projects` Tabelle

## Testing

Der externe Coding_engine enthält BDD-Testing-Infrastruktur:
- 23 Gherkin Feature-Files (User Stories)
- Pytest Step-Definitions mit Factories und Fixtures
- `seed_data.sql` für Test-Datenbanken
- `--enable-validation` Flag für automatische Tests

> **Hinweis:** Test-Ergebnisse werden vom externen Subprocess verarbeitet. Voice-gesteuerte Test-Ausführung und Ergebnis-Anzeige in Electron sind noch nicht implementiert.

## Current Status

> Die folgende Liste beschreibt den Stand vor der Entfernung von
> `spaces/coding/` am 2026-06-16 (siehe Hinweis oben). Sie ist im aktuellen
> Code nicht mehr nachvollziehbar.

### Implementiert
- Voice-gesteuerte Code-Generierung über Intent-Classification
- 8 Event-Types mit vollständigem Tool-Mapping
- CodingEngineRunner als Subprocess-Bridge
- VNC-Preview-System mit Multi-Project Port-Management
- Echtzeit-Status-Streaming zu Electron UI
- Job-Lifecycle-Management (Start, Cancel, Status)
- Quality-Monitoring via self_critique_report.json
- Docker-Sandbox-Integration (Flags an Engine)
- Projekt-Tracking in SQLite (projects Tabelle)
- Idea-to-Project Konvertierung aus Bubbles

### Nicht implementiert
- Test-Ergebnisse nicht in Electron UI angezeigt
- Keine Voice-gesteuerte Einzeltest-Ausführung
- Kein Code-Review-Gate in VibeMind (extern im Coding_engine)
- Production-Deployment-Pipeline über Preview hinaus
- UI/UX-Design-to-Code-Konvertierung

## Roadmap

- Test-Ergebnisse und Quality-Reports in Electron UI anzeigen
- Voice-gesteuerte Test-Ausführung und Debugging
- Production-Deployment-Infrastructure über Preview hinaus
- Spezialisierte Code-Generierung für Domain-spezifische Probleme
- Code-Review-System mit automatisierten Quality-Checks
- Progressive Refinement (iterative Verbesserung basierend auf Feedback)
- Containerized Environment Generation für komplexe Deployments

## Ecosystem-Fit

Coding.Space transformiert Intent in Production Code. Ideas.Space artikuliert was gebaut werden soll, und Coding.Space generiert es. Rowboat.Space liefert Business-Logik und Daten-Requirements. Software Design.Space validiert Architektur-Entscheidungen. Desktop.Space validiert, dass deployed Applications korrekt funktionieren. The Brain.Space informiert architektonische Entscheidungen durch Pattern-Erkennung.
