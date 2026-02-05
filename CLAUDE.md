# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**VibeMind Voice Dialog** is a voice-controlled workspace where ElevenLabs voice agents capture user input and route it through a swarm backend for execution.

**Current Architecture:**

- **4 ElevenLabs Voice Agents** - Rachel (entry), Alice (coordinator), Adam (desktop), Antoni (coding)
- **Intent Classification** - LLM-based classification of natural language to event types
- **Swarm Backend** - Executes tools via domain-specific backend agents
- **Electron UI** - 3D multiverse with bubbles (ideas) rendered via Three.js

## Quick Start

### Voice Dialog Only

```bash
cd python
python voice_dialog_main.py
```

### Full System (Electron UI)

```bash
cd electron-app
npm install  # first time only
npm start    # spawns Python backend automatically
```

### Configuration

Copy `.env.example` to `.env`:

```bash
# Required
ELEVENLABS_API_KEY=xxx
AGENT_MULTIVERSE=agent_xxx  # Rachel's agent ID

# Default: sync mode (no Redis required)
FORCE_SYNC_MODE=true
```

## Architecture

### Main Flow

```
User Voice → Rachel (ElevenLabs Voice Agent)
                    ↓
            Intent Classification
            (LLM classifies to event_type + payload)
                    ↓
            Event Routing (event_type → stream)
                    ↓
    ┌───────────────┼───────────────┐
    ↓               ↓               ↓
IdeasAgent    CodingAgent    DesktopAgent
(ideas.*)     (code.*)       (desktop.*)
    ↓               ↓               ↓
    └───────────────┼───────────────┘
                    ↓
            Electron UI (3D Bubbles)
```

### Multi-Agent System

4 ElevenLabs voice agents with transfer capabilities:

```
Rachel (Entry) ──transfer──► Alice (Hub)
                               │
                    ┌──────────┴──────────┐
                    ▼                      ▼
               Adam (Desktop)        Antoni (Coding)
```

| Agent | Role | Transfers To |
|-------|------|--------------|
| Rachel | Multiverse Navigator (Entry) | Alice |
| Alice | Coordinator Hub | Adam, Antoni, Rachel |
| Adam | Desktop Worker | Alice |
| Antoni | Coding/Writing | Alice |

Agent configs: `python/agents/{name}/config.py` + `prompts.py` + `tools.py`

### Three Spaces (Domains)

VibeMind has 3 main workspaces, each handled by a backend agent:

| Space | Domain | Backend Agent | Purpose |
| ----- | ------ | ------------- | ------- |
| IDEAS | `bubble.*`, `idea.*` | IdeasAgent | Bubble/idea management |
| CODING | `code.*` | CodingAgent | Code generation |
| DESKTOP | `desktop.*` | DesktopAgent | System automation |

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
| Ideas Agent | `python/swarm/backend_agents/ideas_agent.py` |
| Coding Agent | `python/swarm/backend_agents/coding_agent.py` |
| Desktop Agent | `python/swarm/backend_agents/desktop_agent.py` |

### Orchestration Flow (Detailed)

```
1. User speaks → Rachel (ElevenLabs)
2. Rachel calls swarm_entry tool with user_text

3. IntentOrchestrator receives text:
   ├── (Optional) CollectorAgent: Accumulate fragments
   ├── (Optional) IntentEnhancer: Fix ASR errors
   └── IntentClassifier: Classify to event_type + payload

4. Event routing:
   ├── SYNC mode: Execute tool directly
   └── ASYNC mode: Publish to Redis stream

5. Backend Agent:
   ├── Map event_type → tool function (TOOL_MAP)
   ├── Normalize params (PARAM_MAPPING)
   └── Execute tool

6. Result:
   ├── Broadcast to Electron (node_added, etc.)
   └── Return response_hint to Rachel
```

**Key Files:**

| Component | File |
| --------- | ---- |
| Orchestrator | `python/swarm/orchestrator/intent_orchestrator.py` |
| Classifier | `python/swarm/orchestrator/intent_classifier.py` |
| Tool Orchestrator (multi-step) | `python/swarm/orchestrator/tool_orchestrator.py` |
| Event Router | `python/swarm/event_team/event_router.py` |
| Event Bus | `python/swarm/event_bus.py` |
| Swarm Entry Tool | `python/tools/swarm_entry.py` |

### Input Enhancement Pipeline (Optional)

Pre-processes voice input before classification:

1. **CollectorAgent** - Accumulates fragmented speech (<3 words)
2. **IntentEnhancer** - Fixes ASR errors using learned rules, normalizes dialects
3. **ExecutionValidator** - Validates results, triggers learning feedback

Files in `python/swarm/agents/`

### Tool System

Tools are Python functions that agents can call. Two types:

**1. ElevenLabs Client Tools** (voice agent calls directly)

- Registered via `ClientToolsManager`
- Used for session control, transfers

**2. Backend Tools** (executed via swarm)

- Located in `python/tools/`
- Mapped from event types in backend agents

| Tool Module | Purpose | Key Functions |
| ----------- | ------- | ------------- |
| `bubble_tools.py` | Bubble CRUD | `create_bubble`, `enter_bubble`, `list_bubbles` |
| `idea_tools.py` | Idea CRUD | `create_idea_tool`, `auto_link_ideas` |
| `coding_tools.py` | Code generation | `generate_code`, `get_code_status` |
| `desktop_tools.py` | Desktop automation | `open_app`, `click`, `type_text` |
| `summary_tools.py` | LLM summaries | `summarize_bubble` |
| `structured_formatting_tools.py` | Format ideas | `format_idea_content` |

### Database

SQLite: `python/vibemind.db`

**Schema:**

| Table | Purpose | Key Columns |
| ----- | ------- | ----------- |
| `ideas` | Bubbles and ideas | `id`, `title`, `description`, `parent_id`, `format_schema`, `content_json` |
| `projects` | Code generation | `id`, `name`, `generation_status`, `vnc_port`, `preview_url` |
| `canvas_nodes` | Visual nodes | `id`, `node_type`, `linked_idea_id`, `x`, `y` |
| `canvas_edges` | Node connections | `from_node_id`, `to_node_id`, `edge_type` |
| `conversation_sessions` | Chat sessions | `id`, `started_at`, `agent_id` |
| `conversation_messages` | Chat history | `session_id`, `speaker`, `text` |
| `shuttles` | Requirements pipeline | `shuttle_id`, `bubble_id`, `current_stage` |

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
| `edge_added` | Connection created |
| `space_changed` | Navigate to bubble |
| `node_structured_update` | Rich content update |

**Key Files:**

- [electron-app/main.js](electron-app/main.js) - Python spawning, IPC routing
- [python/electron_backend.py](python/electron_backend.py) - Message handler
- [electron-app/renderer/glass_bubbles.js](electron-app/renderer/glass_bubbles.js) - 3D rendering

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
# Voice dialog standalone
cd python && python voice_dialog_main.py

# Electron app
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

# Deploy client tools to ElevenLabs
cd python && python deploy_client_tools.py --show
cd python && python deploy_client_tools.py --deploy

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

```bash
# Required
ELEVENLABS_API_KEY=xxx
AGENT_MULTIVERSE=agent_xxx

# Execution Mode
FORCE_SYNC_MODE=true         # false enables Redis-based async execution

# Orchestrator Features
USE_TOOL_ORCHESTRATOR=true   # Claude Sonnet for multi-step requests
USE_INTENT_ANALYSIS=true     # Multi-agent intent analysis
USE_RAG_CLASSIFIER=true      # Semantic classification

# Memory Services
USE_TASK_MEMORY=true
USE_CONVERSATION_MEMORY=true
USE_USER_PROFILES=true
SUPERMEMORY_API_KEY=xxx

# Performance
FAST_STARTUP=true            # Skips Supermemory API calls at startup

# LLM
OPENROUTER_API_KEY=xxx

# Optional
CODING_ENGINE_PATH=C:\path\to\Coding_engine
VNC_BASE_URL=https://preview.vibemind.io/vnc
```

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

1. Subclass `BaseBackendAgent` in `python/swarm/backend_agents/`
2. Define `stream`, `name`, `TOOL_MAP`, `PARAM_MAPPING`
3. Implement `_load_tools()` and `_get_tool_name()`
4. Add routing in `event_router.py`

### Tool Definition Format (ElevenLabs)

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
