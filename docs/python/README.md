# Python Backend

Overview of the `python/` directory structure.

## Directory Map

| Directory | Purpose | Docs |
|-----------|---------|------|
| `data/` | SQLite database, models, repository pattern | [data/](data/) |
| `memory/` | Supermemory services (task, conversation, user profile) | [memory/](memory/) |
| `spaces/` | 8 domain spaces (ideas, coding, desktop, rowboat, research, minibook, schedule, shuttles) | [spaces/](spaces/) |
| `swarm/` | Orchestrator, backend agents, event routing, 20 subsystems | [swarm/](swarm/) |
| `tools/` | 22 shared tool modules (cross-space utilities) | [tools/](tools/) |
| `tests/` | Test suites | See [testing guide](../development/testing-guide.md) |

## Key Entry Points

| File | Purpose |
|------|---------|
| `electron_backend.py` | Electron <-> Python IPC handler (stdin/stdout JSON) |
| `voice_dialog_main.py` | Standalone voice dialog entry point |
| `config.py` | Central configuration loader from .env |
| `vibemind.db` | SQLite database (auto-created) |

## Spaces Architecture

Each space follows a consistent layout:

```
spaces/<name>/
    agents/       # Backend agents (subclass BaseBackendAgent)
    tools/        # Domain-specific tool functions
    __init__.py
```

The 8 spaces and their roles:

| Space | Purpose | Has Agent? |
|-------|---------|------------|
| `ideas/` | Bubble and idea management, exploration, formatting | Yes (BubblesAgent, IdeasAgent, RachelAgent) |
| `coding/` | Code generation via external Coding Engine | Yes (CodingAgent) |
| `desktop/` | Desktop automation via pyautogui/Moire | Yes (DesktopAgent) |
| `rowboat/` | Rowboat knowledge graph integration | Yes (RoarbootAgent) |
| `research/` | ZeroClaw deep research sessions | Yes (ZeroClawResearchAgent) |
| `minibook/` | MinibookHub execution and enrichment pipeline | Yes (MinibookAgent) |
| `schedule/` | Scheduled task execution (cron, interval, one-shot) | Yes (ScheduleAgent) |
| `shuttles/` | Requirements pipeline (bubble -> project) | No (tools only) |

## Execution Modes

The system supports two execution modes controlled by `FORCE_SYNC_MODE`:

- **Sync mode** (`FORCE_SYNC_MODE=true`): Tools execute directly in-process. No Redis required. Default for development.
- **Async mode** (`FORCE_SYNC_MODE=false`): Events are published to Redis streams, consumed by backend agents. Supports parallel workers via AgentPool.
