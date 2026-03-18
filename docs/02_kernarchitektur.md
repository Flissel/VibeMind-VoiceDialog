# Kernarchitektur

## Voice Layer

### OpenAI Realtime API

VibeMind nutzt ausschliesslich die **OpenAI Realtime API** als Voice Provider:

| Eigenschaft | Wert |
|------------|------|
| Provider | OpenAI Realtime API |
| Modell | gpt-4o-realtime |
| Latenz | ~300ms |
| Features | Speech-to-Speech, native Function Calling, VAD |
| Sprachen | Deutsch + Englisch |

```
Mikrofon --> AudioManager --> WebSocket (input_audio_buffer.append)
                                |
                      OpenAI Realtime API (gpt-4o-realtime)
                                |
Lautsprecher <-- AudioManager <-- WebSocket (response.audio.delta)
                                |
                      Function Calls --> send_intent()
                                |
                      IntentOrchestrator --> Backend Agents
```

**Dateien:**

- `python/voice/openai_realtime.py` — Session-Manager (34KB)
- `python/voice/audio_manager.py` — Mikrofon-Capture & Speaker-Playback
- `python/voice/session_config.py` — Session-Konfiguration mit SEND_INTENT_TOOL

**Features:**

- 30-Minuten Session Timeout mit automatischer Reconnection
- Voice Activity Detection (VAD)
- Deutsch + Englisch
- Bidirektionales Audio-Streaming via WebSocket

---

## Intent Pipeline

### Vollstaendiger Verarbeitungsfluss

```
Nutzer spricht: "Erstelle eine Bubble namens Marketing"
    |
    v
[1. Voice Layer - OpenAI Realtime API]
    Mikrofon --> Base64 Audio --> WebSocket
    Transkription: "Erstelle eine Bubble namens Marketing"
    |
    v
[2. Function Call - send_intent]
    tool_call: send_intent
    arguments: {"user_text": "Erstelle eine Bubble namens Marketing"}
    |
    v
[3. IntentOrchestrator.on_tool_call()]
    |
    +-- (Optional) CollectorAgent: Fragmentakkumulation (<3 Woerter)
    +-- (Optional) IntentEnhancer: ASR-Fehlerkorrektur
    +-- (Optional) DroPE Resolver: Referenzaufloesung ("das", "nochmal")
    |
    v
[4. IntentClassifier.classify()]
    --> event_type: "bubble.create"
    --> payload: {"title": "Marketing"}
    |
    v
[5. Event Routing]
    +-- Direktausfuehrung (Standard, FORCE_SYNC_MODE=true)
    +-- (Optional) Redis Stream (events:tasks:bubbles)
    |
    v
[6. Backend Agent - BubblesAgent]
    TOOL_MAP["bubble.create"] --> create_bubble()
    PARAM_MAPPING: Normalisierung
    |
    v
[7. Tool-Ausfuehrung]
    create_bubble(title="Marketing")
    --> SQLite: INSERT INTO ideas (title, parent_id, ...)
    --> _broadcast_to_electron({"type": "node_added", "node": {...}})
    |
    v
[8. Electron UI Update]
    Three.js: Neue Bubble erscheint im 3D-Raum
    |
    v
[9. Voice Response]
    Rachel: "Bubble Marketing wurde erstellt"
```

### Orchestrator-Komponenten

| Komponente | Datei | Zeilen | Funktion |
|-----------|-------|--------|----------|
| IntentOrchestrator | `python/swarm/orchestrator/intent_orchestrator.py` | 3.142 | Zentrale Koordination |
| IntentClassifier | `python/swarm/orchestrator/intent_classifier.py` | 1.448 | LLM-Klassifikation |
| ToolOrchestrator | `python/swarm/orchestrator/tool_orchestrator.py` | 519 | Multi-Step Execution |
| RAGIntentClassifier | `python/swarm/orchestrator/rag_intent_classifier.py` | 500 | Semantische Klassifikation |
| ToolDefinitions | `python/swarm/orchestrator/tool_definitions.py` | 619 | Tool-Registry |
| NotificationQueue | `python/swarm/orchestrator/notification_queue.py` | — | Async Notification Delivery |
| QuestionQueue | `python/swarm/orchestrator/question_queue.py` | — | Klaerungsfragen |
| ResponseGenerator | `python/swarm/orchestrator/response_generator.py` | — | Ergebnis-Formatierung |
| SystemContextStore | `python/swarm/orchestrator/system_context_store.py` | — | Kurzzeit-Wissenspeicher |
| ReferenceResolver | `python/swarm/orchestrator/reference_resolver.py` | — | DroPE-Referenzaufloesung |

### Optionale Pipeline-Stufen

| Feature | ENV-Variable | Beschreibung |
|---------|-------------|-------------|
| Fragment-Sammlung | (immer aktiv) | CollectorAgent akkumuliert Fragmente <3 Woerter |
| ASR-Korrektur | (immer aktiv) | IntentEnhancer korrigiert Spracherkennungsfehler |
| DroPE Resolver | `USE_DROPE_RESOLVER=true` | Loest ambige Referenzen auf ("das", "es", "nochmal") |
| RAG Classifier | `USE_RAG_CLASSIFIER=true` | Supermemory-basierte semantische Klassifikation |
| Tool Orchestrator | `USE_TOOL_ORCHESTRATOR=true` | Claude Sonnet fuer Multi-Step Requests |
| Broadcast Mode | `USE_BROADCAST_MODE=true` | Fan-out Intent an alle Domain-Agents |
| Intent Analysis | `USE_INTENT_ANALYSIS=true` | Multi-Agent Hypothesengenerierung |

---

## Backend Agents

### BaseBackendAgent Pattern

Alle Domain-Agents erben von `BaseBackendAgent` (`python/swarm/backend_agents/base_agent.py`):

```python
class MyBackendAgent(BaseBackendAgent):
    stream = "events:tasks:my_domain"
    name = "MyAgent"

    TOOL_MAP = {
        "domain.action": "tool_function_name",
    }

    PARAM_MAPPING = {
        "domain.action": {"classifier_param": "tool_param"},
    }
```

**Ablauf:**

1. Agent wird direkt aufgerufen (Sync) oder hoert auf Redis Stream (optional)
2. Event-Type wird via TOOL_MAP auf Tool-Funktion gemappt
3. Parameter werden via PARAM_MAPPING normalisiert
4. Tool wird ausgefuehrt
5. Ergebnis wird an Electron gebroadcasted

### Aktive Backend Agents

| Agent | Space | Stream | Tools |
|-------|-------|--------|-------|
| BubblesAgent | Ideas | events:tasks:bubbles | 13 |
| IdeasAgent | Ideas | events:tasks:ideas | 38 |
| DesktopAgent | Desktop | events:tasks:desktop | 12 |
| CodingAgent | Coding | events:tasks:coding | 8 |
| RoarbootAgent | Roarboot | events:tasks:roarboot | 13 |
| ZeroClawResearchAgent | Research | events:tasks:zeroclaw | 5 |
| MinibookAgent | Minibook | events:tasks:minibook | 5+ |

---

## Electron IPC

### Kommunikationsprotokoll

```
Electron Main --spawn--> Python Backend (stdin/stdout JSON)
     |                            |
 Renderer (Three.js)      Tool Execution + DB
```

**Message Types (Python --> Electron):**

| Message Type | Zweck | Beispiel |
|-------------|-------|---------|
| `node_added` | Neue Bubble/Idee erstellt | `{"type": "node_added", "node": {"id": "abc", "title": "Marketing"}}` |
| `node_removed` | Bubble/Idee geloescht | `{"type": "node_removed", "node_id": "abc"}` |
| `edge_added` | Verbindung erstellt | `{"type": "edge_added", "from": "a", "to": "b"}` |
| `space_changed` | Navigation zu Space | `{"type": "space_changed", "space": "coding"}` |
| `node_structured_update` | Rich Content Update | `{"type": "node_structured_update", "data": {...}}` |

### Electron Manager

| Manager | Datei | Funktion |
|---------|-------|----------|
| Docker Manager | `electron-app/docker-manager.js` | Coding Engine Container |
| Port Allocator | `electron-app/port-allocator.js` | Dynamische Port-Zuweisung |
| Dashboard Manager | `electron-app/dashboard-manager.js` | Coding Engine Dashboard |
| Rowboat Manager | `electron-app/rowboat-manager.js` | Rowboat BrowserView |
| SWE Design Manager | `electron-app/swe-design-manager.js` | Factory Space Integration |

---

## 3D UI (Three.js Multiverse)

### Renderer-Komponenten

| Datei | Groesse | Funktion |
|-------|---------|----------|
| `electron-app/renderer/multiverse.js` | 104KB | Kern-3D-Visualisierung |
| `electron-app/renderer/glass_bubbles.js` | — | MultiverseApp Bootstrap |
| `electron-app/renderer/shuttle_manager.js` | 48KB | Shuttle Pipeline UI |
| `electron-app/renderer/universe_canvas.js` | 49KB | Canvas Rendering |
| `electron-app/renderer/rich_content_renderer.js` | 61KB | Rich Media Formatierung |
| `electron-app/renderer/exploration_dialog.js` | 24KB | Exploration/Research UI |

### Visualisierungstypen

| Space | Visualisierung | Beschreibung |
|-------|---------------|-------------|
| IDEAS | `bubbles` | Glasartige 3D-Bubbles |
| CODING | `nebula` | Nebel-Effekt |
| DESKTOP | `light_planet` | Leuchtender Planet mit Pulsation |
| OPENCLAW | `planet` | Solider Planet |
| TRANSFORMER | `portal` | Portal-Effekt |
| ROWBOAT | `nebula` | Nebel-Effekt |
| SWE_DESIGN | `factory` | Fabrik-Visualisierung |
| MINIBOOK | `nebula` | Nebel-Effekt |

---

## Neue Features (Aktuell)

### Messaging Pipeline
Voice-gesteuerte Nachrichten ueber WhatsApp/Telegram via Clawdbot Gateway.

```
"Schreib meiner Mutter dass ich spaeter komme"
    --> messaging.send Event
    --> Rowboat: Kontakt-Kontext laden
    --> Clawdbot: WhatsApp senden
    --> Rachel: "Nachricht gesendet"
```

**Dateien:** `python/spaces/desktop/messaging/`

### ZeroClaw Research
Tiefgehende Web-Recherche, Scraping und Zusammenfassung via Rust-Subprocess.

**Event-Abgrenzung:**
- `research.web` = Tiefe Web-Recherche (ZeroClaw)
- `roarboot.search` = Internes Wissen (Rowboat Knowledge Graph)
- `web.search` = Einfache Web-Suche (Desktop Agent)

### Minibook Hub — Zentrales Routing aller Intents

Wenn `USE_MINIBOOK_HUB=true` (primaerer Routing-Modus), fliessen **alle** Intents durch den MinibookHub — nicht nur explizite `minibook.*` Events. Minibook fungiert als **Message Bus**, nicht als Execution Engine. Die eigentliche Tool-Ausfuehrung uebernehmen SpaceMinibookResponders pro Space.

```
process_intent() → MinibookHub.dispatch()
    → EnrichmentPipeline (4 Stufen)
    → Minibook POST mit @mentions fuer relevante Agents
    → Single-Space: sync-wait (<=10s)
    → Multi-Space: async-poll via ResultAggregator (<=120s)
    → Fallback auf _process_sync() bei Timeout/Fehler
```

**EnrichmentPipeline — 4 Stufen:**

| Stufe | Komponente | Funktion |
|-------|-----------|----------|
| 1 | ContextGather | Metadaten aus allen VibeMind-Stores sammeln (DB, Memory, Session) |
| 2 | IntentClassifier | Klassifikation zu event_type + payload (bestehender Classifier wird wiederverwendet) |
| 3 | SpaceRouter | LLM-basierte Entscheidung: welche(r) Space(s) bearbeiten die Aufgabe |
| 4 | TaskEnricher | Pro Agent angereicherte Payloads mit Kontext erstellen |

**Ausfuehrungsmodi:**

| Modus | Bedingung | Timeout | Ablauf |
|-------|-----------|---------|--------|
| Single-Space (sync) | SpaceRouter erkennt genau 1 Space | 10s | Synchrones Warten auf Ergebnis des SpaceMinibookResponders |
| Multi-Space (async) | SpaceRouter erkennt 2+ Spaces | 120s | Sofortige Bestaetigung an Rachel, ResultAggregator pollt Teilergebnisse |

**Beispiele:**

```
# Single-Space (sync, 10s)
"Erstelle eine Bubble Marketing"
    → EnrichmentPipeline → event_type: bubble.create, primary_space: ideas
    → Minibook POST @BubblesAgent
    → sync-wait → Ergebnis in <10s

# Multi-Space (async, 120s)
"Recherchiere X und erstelle daraus eine Idee"
    → EnrichmentPipeline → primary: research, secondary: [ideas]
    → Minibook POST @ZeroClawResearchAgent @IdeasAgent
    → async-poll → ResultAggregator sammelt Teilergebnisse
    → Rachel erhaelt Zwischenupdates
```

**Docker-Voraussetzung:** Minibook benoetigt eigene Container-Infrastruktur:

```bash
docker compose -f docker-compose.minibook.yml up -d
```

**Dateien:**

| Komponente | Datei |
|-----------|-------|
| MinibookHub | `python/spaces/minibook/minibook_hub.py` |
| EnrichmentPipeline | `python/spaces/minibook/enrichment/pipeline.py` |
| ContextGather | `python/spaces/minibook/enrichment/context_gather.py` |
| SpaceRouter | `python/spaces/minibook/enrichment/space_router.py` |
| TaskEnricher | `python/spaces/minibook/enrichment/task_enricher.py` |
| ResultAggregator | `python/spaces/minibook/result_aggregator.py` |
| RachelInterface | `python/spaces/minibook/rachel_interface.py` |
| MinibookClient | `python/spaces/minibook/tools/minibook_client.py` |

**Konfiguration:**

```bash
USE_MINIBOOK_HUB=true        # Alle Intents durch Minibook routen
MINIBOOK_ENABLED=true        # Minibook Space aktivieren
```

Single-Space-Aufgaben im Minibook-Modus haben minimalen Overhead (~10s sync-wait). Ist `USE_MINIBOOK_HUB=false`, wird Minibook komplett umgangen und Intents fliessen direkt zum jeweiligen Backend Agent (Zero Overhead).
