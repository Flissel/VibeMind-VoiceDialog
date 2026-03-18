# Rowboat.Space

**Zentrale Daten-Orchestrierung mit Knowledge-Graph, Content-Generation und Docker-Management.**

## Overview

Rowboat.Space (intern: "Roarboot") ist das Daten-Backbone von Vibemind. Es bietet einheitlichen Zugriff auf Business-Daten, generiert Inhalte (E-Mails, Meeting-Briefs, Decks), verarbeitet Voice-Notes und verwaltet seinen eigenen Docker-Container. Die Datenquelle ist ein Knowledge-Graph im Rowboat-Submodul.

## Backend-Agent: RoarbootBackendAgent (13 Events)

**Datei:** `python/spaces/rowboat/agents/roarboot_agent.py`

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
| Rowboat Submodul | `rowboat/` (Git Submodul) | Knowledge-Graph Service |

## Rowboat-Submodul

Das eigentliche Knowledge-Graph-System läuft als Docker-Container:

```
python/spaces/rowboat/rowboat/  (Git Submodul)
├── apps/           # Rowboat-Anwendungen
├── data/           # Daten-Verzeichnis
├── docker-compose.yml
├── Dockerfile
├── start.sh
└── README.md
```

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
