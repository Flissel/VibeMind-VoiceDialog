# Space Communication Architecture

Detaillierte Beschreibung der Kommunikation zwischen allen VibeMind Spaces, deren Datenflüsse und geplanten Erweiterungen.

## Übersicht: 10 Spaces (8 aktiv + 2 geplant)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          RACHEL (Voice Interface)                       │
│                    OpenAI Realtime API · ClawPort Chat                  │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  IntentOrchestrator  │
                    │  ┌───────────────┐  │
                    │  │ MinibookHub?  │  │ ← USE_MINIBOOK_HUB=true
                    │  │ (Multi-Space  │  │   routes to 1+ Spaces
                    │  │  Dispatch)    │  │
                    │  └───────────────┘  │
                    └──────────┬──────────┘
                               │
  ┌────────┬────────┬──────────┼──────────┬──────────┬────────┬────────┐
  ▼        ▼        ▼          ▼          ▼          ▼        ▼        ▼
IDEAS   BUBBLES   CODING   DESKTOP   ROWBOAT   RESEARCH  SCHEDULE  MINIBOOK
  │        │        │         │          │          │        │        │
  │        │        │    ┌────┴────┐     │          │        │     (Hub)
  │        │        │    │OpenClaw │     │          │        │
  │        │        │    │Messaging│     │          │        │
  │        │        │    │Web Ops  │     │          │        │
  │        │        │    └─────────┘     │          │        │
  │        │        │                    │          │        │
  └────────┴────────┴────────────────────┴──────────┴────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Electron UI       │
                    │   3D Multiverse     │
                    │   ClawPort Dashboard│
                    └─────────────────────┘
```

---

## 1. ROWBOAT — Daten-Hub & Knowledge Graph

**Rolle:** Zentrale Datenquelle für Business-Daten, Ideen-Metadaten, E-Mail-Verteiler und Kontext. Liefert Daten an Arch Team, SWE Design und Coding.

**Stream:** `events:tasks:roarboot` · **Prefix:** `roarboot.*`

### Datenquellen

| Datentyp | Quelle | Konversations-Kontext |
|----------|--------|----------------------|
| Business-Daten | MongoDB Knowledge Graph | `"search"` |
| Ideen-Metadaten | Bubbles/Ideas → Rowboat Publish | `"default"` |
| E-Mail-Verteiler | Clawdbot Gateway → Rowboat | `"email"` |
| Meeting-Kontext | Kalender + History | `"meeting"` |
| Voice Notes | Transkriptionen | `"voice_note"` |
| Präsentationen | Deck-Generator | `"deck"` |

### .rowboat Datenverteilung (Zielarchitektur)

```
.rowboat/                          ← Zentrales Daten-Verzeichnis
├── knowledge/                     ← Knowledge Graph Exports
│   ├── people.json               ← Personen & Kontakte
│   ├── projects.json             ← Projekt-Metadaten
│   ├── decisions.json            ← Entscheidungs-Log
│   └── relationships.json        ← Entitäts-Beziehungen
├── email/                         ← E-Mail Kontext & Drafts
│   ├── contacts.json             ← Verteiler
│   ├── drafts/                   ← Generierte Entwürfe
│   └── templates/                ← E-Mail-Templates
├── meetings/                      ← Meeting Briefs
│   ├── upcoming.json
│   └── briefs/                   ← Generierte Vorbereitungen
├── arch/                          ← Architektur-Daten für SWE Design
│   ├── requirements.json         ← Aus Shuttles Pipeline
│   ├── tech_stacks.json          ← Evaluierte Tech-Stacks
│   └── specs/                    ← Generierte Spezifikationen
├── coding/                        ← Daten für Coding Space
│   ├── project_briefs.json       ← Von Rowboat angereicherte Briefs
│   └── context/                  ← Business-Kontext pro Projekt
└── exports/                       ← Deck/Report Exports
    ├── decks/
    └── reports/
```

### Event-Flow: Rowboat als Datenlieferant

```
                    Rowboat (Knowledge Graph)
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
    Arch Team         SWE Design          Coding
   (Shuttles)       (Requirements)     (Code Gen)
         │                 │                 │
         ▼                 ▼                 ▼
  .rowboat/arch/    .rowboat/arch/    .rowboat/coding/
  requirements      specs             project_briefs
```

### IPC Messages (Rowboat)

| Message Type | Richtung | Zweck |
|-------------|----------|-------|
| `roarboot_result` | Python → Electron | Knowledge/Email/Meeting Ergebnis |
| `roarboot_status` | Python → Electron | Verbindungsstatus (connected/disconnected) |
| `roarboot_conversation_update` | Python → Electron | Konversations-ID Tracking |
| `roarboot_open_webview` | Python → Electron | Rowboat UI im BrowserView öffnen |

### Tools (13 Stück)

| Tool | Event | Funktion |
|------|-------|----------|
| `search_knowledge` | `roarboot.search` | Wissen durchsuchen |
| `query_knowledge` | `roarboot.query` | Personen/Projekte abfragen |
| `draft_email` | `roarboot.email_draft` | E-Mail aus Kontext generieren |
| `generate_meeting_brief` | `roarboot.meeting_brief` | Meeting-Vorbereitung |
| `generate_deck` | `roarboot.deck` | Präsentation generieren |
| `process_voice_note` | `roarboot.voice_note` | Voice Note verarbeiten |
| `get_status` | `roarboot.status` | API-Status prüfen |
| `open_webview` | `roarboot.open` | Rowboat UI öffnen |
| `reset_conversation` | `roarboot.reset` | Kontext zurücksetzen |
| `start_docker` | `roarboot.docker.start` | Docker-Stack starten |
| `stop_docker` | `roarboot.docker.stop` | Docker-Stack stoppen |
| `restart_docker` | `roarboot.docker.restart` | Docker-Stack neustarten |
| `docker_status` | `roarboot.docker.status` | Container-Status |

---

## 2. DESKTOP + OPENCLAW — Desktop-Automation

**Rolle:** Desktop-Automatisierung, Messaging (WhatsApp/Telegram), Web-Operationen. OpenClaw ist die Clawdbot Messaging-Bridge.

**Stream:** `events:tasks:desktop` · **Prefixes:** `desktop.*`, `messaging.*`, `web.*`, `openclaw.*`

### Architektur

```
User Voice/Chat
       │
       ▼
IntentClassifier
       │
  ┌────┼────────────────┬──────────────┐
  ▼    ▼                ▼              ▼
desktop.*          messaging.*       web.*          openclaw.*
  │                    │              │                │
  ▼                    ▼              ▼                ▼
DesktopAgent ←── Alle 4 Prefixes auf EINEM Stream ──►
       │
  ┌────┼────────────────┐
  ▼                     ▼
AutomationUIClient   Lokale Tools
(localhost:8007)     (pyautogui)
  │                     │
  ├─ /api/llm/intent   ├─ open_app()
  ├─ /api/automation/* ├─ task management
  └─ /api/clawdbot/*   └─ Fallback clicks/type
       │
       ▼
  ┌────────────────┐
  │ Automation_ui  │ (Externer Service)
  │ ├─ Vision AI   │ ← Screenshot → LLM → Aktionen
  │ ├─ Clawdbot    │ ← WhatsApp/Telegram Bridge
  │ └─ Browser     │ ← Web Automation
  └────────────────┘
```

### Desktop Tools (12 Stück)

| Tool | Event | Funktion |
|------|-------|----------|
| `open_app` | `desktop.open_app` | App öffnen (Chrome, VS Code, etc.) |
| `click_element` | `desktop.click` | UI-Element klicken (Vision) |
| `type_text` | `desktop.type` | Text eingeben |
| `press_key` | `desktop.press_key` | Taste drücken (Enter, Strg+C) |
| `take_screenshot` | `desktop.screenshot` | Screenshot + Beschreibung |
| `scroll_screen` | `desktop.scroll` | Scrollen |
| `execute_desktop_task` | `desktop.task` | Multi-Step Vision Task |
| `create_task_node` | `desktop.task.create` | To-Do erstellen |
| `update_task_status` | `desktop.task.update` | To-Do Status ändern |
| `get_task_list` | `desktop.task.list` | To-Do Liste |
| `moire_scan` | `desktop.moire.scan` | OCR: Alle UI-Elemente listen |
| `moire_find_element` | `desktop.moire.find` | OCR: Element finden |

### Messaging Tools (OpenClaw/Clawdbot)

| Tool | Event | Funktion |
|------|-------|----------|
| `send_whatsapp` | `messaging.whatsapp` | WhatsApp Nachricht senden |
| `send_telegram` | `messaging.telegram` | Telegram Nachricht senden |
| `send_message` | `messaging.send` | Auto-Detect Plattform |
| `web_search` | `web.search` | Web-Suche via Clawdbot |
| `web_fetch` | `web.fetch` | Webseite abrufen + zusammenfassen |
| `get_clawdbot_status` | `openclaw.status` | Gateway-Status |
| `get_notifications` | `openclaw.notifications` | Benachrichtigungen |

---

## 3. IDEAS + BUBBLES — Wissens-Container

**Rolle:** Kernspace. Verwaltet Bubbles (Container) und Ideas (Inhalte) in navigierbarer Hierarchie.

**Streams:** `events:tasks:ideas` + `events:tasks:bubbles` · **Prefixes:** `idea.*`, `bubble.*`

### Datenfluss

```
Bubble (Container)
  └── Ideas (Inhalte)
       ├── Auto-Link (semantische Verbindungen)
       ├── Format (Action List, Kanban, SWOT, ...)
       ├── Explore (AI-Scientist Baumsuche)
       └── → Shuttle Pipeline (bubble.evaluate → SWE Design)
           → Code Generation (idea.to_project → Coding Space)
           → Rowboat Publish (Metadaten → Knowledge Graph)
```

### Cross-Space Verbindungen

| Von | Nach | Event | Beschreibung |
|-----|------|-------|-------------|
| Ideas | Coding | `idea.to_project` | Idee → Code-Projekt konvertieren |
| Ideas | Shuttles | `bubble.evaluate` | Bubble → Requirements Pipeline |
| Ideas | Rowboat | Publish | Metadaten in Knowledge Graph |
| Rowboat | Ideas | `research.to_idea` | Recherche-Ergebnis → Neue Idee |

---

## 4. CODING — Code-Generierung

**Rolle:** Generiert Code-Projekte aus Beschreibungen. Nutzt externes Coding Engine mit VNC Preview.

**Stream:** `events:tasks:coding` · **Prefix:** `code.*`

### Datenfluss

```
Rowboat (.rowboat/coding/)           Ideas (idea.to_project)
       │                                   │
       ▼                                   ▼
    CodingAgent ──────────────────────────────
       │
       ▼
  Coding Engine (extern)
       │
  ┌────┼────┐
  ▼         ▼
VNC       Dashboard
Preview   (Status)
```

### Tools

| Tool | Event | Funktion |
|------|-------|----------|
| `generate_code` | `code.generate` | Code generieren |
| `get_generation_status` | `code.status` | Fortschritt abfragen |
| `start_preview` | `code.preview.start` | VNC Live-Preview starten |
| `stop_preview` | `code.preview.stop` | Preview stoppen |
| `modify_code` | `code.modify` | Code ändern |
| `idea_to_project` | `idea.to_project` | Idee direkt zu Projekt |

---

## 5. RESEARCH (ZeroClaw) — Web-Recherche

**Rolle:** Autonome Web-Recherche mit dem ZeroClaw Engine.

**Stream:** `events:tasks:zeroclaw` · **Prefix:** `research.*`

### Cross-Space

| Von | Nach | Trigger |
|-----|------|---------|
| Research | Ideas | `research.to_idea` — Ergebnis als Idee speichern |
| Research | Rowboat | `research.to_rowboat` — In Knowledge Graph einspeisen |

---

## 6. SCHEDULE — Aufgabenplanung

**Rolle:** APScheduler-basierte Planung — Erinnerungen, Alarme, wiederkehrende Tasks.

**Stream:** `events:tasks:schedule` · **Prefix:** `schedule.*`

---

## 7. MINIBOOK — Inter-Space Hub

**Rolle:** Nachrichtenbus für Multi-Space Koordination. Minibook IST das "Brain" — es orchestriert alle Spaces.

**Stream:** `events:tasks:minibook` · **Prefix:** `minibook.*`

### Dispatch-Logik

```
User Intent
    │
    ▼
MinibookHub.dispatch()
    │
    ├── EnrichmentPipeline
    │   ├── ContextGather (Workspace-Status aller Spaces)
    │   ├── IntentClassifier (Event-Typ bestimmen)
    │   ├── SpaceRouter (LLM: welche(r) Space(s)?)
    │   └── TaskEnricher (Payload pro Space anreichern)
    │
    ├── Single-Space → Sync-Wait (≤10s)
    └── Multi-Space → Async-Poll
```

### Registrierte Agenten (9)

```python
SPACE_AGENT_REGISTRY = {
    "ideas":       vibemind_ideas,        # Ideen & Bubbles
    "coding":      vibemind_coding,       # Code-Generierung
    "desktop":     vibemind_desktop,      # Desktop-Automation
    "research":    vibemind_research,     # Web-Recherche
    "rowboat":     vibemind_rowboat,      # Knowledge Graph
    "openclaw":    vibemind_openclaw,     # Messaging Bridge
    "swe_design":  vibemind_swe_design,   # Requirements Pipeline
    "transformer": vibemind_transformer,  # Format-Transformationen
    "schedule":    vibemind_schedule,     # Aufgabenplanung
}
```

---

## 8. SHUTTLES (SWE Design) — Requirements Pipeline

**Rolle:** Requirements Engineering Pipeline. Nimmt Bubble durch Stages: Mining → Requirements → Validation → Knowledge Graph → Techstack.

**Kein eigener Stream** — Events (`bubble.evaluate`, `bubble.promote`) werden von BubblesAgent verarbeitet.

### Datenfluss über Rowboat

```
Bubble → bubble.evaluate
    │
    ▼
Shuttles Pipeline (6 Stages)
    │
    ├── Stage 1: Requirements Mining
    ├── Stage 2: Validation
    ├── Stage 3: Knowledge Graph Update → Rowboat (.rowboat/arch/)
    ├── Stage 4: Tech-Stack Evaluation
    ├── Stage 5: Specification Generation → .rowboat/arch/specs/
    └── Stage 6: Handoff to Coding
                    │
                    ▼
              Coding Space (code.generate mit Kontext aus .rowboat/)
```

---

## 9. AGENTFARM (🚧 Baustelle — Konzept vorhanden, Implementation ausstehend)

```
  🚧🏗️ UNDER CONSTRUCTION 🏗️🚧
  ┌─────────────────────────────┐
  │  ╔══════════════════════╗   │
  │  ║  A G E N T F A R M  ║   │
  │  ║   Worker Fleet v0    ║   │
  │  ╚══════════════════════╝   │
  │                             │
  │  N Parallel Worker Agents   │
  │  Task Queue + Scoring       │
  │  Quality Gate Pipeline      │
  │  Auto Code-Review & Tests   │
  │                             │
  │  ⚠️ Nicht implementiert     │
  │  Konzept in Planung         │
  └─────────────────────────────┘
```

**Rolle:** Autonome Agent-Flotte die parallel an Tasks arbeitet. Mehrere spezialisierte Agents die eigenständig Bubbles/Ideas bearbeiten, Code reviewen, Tests schreiben.

**Geplante Architektur:**

```
AgentFarm
├── Worker Pool (N parallel Agents)
│   ├── CodeReviewer Agent
│   ├── TestWriter Agent
│   ├── DocWriter Agent
│   └── Refactoring Agent
├── Task Queue (aus Ideas/Coding Space)
├── Result Aggregation
└── Quality Gate (Score-basiert)
```

**Geplante Integration:**
- Empfängt Tasks von Ideas (Bubble mit Sub-Ideas)
- Empfängt Code-Reviews von Coding Space
- Ergebnisse fließen zurück in .rowboat/ für Tracking
- **Stream:** `events:tasks:agentfarm` (geplant)
- **Prefix:** `farm.*` (geplant)

**Status:** 🚧 Nicht im Codebase. Konzept basiert auf der existierenden Minibook Multi-Space Dispatch Logik.

---

## 10. BRAIN (🚧 Baustelle — Submodule vorhanden, Integration ausstehend)

```
  🚧🏗️ UNDER CONSTRUCTION 🏗️🚧
  ┌─────────────────────────────┐
  │  ╔══════════════════════╗   │
  │  ║   T A H L A M U S   ║   │
  │  ║   Brain Space v1.0   ║   │
  │  ╚══════════════════════╝   │
  │                             │
  │  43 Neuroscience-Module     │
  │  5-Ring Radial Attention    │
  │  10 Neuromodulation Bridges │
  │  9-Phase Cognitive Loop     │
  │  Multi-LLM Router           │
  │                             │
  │  ⚠️ Nicht integriert        │
  │  Braucht besondere Zeit     │
  └─────────────────────────────┘
```

**Rolle:** Neurowissenschaftlich inspiriertes Cognitive-AI-System. Zentrales Gedächtnis, Entscheidungsfindung, emotionale Modulation und strategische Planung.

**Submodule:** `python/spaces/brain/the_brain/` ← [Flissel/the_brain](https://github.com/Flissel/the_brain)

**Was the_brain mitbringt (Tahlamus):**

| Komponente | Beschreibung |
|-----------|-------------|
| **43 Neuroscience-Module** | PFC, Amygdala, Hippocampus, Cerebellum, VTA, LC, Raphe, Claustrum, etc. |
| **5-Ring Radial Attention** | Sensory(64D) → Pattern(128D) → Semantic(256D) → Abstract(256D) → Meta(128D) |
| **10 Bridges** | Neuromod, Cortex, Limbic, Sleep/Wake, Motor, Defense, Memory, Integration, Visceral, Social |
| **29 Modulation Hooks** | → 4 Composite-Faktoren (attention_gain, precision_boost, ffn_throughput, threshold_mod) |
| **9-Phase Cognitive Loop** | perceive → appraise → remember → attend → modulate → reason → reflect → learn → consolidate |
| **Multi-LLM Router** | GPT-4o (Kommunikation), DeepSeek R1 (Reasoning), Claude 3.5 (Planning), Gemini Flash (Memory) |
| **V2 Agent Loop** | Autonomer FSM mit Sensoren, Aktionen, Zielen, Motivation, Safety |
| **3 Dashboards** | Brain Dashboard, Unified Brain (SVG), Radial Dashboard |
| **FastAPI Server** | Port 5000, WebSocket Chat mit Brain-State |
| **1981+ Tests** | Umfassende Testsuite |

**Geplante VibeMind-Integration:**

```
Geplant:
├── python/spaces/brain/
│   ├── the_brain/          ← Submodule (vorhanden ✅)
│   ├── agents/
│   │   └── brain_agent.py  ← BrainBackendAgent (ausstehend 🚧)
│   ├── tools/
│   │   └── brain_tools.py  ← VibeMind ↔ Brain Bridge (ausstehend 🚧)
│   └── __init__.py         ← Space-Export (ausstehend 🚧)
├── Stream: events:tasks:brain (ausstehend 🚧)
├── Prefix: brain.* (ausstehend 🚧)
└── Electron: Brain Dashboard BrowserView (ausstehend 🚧)
```

**Geplante Event-Typen:**

| Event | Funktion |
|-------|----------|
| `brain.think` | Cognitive Loop auf Input ausführen |
| `brain.status` | Brain-State abfragen (Emotionen, Neuromodulation) |
| `brain.chat` | Chat mit Brain-State-gefärbter Antwort |
| `brain.goal.set` | Ziel setzen/ändern |
| `brain.goal.list` | Aktive Ziele anzeigen |
| `brain.dream` | Dream-Mode triggern (Konsolidierung) |
| `brain.dashboard` | Brain Dashboard BrowserView öffnen |

**Bausteine die bereits in VibeMind existieren:**

| Baustein | Existiert? | Datei | Brain-Äquivalent |
|----------|-----------|-------|-----------------|
| TaskMemory | ✅ | `python/memory/task_memory_service.py` | Memory Bridge |
| ConversationMemory | ✅ | `python/memory/conversation_memory_service.py` | Conversation Graph |
| UserProfile | ✅ | `python/memory/user_profile_service.py` | Personality Model |
| IntentEnhancer | ✅ | `python/swarm/agents/intent_enhancer.py` | Hierarchical Planner |
| ExecutionValidator | ✅ | `python/swarm/agents/execution_validator.py` | Safety Regulation |
| MinibookHub | ✅ | `python/spaces/minibook/minibook_hub.py` | Decision Router |

**Status:** 🚧 Submodule vorhanden. Integration braucht besondere Zeit — eigenständiger Sprint.

---

## Cross-Space Kommunikationsmatrix

Welcher Space kommuniziert mit wem:

```
            IDEAS  BUBBLES  CODING  DESKTOP  ROWBOAT  RESEARCH  SCHEDULE  MINIBOOK
IDEAS         ─      ✅       ✅       ─       ✅        ✅         ─        ✅
BUBBLES      ✅       ─        ─       ─        ─         ─         ─        ✅
CODING        ─       ─        ─       ─       ✅         ─         ─        ✅
DESKTOP       ─       ─        ─       ─        ─         ─         ─        ✅
ROWBOAT      ✅       ─       ✅       ─        ─        ✅         ─        ✅
RESEARCH     ✅       ─        ─       ─       ✅         ─         ─        ✅
SCHEDULE      ─       ─        ─       ─        ─         ─         ─        ✅
MINIBOOK     ✅      ✅       ✅      ✅       ✅        ✅        ✅         ─
```

**Legende:**
- ✅ = Direkte Kommunikation (Event-basiert oder Tool-Aufruf)
- ─ = Keine direkte Kommunikation
- Minibook verbindet alle (Hub-Pattern)

---

## Datenfluss: Vollständiges Beispiel

**User sagt:** "Recherchiere KI-Trends, erstelle eine Idee daraus, und bereite ein Meeting-Brief vor"

```
1. Rachel empfängt Voice
2. IntentOrchestrator → MinibookHub.dispatch()

3. EnrichmentPipeline:
   ├── SpaceRouter: research (primär) + ideas + rowboat (sekundär)
   └── TaskEnricher: 3 angereicherte Payloads

4. Parallele Ausführung:
   ├── ZeroClawAgent: research.web → Web-Recherche
   ├── IdeasAgent: idea.create → Neue Idee aus Ergebnis
   └── RoarbootAgent: roarboot.meeting_brief → Meeting-Brief

5. Ergebnisse:
   ├── Research → .rowboat/knowledge/ (neues Wissen)
   ├── Ideas → neue Bubble mit verlinkten Ideen
   └── Rowboat → .rowboat/meetings/briefs/ (Meeting-Dokument)

6. ResultAggregator fasst zusammen → Rachel spricht Zusammenfassung
7. Electron UI aktualisiert: neue Bubble + Meeting-Brief Notification
```

---

## Voice-Erreichbarkeit der Spaces

| Space | Per Sprache? | Befehl |
|-------|-------------|--------|
| Ideas | ✅ | "Geh zu Ideas" / "Zeig Bubbles" |
| Projects | ✅ | "Geh zu Projects" |
| Desktop | ✅ | "Geh zu Desktop" |
| Rowboat | ❌ | Nur Tab-Klick |
| SWE Design | ❌ | Nur Tab-Klick |
| Dashboard | ❌ | Nur Tab-Klick |

**Geplant:** Alle Spaces per Voice erreichbar machen (navigation_tools.py erweitern).

---

## Konfiguration

```bash
# Spaces aktivieren/deaktivieren
MINIBOOK_ENABLED=false          # Inter-Space Hub
USE_MINIBOOK_HUB=false          # Alle Intents durch Minibook routen
SCHEDULE_ENABLED=false          # Aufgabenplanung
USE_ZEROCLAW=false              # Web-Recherche
ROWBOAT_ENABLED=true            # Knowledge Graph

# Rowboat Verbindung
ROWBOAT_URL=http://localhost:3000
ROWBOAT_API_KEY=xxx
ROWBOAT_PROJECT_ID=xxx
ROWBOAT_AUTO_START=false

# Desktop Automation
AUTOMATION_UI_URL=http://localhost:8007

# Memory (Brain-Bausteine)
USE_TASK_MEMORY=true
USE_CONVERSATION_MEMORY=true
USE_USER_PROFILES=true
SUPERMEMORY_API_KEY=xxx
```
