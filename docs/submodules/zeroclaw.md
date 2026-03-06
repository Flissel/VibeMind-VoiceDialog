# ZeroClaw Submodule

## Overview

ZeroClaw is a research engine that powers the Research space in VibeMind. It provides deep research capabilities including query processing, source gathering, and result synthesis.

> **IMPORTANT:** The zeroclaw submodule directory exists but is currently **EMPTY**. It must be initialized before the Research space can function.

## Location

- **Path in VibeMind:** `external/zeroclaw/`
- **Upstream repository:** https://github.com/zeroclaw-labs/zeroclaw.git
- **Configured in:** `.gitmodules`

> **Note:** Like minibook, zeroclaw is in the top-level `external/` directory rather than inside the space directory.

## Status: Empty (Needs Initialization)

The submodule is registered in `.gitmodules` but its directory is empty. To initialize:

```bash
git submodule update --init external/zeroclaw
```

If this fails, verify you have access to the upstream repository at https://github.com/zeroclaw-labs/zeroclaw.git.

## How VibeMind Uses It

### Agent

The **ZeroClawResearchAgent** (`python/spaces/research/agents/zeroclaw_research_agent.py`) handles all `research.*` events:

- `research.start` -- Start a research session
- `research.query` -- Submit a research query
- `research.status` -- Check research progress
- `research.results` -- Retrieve research results
- `research.stop` -- Stop an active research session

Stream: `events:tasks:zeroclaw`

### Tools

- `research_tools.py` (`python/spaces/research/tools/research_tools.py`) -- Core research operations that interface with the ZeroClaw engine

## Configuration

Enable via `.env`:

```bash
USE_ZEROCLAW=true
```

When `USE_ZEROCLAW` is not set or is `false`, the Research space is inactive.

## Initialize / Update

```bash
# Initialize (required -- directory is currently empty)
git submodule update --init external/zeroclaw

# Update to latest
cd external/zeroclaw
git pull origin main
cd ../..
git add external/zeroclaw
git commit -m "Update zeroclaw submodule"
```
