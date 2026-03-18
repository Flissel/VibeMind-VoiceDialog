# Spaces — Bereiche im Multiverse

VibeMind organisiert Funktionalitaet in modulare **Spaces**. Jeder Space hat eigene Agents, Tools, Workers und Broadcast-Agents.

## Verzeichnisse vs. Enum

**Tatsaechliche Space-Verzeichnisse** in `python/spaces/`:

| # | Space | Verzeichnis | Status |
|---|-------|------------|--------|
| 1 | Ideas Universe | `ideas/` | Produktionsreif |
| 2 | Coding Workshop | `coding/` | Produktionsreif |
| 3 | Desktop Space | `desktop/` | Produktionsreif |
| 4 | Rowboat | `rowboat/` | Aktiv |
| 5 | Research | `research/` | Produktionsreif |
| 6 | Minibook | `minibook/` | Aktiv |
| 7 | Shuttles/SWE Design | `shuttles/` | Integration laeuft |
| 8 | Roarboot (Submodul) | `roarboot/` | Nur Git-Submodul-Container |

**SpaceType Enum** (`python/spaces/__init__.py`) definiert zusaetzlich:

| SpaceType | Verzeichnis | Implementierung |
|-----------|------------|-----------------|
| `OPENCLAW` | Kein Verzeichnis | Nur Enum + 3D-Position, keine Agents/Tools |
| `TRANSFORMER` | Kein Verzeichnis | Nur Enum + 3D-Position, keine Agents/Tools |

---

## Uebersicht (implementierte Spaces)

| # | Space | Pfad | Farbe | Event-Prefix | Visualisierung |
|---|-------|------|-------|-------------|----------------|
| 1 | Ideas Universe | `python/spaces/ideas/` | Blau (0x4488ff) | `bubble.*`, `idea.*` | bubbles |
| 2 | Coding Workshop | `python/spaces/coding/` | Gruen (0x44ff88) | `code.*` | nebula |
| 3 | Desktop Space | `python/spaces/desktop/` | Orange (0xff8844) | `desktop.*`, `messaging.*` | light_planet |
| 4 | Rowboat | `python/spaces/rowboat/` | Gold (0xffaa00) | `roarboot.*` | nebula |
| 5 | Research | `python/spaces/research/` | — | `research.*` | — |
| 6 | Minibook | `python/spaces/minibook/` | Hellblau (0x00aaff) | `minibook.*` | nebula |
| 7 | SWE Design Factory | `python/spaces/shuttles/` | Orange-Rot (0xff6633) | `shuttle.*` | factory |

---

## 1. IDEAS UNIVERSE

**Rachels Einstiegspunkt** — Sprachgesteuerte Ideen- und Bubble-Verwaltung

```
python/spaces/ideas/
+-- agents/         rachel_agent, bubbles_agent, ideas_agent
+-- tools/          bubble_tools, idea_tools, exploration_tools
+-- explorer/       AI-Scientist Tree Search (semantische Verbindungen)
+-- adapted/        Legacy-Wrapper
+-- broadcast/      Fan-out Broadcast Agents
+-- swarm/          Lokale Swarm Agents
+-- workers/        Hintergrund-Workers
+-- sub_agents/     Spezialisierte Sub-Agents
+-- README.md       Dokumentation (10KB)
```

### Agent: IdeasBackendAgent + BubblesBackendAgent

### Event Types

**Bubble Events:**

| Event | Deutsch | Aktion |
|-------|---------|--------|
| `bubble.list` | "Zeig mir meine Bubbles" | Alle Spaces auflisten |
| `bubble.create` | "Erstelle Bubble Marketing" | Neuen Space erstellen |
| `bubble.enter` | "Geh in Marketing" | Space betreten |
| `bubble.find` | "Such nach Bubble X" | Suchen + betreten |
| `bubble.exit` | "Zurueck" | Space verlassen |
| `bubble.delete` | "Loesche Bubble X" | Space loeschen |
| `bubble.stats` | "Zeig Statistiken" | Space-Statistiken |

**Idea Events:**

| Event | Deutsch | Aktion |
|-------|---------|--------|
| `idea.create` | "Notiere: API Design" | Idee erstellen |
| `idea.list` | "Zeig alle Ideen" | Ideen auflisten |
| `idea.find` | "Finde Idee X" | Idee suchen |
| `idea.update` | "Aendere Idee X" | Idee aktualisieren |
| `idea.delete` | "Loesche Idee X" | Idee entfernen |
| `idea.connect` | "Verbinde X mit Y" | Zwei Ideen verlinken |
| `idea.auto_link` | "Verlinke die Ideen sinnvoll" | KI-basierte Verlinkung |
| `idea.expand` | "Erweitere die Ideen" | KI-generierte verwandte Ideen |
| `idea.format` | "Formatiere in Aktionslisten" | Format-Konvertierung |
| `idea.summarize` | "Fasse zusammen" | LLM-Zusammenfassung |
| `idea.explore.start` | "Finde tiefere Verbindungen" | Tree Search Exploration |

### Tools (38+ Funktionen)

`create_bubble`, `enter_bubble`, `list_bubbles`, `exit_bubble`, `delete_bubble`, `find_bubble`, `create_idea_tool`, `list_ideas`, `connect_ideas`, `auto_link_ideas`, `expand_ideas`, `format_idea_content`, `summarize_bubble`, etc.

### Status: Produktionsreif

---

## 2. CODING WORKSHOP

**Autonome Code-Generierung** via Society of Mind Orchestration

```
python/spaces/coding/
+-- Coding_engine/  Git Submodul (externes Projekt, 40+ Agents)
+-- agents/         coding_agent, coding_swarm_agent
+-- engine/         Bridge zum externen Coding_engine
+-- tools/          coding_tools, voice_coding_tools, adapted_coding_tools
+-- broadcast/      Broadcasting Agents
+-- sub_agents/     Spezialisierte Agents
+-- workers/        Hintergrund-Workers
+-- README.md       Dokumentation (6KB)
```

### Agent: CodingBackendAgent

### Event Types

| Event | Deutsch | Aktion |
|-------|---------|--------|
| `code.generate` | "Erstelle eine App fuer X" | Code-Generierung starten |
| `code.status` | "Wie ist der Code-Status?" | Fortschritt pruefen |
| `code.cancel` | "Stopp die Generierung" | Abbrechen |
| `code.list` | "Zeig meine Projekte" | Projekte auflisten |
| `code.preview.start` | "Zeig Preview" | VNC-Stream starten |
| `code.preview.stop` | "Stopp Preview" | VNC-Stream stoppen |
| `idea.to_project` | "Mach daraus ein Projekt" | Idee zu Code-Projekt |

### Architektur

- **Hybrid 5-Phase Pipeline:** Architecture Analysis --> Parallel Code Gen --> Merge --> Verification --> Deployment
- **Convergence Modes:** `--autonomous`, `--strict`, `--relaxed`, `--fast`
- **Docker Sandbox** fuer isolierte Code-Ausfuehrung
- **VNC Streaming** fuer Live-Preview
- **Fungus Memory** (RAG via Qdrant) fuer Code-Kontext

### Externer Engine

`Coding_engine/` ist ein Git-Submodul mit 40+ spezialisierten AutoGen Agents.

### Status: Produktionsreif, Submodul aktiv

---

## 3. DESKTOP SPACE

**Desktop-Automatisierung** und System-Kontrolle

```
python/spaces/desktop/
+-- Automation_ui/  Git Submodul (Custom Automation Framework)
+-- messaging/      NEU: WhatsApp/Telegram Pipeline
|   +-- messaging_pipeline.py    Voice --> Clawdbot (12KB)
|   +-- incoming_handler.py      Webhook --> Voice (9KB)
|   +-- relevance_filter.py      Intelligente Filterung (7KB)
+-- agents/         desktop_agent
+-- adapted/        Legacy-Wrapper
+-- broadcast/      Broadcasting Agents
+-- tools/          desktop_tools, moire_tools, quickaction_tools, task_tools
+-- sub_agents/     Spezialisierte Agents
+-- workers/        Hintergrund-Workers
+-- automation_ui_client.py  Bridge zu Automation_ui
```

### Agent: DesktopBackendAgent

### Event Types

| Event | Deutsch | Aktion |
|-------|---------|--------|
| `desktop.open_app` | "Oeffne Chrome" | App starten |
| `desktop.click` | "Klick auf OK" | UI-Interaktion |
| `desktop.type` | "Tippe Hallo" | Texteingabe |
| `desktop.press_key` | "Druecke Enter" | Tastendruck |
| `desktop.screenshot` | "Screenshot" | Bildschirmfoto |
| `desktop.scroll` | "Scroll runter" | Scrollen |
| `desktop.task` | "Erstelle Aufgabe X" | Task Management |

### Messaging Pipeline (NEU)

```
Ausgehend:
  "Schreib meiner Mutter dass ich spaeter komme"
      --> messaging.send
      --> Rowboat: query_knowledge("Mutter") --> Kontakt-Kontext
      --> ContactRegistry: "Mutter" --> Telefonnummer
      --> Clawdbot: send_whatsapp(nummer, nachricht)
      --> Voice: "Nachricht gesendet"

Eingehend:
  WhatsApp/Telegram --> Clawdbot Webhook
      --> IncomingMessageHandler.on_message()
      --> RelevanceFilter (Ollama): Relevant genug fuer Unterbrechung?
      --> Wenn ja: Voice-Injection + Rowboat-Speicherung
      --> Wenn nein: Nur Logging
```

| Event | Deutsch | Aktion |
|-------|---------|--------|
| `messaging.send` | "Schreib meiner Mutter..." | Nachricht senden |
| `messaging.read` | "Gibt es neue Nachrichten?" | Nachrichten pruefen |
| `web.search` | "Such im Web nach X" | Einfache Web-Suche |

### Status: Produktionsreif, Messaging in Entwicklung

---

## 4. ROWBOAT

**Wissensmanagement** via Rowboat Knowledge Graph

> **Hinweis:** Der Rowboat Space liegt in `python/spaces/rowboat/` (nicht `roarboot/`).
> Das Verzeichnis `python/spaces/roarboot/` enthaelt nur das Git-Submodul fuer das Rowboat-Repository.

```
python/spaces/rowboat/
+-- rowboat/        Git Submodul (Rowboat Repository, innerhalb von rowboat/)
+-- config.py       RoarbootConfig (Rowboat API, Docker, Feature Flags)
+-- agents/         roarboot_agent.py
+-- broadcast/      roarboot_broadcast_agent
+-- tools/          roarboot_client.py, roarboot_tools.py, docker_tools.py
+-- workers/        HealthCheckWorker
+-- sub_agents/     (reserviert)
+-- README.md       Dokumentation (4KB)
```

Zusaetzlich: `python/spaces/roarboot/rowboat/` — Separater Git-Submodul-Container.

### Agent: RoarbootBackendAgent

### Konfiguration (RoarbootConfig)

| Einstellung | Default | ENV-Variable |
|------------|---------|-------------|
| Rowboat URL | `http://localhost:3000` | `ROWBOAT_URL` |
| API Key | — | `ROWBOAT_API_KEY` |
| Project ID | — | `ROWBOAT_PROJECT_ID` |
| Docker Compose | `rowboat/docker-compose.yml` | `ROWBOAT_DOCKER_COMPOSE` |
| Auto-Start | false | `ROWBOAT_AUTO_START` |
| Enabled | true | `ROWBOAT_ENABLED` |
| Event Stream | `events:tasks:roarboot` (optional) | `REDIS_STREAM_ROARBOOT` |

### Event Types

| Event | Deutsch | Aktion |
|-------|---------|--------|
| `roarboot.search` | "Was weiss ich ueber X?" | Knowledge Graph abfragen |
| `roarboot.query` | "Finde Infos zu Y" | Detaillierte Abfrage |
| `roarboot.email_draft` | "Schreibe Email an X" | Email-Entwurf mit Kontext |
| `roarboot.meeting_brief` | "Bereite mein Meeting vor" | Meeting-Vorbereitung |
| `roarboot.generate_deck` | "Erstelle Praesentation" | Deck-Generierung |
| `roarboot.voice_note` | "Sprachnotiz verarbeiten" | Voice Note --> Knowledge Graph |
| `roarboot.docker.start` | "Starte Roarboot" | Docker Stack starten |
| `roarboot.docker.stop` | "Stoppe Roarboot" | Docker Stack stoppen |
| `roarboot.docker.status` | "Roarboot Status?" | Docker Status pruefen |

### Docker Stack

- Rowboat: `localhost:3000`
- MongoDB: `localhost:27017`
- Redis: `localhost:6379`
- Qdrant: `localhost:6333`

### Electron Integration

Rowboat wird als BrowserView (nicht iframe) in Electron eingebettet. Services sind als esbuild CJS (`rowboat-services.cjs`) gebuendelt.

### Status: Aktiv, Electron-Integration in Arbeit

---

## 5. RESEARCH (ZeroClaw)

**Web-Recherche, Scraping, Zusammenfassung** via ZeroClaw Gateway

```
python/spaces/research/
+-- agents/     zeroclaw_research_agent
+-- tools/      research_tools
+-- __init__.py
```

### Agent: ZeroClawResearchAgent

### Event Types

| Event | Deutsch | Aktion |
|-------|---------|--------|
| `research.web` | "Recherchiere ueber X" | Tiefe Web-Recherche |
| `research.scrape` | "Scrape die Seite URL" | Inhalte extrahieren |
| `research.summarize` | "Fasse die Seite zusammen" | Web-Seite zusammenfassen |
| `research.to_idea` | "Recherchiere und speichere" | Recherche --> Idee |
| `research.to_rowboat` | "Recherchiere und archiviere" | Recherche --> Knowledge Graph |

### Abgrenzung

- `research.web` = Tiefe Web-Recherche (ZeroClaw, Rust Subprocess)
- `roarboot.search` = Internes Wissen (Rowboat Knowledge Graph)
- `web.search` = Einfache Web-Suche (Desktop Agent)

### Status: Produktionsreif, optional (USE_ZEROCLAW=true)

---

## 6. MINIBOOK

**Inter-Space Collaboration und zentraler Message Bus** — Multi-Agent Diskussionen und Hub-Routing

```
python/spaces/minibook/
+-- config.py              MinibookConfig
+-- minibook_hub.py        MinibookHub (zentraler Dispatch fuer alle Intents)
+-- rachel_interface.py    Status-Updates fuer Rachel
+-- result_aggregator.py   Ergebnis-Aggregation (sync + async)
+-- agents/                MinibookBackendAgent, get_minibook_agent
+-- broadcast/             Broadcasting Agents
+-- enrichment/            EnrichmentPipeline (classify, route, enrich)
+-- tools/                 MinibookClient, collaboration_tools, minibook_tools
+-- workers/               DiscussionPollerWorker, SpaceMinibookResponder
+-- __init__.py            Exports (2KB)
+-- README.md
```

### Zwei Betriebsmodi

Minibook hat zwei unabhaengige Feature-Flags mit unterschiedlicher Reichweite:

| Flag | ENV-Variable | Wirkung |
|------|-------------|---------|
| **Collaboration Mode** | `MINIBOOK_ENABLED=true` | Aktiviert das Minibook-Kollaborationssystem. Space-Agents registrieren sich, reagieren auf @mentions, koennen Diskussionen fuehren. Nur `minibook.*`-Events werden verarbeitet. |
| **Hub Mode (Primaer)** | `USE_MINIBOOK_HUB=true` | **ALLE Intents** — nicht nur `minibook.*` — werden ueber den MinibookHub geroutet. Minibook wird zum zentralen Message Bus fuer die gesamte Intent-Verarbeitung. |

### MinibookHub — Zentraler Message Bus

Wenn `USE_MINIBOOK_HUB=true`, fliesst jeder User-Intent durch den MinibookHub:

```
process_intent()
    --> MinibookHub.dispatch()
        --> EnrichmentPipeline (klassifizieren + routen + anreichern)
        --> Minibook POST (@mentions fuer relevante Agents)
        --> Single-Space: sync-wait auf Antwort (<=10s)
        --> Multi-Space: async-poll via ResultAggregator
        --> Fallback auf _process_sync() bei Timeout/Fehler
```

**Architektur-Prinzip:** Minibook ist der **Message Bus**, nicht die Execution Engine. Die SpaceMinibookResponder in den einzelnen Spaces fuehren die Tools aus. Minibook speichert die Task/Result-Paare.

**Auch Single-Space-Aufgaben** (z.B. `bubble.create`) laufen im Hub-Modus durch Minibook. Das stellt konsistente Auditierbarkeit und Nachvollziehbarkeit aller Aktionen sicher — jeder Intent wird als Minibook-Task protokolliert.

### Agent: MinibookBackendAgent

### Event Types (explizite Kollaboration)

Die folgenden Events sind fuer **explizite** Multi-Space-Kollaboration. Im Hub-Modus verarbeitet MinibookHub zusaetzlich **alle** anderen Event-Typen (`bubble.*`, `idea.*`, `code.*`, etc.).

| Event | Deutsch | Aktion |
|-------|---------|--------|
| `minibook.collaborate` | "Recherchiere X und erstelle Idee" | Multi-Space Aufgabe |
| `minibook.discuss` | "Starte Diskussion ueber X" | Diskussion starten |
| `minibook.poll` | "Neue Antworten?" | Ergebnisse pruefen |
| `minibook.results` | "Zeig Diskussionsergebnisse" | Ergebnisse abrufen |

### Architektur (Collaboration Mode)

```
Multi-Space Aufgabe
    --> Minibook Discussion erstellen
    --> @mentions an beteiligte Spaces
    --> Space-Agents antworten asynchron
    --> Ergebnisse aggregieren
    --> Nutzer informieren
```

### Konfiguration

| Einstellung | Default | ENV-Variable |
|------------|---------|-------------|
| Minibook URL | `http://localhost:3480` | `MINIBOOK_URL` |
| Frontend URL | `http://localhost:3481` | `MINIBOOK_FRONTEND_URL` |
| Collaboration aktiviert | false | `MINIBOOK_ENABLED` |
| Hub-Modus (alle Intents) | false | `USE_MINIBOOK_HUB` |
| Hub Sync-Timeout | 10s | `MINIBOOK_HUB_SYNC_TIMEOUT` |

### Status: Aktiv, optional (MINIBOOK_ENABLED=true / USE_MINIBOOK_HUB=true)

---

## 7. SWE DESIGN FACTORY (Shuttles)

**Requirements Pipeline** und Software Engineering Design Factory

```
python/spaces/shuttles/
+-- swe_desgine/    Git Submodul (SWE Design Factory)
```

### Beschreibung

Shuttles landen hier fuer vollstaendige Spezifikationsgenerierung. Die SWE Design Factory nimmt Ideen/Requirements entgegen und generiert vollstaendige technische Spezifikationen ueber ein ArchitectTeam API (`localhost:8087`).

### Shuttle-Pipeline

```
Idee/Requirement
    --> Shuttle erstellen (Requirements definieren)
    --> SWE Design Factory
    --> ArchitectTeam API
    --> Technische Spezifikation
    --> Coding Space (optional: Code-Generierung)
```

### Status: Submodul vorhanden, Integration in Arbeit

---

## Nur in Enum definiert (keine eigenen Verzeichnisse)

### OpenClaw Desktop

OpenClaw ist kein eigener Space, sondern Teil von **Automation_ui** im Desktop Space. Die OpenClaw-Logik (AutoGen Desktop Swarm mit Claude CLI) lebt in `python/spaces/desktop/Automation_ui/`.

| Eigenschaft | Wert |
|------------|------|
| SpaceType | `OPENCLAW` |
| Name | OpenClaw Desktop |
| Tatsaechlicher Ort | `python/spaces/desktop/Automation_ui/` |
| Farbe | Rot (0xff4444) |
| Position | (12, 3, -8) |
| Visualisierung | planet |

### Transformer Pipeline

Konzept-Space ohne Implementierung — Bubble-to-Coding Pipeline wird aktuell ueber Shuttles/SWE Design abgebildet.

| Eigenschaft | Wert |
|------------|------|
| SpaceType | `TRANSFORMER` |
| Name | Transformer Pipeline |
| Farbe | Lila (0xaa44ff) |
| Position | (-4, 4, -6) |
| Visualisierung | portal |

---

## Space-Positionen im 3D-Raum

```
                    Transformer (-4, 4, -6)     [nur Enum]
                         |
                         |
OpenClaw (12, 3, -8)     |     Coding (-8, 2, -3)
  [nur Enum]             |        /
                         |       /
Desktop (10, 0, -5)  IDEAS (0, 0, 0)
          /              |       \
         /               |        \
SWE Design (8, 0, 5.5)  |     Rowboat (-12, -2, -10)
                         |
                    Minibook (6, -3, -12)
```

IDEAS ist der zentrale Einstiegspunkt (Entry Point).
