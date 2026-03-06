# Electron ↔ Python IPC

## Overview

Electron spawns Python as a child process. Communication uses stdin/stdout with JSON-encoded messages, one per line.

```
Electron Main ──spawn──► Python Backend (electron_backend.py)
     │                          │
     │   stdin (JSON commands)  │
     │ ◄─────────────────────── │
     │   stdout (JSON events)   │
     │ ─────────────────────────►│
     │                          │
 Renderer (Three.js)     Tool Execution + DB
```

## Message Format

All messages are JSON objects with a `type` field:

```json
{"type": "node_added", "node": {"id": "abc", "title": "My Idea", "x": 100, "y": 200}}
```

## Python → Electron Messages

| Type | Payload | When |
|------|---------|------|
| `node_added` | `{node: {id, title, type, x, y, ...}}` | Bubble/idea created |
| `node_removed` | `{node_id: "abc"}` | Bubble/idea deleted |
| `node_updated` | `{node: {id, title, ...}}` | Bubble/idea modified |
| `node_structured_update` | `{node_id, format_schema, content_json}` | Rich content update (formatted idea) |
| `edge_added` | `{edge: {from_id, to_id, type}}` | Connection created |
| `edge_removed` | `{from_id, to_id}` | Connection removed |
| `space_changed` | `{bubble_id, bubble_name}` | Navigate into/out of bubble |
| `exploration_update` | `{session_id, nodes, edges, status}` | AI exploration progress |
| `code_status` | `{project_id, status, progress}` | Code generation progress |
| `error` | `{message, event_type}` | Tool execution error |

## Electron → Python Messages

| Type | Payload | Purpose |
|------|---------|---------|
| `voice_input` | `{text: "user said this"}` | Manual text input (bypass voice) |
| `navigate` | `{bubble_id}` | UI navigation event |
| `command` | `{action, params}` | Direct command execution |

## Broadcasting from Tools

Tools broadcast to Electron using the `_broadcast_to_electron` helper:

```python
from tools.bubble_tools import _broadcast_to_electron

def my_tool():
    # Do work...
    _broadcast_to_electron({
        "type": "node_added",
        "node": {"id": "123", "title": "New Idea", "x": 0, "y": 0}
    })
    return {"success": True, "message": "Done"}
```

## Key Files

| File | Role |
|------|------|
| `electron-app/main.js` | Spawns Python, routes IPC |
| `electron-app/preload.js` | Exposes IPC bridge to renderer |
| `python/electron_backend.py` | Receives commands, dispatches to orchestrator |
| `electron-app/renderer/glass_bubbles.js` | Handles incoming node/edge messages |
