# Developer Getting Started

## Dev Environment Setup

1. **Clone with submodules:**
   ```bash
   git clone --recursive https://github.com/Flissel/VibeMind-VoiceDialog.git
   cd VibeMind-VoiceDialog
   ```

2. **Python venv:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate    # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Electron:**
   ```bash
   cd electron-app && npm install && cd ..
   ```

4. **Configure:**
   ```bash
   cp .env.example .env
   # Set OPENAI_API_KEY and FORCE_SYNC_MODE=true
   ```

5. **Run:**
   ```bash
   cd electron-app && npm start
   ```

## Project Layout

```
python/
├── core/           # Shared infrastructure (database, LLM, voice, orchestrator)
├── spaces/         # Domain spaces — this is where most development happens
│   └── <space>/
│       ├── agents/ # Backend agent (TOOL_MAP, PARAM_MAPPING)
│       └── tools/  # Tool functions
├── data/           # Database, models, repositories
├── swarm/          # Orchestrator, event router, backend agents
├── tools/          # Shared/legacy tools
├── memory/         # Supermemory services
└── tests/          # Test suites

electron-app/
├── main.js         # Python spawning, IPC
├── preload.js      # IPC bridge
└── renderer/       # Three.js UI
```

## Development Workflow

1. Make changes in `python/` or `electron-app/`
2. Restart the Electron app (`Ctrl+C` then `npm start`)
3. Test via voice or the console
4. Run relevant tests: `cd python && python -m tests.test_<feature>`

## Logs

| Location | Content |
|----------|---------|
| `python/logs/agents/` | Agent execution logs |
| `python/logs/intents/` | Intent classification results |
| `python/logs/tools/` | Tool call logs |
| `python/logs/tool_calls/` | Detailed tool invocations |
| `python/voice_dialog.log` | Voice session log |

## Quick Reference

| I want to... | Go to... |
|--------------|----------|
| Add a voice command | [Adding Event Types](adding-event-types.md) |
| Add a tool function | [Adding a Tool](adding-a-tool.md) |
| Add an entire space | [Adding a Space](adding-a-space.md) |
| Write tests | [Testing Guide](testing-guide.md) |
| Debug an issue | [Debugging](debugging.md) |
| Understand the code style | [Code Style](code-style.md) |
