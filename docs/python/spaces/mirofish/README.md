# MiroFish Space

> Offline AI prediction engine with multi-agent simulations, knowledge graphs, and predictive reports.

## Overview

MiroFish runs multi-agent simulations to generate predictions from documents and knowledge graphs. The core engine is a Flask + Vue app running in Docker, accessed via a REST API client. The space supports graph building, agent-based simulation, report generation, and interactive agent interviews.

## Architecture

```
Voice / ClawPort Chat
        ↓
MiroFishBackendAgent (events:tasks:mirofish_pred)
        ↓
mirofish_tools.py → MiroFishClient (HTTP)
        ↓
MiroFish Docker Container (localhost:5001)
   ├── Flask REST API
   ├── Neo4j (knowledge graph)
   ├── Ollama (local LLM inference)
   └── Vue Frontend (localhost:3001)
        ↓
Electron BrowserView (loads localhost:3001)
```

## Backend Agent

**File:** `python/spaces/mirofish/agents/mirofish_agent.py`
**Class:** `MiroFishBackendAgent`
**Stream:** `events:tasks:mirofish_pred`

### Event Types (15)

| Event | Tool | Description |
|-------|------|-------------|
| `mirofish.simulate` | `simulate` | End-to-end prediction (upload → graph → simulation → report) |
| `mirofish.predict` | `simulate` | Alias for simulate |
| `mirofish.predict_from_knowledge` | `predict_from_knowledge` | Simulate using existing graph query |
| `mirofish.graph.build` | `build_graph` | Build knowledge graph from seed data |
| `mirofish.graph.search` | `search_graph` | Search existing graph |
| `mirofish.list_projects` | `list_projects` | List all MiroFish projects |
| `mirofish.report.chat` | `chat_report` | Interactive chat with report agent |
| `mirofish.interview` | `interview_agent` | Query specific simulated agent |
| `mirofish.docker.start` | `start_docker` | Start Docker containers |
| `mirofish.docker.stop` | `stop_docker` | Stop Docker containers |
| `mirofish.docker.restart` | `restart_docker` | Restart Docker containers |
| `mirofish.docker.status` | `docker_status` | Check container health |
| `mirofish.evaluate` | `evaluate_bubble_readiness` | Evaluate bubble prediction confidence |
| `mirofish.status` | `get_status` | Connection health check |

### Parameter Mapping (German → English)

| Event | Mapping |
|-------|---------|
| `mirofish.simulate` | anforderung/beschreibung/was → requirement, inhalt/content → text, datei/file → file_path, agenten → agent_count, runden → rounds |
| `mirofish.predict_from_knowledge` | suche/suchbegriff → query, agenten → agent_count, runden → rounds |
| `mirofish.graph.search` | suche/suchbegriff/anfrage → query, graph → graph_id |
| `mirofish.report.chat` | frage/question → question, report → report_id |
| `mirofish.interview` | agent/name → agent_name, frage → question, simulation → simulation_id |
| `mirofish.evaluate` | name/bubble/title/titel/space → bubble_name |

## Tools

**File:** `python/spaces/mirofish/tools/mirofish_tools.py` (982 lines)

### Core Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_status()` | — | Health check against Flask API |
| `simulate(requirement, text, file_path, agent_count=100, rounds=10)` | requirement, text, file, agents, rounds | Full pipeline: upload → ontology → graph → simulation → report |
| `build_graph(requirement, text, file_path)` | requirement, text or file | Build knowledge graph from seed data |
| `search_graph(graph_id, query)` | graph_id, query | Search existing knowledge graph |
| `list_projects()` | — | List all MiroFish projects |
| `chat_report(report_id, message)` | report_id, message | Chat with report agent |
| `interview_agent(simulation_id, agent_id, question)` | sim_id, agent_id, question | Query a simulated agent |
| `predict_from_knowledge(requirement, query, agent_count, rounds)` | requirement + graph query | Simulate from existing graph |
| `evaluate_bubble_readiness(project_id)` | project_id | Prediction confidence check |

### Docker Tools

**File:** `python/spaces/mirofish/tools/docker_tools.py`

| Tool | Description |
|------|-------------|
| `start_docker()` | Start MiroFish Docker compose stack |
| `stop_docker()` | Stop containers |
| `restart_docker()` | Restart containers |
| `docker_status()` | Check service health |

## API Client

**File:** `python/spaces/mirofish/tools/mirofish_client.py`

REST client wrapping the MiroFish Flask API:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/api/graph/ontology/generate` | POST | Generate ontology from seed files |
| `/api/graph/build` | POST | Build knowledge graph |
| `/api/graph/task/<task_id>` | GET | Poll async task progress |
| `/api/graph/project/<id>` | GET | Get project details |
| `/api/graph/project/list` | GET | List all projects |
| `/api/simulation/configure` | POST | Configure simulation parameters |
| `/api/simulation/start` | POST | Start simulation run |
| `/api/simulation/status/<id>` | GET | Poll simulation progress |
| `/api/simulation/interview` | POST | Interview simulated agent |
| `/api/report/generate` | POST | Generate report from simulation |
| `/api/report/<id>` | GET | Get completed report |
| `/api/report/chat` | POST | Chat with report |
| `/api/report/tools/search` | POST | Direct graph search |

## Configuration

**File:** `python/spaces/mirofish/config.py`
**Class:** `MiroFishConfig` (dataclass)

| Setting | Default | Env Var |
|---------|---------|---------|
| API URL | `http://localhost:5001` | `MIROFISH_API_URL` |
| Neo4j | `bolt://localhost:7687` | (internal) |
| LLM | OpenRouter | `OPENROUTER_API_KEY` |
| Build timeout | 300s | — |
| Simulation timeout | 600s | — |
| Report timeout | 300s | — |

## Electron UI

| Component | File |
|-----------|------|
| BrowserView Manager | `electron-app/mirofish-manager.js` |
| Preload | `electron-app/mirofish-preload.js` |

- Loads MiroFish Vue frontend from `http://localhost:3001` (`MIROFISH_URL`)
- Retry logic for connection-refused (up to 10 retries with backoff)
- IPC API: `window.vibemindMirofish` with `startSimulation()`, `getStatus()`, `onEvent()`

## Directory Structure

```
python/spaces/mirofish/
├── agents/
│   └── mirofish_agent.py        # MiroFishBackendAgent (15 events, 13 tools)
├── config/
│   └── __init__.py              # Config proxy
├── config.py                     # MiroFishConfig dataclass
├── tools/
│   ├── mirofish_tools.py        # Core tool functions (982 lines)
│   ├── mirofish_client.py       # REST API client
│   └── docker_tools.py          # Docker management
└── mirofish/                     # Submodule: Flask + Vue app
```
