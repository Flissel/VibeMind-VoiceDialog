# Entwicklungsphilosophie

---

## Vision

> **"Dein Universum, deine Stimme."**

VibeMind ist ein Voice-First Multiverse — ein Workspace, in dem natuerliche Sprache der primaere Interaktionskanal ist. Der Nutzer spricht, das System handelt. Keine Menues, keine Formulare, keine Klicks. Stattdessen: Sprache als Interface zu einem 3D-Universum aus Ideen, Code, Wissen und Automatisierung.

---

## Architektur-Prinzipien

### 1. Modulare Spaces

Jeder Space ist eine eigenstaendige Domain mit eigenen Agents, Tools und Workers:

```
python/spaces/{space_name}/
+-- agents/       Domain-spezifische Agents
+-- tools/        Tool-Implementierungen
+-- broadcast/    Fan-out Agents
+-- workers/      Hintergrund-Workers
+-- sub_agents/   Spezialisierte Sub-Agents
```

**Warum:** Unabhaengige Entwicklung, klare Verantwortlichkeiten, einfaches Hinzufuegen neuer Spaces.

### 2. Event-Driven Architecture

```
Intent --> Classification --> Routing --> Execution --> Broadcast
```

Jede Nutzer-Eingabe wird in einen strukturierten Event klassifiziert und an den zustaendigen Agent geroutet. Kein Space kennt die anderen — Kommunikation laeuft ueber den Event Bus.

**Warum:** Lose Kopplung, Skalierbarkeit, einfaches Testing.

### 3. Agent-Based Execution

Alle Domain-Logik steckt in Backend Agents, die dem `BaseBackendAgent` Pattern folgen:

```python
class MyAgent(BaseBackendAgent):
    TOOL_MAP = {"event.type": "tool_function"}
    PARAM_MAPPING = {"event.type": {"from": "to"}}
```

**Warum:** Konsistentes Pattern, einfaches Onboarding, vorhersagbares Verhalten.

### 4. Voice-First Design

Sprache ist das primaere Interface. Jedes Feature muss per Sprachbefehl erreichbar sein. Die Intent-Pipeline ist der Dreh- und Angelpunkt — LLM-Klassifikation statt Regex, natuerliche Sprache statt Kommandos.

**Warum:** Natuerlichere Interaktion, niedrigere Einstiegshuerde, Hands-free Nutzung.

### 5. Graceful Degradation

Optionale Features werden ueber ENV-Flags aktiviert:

```bash
USE_TOOL_ORCHESTRATOR=true    # Multi-Step Execution
USE_TASK_MEMORY=true          # Aufgaben-Tracking
USE_DROPE_RESOLVER=true       # Referenzaufloesung
MINIBOOK_ENABLED=true         # Inter-Space Collaboration
FORCE_SYNC_MODE=true          # Kein Redis erforderlich
```

**Warum:** Minimale Abhaengigkeiten fuer den Start, schrittweise Erweiterung, robust gegen Ausfaelle.

---

## Entwicklungs-Erkenntnisse

### Modular > Monolith

Die Migration von einer monolithischen Struktur (`python/tools/*.py`, `python/swarm/backend_agents/*.py`) zu modularen Spaces (`python/spaces/*/`) war die wichtigste architektonische Entscheidung.

**Vorher:**
```
python/
+-- tools/bubble_tools.py
+-- tools/coding_tools.py
+-- tools/desktop_tools.py
+-- swarm/backend_agents/ideas_agent.py
+-- swarm/backend_agents/coding_agent.py
```

**Nachher:**
```
python/spaces/
+-- ideas/agents/ + ideas/tools/
+-- coding/agents/ + coding/tools/
+-- desktop/agents/ + desktop/tools/
```

**Ergebnis:** Jeder Space kann unabhaengig entwickelt, getestet und deployed werden.

### OpenAI Realtime API als einziger Voice Provider

VibeMind nutzt ausschliesslich die OpenAI Realtime API:

- Speech-to-Speech mit ~300ms Latenz
- Native Function Calling (send_intent)
- Voice Activity Detection (VAD)

**Erkenntnis:** Ein einzelner, leistungsfaehiger Provider ist besser als Dual-Provider-Komplexitaet. ElevenLabs wurde komplett entfernt.

### LLM-Classification > Regex

Frueher: Regex-basiertes Intent-Matching
Jetzt: LLM-basierte Klassifikation mit `CLASSIFIER_PROMPT_TEMPLATE`

**Erkenntnis:** LLM versteht Kontext, Synonyme und Dialekte. Regex scheitert an natuerlicher Sprache. Der Classifier-Prompt ist das zentrale Konfigurationselement.

### Sync-First, Async Optional

`FORCE_SYNC_MODE=true` als Default — kein Redis erforderlich fuer Entwicklung und einfache Setups.

**Erkenntnis:** Redis Streams sind maechtig, aber fuer den Einzelnutzer-Fall Overhead. Sync-Modus reduziert Komplexitaet und Debugging-Aufwand erheblich.

### Space-per-Domain Isolation

Jeder Space hat eigene Git-Submodule (Coding_engine, Automation_ui, Rowboat, SWE Design):

**Erkenntnis:** Grosse externe Projekte als Submodule halten das Hauptrepo schlank. Submodule koennen unabhaengig versioniert werden.

---

## Claude Code als Co-Pilot

VibeMind wird mit Claude Code als AI-assistiertem Entwicklungs-Co-Pilot gebaut:

### CLAUDE.md als Living Document

Die `CLAUDE.md` im Root-Verzeichnis ist das zentrale Wissensdokument fuer Claude Code:
- Vollstaendige Architektur-Uebersicht
- Alle Event Types und Tool-Mappings
- Patterns fuer neue Features
- Common Commands

**Erkenntnis:** Eine gut gepflegte CLAUDE.md macht Claude Code sofort produktiv in jedem Kontext.

### AI-Assisted Patterns

| Pattern | Beschreibung |
|---------|-------------|
| **Explore-First** | Codebase erkunden, bevor Code geschrieben wird |
| **Plan-Then-Execute** | Plan erstellen, genehmigen lassen, dann umsetzen |
| **Parallel Agents** | Mehrere Explore-Agents gleichzeitig fuer breitere Erkundung |
| **Memory Files** | Persistente Notizen fuer Cross-Session Kontext |

---

## Design-Entscheidungen

### Warum Electron?

- Cross-Platform Desktop App mit Web-Technologien
- Three.js fuer 3D-Visualisierung direkt im Renderer
- BrowserView fuer Rowboat Integration (kein iframe)
- Python-Subprocess ueber stdin/stdout (einfach, robust)

### Warum SQLite?

- Kein Server erforderlich
- WAL Mode fuer Concurrent Access
- Schema-Migrations in `database.py`
- Eingebettet in Python (kein Docker)

### Warum AutoGen?

- Multi-Agent Framework mit nativer Swarm-Unterstuetzung
- gRPC und Ollama Extensions
- Society of Mind Pattern fuer Coding Engine

### Warum Redis Streams (optional)?

- Publish/Subscribe fuer asynchrone Event-Verarbeitung
- Consumer Groups fuer Multi-Agent Skalierung
- Stream-basiertes Job-Tracking
- Aber: Sync-Modus als Default fuer Einfachheit

---

## Zukunftsvision

### Kurzfristig
- Messaging Pipeline fertigstellen (Voice --> WhatsApp/Telegram)
- Rowboat BrowserView in Electron finalisieren
- Security Hardening (IPC, Input Validation)

### Mittelfristig
- Multi-User Support (User-isolierte Streams)
- Cloud Deployment (Docker Compose, VNC Reverse Proxy)
- End-to-End Shuttle Pipeline (Idee --> Spezifikation --> Code)

### Langfristig
- **Multiverse-as-a-Service** — Cloud-hosted 3D Workspaces
- **Voice Agents Marketplace** — Custom Agents fuer verschiedene Domains
- **Cross-Multiverse Collaboration** — Mehrere Nutzer in einem Multiverse

---

## Leitprinzipien

1. **Sprache zuerst** — Jedes Feature muss per Stimme erreichbar sein
2. **Modular bleiben** — Neue Domains = Neuer Space, nicht mehr Code im Monolith
3. **Einfach starten** — `FORCE_SYNC_MODE=true`, kein Docker, kein Redis
4. **Schrittweise erweitern** — Features per ENV-Flag aktivieren
5. **Code-Qualitaet** — BaseBackendAgent Pattern, Repository Pattern, konsistente Strukturen
6. **AI-assisted** — Claude Code als Co-Pilot, CLAUDE.md als Living Doc
