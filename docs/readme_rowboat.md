# Rowboat.Space

**Zentrale Daten-Orchestrierung mit Knowledge-Graph, Content-Generation und Docker-Management.**

## Overview

Rowboat.Space (intern: "Roarboot") ist das Daten-Backbone von Vibemind. Es bietet einheitlichen Zugriff auf Business-Daten, generiert Inhalte (E-Mails, Meeting-Briefs, Decks), verarbeitet Voice-Notes und verwaltet seinen eigenen Docker-Container. Die Datenquelle ist ein Knowledge-Graph im Rowboat-Submodul.

## Backend-Agent: RoarbootBackendAgent (13 Events)

> **Hinweis (2026-09-22):** `agents/roarboot_agent.py` selbst (die
> Event-Dispatcher-Klasse) wurde am 2026-06-16 entfernt (Commit `ec98a0c6`,
> Teil derselben spaces-weiten Bereinigung wie bei Desktop/Coding/AgentFarm/
> Ideas). **Anders als dort ist das hier kein Fähigkeitsverlust:** die neun
> Tool-Funktionen, die die Tabelle unten nennt — `search_knowledge`,
> `query_knowledge`, `draft_email`, `generate_meeting_brief`,
> `generate_deck`, `process_voice_note`, `get_status`, `open_webview`,
> `reset_conversation` — existieren wortgleich und aktuell in
> `spaces/rowboat/tools/roarboot_tools.py` (513 Zeilen); `tools/docker_tools.py`
> (269 Zeilen), `tools/roarboot_client.py` (350 Zeilen) und
> `workers/update_checker.py` existieren ebenfalls weiterhin. Nur die
> Wrapper-Klasse, die Events auf diese Funktionen abbildete, ist weg. Der
> Zugriff läuft jetzt über die Routing-SoT `config/space_agent_registry.yml`
> (Stand 2026-09-08, Space-Key `rowboat`, Agent `rowboat-chat`) plus einen
> neuen `spaces/rowboat/mcp_server.py` (184 Zeilen), der bislang genau ein
> Tool exponiert (`rowboat_status`).

**Datei (Wrapper-Klasse entfernt, Tool-Funktionen bestehen weiter — s. Hinweis oben):** `python/spaces/rowboat/agents/roarboot_agent.py`

### Knowledge-Graph (2 Events)

| Event | Tool-Funktion | Beschreibung |
|-------|--------------|-------------|
| `roarboot.search` | `search_knowledge` | Knowledge-Graph durchsuchen |
| `roarboot.query` | `query_knowledge` | Strukturierte Abfrage |

### Content-Generation (3 Events)

| Event | Tool-Funktion | Beschreibung |
|-------|--------------|-------------|
| `roarboot.email_draft` | `draft_email` | E-Mail-Entwurf generieren |
| `roarboot.meeting_brief` | `generate_meeting_brief` | Meeting-Brief erstellen |
| `roarboot.deck` | `generate_deck` | Präsentation generieren |

### Voice-Notes (1 Event)

| Event | Tool-Funktion |
|-------|--------------|
| `roarboot.voice_note` | `process_voice_note` |

### Docker-Management (4 Events)

| Event | Tool-Funktion | Beschreibung |
|-------|--------------|-------------|
| `roarboot.docker.start` | `start_docker` | Rowboat-Container starten |
| `roarboot.docker.stop` | `stop_docker` | Container stoppen |
| `roarboot.docker.restart` | `restart_docker` | Container neustarten |
| `roarboot.docker.status` | `docker_status` | Container-Status abfragen |

### System (3 Events)

| Event | Tool-Funktion |
|-------|--------------|
| `roarboot.status` | `get_status` |
| `roarboot.open` | `open_webview` |
| `roarboot.reset` | `reset_conversation` |

## Key Components

| Komponente | Datei | Zweck |
|-----------|-------|-------|
| Backend-Agent | `agents/roarboot_agent.py` | 13 Events → 13 Tools |
| Roarboot Tools | `tools/roarboot_tools.py` | Knowledge, Content, Voice-Note Tools |
| Docker Tools | `tools/docker_tools.py` | Container-Management |
| Roarboot Client | `tools/roarboot_client.py` | HTTP-Client zum Rowboat-Service |
| Update Checker | `workers/update_checker.py` | Statusprüfung |
| Rowboat-Code | `rowboat/` (kein Git-Submodul mehr — s. Hinweis unten) | Knowledge-Graph Service |

## Rowboat-Code

> **Hinweis (2026-09-22):** `python/spaces/rowboat/rowboat/` ist kein
> Git-Submodul (mehr): `git ls-tree` zeigt ein Tree-Objekt (Modus `040000`),
> kein Gitlink (`160000`), und `.gitmodules` führt dafür keinen Eintrag. Der
> Code liegt direkt im Repo vendort.

Das eigentliche Knowledge-Graph-System läuft als Docker-Container:

```
python/spaces/rowboat/rowboat/
├── apps/           # Rowboat-Anwendungen
├── docker-compose.yml
├── start.sh
└── README.md
```

(Kein separates `data/` oder `Dockerfile` auf dieser Ebene — stattdessen
`Dockerfile.qdrant` sowie zusätzlich `assets/`, `config/`, `docs/`,
`packages/`, `scripts/`, die das Dokument nicht nennt.)

## Technology Stack

- **Knowledge-Graph**: Rowboat-eigener Graph-Service (Docker)
- **MCP-Integrationen**: Composio, OAuth für Business-Tools
- **Content-Generation**: LLM-gesteuerte E-Mail-, Brief- und Deck-Generierung
- **Docker**: Selbstverwaltetes Container-Lifecycle-Management
- **Event-Streaming**: Redis-Stream `events:tasks:roarboot`

## Current Status

### Implementiert

- Knowledge-Graph Suche und Abfrage (2 Events)
- Content-Generation: E-Mail-Draft, Meeting-Brief, Deck (3 Events)
- Voice-Note Verarbeitung (1 Event)
- Docker-Container-Management: Start, Stop, Restart, Status (4 Events)
- System-Status, WebView, Conversation-Reset (3 Events)
- Rowboat-Submodul mit Docker-Compose
- MCP-Integrations-Framework

### In Entwicklung

- Sync mit Ideas.Space für Workflow-Guidance
- Erweiterung auf 10+ Business-Tool-Integrationen
- Echtzeit-Änderungsbenachrichtigungen

## Roadmap

- Complete Ideas.Space sync for full workflow guidance (Q1-Q2 2026)
- Expand pre-built integrations to 25+ common business tools
- Implement advanced data lineage and dependency tracking
- Add data transformation and ETL pipeline capabilities
- Create data governance and quality assurance framework
- Develop predictive insights based on historical data patterns

## Ecosystem-Fit

Rowboat.Space ist das Bindegewebe von Vibemind. Es speist Business-Daten in The Brain.Space für Analyse und Pattern-Discovery. Ideas.Space nutzt Rowboat-Daten für Business-Kontext. Coding.Space greift auf Business-Daten zu. N8n.Space automatisiert externe Daten-Workflows. Desktop.Space lernt aus Business-Kontext. Die gesamte Plattform wird intelligenter durch Rowboats Business-Verständnis.
