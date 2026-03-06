# VibeMind Voice Dialog

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](https://python.org)
[![Node.js 18+](https://img.shields.io/badge/Node.js-18+-339933.svg)](https://nodejs.org)
[![Electron 25](https://img.shields.io/badge/Electron-25-47848F.svg)](https://electronjs.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

**A voice-controlled 3D workspace where you speak ideas into existence.** VibeMind captures voice input via dual voice providers (OpenAI Realtime API or ElevenLabs Conversational AI), classifies intent through a swarm backend, and renders ideas as interactive 3D bubbles in an Electron UI.

<!-- TODO: Add demo GIF/video here -->
<!-- ![VibeMind Demo](docs/assets/demo.gif) -->

---

## Features

- **Voice-First Interface** — Speak naturally in German or English; OpenAI Realtime API handles speech-to-speech with sub-second latency
- **3D Multiverse UI** — Ideas rendered as glass bubbles in a Three.js scene; navigate nested spaces visually
- **Intent Classification** — LLM-based classification routes natural language to structured event types (`bubble.create`, `idea.format`, `code.generate`, etc.)
- **8 Domain Spaces** — Ideas, Coding, Desktop Automation, Rowboat (Knowledge Graph), Research, Minibook, Shuttles, Schedule
- **Swarm Backend** — Domain-specific agents execute tools and broadcast results to the UI in real-time
- **Memory System** — Optional Supermemory integration for cross-session context, task tracking, and user preference learning
- **Reference Resolution** — DroPE resolves ambiguous references ("do that again", "delete it") using conversation history
- **Multi-Step Orchestration** — Claude Sonnet handles complex requests that span multiple tools
- **Sync & Async Modes** — Run locally with zero dependencies (sync) or scale with Redis streams (async)

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- An [OpenAI API key](https://platform.openai.com/api-keys) (for voice + intent classification)

### Install & Run

```bash
# Clone with submodules
git clone --recursive https://github.com/Flissel/VibeMind-VoiceDialog.git
cd VibeMind-VoiceDialog

# Python backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Electron frontend
cd electron-app
npm install
cd ..

# Configure
cp .env.example .env
# Edit .env — set OPENAI_API_KEY at minimum

# Launch
cd electron-app
npm start
```

This starts the Electron app which automatically spawns the Python backend. Speak into your microphone to interact.

> **Minimal mode:** Set `FORCE_SYNC_MODE=true` in `.env` to run without Redis or any external services.

See [docs/installation/](docs/installation/) for platform-specific guides and troubleshooting.

## Architecture

```
User Voice ──► Voice Provider (OpenAI Realtime / ElevenLabs)
                        │
                   send_intent()
                        │
                ┌───────▼────────┐
                │ Intent Classifier│
                │ (LLM-based)     │
                └───────┬────────┘
                        │ event_type + payload
     ┌──────────┬───────┼───────┬──────────┐
     ▼          ▼       ▼       ▼          ▼
 BubblesAgent IdeasAgent CodingAgent DesktopAgent  ...4 more
 (bubble.*)  (idea.*)  (code.*)  (desktop.*)
     │          │       │       │          │
     └──────────┴───────┼───────┴──────────┘
                        ▼
                   Electron UI
                (Three.js 3D Bubbles)

8 agents total: Bubbles, Ideas, Coding, Desktop,
Roarboot, ZeroClaw Research, Minibook, Schedule
```

**Key flow:** Voice input → Rachel (OpenAI Realtime) → `send_intent` tool → IntentClassifier → event routing → backend agent executes tool → broadcasts result to Electron UI.

See [docs/architecture/](docs/architecture/) for detailed diagrams and component docs.

## Spaces

| Space | Domain | What It Does |
|-------|--------|--------------|
| **Ideas** | `bubble.*`, `idea.*` | Create/navigate bubbles, manage ideas, auto-link, format |
| **Coding** | `code.*` | Generate code projects, check status, live preview |
| **Desktop** | `desktop.*` | Open apps, click elements, type text, take screenshots |
| **Rowboat** | `roarboot.*` | Knowledge graph exploration and RAG |
| **Research** | `research.*` | Web research via ZeroClaw engine |
| **Minibook** | `minibook.*` | Inter-space collaboration workflows |
| **Shuttles** | _(handled by BubblesAgent via `bubble.evaluate`/`bubble.promote`)_ | Requirements pipeline and SWE design |
| **Schedule** | `schedule.*` | Task scheduling, reminders, alarms |

## Voice Commands (Examples)

```
"Erstelle eine Bubble Marketing"     → bubble.create  {title: "Marketing"}
"Notiere: API Design Review"         → idea.create    {title: "API Design Review"}
"Verlinke die Ideen sinnvoll"        → idea.auto_link
"Erstelle eine App fuer Notizen"     → code.generate  {description: "Notizen App"}
"Oeffne Chrome"                      → desktop.open_app {app_name: "Chrome"}
"Zurueck"                            → bubble.exit
```

See [docs/user-guide/voice-commands.md](docs/user-guide/voice-commands.md) for the full command reference.

## Project Structure

```
VibeMind-VoiceDialog/
├── python/
│   ├── core/                  # Shared: database, event bus, LLM, orchestrator, voice
│   ├── spaces/                # 8 domain spaces (ideas, coding, desktop, ...)
│   │   └── <space>/
│   │       ├── agents/        # Space-specific agents
│   │       └── tools/         # Space-specific tools
│   ├── data/                  # SQLite database, models, repository
│   ├── tools/                 # Shared tool implementations
│   ├── memory/                # Supermemory services
│   ├── swarm/                 # Orchestrator, backend agents, event routing
│   ├── tests/                 # Test suites (62+ test files)
│   └── electron_backend.py    # Python ↔ Electron IPC handler
├── electron-app/
│   ├── main.js                # Electron main process, Python spawning
│   └── renderer/              # Three.js 3D multiverse UI
├── docs/                      # Documentation
├── external/                  # Submodules (minibook, zeroclaw)
├── .env.example               # Configuration template
└── requirements.txt           # Python dependencies
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Installation](docs/installation/) | Platform-specific setup guides |
| [Architecture](docs/architecture/) | System design, diagrams, component docs |
| [Developer Guide](docs/development/) | Contributing code, adding spaces/tools/events |
| [API Reference](docs/api/) | Event types, IPC messages, tool functions, database schema |
| [User Guide](docs/user-guide/) | Voice commands, space walkthroughs, FAQ |
| [Configuration](docs/configuration.md) | Every environment variable explained |
| [CLAUDE.md](CLAUDE.md) | Quick architecture reference for AI-assisted development |

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required
OPENAI_API_KEY=sk-xxx              # Voice + intent classification

# Execution mode
FORCE_SYNC_MODE=true               # true = no Redis needed (default)

# Optional features
USE_TOOL_ORCHESTRATOR=true         # Multi-step request handling
USE_TASK_MEMORY=true               # Cross-session task tracking
USE_CONVERSATION_MEMORY=true       # Conversation context persistence
USE_DROPE_RESOLVER=true            # Ambiguous reference resolution
```

See [docs/configuration.md](docs/configuration.md) for the complete reference (50+ variables).

## Testing

```bash
cd python
python -m tests.test_data_layer        # Database layer
python -m tests.test_intent_to_tool    # Intent → tool routing
python -m tests.test_desktop_tools     # Desktop automation
python -m tests.test_integration_e2e   # End-to-end flow
```

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Windows 10/11 | Fully tested | Primary development platform |
| macOS | Builds available | Community testing welcome |
| Linux | Builds available | Community testing welcome |

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Fork/clone workflow
- Branch naming and PR process
- Architecture quick reference for adding spaces, tools, and events
- Code style guidelines

Good first issues are labeled [`good first issue`](https://github.com/Flissel/VibeMind-VoiceDialog/labels/good%20first%20issue).

## License

[MIT License](LICENSE) — free for personal and commercial use.

## Acknowledgments

Built with [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime), [ElevenLabs Conversational AI](https://elevenlabs.io), [Electron](https://electronjs.org), [Three.js](https://threejs.org), [AutoGen](https://github.com/microsoft/autogen), and [Supermemory](https://supermemory.ai).
