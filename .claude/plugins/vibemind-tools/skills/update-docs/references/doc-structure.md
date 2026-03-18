# VibeMind Documentation Structure

This reference maps every documentation file to its code source of truth, enabling targeted updates.

## Documentation Inventory

### Root Files

| Doc File | Code Source of Truth | Update Triggers |
|----------|---------------------|-----------------|
| `CLAUDE.md` | Entire codebase | New spaces, agents, tools, event types, DB schema changes |
| `QUICKSTART.md` | `electron-app/`, `python/voice/` | Setup flow changes |

### Numbered German Docs (`docs/0X_*.md`)

| Doc File | Code Source | Sections to Watch |
|----------|------------|-------------------|
| `01_systembeschreibung.md` | Architecture overview | Space count, component list |
| `02_kernarchitektur.md` | `python/swarm/`, agents | Layer descriptions, TOOL_MAP examples |
| `03_spaces.md` | `python/spaces/*/` | Space list, agent names, tool counts |
| `04_swarm_layer.md` | `python/swarm/` | Orchestrator flow, agent registry |
| `05_technologiestack.md` | `requirements.txt`, `package.json` | Dependencies, versions |
| `06_git_repositories.md` | `.gitmodules`, submodules | Submodule URLs, paths |
| `07_aktueller_status.md` | Git history, project state | Feature status, milestones |
| `08_entwicklungsphilosophie.md` | Patterns and conventions | Coding patterns, TOOL_MAP |

### API Reference (`docs/api/`)

| Doc File | Code Source | Scan Method |
|----------|------------|-------------|
| `event-types.md` | `python/swarm/event_team/event_router.py` STREAM_MAPPING | Regex for event type strings |
| `tool-functions.md` | `python/tools/*.py` + `python/spaces/*/tools/*.py` | `def function_name(` extraction |
| `database-schema.md` | `python/data/database.py` + `python/data/migrations/*.sql` | CREATE TABLE + ALTER TABLE |
| `ipc-messages.md` | `_broadcast_to_electron()` calls + `electron-app/main.js` | Regex for `"type": "xxx"` |

### Architecture Docs (`docs/architecture/`)

| Doc File | Code Source | Key Patterns |
|----------|------------|-------------|
| `overview.md` | System-wide | Architecture diagram accuracy |
| `voice-layer.md` | `python/voice/`, `rachel_agent.py` | Voice provider, session config |
| `intent-pipeline.md` | `python/swarm/orchestrator/` | Classifier prompt, enhancer flow |
| `swarm-backend.md` | `python/swarm/backend_agents/` | Agent count, stream names |
| `spaces.md` | `python/spaces/*/` | Space list, descriptions |
| `electron-ipc.md` | `electron-app/main.js`, `electron_backend.py` | Message types, IPC flow |
| `database.md` | `python/data/` | Table list, relationships |
| `memory-system.md` | `python/memory/` | Service list, config flags |

### Space-Specific Docs (`docs/python/spaces/`)

Each space has a mirrored doc at `docs/python/spaces/{space}/README.md`.
Code source: `python/spaces/{space}/`

Check for:
- Agent class names match
- Tool function lists match
- Event type prefixes match
- Architecture diagrams reflect current flow

### Development Guides (`docs/development/`)

| Doc File | Validation Method |
|----------|-------------------|
| `adding-a-tool.md` | Compare steps against actual tool files |
| `adding-event-types.md` | Compare against `intent_classifier.py` flow |
| `adding-a-space.md` | Compare against existing space structure |
| `testing-guide.md` | Compare against `python/tests/` files |

## Update Priority Matrix

| Priority | Condition | Action |
|----------|-----------|--------|
| Critical | New space added | Update CLAUDE.md tables, `docs/03_spaces.md`, `docs/api/event-types.md`, `docs/python/spaces/README.md` |
| Critical | New DB table | Update `docs/api/database-schema.md`, CLAUDE.md schema section |
| High | New event types | Update `docs/api/event-types.md`, CLAUDE.md classifier section |
| High | New tool functions | Update `docs/api/tool-functions.md`, space README |
| High | New backend agent | Update CLAUDE.md agent table, `docs/04_swarm_layer.md` |
| Medium | New IPC message | Update `docs/api/ipc-messages.md`, CLAUDE.md IPC section |
| Medium | Config var added | Update `docs/configuration.md`, `.env.example` |
| Low | Code refactoring | Check architecture docs still accurate |

## Cross-Reference Map

These sections must stay in sync across multiple files:

### Space Count & Names
- `CLAUDE.md` → "Eight Spaces (Domains)" section
- `docs/03_spaces.md` → Full space descriptions
- `docs/python/spaces/README.md` → Space overview table
- `docs/architecture/spaces.md` → Architecture perspective

### Event Types
- `CLAUDE.md` → "Intent Classification" examples
- `docs/api/event-types.md` → Complete reference
- `python/swarm/event_team/event_router.py` → STREAM_MAPPING (source of truth)
- `python/swarm/orchestrator/intent_classifier.py` → CLASSIFIER_PROMPT_TEMPLATE

### Backend Agents
- `CLAUDE.md` → Agent table with streams
- `docs/04_swarm_layer.md` → German agent descriptions
- `docs/python/swarm/backend-agents/README.md` → Technical reference
- `python/swarm/backend_agents/__init__.py` → Registry (source of truth)

### Database Schema
- `CLAUDE.md` → Schema summary table
- `docs/api/database-schema.md` → Full reference with columns
- `python/data/database.py` → CREATE TABLE statements (source of truth)
- `python/data/migrations/*.sql` → Schema evolution