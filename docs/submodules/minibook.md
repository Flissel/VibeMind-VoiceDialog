# Minibook Submodule

## Overview

Minibook is a lightweight document collaboration platform. VibeMind integrates it as an external submodule to provide document creation, editing, sharing, and collaborative workflows through the Minibook space.

## Location

- **Path in VibeMind:** `external/minibook/`
- **Upstream repository:** https://github.com/c4pt0r/minibook.git
- **Configured in:** `.gitmodules`

> **Note:** Unlike most submodules which live inside their space directory, minibook is in the top-level `external/` directory because it is a shared external dependency.

## How VibeMind Uses It

### Agent

The **MinibookBackendAgent** (`python/spaces/minibook/agents/minibook_agent.py`) handles all `minibook.*` events (create, edit, list, share, export, collaborate).

### Client

The **`minibook_client.py`** (`python/spaces/minibook/tools/minibook_client.py`) provides an HTTP client for communicating with the Minibook API.

### MinibookHub

The **`minibook_hub.py`** (`python/spaces/minibook/minibook_hub.py`) is the central execution router. It coordinates between the Minibook API client, the enrichment pipeline, and the result aggregator.

### Enrichment Pipeline

The Minibook space includes an enrichment pipeline (`python/spaces/minibook/enrichment/`) that enhances documents with context gathered from other VibeMind spaces:

- `context_gather.py` -- Gathers context from ideas, coding, and other spaces
- `pipeline.py` -- Main pipeline orchestrator
- `space_router.py` -- Routes enrichment tasks to relevant spaces
- `task_enricher.py` -- Enriches tasks with gathered context

### Tools

- `minibook_tools.py` -- Core document operations
- `minibook_client.py` -- HTTP client for the Minibook REST API
- `collaboration_tools.py` -- Multi-user collaboration features

## Configuration

Enable via `.env`:

```bash
MINIBOOK_ENABLED=true
USE_MINIBOOK_HUB=true
```

## Initialize / Update

```bash
# Initialize
git submodule update --init external/minibook

# Update to latest
cd external/minibook
git pull origin main
cd ../..
git add external/minibook
git commit -m "Update minibook submodule"
```
