# Swarm Layer

Die Swarm-Schicht ist das zentrale Nervensystem von VibeMind. Sie nimmt Voice-Intents entgegen, klassifiziert sie, routet sie an die richtigen Backend Agents und koordiniert die Ausfuehrung.

---

## Architektur-Uebersicht

```
Voice Input
    |
    v
+-----------------------------------+
| IntentOrchestrator (3.142 Zeilen) |
| - Empfaengt Intent                |
| - Optionale Pre-Processing Stufen |
| - Klassifiziert via LLM           |
| - Routet Event                    |
+-----------------------------------+
    |
    v
+-----------------------------------+
| Event Team                        |
| - EventRouter (Stream-Mapping)    |
| - TaskSeeder (Job-Erstellung)     |
| - JobManager (Lifecycle)          |
+-----------------------------------+
    |
    v
+-----------------------------------+
| Event Bus (Redis Streams)         |
| 8 Task-Streams + 4 System-Streams|
+-----------------------------------+
    |
    +------+------+------+------+------+------+------+
    |      |      |      |      |      |      |      |
    v      v      v      v      v      v      v      v
  Ideas  Coding Desktop Bubbles Roarboot ZeroClaw Shuttles
  Agent  Agent  Agent   Agent   Agent    Agent    Agent
    |      |      |      |      |      |      |
    v      v      v      v      v      v      v
  Tools  Tools  Tools  Tools  Tools  Tools  Tools
    |
    v
+-----------------------------------+
| Broadcast --> Electron UI         |
+-----------------------------------+
```

---

## Orchestrator Suite

### IntentOrchestrator
**Datei:** `python/swarm/orchestrator/intent_orchestrator.py` (3.142 Zeilen)

Zentrale Koordinationseinheit. Empfaengt Intents von der Voice Layer und orchestriert den gesamten Verarbeitungsfluss.

**Hauptmethoden:**
- `on_tool_call()` — Einstiegspunkt fuer Voice Function Calls
- `classify_and_route()` — Klassifikation + Routing
- `execute_sync()` — Direktausfuehrung (Standard)
- `publish_to_stream()` — Optional: Veroeffentlichung auf Redis Stream

### IntentClassifier
**Datei:** `python/swarm/orchestrator/intent_classifier.py` (1.448 Zeilen)

LLM-basierte Klassifikation von natuerlicher Sprache in strukturierte Event Types.

**Kern:** `CLASSIFIER_PROMPT_TEMPLATE` — Vollstaendiges Mapping aller Event Types mit deutschen Beispielen, Regeln fuer Disambiguierung und Payload-Extraktion.

**Unterstuetzte Event-Familien:**
- `bubble.*` — Bubble/Space-Verwaltung (7 Types)
- `idea.*` — Ideen-Management (15+ Types)
- `code.*` — Code-Generierung (6 Types)
- `desktop.*` — Desktop-Automatisierung (8+ Types)
- `messaging.*` — Nachrichten (3 Types)
- `roarboot.*` — Knowledge Graph (9+ Types)
- `research.*` — Web-Recherche (5 Types)
- `minibook.*` — Collaboration (4 Types)
- `shuttle.*` — Requirements Pipeline
- `evaluation.*` — Feedback (2 Types)

### ToolOrchestrator
**Datei:** `python/swarm/orchestrator/tool_orchestrator.py` (519 Zeilen)

Multi-Step Tool Execution via Claude Sonnet. Zerteilt komplexe Anfragen in mehrere Tool-Aufrufe und fuehrt sie sequenziell aus.

**Aktivierung:** `USE_TOOL_ORCHESTRATOR=true`

### RAGIntentClassifier
**Datei:** `python/swarm/orchestrator/rag_intent_classifier.py` (500 Zeilen)

Supermemory-basierte semantische Klassifikation als Ergaenzung zum LLM-Classifier.

**Aktivierung:** `USE_RAG_CLASSIFIER=true`

### MinibookHub — Zentraler Routing-Hub

**Verzeichnis:** `python/spaces/minibook/`

Wenn `USE_MINIBOOK_HUB=true` gesetzt ist, delegiert der IntentOrchestrator **alle** Intents exklusiv an den MinibookHub (Phase 0.5 — Exclusive Mode). Der MinibookHub uebernimmt dann Klassifikation, Routing und Ausfuehrung als zentraler Koordinator.

**Verarbeitungsfluss:**

```
IntentOrchestrator
    |  (USE_MINIBOOK_HUB=true --> alle Intents delegiert)
    v
MinibookHub (minibook_hub.py)
    |
    v
EnrichmentPipeline (enrichment/pipeline.py)
    |-- Klassifikation des Intents
    |-- Anreicherung mit Kontext
    v
SpaceRouter (enrichment/space_router.py)
    |-- Bestimmt 1-3 zustaendige Spaces
    |   1. Deterministische Zuordnung nach Event-Prefix (bubble.* --> Ideas)
    |   2. LLM-Fallback fuer mehrdeutige Intents
    |   3. Keyword-Fallback als letzte Instanz
    v
Minibook API (POST mit @agent Mentions)
    |
    v
SpaceMinibookResponders (workers/minibook_workers.py)
    |-- 8 Worker-Threads (einer pro Space)
    |-- Jeder Worker reagiert auf seine @mentions
    |-- Fuehrt Space-spezifische Tools aus
    v
ResultAggregator (result_aggregator.py)
    |-- Sync-Modus: Wartet max. 10s auf alle Antworten
    |-- Async-Modus: Pollt bis zu 120s fuer langlaufende Tasks
    v
Aggregiertes Ergebnis --> IntentOrchestrator --> Rachel
```

**Aktivierung:** `USE_MINIBOOK_HUB=true`

**Schluessel-Dateien:**

| Datei | Funktion |
|-------|----------|
| `python/spaces/minibook/minibook_hub.py` | Zentraler Hub — empfaengt Intents, koordiniert Pipeline |
| `python/spaces/minibook/enrichment/pipeline.py` | EnrichmentPipeline — Klassifikation + Kontextanreicherung |
| `python/spaces/minibook/enrichment/space_router.py` | SpaceRouter — deterministische + LLM-basierte Space-Zuordnung |
| `python/spaces/minibook/result_aggregator.py` | ResultAggregator — Zusammenfuehrung der Space-Antworten |
| `python/spaces/minibook/workers/minibook_workers.py` | SpaceMinibookResponders — 8 Worker-Threads fuer Space-Ausfuehrung |

---

## Unterstuetzende Systeme

| Komponente | Datei | Funktion |
|-----------|-------|----------|
| ToolDefinitions | `python/swarm/orchestrator/tool_definitions.py` | Zentrales Tool-Registry (619 Zeilen) |
| NotificationQueue | `python/swarm/orchestrator/notification_queue.py` | Async Notification Delivery |
| QuestionQueue | `python/swarm/orchestrator/question_queue.py` | Klaerungsfragen an Nutzer |
| ResponseGenerator | `python/swarm/orchestrator/response_generator.py` | LLM-basierte Ergebnis-Formatierung |
| SystemContextStore | `python/swarm/orchestrator/system_context_store.py` | Kurzzeit-Wissensspeicher |
| ReferenceResolver | `python/swarm/orchestrator/reference_resolver.py` | DroPE-Referenzaufloesung |

---

## Event Team

**Verzeichnis:** `python/swarm/event_team/`

| Datei | Funktion |
|-------|----------|
| `event_router.py` | Mappt event_type --> Redis Stream (STREAM_MAPPING) |
| `task_seeder.py` | Erstellt strukturierte Task-Events mit Job-Tracking |
| `job_manager.py` | Verwaltet Job-Lifecycle und Execution-Status |

### Stream-Mapping (EventRouter)

```
bubble.*    --> events:tasks:bubbles
idea.*      --> events:tasks:ideas
code.*      --> events:tasks:coding
desktop.*   --> events:tasks:desktop
messaging.* --> events:tasks:desktop
roarboot.*  --> events:tasks:roarboot
research.*  --> events:tasks:zeroclaw
minibook.*  --> events:tasks:minibook  (implizit)
shuttle.*   --> events:tasks:shuttles
```

---

## Event Bus

**Datei:** `python/swarm/event_bus.py`

Optionale Redis Streams Kommunikationsschicht zwischen Voice Layer und Backend Agents. Im Standard-Betrieb (FORCE_SYNC_MODE=true) werden Agents direkt aufgerufen ohne Redis.

### Stream-Konstanten

**Task Streams (Domain-spezifisch):**

| Konstante | Stream | Nutzer |
|-----------|--------|--------|
| `STREAM_TASKS` | `events:tasks` | Allgemein |
| `STREAM_TASKS_CODING` | `events:tasks:coding` | CodingAgent |
| `STREAM_TASKS_DESKTOP` | `events:tasks:desktop` | DesktopAgent |
| `STREAM_TASKS_IDEAS` | `events:tasks:ideas` | IdeasAgent |
| `STREAM_TASKS_BUBBLES` | `events:tasks:bubbles` | BubblesAgent |
| `STREAM_TASKS_ROARBOOT` | `events:tasks:roarboot` | RoarbootAgent |
| `STREAM_TASKS_ZEROCLAW` | `events:tasks:zeroclaw` | ZeroClawAgent |
| `STREAM_TASKS_SHUTTLES` | `events:tasks:shuttles` | ShuttlesAgent |

**System Streams:**

| Konstante | Stream | Funktion |
|-----------|--------|----------|
| `STREAM_STATUS` | `events:status` | Backend --> Rachel (Status Updates) |
| `STREAM_JOBS` | `events:jobs` | Job State Tracking |
| `STREAM_REASONING` | `events:reasoning` | Execution Reasoning (Thinking Panel) |
| `STREAM_QUESTIONS` | `events:questions` | Backend --> Rachel (Fragen an Nutzer) |
| `STREAM_ANSWERS` | `events:answers` | Rachel --> Backend (Nutzer-Antworten) |

### SwarmEvent

```python
@dataclass
class SwarmEvent:
    stream: str           # "events:tasks:coding"
    event_type: str       # "code.generate"
    payload: Dict[str, Any]
    job_id: Optional[str] = None
    timestamp: float = ...
```

### Multi-User Support
Optionale User-Isolation ueber Stream-Prefixes:
- Ohne user_id: `events:tasks:ideas`
- Mit user_id: `events:user:alice:tasks:ideas`

---

## Backend Agents

**Verzeichnis:** `python/swarm/backend_agents/`

### BaseBackendAgent
**Datei:** `python/swarm/backend_agents/base_agent.py` (26KB)

Abstrakte Basisklasse fuer alle Domain-Agents:

```python
class BaseBackendAgent:
    stream = ""           # Event Stream (optional, fuer Redis-Modus)
    name = ""             # Agent-Name
    TOOL_MAP = {}         # event_type --> tool_function_name
    PARAM_MAPPING = {}    # event_type --> {classifier_param: tool_param}

    def handle_event(self, event):
        tool_name = self.TOOL_MAP.get(event.event_type)
        params = self._normalize_params(event)
        result = self._execute_tool(tool_name, params)
        self._broadcast_to_electron(result)
```

### Agent Pool
**Datei:** `python/swarm/backend_agents/agent_pool.py`

Agent-Pooling fuer parallele Ausfuehrung mehrerer Agents.

### Domain Agents

| Agent | Stream | TOOL_MAP Eintraege | Space |
|-------|--------|-------------------|-------|
| BubblesAgent | events:tasks:bubbles | 13 | Ideas |
| IdeasAgent | events:tasks:ideas | 38 | Ideas |
| DesktopAgent | events:tasks:desktop | 12 | Desktop |
| CodingAgent | events:tasks:coding | 8 | Coding |
| RoarbootAgent | events:tasks:roarboot | 13 | Rowboat |
| ZeroClawResearchAgent | events:tasks:zeroclaw | 5 | Research |
| MinibookAgent | events:tasks:minibook | 5+ | Minibook |

---

## Broadcast System

**Verzeichnis:** `python/swarm/broadcast/`

Fan-out Architektur: Ein Intent wird an alle Domain-Agents gleichzeitig gesendet (fuer Profiling oder parallele Verarbeitung).

**Aktivierung:** `USE_BROADCAST_MODE=true`

Jeder Space hat einen eigenen Broadcast Agent in `python/spaces/*/broadcast/`.

---

## Weitere Swarm-Subsysteme

| Subsystem | Verzeichnis | Funktion |
|-----------|------------|----------|
| Analysis Team | `python/swarm/analysis/` | Multi-Agent Hypothesengenerierung |
| ConversionAI | `python/swarm/conversion/` | Personalisierte Antwort-Generierung |
| Context | `python/swarm/context/` | Session-Kontext, Bubble-Kontext |
| Listeners | `python/swarm/listeners/` | Question + Status Listener |
| Evaluation | `python/swarm/evaluation/` | Echtzeit-Evaluator fuer Intent-Feedback |
| Reasoning | `python/swarm/reasoning/` | Execution Reasoning Logger |
| Debugging | `python/swarm/debugging/` | Agent Execution Logging |
| Monitoring | `python/swarm/monitoring/` | System Status Monitoring |
| ZeroClaw | `python/swarm/zeroclaw/` | Web Research Engine (Rust Wrapper) |
| VoiceBridgeV2 | `python/swarm/voice_bridge_v2.py` | Async Architektur Layer |
| Workers | `python/swarm/workers/` | Basis-Worker-Klasse |
| User Agents | `python/swarm/user_agents/` | Nutzerspezifische Agent-Config |
| Publishing | `python/publishing/` | Space Metadata Publishing |

---

## Optionale Features (ENV-gesteuert)

| Feature | ENV-Variable | Default | Beschreibung |
|---------|-------------|---------|-------------|
| Voice Bridge V2 | `USE_VOICE_BRIDGE_V2` | false | Async Notification Queue |
| Tool Orchestrator | `USE_TOOL_ORCHESTRATOR` | false | Multi-Step Tool Chaining |
| Broadcast Mode | `USE_BROADCAST_MODE` | false | Fan-out an alle Agents |
| Intent Analysis | `USE_INTENT_ANALYSIS` | false | Multi-Agent Hypothesen |
| DroPE Resolver | `USE_DROPE_RESOLVER` | false | Referenzaufloesung |
| RAG Classifier | `USE_RAG_CLASSIFIER` | false | Semantische Klassifikation |
| Minibook Hub | `USE_MINIBOOK_HUB` | false | Zentraler Routing-Hub (alle Intents via MinibookHub) |
| Task Memory | `USE_TASK_MEMORY` | false | Aufgaben-Tracking |
| Conv. Memory | `USE_CONVERSATION_MEMORY` | false | Cross-Session Kontext |
| User Profiles | `USE_USER_PROFILES` | false | Praeferenz-Lernen |
| Sync Mode | `FORCE_SYNC_MODE` | true | Standard-Betrieb, kein Redis erforderlich |

---

## Memory System

**Verzeichnis:** `python/memory/`

| Service | Datei | Funktion |
|---------|-------|----------|
| TaskMemory | `task_memory_service.py` | Aufgaben-Tracking in Supermemory |
| ConversationMemory | `conversation_memory_service.py` | Cross-Session Kontext |
| UserProfile | `user_profile_service.py` | Praeferenz-Lernen |
| ConversationRouter | `conversation_router.py` | RAG-basiertes Context Routing |
| SupermemoryClient | `supermemory_client.py` | API-Client fuer Supermemory |

**Beispiel-Abfragen:**
- "Was habe ich heute gemacht?" --> TaskMemory
- "Was haben wir letztens besprochen?" --> ConversationMemory
- Automatische Praeferenz-Erkennung --> UserProfile
