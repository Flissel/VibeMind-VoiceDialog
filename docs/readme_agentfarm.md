# AgentFarm.Space

**Multi-Agent-Orchestrierung mit AutoGen 0.4 — Team-Erstellung, asynchrone Ausführung, MCP-Server und Hybrid-Pipeline.**

## Overview

AgentFarm.Space erstellt und orchestriert konfigurierbare Multi-Agent-Teams via AutoGen 0.4. Teams führen kollaborative Tasks aus (Code-Generierung, Research, Dokumentation) mit Echtzeit-Progress-Broadcast an Electron. Der Space bietet zusätzlich einen MCP-Server für Claude-Integration und einen Hybrid-Pipeline-Orchestrator für Multi-Space-Kollaboration via Minibook.

## Aktueller Implementierungsstand

> **Hinweis (2026-09-22):** Die Python-Backend-Schicht (Backend-Agent, Tool
> Functions, TeamRunner, MCP Server, Hybrid Pipeline, OpenClaw Bridge — alles
> unter `python/spaces/autogen/`) wurde am 2026-06-16 komplett aus dem Repo
> entfernt (Commit `ec98a0c6`, 193 Dateien / 52.905 Zeilen allein unter
> `spaces/autogen/`, darunter genau die unten genannten Dateien inkl.
> `agentfarm_tools.py` mit den genannten 510 Zeilen). `spaces/agentfarm/`
> (die heutige, andere Verzeichnisebene) enthält nur noch ein leeres
> `agentfarm/__init__.py`-Paket und `runtime-manifest-v1.json`, die selbst
> `"runtime_status": "blocked"`, `"enabled": false`,
> `"blocker": "missing_persistent_agentfarm_runtime"` deklariert. Der
> lazy-Import `AgentFarmBackendAgent` in
> `python/swarm/backend_agents/__init__.py` zeigt auf einen nicht mehr
> vorhandenen Pfad. Die Electron-/Dashboard-Zeilen unten sind davon nicht
> betroffen — diese Dateien existieren weiterhin.

| Komponente | Status | Ort |
|-----------|--------|-----|
| Backend-Agent | **Entfernt (2026-06-16)** | `python/spaces/autogen/agents/agentfarm_agent.py` |
| Tool Functions (8 Tools) | **Entfernt (2026-06-16)** | `python/spaces/autogen/tools/agentfarm_tools.py` (510 Zeilen) |
| TeamRunner (async AutoGen) | **Entfernt (2026-06-16)** | `python/spaces/autogen/runner/team_runner.py` |
| MCP Server | **Entfernt (2026-06-16)** | `python/spaces/autogen/mcp_server/vibemind_mcp.py` |
| Hybrid Pipeline | **Entfernt (2026-06-16)** | `python/spaces/autogen/orchestrator/hybrid_pipeline.py` |
| OpenClaw Bridge | **Entfernt (2026-06-16)** | `python/spaces/autogen/orchestrator/openclaw_bridge.py` |
| Electron UI-Shell | Implementiert | `electron-app/agentfarm-manager.js`, `electron-app/agentfarm/` |
| Next.js Dashboard (AgentFarm-UI) | Implementiert | `electron-app/agentfarm-ui/` |
| ClawPort Dashboard-Tab | Implementiert | `electron-app/dashboard/src/features/AgentFarm.tsx` |

### Backend Agent (entfernt 2026-06-16, Commit `ec98a0c6`)

**Datei (nicht mehr vorhanden):** `python/spaces/autogen/agents/agentfarm_agent.py`
**Klasse:** `AgentFarmBackendAgent`
**Stream:** `events:tasks:agentfarm`

### Events (8)

| Event | Tool | Beschreibung |
|-------|------|-------------|
| `agentfarm.create_team` | `create_team` | Team aus Template oder Config erstellen |
| `agentfarm.run` | `run_team` | Async Team-Task-Ausführung starten |
| `agentfarm.status` | `get_farm_status` | Übersicht aller Teams und aktiver Runs |
| `agentfarm.list_teams` | `list_teams` | Registrierte Teams auflisten |
| `agentfarm.stop` | `stop_run` | Laufendes Team abbrechen |
| `agentfarm.results` | `get_run_results` | Ergebnisse von abgeschlossenem/laufendem Team |
| `agentfarm.list_templates` | `list_templates` | Template-Configs aus Submodule scannen |
| `agentfarm.collaborate` | `start_collaboration` | Multi-Space-Kollaboration via Minibook |

### Parameter Mapping (Deutsch → Englisch)

| Event | Mapping |
|-------|---------|
| `agentfarm.create_team` | vorlage/template → template_id, name → team_name |
| `agentfarm.run` | aufgabe/beschreibung/text → task, team → team_id |
| `agentfarm.stop` | run → run_id |
| `agentfarm.results` | run → run_id |

### ClawPort Dashboard Integration

AgentFarm hat einen eigenen Tab im ClawPort React Dashboard mit zwei Sub-Tabs:

| Sub-Tab | Komponente | Zweck |
|---------|-----------|-------|
| AutoGen | `ProjectProgress.tsx` | Code-Generierungs-Fortschritt aus Coding Engine (6 Stages: Analyzing → Complete) |
| N8n | `WorkflowBuilder.tsx` | N8n-Workflow-Management (Status, Liste, Aktivierung/Deaktivierung) |

## Wo AutoGen auch genutzt wird

AutoGen wird zusätzlich in anderen Spaces eingesetzt:
- **Coding.Space**: `python/spaces/coding/Coding_engine/` — dieser Pfad existiert nicht mehr; `spaces/coding/` wurde am 2026-06-16 komplett entfernt (Commit `ec98a0c6`, 3056 Dateien / 923.402 Zeilen)
- **SWE Design**: `python/spaces/shuttles/swe_desgine/external/arch_team/` — AutoGen-basierte Architektur-Validierung (geprüft, existiert)
- **Ideas.Space**: `python/spaces/ideas/tools/autogen_research.py` — dieser Pfad existiert nicht mehr; `spaces/ideas/` enthält aktuell nur noch `mcp_server.py` und `tests/`
- **N8n.Space**: `python/spaces/n8n/society/` — dieser Pfad existiert nicht mehr; `spaces/n8n/` wurde ebenfalls am 2026-06-16 im selben Commit entfernt

## Subsysteme

> Alle vier folgenden Pfade unter `python/spaces/autogen/` sind Teil der am
> 2026-06-16 entfernten Implementierung (siehe Hinweis oben, Commit
> `ec98a0c6`) und existieren im aktuellen Code nicht mehr.

### TeamRunner (`python/spaces/autogen/runner/team_runner.py`)
Non-blocking async Ausführung von AutoGen 0.4 Teams:
- `start_run(team_id, config, task)` — Background-Task, returned `run_id` sofort
- `autogen_core.CancellationToken` für Abbruch
- Iteriert `team.run_stream()` und sammelt Messages
- Real-time Broadcast an Electron
- Auto-Pruning: max 50 abgeschlossene Runs

### MCP Server (`python/spaces/autogen/mcp_server/`)
- `vibemind_mcp.py` — MCP-Server für Claude-Integration
- `web_fetch_pipe.py` — Web-Fetch-Utility

### Hybrid Pipeline (`python/spaces/autogen/orchestrator/`)
- `hybrid_pipeline.py` — Multi-Space-Kollaboration (AutoGen + Minibook)
- `openclaw_bridge.py` — OpenClaw-Integration
- `pipeline_enrichment.py` — Kontext-Anreicherung
- `step_registry.py` — Dynamische Step-Registrierung

### Config (`python/spaces/autogen/config/`)
Agent-Templates und Pipeline-Konfigurationen in JSON/YAML.

## Geplante Features

- Agent-Marketplace für validierte Agent-Templates
- Monitoring und Performance-Analytics
- Cost-Optimization-Layer für Agent-Execution
- Docker Toolkit für isolierte Agent-Environments

## Ecosystem-Fit

AgentFarm.Space gibt Usern die Werkzeuge, um schnell eigene Agents zu erstellen. Das Konzept wird in Rowboat.Space (Business-Kontext) oder Ideas.Space (kreative Ideation) entworfen und dann in AgentFarm zur Ausführung gebracht. Es arbeitet eng mit Desktop.Space (User-Activity-Trigger) und Coding.Space (Custom-Implementierungen) zusammen.

> Detaillierte technische Dokumentation: [docs/python/spaces/autogen/README.md](python/spaces/autogen/README.md)
