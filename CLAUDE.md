# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**VibeMind Voice Dialog** is a voice-controlled workspace where voice input is captured and routed through a swarm backend for execution.

**Current Architecture:**

- **Voice Provider** — OpenAI Realtime API (speech-to-speech, native function calling) via VoiceBridgeV2 async architecture. Rachel is the single voice interface agent.
- **Intent Classification** — LLM-based classification of natural language to event types
- **Swarm Backend** — 13 backend agents across 15 domain spaces execute tools
- **Electron UI** — 3D multiverse with bubbles (ideas) rendered via Three.js

## Quick Start

### Full System (Electron UI)

```bash
# 1. Start Minibook (central message bus)
docker compose -f docker-compose.minibook.yml up -d --build

# 2. Start Electron app (spawns Python backend automatically)
cd electron-app
npm install  # first time only
npm start
```

### Configuration

Copy `.env.example` to `.env`:

```bash
# Voice (OpenAI Realtime)
OPENAI_API_KEY=sk-xxx

# MinibookHub routing (PRIMARY — requires Docker)
MINIBOOK_ENABLED=true
USE_MINIBOOK_HUB=true
MINIBOOK_URL=http://localhost:3480

# Sync mode (no Redis required for direct fallback)
FORCE_SYNC_MODE=true
```

## Architecture

### Main Flow (MinibookHub — Primary Mode)

```
User Voice / Game Console Chat
            ↓
    OpenAI Realtime API (voice) or process_intent (text)
            ↓
    ┌─── MinibookHub (USE_MINIBOOK_HUB=true) ───┐
    │                                             │
    │  1. EnrichmentPipeline                      │
    │     ├── ContextGather (history, state)       │
    │     ├── IntentClassifier → event_type        │
    │     ├── SpaceRouter (LLM/deterministic)      │
    │     └── TaskEnricher (payload + context)      │
    │                                             │
    │  2. POST to Minibook with @agent mentions   │
    │                                             │
    │  3. SpaceResponders execute tools            │
    │     ├── Single-space: sync-wait (10s)        │
    │     └── Multi-space: async-poll (120s)       │
    └─────────────────────────────────────────────┘
            ↓                        ↓
    ┌───────────────┐    ┌───────────────────┐
    │ Single Space   │    │ Multi Space        │
    │ e.g. Ideas     │    │ e.g. Research +    │
    │ → idea.create  │    │      Ideas         │
    └───────────────┘    └───────────────────┘
            ↓
    Electron UI (3D Multiverse)
```

**Fallback (direct mode):** When `USE_MINIBOOK_HUB=false`, intents route directly:
```
IntentClassifier → event_type → EventRouter → Backend Agent → Tool
```

### Voice Agent

Rachel is the single voice interface agent (OpenAI Realtime). She receives user speech, calls `send_intent` to route through the swarm orchestrator, and speaks the response.

**Key File:** `python/spaces/ideas/agents/rachel_agent.py`

### Fifteen Spaces (Domains)

VibeMind has 15 domain spaces, each with its own backend agent and Redis stream:

| Space | Stream | Backend Agent | Event Prefix | File |
| ----- | ------ | ------------- | ------------ | ---- |
| Bubbles | `events:tasks:bubbles` | BubblesAgent | `bubble.*` | `python/spaces/ideas/agents/bubbles_agent.py` |
| Ideas | `events:tasks:ideas` | IdeasAgent | `idea.*` | `python/spaces/ideas/agents/ideas_agent.py` |
| Coding | `events:tasks:coding` | CodingAgent | `code.*` | `python/spaces/coding/agents/coding_agent.py` |
| Desktop | `events:tasks:desktop` | DesktopAgent | `desktop.*`, `messaging.*`, `web.*`, `openclaw.*` | `python/spaces/desktop/agents/desktop_agent.py` |
| Rowboat | `events:tasks:roarboot` | RoarbootBackendAgent | `roarboot.*` | `python/spaces/rowboat/agents/roarboot_agent.py` |
| Research | `events:tasks:zeroclaw` | ZeroClawResearchAgent | `research.*` | `python/spaces/research/agents/zeroclaw_research_agent.py` |
| Minibook | `events:tasks:minibook` | MinibookBackendAgent | `minibook.*` | `python/spaces/minibook/agents/minibook_agent.py` |
| Schedule | `events:tasks:schedule` | ScheduleBackendAgent | `schedule.*` | `python/spaces/schedule/agents/schedule_agent.py` |
| N8n | `events:tasks:n8n` | N8nBackendAgent | `n8n.*` | `python/spaces/n8n/agents/n8n_agent.py` |
| AgentFarm | `events:tasks:agentfarm` | AgentFarmBackendAgent | `agentfarm.*` | `python/spaces/autogen/agents/agentfarm_agent.py` |
| Video | `events:tasks:video` | VideoBackendAgent | `video.*` | `python/spaces/video/agents/video_agent.py` |
| MiroFish | `events:tasks:mirofish_pred` | MiroFishBackendAgent | `mirofish.*` | `python/spaces/mirofish/agents/mirofish_agent.py` |
| Flowzen | via submodule | FlowzenAgent | `flowzen.*` | `python/spaces/flowzen/agents/flowzen_agent.py` |
| Brain | — (standalone microservices) | — | — | `python/spaces/brain/` (Tahlamus submodule) |

> **Note:** Shuttles (`python/spaces/shuttles/`) contains only the SWE Design submodule and has no dedicated backend agent. Shuttle events (`bubble.evaluate`, `bubble.promote`) are handled by BubblesAgent.
> **Note:** Brain is a standalone neuroscience-inspired cognitive system with its own microservices (ports 5000-5002), not a traditional backend agent.

### Intent Classification

User input is classified by `IntentClassifier` into structured event types:

**Bubble Events:**

```
"Zeig mir meine Bubbles"       → bubble.list
"Erstelle Bubble Marketing"    → bubble.create  {"title": "Marketing"}
"Geh in Marketing"             → bubble.enter   {"bubble_name": "Marketing"}
"Zurück"                       → bubble.exit
```

**Idea Events:**

```
"Notiere: API Design"          → idea.create    {"title": "API Design"}
"Zeig alle Ideen"              → idea.list
"Verlinke die Ideen sinnvoll"  → idea.auto_link
"Formatiere in Aktionslisten"  → idea.format    {"format_type": "action_list"}
```

**Code Events:**

```
"Erstelle eine App für X"      → code.generate  {"description": "X"}
"Wie ist der Code-Status?"     → code.status
```

**Desktop Events:**

```
"Öffne Chrome"                 → desktop.open_app  {"app_name": "Chrome"}
"Klick auf OK"                 → desktop.click     {"element": "OK"}
"Screenshot"                   → desktop.screenshot
```

**N8n Events:**

```
"Erstelle einen Workflow für X" → n8n.generate   {"description": "X"}
"Zeig alle Workflows"           → n8n.list
"Aktiviere Workflow Y"          → n8n.activate   {"name": "Y"}
"N8n Status"                    → n8n.status
```

**AgentFarm Events:**

```
"Erstelle ein Agent-Team"       → agentfarm.create_team {"team_name": "..."}
"Starte das Team"               → agentfarm.run         {"team_id": "...", "task": "..."}
"Agent Farm Status"             → agentfarm.status
"Welche Teams gibt es?"         → agentfarm.list_teams
```

**Key File:** [python/swarm/orchestrator/intent_classifier.py](python/swarm/orchestrator/intent_classifier.py) - Contains full `CLASSIFIER_PROMPT_TEMPLATE` with all event types.

### Backend Agent Execution

Backend agents listen to Redis streams (or run sync in FORCE_SYNC_MODE) and execute tools:

```python
# BaseBackendAgent pattern
class IdeasBackendAgent(BaseBackendAgent):
    stream = "events:tasks:ideas"

    TOOL_MAP = {
        "bubble.create": "create_bubble",
        "bubble.enter": "enter_bubble",
        "idea.create": "create_idea_tool",
        # ...
    }

    PARAM_MAPPING = {
        "bubble.enter": {"title": "bubble_name"},  # classifier → tool param
    }
```

**Key Files:**

| Component | File |
| --------- | ---- |
| Base Agent | `python/swarm/backend_agents/base_agent.py` |
| Agent Registry | `python/swarm/backend_agents/__init__.py` |
| Bubbles Agent | `python/spaces/ideas/agents/bubbles_agent.py` |
| Ideas Agent | `python/spaces/ideas/agents/ideas_agent.py` |
| Coding Agent | `python/spaces/coding/agents/coding_agent.py` |
| Desktop Agent | `python/spaces/desktop/agents/desktop_agent.py` |
| Roarboot Agent | `python/spaces/rowboat/agents/roarboot_agent.py` |
| ZeroClaw Agent | `python/spaces/research/agents/zeroclaw_research_agent.py` |
| Minibook Agent | `python/spaces/minibook/agents/minibook_agent.py` |
| Schedule Agent | `python/spaces/schedule/agents/schedule_agent.py` |
| N8n Agent | `python/spaces/n8n/agents/n8n_agent.py` |
| AgentFarm Agent | `python/spaces/autogen/agents/agentfarm_agent.py` |

### Orchestration Flow (Detailed)

```
1. User speaks → OpenAI Realtime API (speech-to-speech)
   OR: User types in Game Console → process_intent(text)

2. IntentOrchestrator receives text:
   ├── (Optional) CollectorAgent: Accumulate fragments
   ├── (Optional) IntentEnhancer: Fix ASR errors
   └── IntentClassifier: Classify to event_type + payload

3. MinibookHub routing (USE_MINIBOOK_HUB=true — PRIMARY MODE):
   ├── EnrichmentPipeline:
   │   ├── ContextGather: conversation history, bubble state, user prefs
   │   ├── SpaceRouter: LLM or deterministic → which space(s)?
   │   └── TaskEnricher: build per-agent payloads with context
   ├── POST task to Minibook API with @agent mentions
   ├── SpaceMinibookResponders receive @mentions:
   │   ├── Parse enriched JSON (event_type + payload)
   │   └── Execute via orchestrator with domain_hint
   └── ResultAggregator:
       ├── Single-space: sync-wait up to 10s
       └── Multi-space: async-poll up to 120s

4. Direct fallback (USE_MINIBOOK_HUB=false):
   ├── SYNC mode: Execute tool directly
   └── ASYNC mode: Publish to Redis stream

5. Result:
   ├── Broadcast to Electron (node_added, etc.)
   ├── inject_system_message() → Rachel speaks immediately
   └── OR: NotificationQueue → Rachel picks up next turn
```

**Key Files:**

| Component | File |
| --------- | ---- |
| Orchestrator | `python/swarm/orchestrator/intent_orchestrator.py` |
| Classifier | `python/swarm/orchestrator/intent_classifier.py` |
| RAG Classifier | `python/swarm/orchestrator/rag_intent_classifier.py` |
| Tool Orchestrator (multi-step) | `python/swarm/orchestrator/tool_orchestrator.py` |
| Reference Resolver (DroPE) | `python/swarm/orchestrator/reference_resolver.py` |
| Response Generator | `python/swarm/orchestrator/response_generator.py` |
| System Context Store | `python/swarm/orchestrator/system_context_store.py` |
| Notification Queue (V2) | `python/swarm/orchestrator/notification_queue.py` |
| Question Queue | `python/swarm/orchestrator/question_queue.py` |
| Tool Definitions | `python/swarm/orchestrator/tool_definitions.py` |
| Event Router | `python/swarm/event_team/event_router.py` |
| Event Bus | `python/swarm/event_bus.py` |
| MinibookHub | `python/spaces/minibook/minibook_hub.py` |
| Enrichment Pipeline | `python/spaces/minibook/enrichment/pipeline.py` |
| Space Router | `python/spaces/minibook/enrichment/space_router.py` |
| Context Gather | `python/spaces/minibook/enrichment/context_gather.py` |
| Task Enricher | `python/spaces/minibook/enrichment/task_enricher.py` |
| Rachel Interface | `python/spaces/minibook/rachel_interface.py` |
| Result Aggregator | `python/spaces/minibook/result_aggregator.py` |
| Minibook Workers | `python/spaces/minibook/workers/minibook_workers.py` |
| Minibook Client | `python/spaces/minibook/tools/minibook_client.py` |

### Input Enhancement Pipeline (Optional)

Pre-processes voice input before classification:

1. **CollectorAgent** - Accumulates fragmented speech (<3 words)
2. **IntentEnhancer** - Fixes ASR errors using learned rules, normalizes dialects
3. **ExecutionValidator** - Validates results, triggers learning feedback

Files in `python/swarm/agents/`

### Tool System

Tools are Python functions that agents can call. Two types:

**Backend Tools** (executed via swarm)

Tools live in two locations:
- **Shared tools:** `python/tools/` (22 files — cross-space utilities)
- **Space-specific tools:** `python/spaces/*/tools/` (per-space implementations)

**Shared tools (`python/tools/`):**

| Tool Module | Purpose |
| ----------- | ------- |
| `workspace_tools.py` | Workspace management (29KB) |
| `navigation_tools.py` | Space navigation |
| `conversation_tools.py` | Conversation management |
| `session_tools.py` | Session lifecycle |
| `memory_tools.py` | Memory services |
| `task_memory_tools.py` | Supermemory task tracking |
| `supermemory_tools.py` | Supermemory integration |
| `system_status_tools.py` | System health |
| `task_status_tools.py` | Task status monitoring |
| `handoff_tools.py` | Agent transfers |
| `transfer_handler.py` | Agent transfer handling |
| `worker_queue.py` | Async work queue (29KB) |
| `browser_worker.py` | Headless browser automation (13KB) |
| `index_mapping.py` | Event type → tool mapping |
| `moire_tools.py` | MoireTracker integration |
| `bubble_requirements_tool.py` | Shuttle pipeline requirements |
| `bubble_tools.py` | Bubble stubs (actual in spaces/ideas/) |
| `idea_tools.py` | Idea stubs (actual in spaces/ideas/) |
| `summary_tools.py` | LLM summaries |
| `structured_formatting_tools.py` | Format ideas |
| `format_dispatcher.py` | Format routing |

**Space-specific tools** (in `python/spaces/*/tools/`): Each space has its own tools directory with adapted implementations. See `docs/python/spaces/` for details.

### Database

SQLite: `python/vibemind.db`

**Schema (v14, 21 tables):**

| Table | Purpose | Key Columns |
| ----- | ------- | ----------- |
| `ideas` | Bubbles and ideas | `id`, `title`, `description`, `parent_id`, `score`, `status`, `promoted_to_project_id`, `embedding_vector` |
| `projects` | Code generation | `id`, `name`, `generation_status`, `vnc_port`, `preview_url`, `tech_stack`, `created_at`, `metadata` |
| `canvas_nodes` | Visual nodes | `id`, `node_type`, `linked_idea_id`, `x`, `y`, `format_schema`, `content_json`, `summary`, `metadata` |
| `canvas_edges` | Node connections | `from_node_id`, `to_node_id`, `edge_type` |
| `conversation_sessions` | Chat sessions | `id`, `started_at`, `agent_id`, `metadata` |
| `conversation_history` | Chat history | `session_id`, `speaker`, `text`, `timestamp` |
| `shuttles` | Requirements pipeline | `shuttle_id`, `bubble_id`, `current_stage`, `stage_type`, `stage_data`, `passed_count`, `failed_count`, `total_count` |
| `exploration_sessions` | AI-Scientist runs | `root_bubble_id`, `status`, `total_nodes_explored`, `best_score` |
| `exploration_nodes` | Exploration tree nodes | `session_id`, `source_bubble_id`, `target_bubble_id`, `combined_score` |
| `discovered_edges` | Permanent semantic links | `from_idea_id`, `to_idea_id`, `edge_label`, `confidence` |
| `mermaid_diagrams` | Generated diagrams | `title`, `diagram_type`, `content`, `source_idea_id` |
| `scheduled_tasks` | APScheduler tasks | `title`, `action_text`, `trigger_type`, `trigger_config`, `status` |
| `schema_version` | Schema migration tracking | `version` |
| `user_preferences` | User settings | `key`, `value` |
| `intent_analysis_log` | Intent classification audit | `event_type`, `user_input`, `confidence` |
| `intent_corrections` | Classification corrections | `original_event`, `corrected_event` |
| `synthetic_utterances` | Training utterances | `utterance`, `event_type` |
| `evaluation_runs` | Evaluation sessions | `id`, `status`, `total_cases` |
| `evaluation_results` | Evaluation outcomes | `run_id`, `event_type`, `score` |
| `persistent_tasks` | Long-running task state | `task_id`, `status`, `result` |
| `conversion_ai_personalities` | AI personality configs | `name`, `config` |

**Repository Pattern:**

```python
from data import IdeasRepository, CanvasRepository

ideas_repo = IdeasRepository()
idea = ideas_repo.create(title="My Idea")
ideas_repo.get_by_title_fuzzy("my idea")  # Accent-insensitive search
```

**Key Files:**

- [python/data/database.py](python/data/database.py) - Connection, schema, migrations
- [python/data/models.py](python/data/models.py) - Dataclasses
- [python/data/repository.py](python/data/repository.py) - CRUD operations

### Electron + Python IPC

```
Electron Main ──spawn──→ Python Backend (stdin/stdout JSON)
     ↓                            ↓
 Renderer (Three.js)      Tool Execution + DB
```

**Message Types (Python → Electron):**

```python
# Broadcast to Electron UI
_broadcast_to_electron({
    "type": "node_added",
    "node": {"id": "abc", "title": "My Idea", "x": 100, "y": 200}
})
```

| Message Type | Purpose |
| ------------ | ------- |
| `node_added` | New bubble/idea created |
| `node_removed` | Bubble/idea deleted |
| `node_updated` | Bubble/idea metadata changed |
| `node_structured_update` | Rich content update (format + content_json) |
| `edge_added` / `edge_created` | Connection created |
| `edge_deleted` | Connection removed |
| `space_changed` | Navigate to bubble |
| `canvas_refresh` | Full canvas reload |
| `navigate_to_space` | Navigate to named space |
| `agent_transfer_complete` | Voice agent transfer done |
| `project_created` | New coding project |
| `project_status_update` | Code gen progress |
| `project_preview_ready` | VNC preview available |
| `shuttle_launched` | Shuttle pipeline started |
| `shuttle_stage_update` | Pipeline stage progress |
| `exploration_update` | AI-Scientist exploration step |
| `schedule_created` | New scheduled task |
| `roarboot_result` | Rowboat query result |
| `voice_end_requested` | Voice session stop |

**Key Files:**

- [electron-app/main.js](electron-app/main.js) - Python spawning, IPC routing
- [python/electron_backend.py](python/electron_backend.py) - Message handler
- [electron-app/renderer/glass_bubbles.js](electron-app/renderer/glass_bubbles.js) - 3D rendering

### ClawPort Dashboard

A standalone Vite + React dashboard embedded as a BrowserView overlay via `ClawPortManager`. Provides system monitoring and text-based interaction as an alternative to voice.

**4 Dashboard Tabs:**

| Tab | Feature | Python Handler | IPC Messages |
|-----|---------|---------------|-------------|
| Schedule | APScheduler task list + pause/resume | `_handle_get_scheduled_tasks` | `get_scheduled_tasks`, `update_task_status` |
| Agents | 8 backend agent status cards (live dots) | `_handle_get_agent_status_sync` | `get_agent_status` |
| Chat | Text input → same `process_intent` as voice | `_handle_chat_text_input` | `chat_text_input`, `get_conversation_history` |
| Memory | Supermemory service overview + search | `_handle_get_memory_overview` | `get_memory_overview`, `search_memory`, `get_recent_memory` |

**Architecture:**

```
ClawPort React App (dashboard/dist/index.html)
  → window.vibemindDashboard (clawport-preload.js)
    → ipcRenderer.invoke('clawport:*')
      → main.js sendToPythonAndWait()
        → Python electron_backend.py handlers
```

**Key Files:**

| Component | File |
|-----------|------|
| BrowserView Manager | `electron-app/clawport-manager.js` |
| Preload (IPC API) | `electron-app/clawport-preload.js` |
| React App | `electron-app/dashboard/src/App.tsx` |
| IPC Hooks | `electron-app/dashboard/src/hooks/useIPC.ts` |
| TypeScript Types | `electron-app/dashboard/src/types.ts` |
| Schedule UI | `electron-app/dashboard/src/features/ScheduleMonitor.tsx` |
| Agent Status UI | `electron-app/dashboard/src/features/AgentStatus.tsx` |
| Chat UI | `electron-app/dashboard/src/features/ChatPanel.tsx` |
| Memory UI | `electron-app/dashboard/src/features/MemoryBrowser.tsx` |
| CSS Design System | `electron-app/dashboard/src/styles/globals.css` |

**Build:**

```bash
cd electron-app
npm run dashboard:build   # Build to dashboard/dist/
npm run dashboard:dev     # Vite dev server with hot-reload
```

**BrowserView Mutual Exclusion:** All 4 managers (Dashboard, Rowboat, SweDesign, ClawPort) hide each other when any one is shown.

### Memory System (Optional)

Supermemory integration for semantic memory:

| Service | File | Purpose |
| ------- | ---- | ------- |
| TaskMemory | `python/memory/task_memory_service.py` | Task event tracking |
| ConversationMemory | `python/memory/conversation_memory_service.py` | Cross-session context |
| UserProfile | `python/memory/user_profile_service.py` | Preference learning |
| ConversationRouter | `python/memory/conversation_router.py` | RAG-based routing |

Enable via `.env`:

```bash
USE_TASK_MEMORY=true
USE_CONVERSATION_MEMORY=true
USE_USER_PROFILES=true
USE_RAG_CLASSIFIER=true
SUPERMEMORY_API_KEY=xxx
```

## Common Commands

```bash
# Electron app (starts Python backend + voice automatically)
cd electron-app && npm start

# Test agent registry
cd python && python -m agents

# Run agent setup
cd python && python -m agents.setup

# Check audio devices
python -c "import sounddevice as sd; print(sd.query_devices())"

# Electron build
cd electron-app && npm run build:win   # Windows installer
cd electron-app && npm run build:mac   # macOS DMG
cd electron-app && npm run build:linux # Linux AppImage

# Debug startup
start_vibemind_debug.bat               # With debug ports (CDP 9222)
start_vibemind_production.bat          # Headless mode
```

## Testing

Tests are in `python/tests/`. Run individual tests:

```bash
cd python
python -m tests.test_data_layer        # Data layer tests
python -m tests.test_desktop_tools     # Desktop automation tests
python -m tests.test_intent_to_tool    # Intent routing tests
python -m tests.test_integration_e2e   # End-to-end tests
python -m tests.test_agent_transfers   # Agent transfer tests
```

## Configuration Reference

See `.env.example` for all 60+ variables. Key groups:

```bash
# Voice Provider (OpenAI Realtime)
OPENAI_API_KEY=sk-xxx

# Execution Mode
FORCE_SYNC_MODE=true         # false enables Redis-based async execution

# Voice Bridge V2 (async notification mode)
USE_VOICE_BRIDGE_V2=false

# Orchestrator Features
USE_RAG_CLASSIFIER=true      # Semantic classification via Supermemory
USE_DROPE_RESOLVER=false     # Reference resolution (requires torch)
USE_BROADCAST_MODE=false     # Fan-out to all agents for profiling

# Memory Services
USE_TASK_MEMORY=true
USE_CONVERSATION_MEMORY=true
USE_USER_PROFILES=true
SUPERMEMORY_API_KEY=xxx

# Performance
FAST_STARTUP=true            # Skips Supermemory API calls at startup

# LLM
OPENROUTER_API_KEY=xxx
RAG_CLASSIFIER_MODEL=openai/gpt-4o

# Spaces & Routing
MINIBOOK_ENABLED=true        # Minibook collaboration system (requires Docker)
USE_MINIBOOK_HUB=true        # PRIMARY: Route ALL intents through MinibookHub
MINIBOOK_URL=http://localhost:3480  # Minibook REST API (docker-compose.minibook.yml)
SCHEDULE_ENABLED=false       # APScheduler-based scheduling
USE_ZEROCLAW=false           # ZeroClaw web research
ROWBOAT_PUBLISH_ENABLED=true # Publish metadata to knowledge graph

# Database (optional)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=xxx

# Optional
CODING_ENGINE_PATH=C:\path\to\Coding_engine
VNC_BASE_URL=https://preview.vibemind.io/vnc
REQ_ORCHESTRATOR_URL=http://localhost:8087
```

Full reference: [docs/configuration.md](docs/configuration.md)

## Key Patterns

### Adding a New Event Type

1. Add to `CLASSIFIER_PROMPT_TEMPLATE` in `intent_classifier.py`
2. Add tool function in `python/tools/`
3. Add mapping in backend agent's `TOOL_MAP`
4. Add param normalization in `PARAM_MAPPING` if needed

### Adding a New Tool

1. Create function in `python/tools/my_tool.py`
2. Return dict with `success`, `message`, and data
3. Call `_broadcast_to_electron()` for UI updates

```python
def my_tool(param1: str) -> Dict[str, Any]:
    # Do work
    _broadcast_to_electron({"type": "node_added", "node": {...}})
    return {"success": True, "message": "Done", "data": {...}}
```

### Adding a Backend Agent

1. Create space directory in `python/spaces/<your_space>/agents/`
2. Subclass `BaseBackendAgent` (`python/swarm/backend_agents/base_agent.py`)
3. Define `stream`, `name`, `TOOL_MAP`, `PARAM_MAPPING`
4. Implement `_load_tools()` and `_get_tool_name()`
5. Add stream constant and event mappings in `event_router.py`
6. Register lazy import in `python/swarm/backend_agents/__init__.py`

### Tool Definition Format

```python
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "What this tool does",
        "parameters": {
            "type": "object",
            "properties": {...},
            "required": [...]
        }
    }
}
```

## DroPE Reference Resolution

Resolves ambiguous references ("das", "es", "nochmal") using conversation context.

**Key File:** `python/swarm/orchestrator/reference_resolver.py`

**How it works:**

1. User says "Mach das nochmal" (Do that again)
2. DroPEReferenceResolver checks conversation history
3. Resolves to concrete action: "Stopp den Container xyz"
4. IntentClassifier receives resolved text

**Configuration:**

```bash
USE_DROPE_RESOLVER=true
DROPE_MODEL=SakanaAI/DroPE-SmolLM-135M-32K
```

See [docs/DROPE_INTEGRATION.md](docs/DROPE_INTEGRATION.md) for detailed architecture and implementation.
