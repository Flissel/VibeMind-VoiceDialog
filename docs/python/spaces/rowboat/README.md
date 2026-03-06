# Rowboat Space

The Rowboat space provides multi-agent workflow orchestration via the Rowboat platform. It uses Docker containers to run Rowboat instances and exposes them through the VibeMind interface. Note that the event prefix is `roarboot.*` (not `rowboat.*`).

## Directory Structure

```
python/spaces/rowboat/
├── __init__.py
├── README.md
├── config.py                   # ROWBOAT_* configuration settings
├── rowboat/                    # Git submodule (Rowboat platform)
├── agents/                     # Backend agents
│   ├── __init__.py
│   └── roarboot_agent.py       # RoarbootBackendAgent (roarboot.* events)
├── broadcast/                  # Broadcast profiling
│   ├── __init__.py
│   └── roarboot_broadcast_agent.py
├── sub_agents/                 # Sub-agents (placeholder)
│   └── __init__.py
├── tools/                      # Tool implementations
│   ├── __init__.py
│   ├── docker_tools.py         # Docker container management
│   ├── roarboot_client.py      # HTTP client for Rowboat API
│   └── roarboot_tools.py       # Core Rowboat tools
└── workers/                    # Background workers
    ├── __init__.py
    ├── roarboot_workers.py     # Main worker processes
    └── update_checker.py       # Checks for Rowboat updates
```

## Agent

### RoarbootBackendAgent (`agents/roarboot_agent.py`)

Handles all `roarboot.*` events (13 event types):

- `roarboot.create` -- Create a new Rowboat instance
- `roarboot.start` -- Start a Rowboat container
- `roarboot.stop` -- Stop a Rowboat container
- `roarboot.status` -- Check instance status
- `roarboot.list` -- List all instances
- `roarboot.delete` -- Delete an instance
- `roarboot.configure` -- Configure instance settings
- `roarboot.deploy` -- Deploy a workflow
- And more

Stream: `events:tasks:roarboot`

> **Important:** The event prefix is `roarboot.*`, not `rowboat.*`. This naming convention is used throughout the codebase.

## Tools

| Tool File | Key Functions | Purpose |
|-----------|---------------|---------|
| `roarboot_tools.py` | `create_roarboot`, `start_roarboot`, `stop_roarboot`, `list_roarboots` | Core Rowboat instance management |
| `roarboot_client.py` | `RowboatClient` | HTTP client for communicating with the Rowboat API |
| `docker_tools.py` | `start_container`, `stop_container`, `get_container_status` | Docker container lifecycle management |

## Workers

- **`roarboot_workers.py`** -- Background processing for Rowboat operations, container health checks, and event polling.
- **`update_checker.py`** -- Periodically checks for updates to the Rowboat platform and notifies the user.

## Broadcast

`roarboot_broadcast_agent.py` -- Broadcasts Rowboat events to the Electron UI, including instance status changes and deployment progress.

## Configuration

`config.py` contains `ROWBOAT_*` settings:

```python
ROWBOAT_HOST = "localhost"
ROWBOAT_PORT = 3000
ROWBOAT_DOCKER_IMAGE = "rowboat/rowboat:latest"
# ... additional settings
```

Relevant `.env` settings:

```bash
ROWBOAT_ENABLED=true
ROWBOAT_API_URL=http://localhost:3000
```

## Submodule

The rowboat submodule is the Rowboat multi-agent platform:

- **Path:** `python/spaces/rowboat/rowboat/`
- **Upstream:** https://github.com/rowboatlabs/rowboat.git
- **Initialize:** `git submodule update --init python/spaces/rowboat/rowboat`

See [docs/submodules/rowboat.md](../../submodules/rowboat.md) for details.
