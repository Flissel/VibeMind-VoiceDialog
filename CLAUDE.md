# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**VibeMind Voice Dialog** is a multi-agent voice-controlled workspace system powered by ElevenLabs Conversational AI. Users interact with specialized AI agents via voice to manage ideas, control their desktop, and generate code projects - all within a 3D "multiverse" UI.

**System Components:**
- 4 specialized ElevenLabs voice agents with distinct roles
- Electron app with Three.js 3D bubble navigation
- Python backend with SQLite persistence
- User-controlled agent transfers (voice handoffs)
- Optional: desktop automation, code generation, Supermemory

## Quick Start

### Voice Dialog Only (No UI)

```bash
cd python
python voice_dialog_main.py
```

### Full System (with Electron UI)

```bash
cd electron-app
npm install  # first time only
npm start    # spawns Python backend automatically
```

### Configuration

Copy `.env.example` to `.env` and set required values:

```bash
ELEVENLABS_API_KEY=xxx
AGENT_MULTIVERSE=agent_xxx  # Rachel's agent ID (entry agent)
```

## Architecture

### Multi-Agent System

```
User Voice → Rachel (Entry) → Alice (Coordinator)
                                    ↓
                    ┌───────────────┴───────────────┐
                    ↓                               ↓
               Adam (Desktop)                 Antoni (Coding)
```

| Agent | Role | Domain | Voice |
|-------|------|--------|-------|
| Rachel | Multiverse Navigator | Spaces, bubbles, ideas | Rachel |
| Alice | Coordinator Hub | Delegation, orchestration | Alice |
| Adam | Desktop Worker | System automation | Adam |
| Antoni | Coding Worker | Code generation | Antoni |

**Agent Registry:** [python/agents/__init__.py](python/agents/__init__.py)

Each agent has config in `python/agents/{name}/`:
- `config.py` - Agent ID, voice, tools, flags
- `prompts.py` - System prompt, first message

### Agent Transfers

Transfers are user-initiated. When an agent calls `transfer_to_X()`:
1. Transfer handler stores switch info
2. Watcher thread detects pending switch
3. Current conversation ends
4. New conversation starts with target agent

**Transfer Handler:** [python/tools/transfer_handler.py](python/tools/transfer_handler.py)

### Voice Dialog Flow

[python/voice_dialog_main.py](python/voice_dialog_main.py):

```
Microphone (16kHz) → ElevenLabs SDK → Agent Response → Speaker
                          ↓
                   ClientToolsManager
                          ↓
              Tool Execution (bubble, idea, transfer, etc.)
```

The main loop includes a watcher thread for agent switches:

```python
while not _should_exit:
    switch_info = get_pending_agent_switch()
    if switch_info:
        _current_conversation.end_session()
        # restart with new agent
```

### Electron + Python IPC

```
Electron Main (Node.js) ──spawn──→ Python Backend (stdin/stdout JSON)
       ↓                                    ↓
   Renderer (Three.js)              Tool Execution + DB
```

**Key Files:**
- [electron-app/main.js](electron-app/main.js) - Electron entry, Python spawning
- [python/electron_backend.py](python/electron_backend.py) - IPC message handler
- [electron-app/renderer/multiverse.js](electron-app/renderer/multiverse.js) - 3D space navigation

### Tool System

Tools are functions callable by ElevenLabs agents during conversations.

| Category | File | Purpose |
|----------|------|---------|
| Bubble | `bubble_tools.py` | Space/bubble CRUD |
| Idea | `idea_tools.py` | Ideas within bubbles |
| Transfer | `transfer_handler.py` | Agent handoffs |
| Session | `session_tools.py` | Timeout, auto-restart |
| Desktop | `desktop_tools.py` | Adam's automation |
| Coding | `coding_tools.py` | Antoni's code gen |

**Registration:** [python/tools/client_tools_manager.py](python/tools/client_tools_manager.py)

### Database

SQLite: `python/vibemind.db`

Tables: `ideas`, `projects`, `canvas_nodes`, `canvas_edges`, `conversation_sessions`, `conversation_messages`

Repository pattern in [python/data/](python/data/)

### 3D Multiverse UI

Three spaces accessible via voice or keyboard:
1. **Ideas Space** (Rachel) - Bubble navigation, idea management
2. **Desktop Space** (Adam) - System control
3. **Projects Space** (Antoni) - Code projects with VNC previews

**Renderer:** [electron-app/renderer/glass_bubbles.js](electron-app/renderer/glass_bubbles.js)

## Common Commands

```bash
# Voice dialog standalone
cd python && python voice_dialog_main.py

# Full Electron app
cd electron-app && npm start

# Test agent registry
cd python && python -m agents

# Check audio devices
python -c "import sounddevice as sd; print(sd.query_devices())"

# Build C++ visual module (optional)
mkdir build && cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=[vcpkg]/scripts/buildsystems/vcpkg.cmake
cmake --build . --config Release
```

## Configuration Reference

```bash
# Required
ELEVENLABS_API_KEY=xxx
AGENT_MULTIVERSE=agent_xxx

# Multi-Agent (optional - fallback to AGENT_MULTIVERSE)
RACHEL_AGENT_ID=agent_xxx
ALICE_AGENT_ID=agent_xxx
ADAM_AGENT_ID=agent_xxx
ANTONI_AGENT_ID=agent_xxx

# Audio Filtering
AUDIO_THRESHOLD=0.03
MIN_SPEECH_DURATION=0.3
USE_THRESHOLD_FILTERING=true

# Optional Integrations
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
CODING_ENGINE_PATH=C:\path\to\Coding_engine
VNC_BASE_URL=https://preview.vibemind.io/vnc
```

## Keyboard Shortcuts (Electron)

- `Ctrl+Shift+V` - Show/hide window
- `Ctrl+Shift+Space` - Toggle voice
- `Ctrl+1/2/3` - Switch spaces

## Key Patterns

### Adding a New Tool

1. Create tool in `python/tools/my_tool.py`
2. Export tool definition and implementation
3. Register in agent's `config.py` under tools list
4. Tool auto-registers via `ClientToolsManager`

### Agent Config Structure

```python
# python/agents/{name}/config.py
AGENT_CONFIG = {
    "name": "Agent Name",
    "slug": "name",
    "voice_id": "ElevenLabs voice name",
    "is_entry_agent": False,
    "has_fixed_space": False,
    "space_name": None,
}
```

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
