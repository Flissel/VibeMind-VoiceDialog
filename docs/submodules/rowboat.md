# Rowboat Submodule

## Overview

Rowboat is a multi-agent workflow orchestration platform. VibeMind integrates it as a submodule to provide workflow creation, deployment, and management capabilities through the Rowboat space.

## Location

- **Path in VibeMind:** `python/spaces/rowboat/rowboat/`
- **Upstream repository:** https://github.com/rowboatlabs/rowboat.git
- **Configured in:** `.gitmodules`

## How VibeMind Uses It

### Agent

The **RoarbootBackendAgent** (`python/spaces/rowboat/agents/roarboot_agent.py`) handles all `roarboot.*` events. Note the event prefix is `roarboot.*`, not `rowboat.*`.

### Client

The **`roarboot_client.py`** (`python/spaces/rowboat/tools/roarboot_client.py`) provides an HTTP client for communicating with the Rowboat API. It handles:

1. Instance creation and lifecycle management
2. Workflow deployment and configuration
3. Status polling and health checks

### Docker Integration

The **`docker_tools.py`** (`python/spaces/rowboat/tools/docker_tools.py`) manages Docker containers for Rowboat instances. Each Rowboat instance runs in its own container.

### Tools

- `roarboot_tools.py` -- Core Rowboat management tools (`create_roarboot`, `start_roarboot`, `stop_roarboot`, `list_roarboots`)
- `roarboot_client.py` -- HTTP client for the Rowboat REST API
- `docker_tools.py` -- Docker container lifecycle management

### Electron Integration

The Electron app includes a **Rowboat Manager** (`electron-app/rowboat-manager.js`) that embeds the Rowboat UI in a BrowserView, allowing users to interact with Rowboat workflows visually within the VibeMind interface.

### Workers

- `roarboot_workers.py` -- Background processing and container health monitoring
- `update_checker.py` -- Periodically checks for Rowboat platform updates

## Configuration

`python/spaces/rowboat/config.py` contains `ROWBOAT_*` settings including host, port, and Docker image configuration.

## Initialize / Update

```bash
# Initialize
git submodule update --init python/spaces/rowboat/rowboat

# Update to latest
cd python/spaces/rowboat/rowboat
git pull origin main
cd ../../../..
git add python/spaces/rowboat/rowboat
git commit -m "Update rowboat submodule"
```
