# Python Tools

The `python/tools/` directory contains 22 shared tool modules used across the voice dialog system. These are cross-space utilities -- domain-specific tool implementations live in `python/spaces/*/tools/`.

## Dual-Location Pattern

Several tool files in `python/tools/` are **backward-compatibility stubs** that re-export from their actual implementations in `python/spaces/`. This allows old import paths to continue working after the migration to the spaces architecture.

Stub files (re-export only):
- `bubble_tools.py` -> `spaces/ideas/tools/bubble_tools.py`
- `idea_tools.py` -> `spaces/ideas/tools/idea_tools.py`
- `summary_tools.py` -> `spaces/ideas/tools/summary_tools.py`
- `structured_formatting_tools.py` -> `spaces/ideas/tools/structured_formatting_tools.py`
- `format_dispatcher.py` -> `spaces/ideas/tools/format_dispatcher.py`
- `moire_tools.py` -> `spaces/desktop/tools/moire_tools.py`

## Tool Index

### Core Tools

| File | Description |
|------|-------------|
| `bubble_tools.py` | Bubble CRUD operations (stub -- real impl in `spaces/ideas/tools/`) |
| `idea_tools.py` | Idea/note CRUD operations (stub -- real impl in `spaces/ideas/tools/`) |
| `summary_tools.py` | LLM-based bubble and idea summarization (stub -- real impl in `spaces/ideas/tools/`) |
| `structured_formatting_tools.py` | Format ideas into action lists, mind maps, etc. (stub -- real impl in `spaces/ideas/tools/`) |
| `format_dispatcher.py` | Routes formatting requests to appropriate formatters (stub -- real impl in `spaces/ideas/tools/`) |
| `bubble_requirements_tool.py` | Generates requirements from bubble contents for multi-agent processing |
| `workspace_tools.py` | ElevenLabs client tools for ideas, projects, and canvas operations |

### Memory Tools

| File | Description |
|------|-------------|
| `memory_tools.py` | Desktop command history storage and retrieval via Supermemory |
| `supermemory_tools.py` | Voice-callable semantic search and storage in Supermemory |
| `task_memory_tools.py` | Voice-callable task history queries ("Was habe ich heute gemacht?") |

### Voice / Agent Tools

| File | Description |
|------|-------------|
| `client_tools_manager.py` | Registration and routing of ElevenLabs client tools to agents |
| `transfer_handler.py` | Agent switching coordination (monitors pending switch signals) |
| `session_tools.py` | Voice session management (timeout handling, restart, status) |
| `conversation_tools.py` | Capture and transfer conversation content to canvas nodes |
| `navigation_tools.py` | Voice-controlled UI navigation (space navigation, item selection) |
| `handoff_tools.py` | Desktop automation via pyautogui (click, type, scroll, screenshot) |
| `moire_tools.py` | Screen element detection via Moire (stub -- real impl in `spaces/desktop/tools/`) |

### Utility Tools

| File | Description |
|------|-------------|
| `index_mapping.py` | Voice-based referencing by number ("geh in 2", "connect 3 and 4") |
| `system_status_tools.py` | Query system state, check for stuck operations, performance insights |
| `task_status_tools.py` | Monitor task execution (active tasks, queue statistics) |
| `worker_queue.py` | Fast ElevenLabs task seeding -- returns immediately while queueing work |
| `browser_worker.py` | Playwright-based browser automation for image search and web fetching |
| `__init__.py` | Package init (documents cross-cutting tool purpose) |

## Tool Return Convention

All backend tools return a dictionary with at minimum:

```python
{
    "success": True,       # or False
    "message": "...",      # Human-readable result description
    "data": { ... }        # Optional structured data
}
```

Tools that modify the UI also call `_broadcast_to_electron()` to push updates to the Electron renderer.
