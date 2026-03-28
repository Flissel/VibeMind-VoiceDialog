# AgentFarm Space (AutoGen)

> Multi-agent team orchestration using AutoGen 0.4 with MCP server, hybrid pipelines, and OpenClaw integration.

## Overview

The AgentFarm space creates and runs configurable multi-agent teams via AutoGen 0.4. Teams execute collaborative tasks (code generation, research, documentation) with real-time progress broadcast to Electron. The space also provides an MCP server for Claude integration and a hybrid pipeline orchestrator for multi-space collaboration.

## Architecture

```
Voice / ClawPort Chat
        ↓
AgentFarmBackendAgent (events:tasks:agentfarm)
        ↓
agentfarm_tools.py
   ├── TeamRunner (async AutoGen 0.4 execution)
   ├── HybridPipeline (multi-space orchestration)
   └── Template configs (JSON/YAML)
        ↓
Electron AgentFarm UI (Next.js dashboard)
```

## Backend Agent

**File:** `python/spaces/autogen/agents/agentfarm_agent.py`
**Class:** `AgentFarmBackendAgent`
**Stream:** `events:tasks:agentfarm`

### Event Types (8)

| Event | Tool | Description |
|-------|------|-------------|
| `agentfarm.create_team` | `create_team` | Create agent team from template or config |
| `agentfarm.run` | `run_team` | Start async team task execution |
| `agentfarm.status` | `get_farm_status` | Overview of all teams and active runs |
| `agentfarm.list_teams` | `list_teams` | List registered teams |
| `agentfarm.stop` | `stop_run` | Cancel a running team |
| `agentfarm.results` | `get_run_results` | Get results from completed/running team |
| `agentfarm.list_templates` | `list_templates` | Scan submodule for template configs |
| `agentfarm.collaborate` | `start_collaboration` | Multi-space collaboration via Minibook |

### Parameter Mapping (German → English)

| Event | Mapping |
|-------|---------|
| `agentfarm.create_team` | vorlage/template → template_id, name → team_name |
| `agentfarm.run` | aufgabe/beschreibung/text → task, team → team_id |
| `agentfarm.stop` | run → run_id |
| `agentfarm.results` | run → run_id |

## Tools

**File:** `python/spaces/autogen/tools/agentfarm_tools.py` (510 lines)

### Core Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `create_team(template_id, team_name, team_config)` | template or config | Create agent team, broadcasts `agentfarm_team_created` |
| `run_team(team_id, task)` | team_id, task text | Start async execution, returns `run_id` immediately |
| `get_farm_status()` | — | All teams + active runs overview |
| `list_teams()` | — | List all registered teams |
| `stop_run(run_id)` | run_id | Cancel running team via CancellationToken |
| `get_run_results(run_id)` | run_id | Status, messages, duration, errors |
| `list_templates()` | — | Scan submodule for *.json templates |
| `start_collaboration(task, goal)` | task, goal | Multi-space orchestration via Minibook |

### In-Memory State

- `_team_registry` — Dict of created teams (team_id → config)
- `_active_pipeline` — Current pipeline state
- `_active_forge` — Forge state tracking

## Team Runner

**File:** `python/spaces/autogen/runner/team_runner.py`
**Class:** `TeamRunner` (Singleton)

Non-blocking async execution of AutoGen 0.4 teams:

- `start_run(team_id, config, task)` — Creates background task, returns `run_id`
- Uses `autogen_core.CancellationToken` for cancellation
- Iterates `team.run_stream()` collecting messages
- Broadcasts progress to Electron in real-time
- Auto-prunes completed runs (max 50 kept)

## Orchestrator

**Directory:** `python/spaces/autogen/orchestrator/`

| Module | Purpose |
|--------|---------|
| `hybrid_pipeline.py` | Multi-space collaboration (AutoGen teams + Minibook) |
| `openclaw_bridge.py` | OpenClaw integration for advanced workflows |
| `openclaw_setup.py` | OpenClaw configuration |
| `pipeline_enrichment.py` | Pipeline context enrichment |
| `step_registry.py` | Dynamic pipeline step registration |

## MCP Server

**Directory:** `python/spaces/autogen/mcp_server/`

| Module | Purpose |
|--------|---------|
| `vibemind_mcp.py` | MCP server exposing AgentFarm tools to Claude |
| `web_fetch_pipe.py` | Web fetch utility for piped operations |

## Configuration

**Directory:** `python/spaces/autogen/config/`

| File | Purpose |
|------|---------|
| `domino_agents.json` | Agent configuration templates |
| `forge_state.json` | Forge state tracking |
| `swarm_agents.json` | Swarm agent definitions |
| `openclaw_agents.yaml` | OpenClaw agent configs |
| `openclaw_config.yaml` | OpenClaw settings |
| `openclaw_gateway.json` | OpenClaw gateway config |
| `paired.json` | Paired agent configs |
| `pipeline_steps.yaml` | Pipeline step definitions |

## Electron UI

| Component | File |
|-----------|------|
| BrowserView Manager | `electron-app/agentfarm-manager.js` |
| Preload (IPC API) | `electron-app/agentfarm-preload.js` |
| React App (AgentFarm) | `electron-app/agentfarm/src/` |
| Next.js App (AgentFarm-UI) | `electron-app/agentfarm-ui/src/` |

### IPC API (`window.vibemindAgentFarm`)

Exposes team management, N8n workflows, video production, VibeCoder chat, and pipeline run methods. See `agentfarm-preload.js` for full list.

## Submodule

| Submodule | Path | Purpose |
|-----------|------|---------|
| Autogen_AgentFarm | `python/spaces/autogen/farm/` | FastAPI backend + Next.js frontend for agent teams |

## Directory Structure

```
python/spaces/autogen/
├── agents/
│   └── agentfarm_agent.py       # AgentFarmBackendAgent (8 events)
├── config/                       # Agent and pipeline configs (JSON/YAML)
├── farm/                         # Submodule: Autogen_AgentFarm
├── mcp_server/
│   ├── vibemind_mcp.py          # MCP server for Claude
│   └── web_fetch_pipe.py        # Web fetch utility
├── orchestrator/
│   ├── hybrid_pipeline.py       # Multi-space collaboration
│   ├── openclaw_bridge.py       # OpenClaw integration
│   ├── pipeline_enrichment.py   # Context enrichment
│   └── step_registry.py         # Dynamic step registration
├── runner/
│   └── team_runner.py           # Async AutoGen 0.4 execution
├── swarm/                        # Swarm coordination
├── tools/
│   └── agentfarm_tools.py       # All tool functions (510 lines)
└── wrapper/                      # AutoGen wrapper utilities
```
