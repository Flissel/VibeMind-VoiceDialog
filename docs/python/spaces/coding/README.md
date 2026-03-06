# Coding Space

The Coding space handles code generation, project management, and integration with the external Coding_engine submodule. It allows users to voice-command the creation and management of software projects.

## Directory Structure

```
python/spaces/coding/
├── __init__.py
├── README.md
├── Coding_engine/              # Git submodule (external code generation engine)
├── agents/                     # Backend agents
│   ├── __init__.py
│   ├── coding_agent.py         # CodingAgent (code.* events)
│   └── coding_swarm_agent.py   # CodingSwarmAgent (multi-step orchestration)
├── broadcast/                  # Broadcast profiling
│   ├── __init__.py
│   └── coding_broadcast_agent.py
├── engine/                     # Coding engine interface
│   ├── __init__.py
│   └── coding_engine_runner.py # Runner that interfaces with Coding_engine submodule
├── sub_agents/                 # Sub-agents for complex workflows
│   ├── __init__.py
│   └── coding_sub_agents.py
├── tools/                      # Tool implementations
│   ├── __init__.py
│   ├── adapted_coding_tools.py # Adapted tool wrappers
│   ├── coding_tools.py         # Core coding tools
│   └── voice_coding_tools.py   # Voice-specific coding tools
└── workers/                    # Background workers
    ├── __init__.py
    └── coding_workers.py
```

## Agents

### CodingAgent (`agents/coding_agent.py`)

Handles all `code.*` events (9 event types):

- `code.generate` -- Generate a new project from description
- `code.status` -- Check project generation status
- `code.list` -- List all projects
- `code.preview` -- Open project preview
- `code.deploy` -- Deploy a project
- And more

Stream: `events:tasks:coding`

### CodingSwarmAgent (`agents/coding_swarm_agent.py`)

Orchestrates multi-step coding workflows (e.g., "create a project, wait for generation, then open preview").

## Engine

### `coding_engine_runner.py`

The bridge between VibeMind and the Coding_engine submodule. This runner:

- Spawns the Coding_engine process
- Sends generation requests
- Monitors progress and status
- Returns results to the CodingAgent

The Coding_engine submodule lives at `python/spaces/coding/Coding_engine/` and must be initialized via `git submodule update --init`.

## Tools

| Tool File | Key Functions | Purpose |
|-----------|---------------|---------|
| `coding_tools.py` | `generate_code`, `get_code_status`, `list_projects` | Core code generation and project management |
| `adapted_coding_tools.py` | Adapted wrappers | Adapts tool signatures for the backend agent pattern |
| `voice_coding_tools.py` | Voice-specific helpers | Tools optimized for voice interaction (shorter responses, confirmations) |

## Workers

`coding_workers.py` -- Background processing for long-running code generation tasks, status polling, and project cleanup.

## Broadcast

`coding_broadcast_agent.py` -- Broadcasts coding events to the Electron UI, including project creation notifications and generation progress updates.

## Submodule

The Coding_engine submodule is the external code generation engine:

- **Path:** `python/spaces/coding/Coding_engine/`
- **Upstream:** https://github.com/Flissel/Coding_engine.git
- **Initialize:** `git submodule update --init python/spaces/coding/Coding_engine`

See [docs/submodules/coding-engine.md](../../submodules/coding-engine.md) for details.

## Configuration

Relevant `.env` settings:

```bash
CODING_ENGINE_PATH=C:\path\to\Coding_engine   # Override submodule path
VNC_BASE_URL=https://preview.vibemind.io/vnc   # Preview URL base
```
