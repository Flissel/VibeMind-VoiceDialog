# Coding Engine Submodule

## Overview

The Coding_engine is an external code generation engine that powers the Coding space in VibeMind. It takes project descriptions and generates complete software projects, including source code, configuration, and deployment artifacts.

## Location

- **Path in VibeMind:** `python/spaces/coding/Coding_engine/`
- **Upstream repository:** https://github.com/Flissel/Coding_engine.git
- **Configured in:** `.gitmodules`

## How VibeMind Uses It

### Agent

The **CodingAgent** (`python/spaces/coding/agents/coding_agent.py`) is the backend agent that handles `code.*` events. When a user requests code generation (e.g., "Erstelle eine App fuer X"), the agent delegates to the Coding Engine.

### Engine Runner

The **`coding_engine_runner.py`** (`python/spaces/coding/engine/coding_engine_runner.py`) is the bridge between VibeMind and the Coding_engine. It:

1. Spawns the Coding_engine process
2. Sends project generation requests with descriptions and parameters
3. Polls for generation progress and status
4. Returns completed project artifacts to the CodingAgent

### Tools

- `coding_tools.py` -- `generate_code()` initiates a generation request via the engine runner
- `coding_tools.py` -- `get_code_status()` checks the progress of an active generation

### Electron Integration

The Electron app includes a **Dashboard Manager** (`electron-app/dashboard-manager.js`) that provides a BrowserView for the Coding Engine dashboard, allowing users to monitor and interact with code generation visually.

## Configuration

Override the submodule path via `.env`:

```bash
CODING_ENGINE_PATH=C:\path\to\Coding_engine
```

If not set, the submodule path (`python/spaces/coding/Coding_engine/`) is used by default.

## Initialize / Update

```bash
# Initialize
git submodule update --init python/spaces/coding/Coding_engine

# Update to latest
cd python/spaces/coding/Coding_engine
git pull origin main
cd ../../../..
git add python/spaces/coding/Coding_engine
git commit -m "Update Coding_engine submodule"
```
