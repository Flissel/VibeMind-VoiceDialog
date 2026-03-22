# Backend Agents

Backend agents are the execution layer of VibeMind. They receive classified events (from the orchestrator) and execute the corresponding tool functions.

## Architecture

```
Classified Event (event_type + payload)
    |
    v
EventRouter -> Redis Stream (e.g., events:tasks:ideas)
    |
    v
BackendAgent._handle_event()
    |
    +---> _get_tool_name(event_type)   # TOOL_MAP lookup
    +---> _normalize_params()           # PARAM_MAPPING rename
    +---> _extract_params_from_transcript()  # Regex fallback
    +---> _resolve_context_references()      # Conversation history
    |
    v
tool(**params) -> result dict
    |
    v
_publish_status() -> events:status stream
```

## Base Agent

**File**: `python/swarm/backend_agents/base_agent.py`

`BaseBackendAgent` is the abstract base class all domain agents inherit from. It provides:

- **Stream subscription**: Listens to a Redis stream for incoming events
- **Tool loading**: Lazy-loads tool functions via `_load_tools()`
- **Event routing**: Maps `event_type` to tool function name via `_get_tool_name()` / `TOOL_MAP`
- **Parameter normalization**: Renames classifier output params to match tool signatures via `PARAM_MAPPING`
- **Transcript extraction**: Regex fallback to extract missing params from raw user input
- **Context resolution**: Resolves references like "alle" (all) and "die" (those) from conversation history
- **Status publishing**: Reports started/completed/error to `events:status` stream
- **Question asking**: Queues clarification questions for the voice agent
- **Consumer group support**: Methods for Redis consumer group parallel processing
- **Execution logging**: All events logged via `AgentExecutionLogger`

Required overrides for subclasses:
- `stream` (property) -- Redis stream name to listen on
- `name` (property) -- Agent name for logging
- `_load_tools()` -- Returns dict of `{tool_name: callable}`
- `_get_tool_name(event_type)` -- Maps event type to tool function name

Optional override:
- `PARAM_MAPPING` -- Dict of `{event_type: {classifier_param: tool_param}}`

## Agent Registry

**File**: `python/swarm/backend_agents/__init__.py`

The `__init__.py` provides a lazy-import registry that avoids circular dependencies after the migration to the spaces architecture. It exposes:

- `get_bubbles_agent()` -- Singleton from `spaces/ideas/agents/bubbles_agent.py`
- `get_ideas_agent()` -- Singleton from `spaces/ideas/agents/ideas_agent.py`
- `get_desktop_agent()` -- Singleton from `spaces/desktop/agents/desktop_agent.py`
- `get_coding_agent()` -- Singleton from `spaces/coding/agents/coding_agent.py`
- `get_roarboot_agent()` -- Singleton from `spaces/rowboat/agents/roarboot_agent.py`
- `get_n8n_agent()` -- Singleton from `spaces/n8n/agents/n8n_agent.py`

Class names are also available via `__getattr__` for backward compatibility.

## Agent Pool

**File**: `python/swarm/backend_agents/agent_pool.py`

Provides parallel execution via Redis Consumer Groups:

- `AgentWorker` -- Single worker instance using consumer groups for coordinated event consumption
- `AgentPool` -- Pool of workers for one agent type with health monitoring
- `MultiAgentPool` -- Manages multiple pools across agent types
- `create_default_pools()` -- Factory for standard Ideas + Desktop + Coding pools

## Migration: swarm/backend_agents/ to spaces/*/agents/

Agent implementations have migrated from `swarm/backend_agents/` to `spaces/*/agents/`. The base class and registry remain in `swarm/backend_agents/` while concrete agents live in their respective spaces.

## All 10 Backend Agents

| Agent | Stream | File Path | Tool Count |
|-------|--------|-----------|------------|
| BubblesAgent | `events:tasks:ideas` | `python/spaces/ideas/agents/bubbles_agent.py` | 13 tools |
| IdeasAgent | `events:tasks:ideas` | `python/spaces/ideas/agents/ideas_agent.py` | 38 tools |
| RachelAgent | (voice agent) | `python/spaces/ideas/agents/rachel_agent.py` | -- |
| CodingAgent | `events:tasks:coding` | `python/spaces/coding/agents/coding_agent.py` | 8 tools |
| DesktopAgent | `events:tasks:desktop` | `python/spaces/desktop/agents/desktop_agent.py` | 12 tools |
| RoarbootBackendAgent | `events:tasks:roarboot` | `python/spaces/rowboat/agents/roarboot_agent.py` | 13 tools |
| ZeroClawResearchAgent | (research) | `python/spaces/research/agents/zeroclaw_research_agent.py` | -- |
| MinibookAgent | (minibook) | `python/spaces/minibook/agents/minibook_agent.py` | -- |
| ScheduleAgent | (schedule) | `python/spaces/schedule/agents/schedule_agent.py` | -- |
| N8nBackendAgent | `events:tasks:n8n` | `python/spaces/n8n/agents/n8n_agent.py` | 8 tools |

Additionally, some spaces have swarm agent variants for multi-agent coordination:
- `python/spaces/ideas/agents/ideas_swarm_agent.py`
- `python/spaces/coding/agents/coding_swarm_agent.py`
- `python/spaces/desktop/agents/desktop_swarm_agent.py`

## Example: Adding a New Backend Agent

1. Create `python/spaces/myspace/agents/my_agent.py`:

```python
from swarm.backend_agents.base_agent import BaseBackendAgent

class MyAgent(BaseBackendAgent):
    TOOL_MAP = {
        "myspace.action": "do_action",
        "myspace.query": "query_data",
    }

    PARAM_MAPPING = {
        "myspace.action": {"title": "action_name"},
    }

    @property
    def stream(self) -> str:
        return "events:tasks:myspace"

    @property
    def name(self) -> str:
        return "MyAgent"

    def _load_tools(self):
        from spaces.myspace.tools import my_tools
        return {
            "do_action": my_tools.do_action,
            "query_data": my_tools.query_data,
        }

    def _get_tool_name(self, event_type: str):
        return self.TOOL_MAP.get(event_type)
```

2. Add routing in `python/swarm/event_team/event_router.py`
3. Add lazy import in `python/swarm/backend_agents/__init__.py`
