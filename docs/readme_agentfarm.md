# AgentFarm.Space

**Konzept-Framework für schnelles Agent-Building mit AutoGen und N8n — Design erfolgt in Rowboat.Space oder Ideas.Space.**

## Overview

AgentFarm.Space ist darauf ausgelegt, Usern zu ermöglichen, schnell eigene Agents in AutoGen oder N8n zu bauen. Es handelt sich um ein Konzept-Framework — die eigentliche Agent-Konzeption und das Design finden in Rowboat.Space (Business-Daten & Kontext) oder Ideas.Space (kreative Ideation) statt. AgentFarm stellt die Ausführungsumgebung und Orchestrierungsschicht bereit. Aktuell existiert eine Electron-UI-Shell; die zugrunde liegenden Technologien (Microsoft AutoGen, N8n) sind in anderen Spaces implementiert.

## Aktueller Implementierungsstand

| Komponente | Status | Ort |
|-----------|--------|-----|
| Electron UI-Shell | Implementiert | `electron-app/agentfarm-manager.js`, `electron-app/agentfarm/` |
| React Dashboard | Implementiert | `electron-app/agentfarm/dist/index.html` |
| ClawPort Dashboard-Tab | Implementiert | `electron-app/dashboard/src/features/AgentFarm.tsx` |
| ProjectProgress | Implementiert | `electron-app/dashboard/src/features/ProjectProgress.tsx` |
| WorkflowBuilder | Implementiert | `electron-app/dashboard/src/features/WorkflowBuilder.tsx` |
| Backend-Agent | **Nicht vorhanden** | Kein Eintrag in `python/swarm/backend_agents/__init__.py` |
| Python Space-Verzeichnis | **Nicht vorhanden** | `python/spaces/autogen/` existiert aber ist leer |

### ClawPort Dashboard Integration

AgentFarm hat einen eigenen Tab im ClawPort React Dashboard mit zwei Sub-Tabs:

| Sub-Tab | Komponente | Zweck |
|---------|-----------|-------|
| AutoGen | `ProjectProgress.tsx` | Code-Generierungs-Fortschritt aus Coding Engine (6 Stages: Analyzing → Complete) |
| N8n | `WorkflowBuilder.tsx` | N8n-Workflow-Management (Status, Liste, Aktivierung/Deaktivierung) |

## Wo die Technologien tatsächlich leben

### Microsoft AutoGen
AutoGen wird in mehreren anderen Spaces genutzt, nicht zentral in AgentFarm:
- **Coding.Space**: `python/spaces/coding/Coding_engine/` — Extensive AutoGen-Nutzung für Code-Generierung
- **SWE Design**: `python/spaces/shuttles/swe_desgine/external/arch_team/` — AutoGen-basierte Architektur-Validierung
- **Ideas.Space**: `python/spaces/ideas/tools/autogen_research.py` — AutoGen für Research-Tasks
- **N8n.Space**: `python/spaces/n8n/society/` — AutoGen-Society für Workflow-Generierung

### N8n Workflow-Generierung
N8n ist als eigenständiger Space mit 8 Events implementiert:
- Backend-Agent: `python/spaces/n8n/agents/n8n_agent.py` (8 Events: generate, list, status, activate, deactivate, delete, execute, describe)
- 40+ Workflow-Templates in `python/spaces/n8n/templates/`
- AutoGen-Society in `python/spaces/n8n/society/` mit 6 spezialisierten Agents:
  - `workflow_architect` — Workflow-Design
  - `n8n_docs_expert` — N8n-API-Wissen
  - `workflow_builder` — JSON-Generierung
  - `workflow_tester` — Validierung
  - `ux_agent` — User-Experience
  - `workflow_reviewer` — Qualitätssicherung
- Orchestriert via AutoGen 0.4 `SocietyOfMindAgent` mit `SelectorGroupChat`

## Geplante Features

- Zentralisierte Agent-Orchestrierung über alle Spaces hinweg
- Docker Toolkit für isolierte Agent-Environments
- MCP-Integration für standardisierte Tool-Konnektivität
- Custom-Tooling-Framework für domänenspezifische Capabilities
- Agent-Marketplace für validierte Agent-Templates
- Monitoring und Performance-Analytics

## Roadmap

- Dedizierter Backend-Agent implementieren
- AutoGen-Nutzung aus einzelnen Spaces in AgentFarm zentralisieren
- Custom-Tooling-Framework vervollständigen (Q2 2026)
- Cost-Optimization-Layer für Agent-Execution
- Multi-Agent-Orchestrierung für sequentielle und parallele Tasks

## Ecosystem-Fit

AgentFarm.Space gibt Usern die Werkzeuge, um schnell eigene Agents zu erstellen. Das Konzept wird in Rowboat.Space (Business-Kontext) oder Ideas.Space (kreative Ideation) entworfen und dann in AgentFarm zur Ausführung gebracht. Es arbeitet eng mit Desktop.Space (User-Activity-Trigger) und Coding.Space (Custom-Implementierungen) zusammen.
