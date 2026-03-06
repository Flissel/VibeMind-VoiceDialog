# VibeMind Documentation

Master index of all documentation. Each doc maps to a specific part of the codebase.

## Quick Navigation

| Need | Go To |
|------|-------|
| Set up VibeMind | [Installation](installation/) |
| Understand the system | [Architecture](architecture/) |
| Add features | [Development Guide](development/) |
| Event types / IPC / DB | [API Reference](api/) |
| Voice commands | [User Guide](user-guide/) |
| Configure .env | [Configuration](configuration.md) |

## Documentation Map

### Codebase-Mirrored Docs

These docs mirror the actual filesystem — find the doc for any source file:

| Code Path | Documentation |
|-----------|---------------|
| `python/` | [docs/python/](python/) — Backend overview |
| `python/tools/` | [docs/python/tools/](python/tools/) — 22 shared tool modules |
| `python/data/` | [docs/python/data/](python/data/) — Database, models, repos |
| `python/data/` (schema) | [docs/python/data/schema.md](python/data/schema.md) — All 12 tables |
| `python/memory/` | [docs/python/memory/](python/memory/) — Supermemory services |
| `python/swarm/` | [docs/python/swarm/](python/swarm/) — 20 swarm subsystems |
| `python/swarm/orchestrator/` | [docs/python/swarm/orchestrator/](python/swarm/orchestrator/) — 10 orchestrator files |
| `python/swarm/backend_agents/` | [docs/python/swarm/backend-agents/](python/swarm/backend-agents/) — Agent pattern |
| `python/spaces/` | [docs/python/spaces/](python/spaces/) — All 8 spaces |
| `python/spaces/ideas/` | [docs/python/spaces/ideas/](python/spaces/ideas/) |
| `python/spaces/coding/` | [docs/python/spaces/coding/](python/spaces/coding/) |
| `python/spaces/desktop/` | [docs/python/spaces/desktop/](python/spaces/desktop/) |
| `python/spaces/rowboat/` | [docs/python/spaces/rowboat/](python/spaces/rowboat/) |
| `python/spaces/research/` | [docs/python/spaces/research/](python/spaces/research/) |
| `python/spaces/minibook/` | [docs/python/spaces/minibook/](python/spaces/minibook/) |
| `python/spaces/schedule/` | [docs/python/spaces/schedule/](python/spaces/schedule/) |
| `python/spaces/shuttles/` | [docs/python/spaces/shuttles/](python/spaces/shuttles/) |
| `electron-app/` | [docs/electron-app/](electron-app/) — Electron structure |
| Git submodules | [docs/submodules/](submodules/) — All 6 submodules |

### Architecture Docs

| Document | What It Covers |
|----------|----------------|
| [Architecture Overview](architecture/overview.md) | System diagram, 4 layers |
| [Voice Layer](architecture/voice-layer.md) | Dual provider (OpenAI Realtime + ElevenLabs) |
| [Intent Pipeline](architecture/intent-pipeline.md) | Classification, enhancement, routing |
| [Swarm Backend](architecture/swarm-backend.md) | Agent pattern, sync/async modes |
| [Spaces](architecture/spaces.md) | All 8 domain spaces |
| [Electron IPC](architecture/electron-ipc.md) | stdin/stdout JSON protocol |
| [Database](architecture/database.md) | SQLite schema v14 |
| [Memory System](architecture/memory-system.md) | Supermemory integration |
| [Submodules](architecture/submodules.md) | 6 git submodules |

### API Reference

| Document | What It Covers |
|----------|----------------|
| [Event Types](api/event-types.md) | All 100+ events by domain |
| [IPC Messages](api/ipc-messages.md) | Python → Electron messages |
| [Tool Functions](api/tool-functions.md) | All tool functions by space |
| [Database Schema](api/database-schema.md) | 12 tables with columns |

### Developer Guide

| Document | What It Covers |
|----------|----------------|
| [Getting Started](development/getting-started.md) | Dev environment setup |
| [Adding a Tool](development/adding-a-tool.md) | Worked example |
| [Adding Event Types](development/adding-event-types.md) | 4 files to update |
| [Adding a Space](development/adding-a-space.md) | Full space creation |
| [Testing Guide](development/testing-guide.md) | Running and writing tests |
| [Debugging](development/debugging.md) | Logs, common issues |
| [Code Style](development/code-style.md) | Python/JS conventions |
| [Building Releases](development/building-releases.md) | Electron builds |

### User Guide

| Document | What It Covers |
|----------|----------------|
| [Quick Start](user-guide/quick-start.md) | First 5 minutes |
| [Voice Commands](user-guide/voice-commands.md) | Full command reference |
| [FAQ](user-guide/faq.md) | Common questions |

### Other

| Document | What It Covers |
|----------|----------------|
| [Configuration](configuration.md) | All 60+ env variables |
| [Glossary](glossary.md) | Project terminology |
| [Roadmap](roadmap.md) | Planned features |
| [DroPE Integration](DROPE_INTEGRATION.md) | Reference resolution |

### German Documentation

| Document | Description |
|----------|-------------|
| [01 Systembeschreibung](01_systembeschreibung.md) | System description |
| [02 Kernarchitektur](02_kernarchitektur.md) | Core architecture |
| [03 Spaces](03_spaces.md) | Spaces detail |
| [04 Swarm Layer](04_swarm_layer.md) | Swarm layer |
| [05 Technologiestack](05_technologiestack.md) | Technology stack |
| [06 Git Repositories](06_git_repositories.md) | Git repos |
| [07 Aktueller Status](07_aktueller_status.md) | Current status |
| [08 Entwicklungsphilosophie](08_entwicklungsphilosophie.md) | Development philosophy |
| [Multi-Agent System](multi-agent-system/) | German multi-agent docs |
