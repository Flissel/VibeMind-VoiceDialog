# AgentFarm Autogen Space — Design Spec

**Date:** 2026-03-16
**Status:** Approved
**Scope:** Git submodule + AgentFarmBackendAgent + IPC handlers + Dashboard UI

## 1. Overview

Add a dedicated `autogen` space to VibeMind that:

1. Integrates `github.com/Flissel/Autogen_AgentFarm` as a git submodule
2. Provides an `AgentFarmBackendAgent` following the existing BaseBackendAgent pattern
3. Exposes Autogen 0.4 team orchestration as non-blocking tools
4. Wires missing Python IPC handlers in `electron_backend.py`
5. Updates the Dashboard AgentFarm tab to show real Autogen team runs

## 2. Submodule

```bash
git submodule add https://github.com/Flissel/Autogen_AgentFarm.git external/Autogen_AgentFarm
```

The submodule provides team templates, agent configurations, and prompts. VibeMind imports from it but does not modify it — updates flow via `git submodule update`.

## 3. Directory Structure

```
external/Autogen_AgentFarm/              # git submodule

python/spaces/autogen/
├── __init__.py
├── agents/
│   ├── __init__.py
│   └── agentfarm_agent.py               # AgentFarmBackendAgent
├── tools/
│   ├── __init__.py
│   └── agentfarm_tools.py               # 8 tool functions
└── runner/
    ├── __init__.py
    └── team_runner.py                    # Async team executor
```

## 4. Event Types

8 new event types under the `agentfarm.*` prefix:

| Event Type | Tool Function | Voice Example (DE) |
|------------|--------------|-------------------|
| `agentfarm.create_team` | `create_team` | "Erstelle ein Agent-Team für Customer Support" |
| `agentfarm.run` | `run_team` | "Starte das Team mit der Aufgabe FAQ erstellen" |
| `agentfarm.status` | `get_farm_status` | "Wie ist der Status der Agent Farm?" |
| `agentfarm.list_teams` | `list_teams` | "Zeig mir alle Teams" |
| `agentfarm.stop` | `stop_run` | "Stopp den laufenden Run" |
| `agentfarm.results` | `get_run_results` | "Was sind die Ergebnisse?" |
| `agentfarm.list_templates` | `list_templates` | "Welche Team-Templates gibt es?" |
| `agentfarm.collaborate` | `start_collaboration` | "Starte eine Zusammenarbeit aller Agents für X" |

## 5. AgentFarmBackendAgent

File: `python/spaces/autogen/agents/agentfarm_agent.py`

```python
class AgentFarmBackendAgent(BaseBackendAgent):

    @property
    def name(self) -> str:
        return "AgentFarmAgent"

    @property
    def stream(self) -> str:
        return "events:tasks:agentfarm"

    EVENT_TO_TOOL: Dict[str, str] = {
        "agentfarm.create_team":    "create_team",
        "agentfarm.run":            "run_team",
        "agentfarm.status":         "get_farm_status",
        "agentfarm.list_teams":     "list_teams",
        "agentfarm.stop":           "stop_run",
        "agentfarm.results":        "get_run_results",
        "agentfarm.list_templates": "list_templates",
        "agentfarm.collaborate":    "start_collaboration",
    }

    PARAM_MAPPING: Dict[str, Dict[str, str]] = {
        "agentfarm.create_team": {
            "vorlage": "template_id",
            "template": "template_id",
            "name": "team_name",
        },
        "agentfarm.run": {
            "aufgabe": "task",
            "beschreibung": "task",
            "text": "task",
            "team": "team_id",
        },
        "agentfarm.stop": {
            "run": "run_id",
        },
        "agentfarm.results": {
            "run": "run_id",
        },
    }

    def _get_tool_name(self, event_type: str) -> Optional[str]:
        return self.EVENT_TO_TOOL.get(event_type)

    def _load_tools(self) -> Dict[str, Callable]:
        tools = {}
        try:
            from spaces.autogen.tools.agentfarm_tools import (
                create_team, run_team, get_farm_status, list_teams,
                stop_run, get_run_results, list_templates, start_collaboration,
            )
            tools.update({
                "create_team": create_team,
                "run_team": run_team,
                "get_farm_status": get_farm_status,
                "list_teams": list_teams,
                "stop_run": stop_run,
                "get_run_results": get_run_results,
                "list_templates": list_templates,
                "start_collaboration": start_collaboration,
            })
        except ImportError as e:
            logger.warning(f"{self.name}: Could not load tools: {e}")
        return tools


# --- Singleton ---
_agentfarm_agent: Optional[AgentFarmBackendAgent] = None

def get_agentfarm_agent() -> AgentFarmBackendAgent:
    global _agentfarm_agent
    if _agentfarm_agent is None:
        _agentfarm_agent = AgentFarmBackendAgent()
    return _agentfarm_agent

__all__ = ["AgentFarmBackendAgent", "get_agentfarm_agent"]
```

Follows the identical pattern as N8nBackendAgent: `@property` for `name`/`stream`, explicit `_get_tool_name()` + `_load_tools()`, and singleton with `get_agentfarm_agent()`.

## 6. Team Runner (Non-Blocking Execution)

File: `python/spaces/autogen/runner/team_runner.py`

### Why non-blocking works without subprocesses

Autogen 0.4 is async-native. `team.run_stream()` returns an async generator that yields between LLM API calls (I/O-bound). Using `asyncio.create_task()` keeps the event loop free for voice and other agents.

### Design

```python
@dataclass
class RunState:
    run_id: str
    team_id: str
    task: str
    status: str = "running"          # running | completed | failed | cancelled
    step_count: int = 0
    messages: List[Dict] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    cancel_token: Optional[CancellationToken] = None  # initialized in start_run


class TeamRunner:
    """Singleton manager for async Autogen 0.4 team runs."""

    _instance: Optional["TeamRunner"] = None
    _active_runs: Dict[str, RunState]
    MAX_COMPLETED_RUNS = 50  # prune oldest completed runs beyond this

    def __init__(self):
        self._active_runs = {}

    @classmethod
    def get_instance(cls) -> "TeamRunner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start_run(self, team_id: str, team_config: dict, task: str) -> str:
        """Start a team run. Returns run_id immediately."""
        from autogen_core import CancellationToken

        run_id = str(uuid4())
        state = RunState(run_id=run_id, team_id=team_id, task=task)
        state.cancel_token = CancellationToken()
        self._active_runs[run_id] = state
        self._prune_completed()
        asyncio.create_task(self._execute_run(state, team_config))
        _broadcast_to_electron({
            "type": "agentfarm_run_started",
            "run_id": run_id,
            "team_id": team_id,
            "task": task,
        })
        return run_id

    async def _execute_run(self, state: RunState, team_config: dict):
        """Background execution. Streams progress via Electron broadcast."""
        try:
            team = self._build_team(team_config)
            async for message in team.run_stream(
                task=state.task,
                cancellation_token=state.cancel_token,
            ):
                state.step_count += 1
                state.messages.append({
                    "source": message.source,
                    "content": message.content,
                })
                _broadcast_to_electron({
                    "type": "agentfarm_progress",
                    "run_id": state.run_id,
                    "agent": message.source,
                    "content": message.content,
                    "step": state.step_count,
                })
            state.status = "completed"
        except asyncio.CancelledError:
            state.status = "cancelled"
        except Exception as e:
            state.status = "failed"
            state.error = str(e)
        finally:
            state.completed_at = datetime.now()
            _broadcast_to_electron({
                "type": "agentfarm_run_finished",
                "run_id": state.run_id,
                "status": state.status,
                "step_count": state.step_count,
                "error": state.error,
            })

    def cancel_run(self, run_id: str) -> bool:
        state = self._active_runs.get(run_id)
        if state and state.status == "running" and state.cancel_token:
            state.cancel_token.cancel()
            return True
        return False

    def get_status(self) -> Dict:
        return {
            run_id: {
                "team_id": s.team_id,
                "status": s.status,
                "step_count": s.step_count,
                "task": s.task,
                "started_at": s.started_at.isoformat(),
            }
            for run_id, s in self._active_runs.items()
        }

    def _prune_completed(self):
        """Remove oldest completed runs to prevent memory leak."""
        completed = [
            (rid, s) for rid, s in self._active_runs.items()
            if s.status in ("completed", "failed", "cancelled")
        ]
        if len(completed) > self.MAX_COMPLETED_RUNS:
            completed.sort(key=lambda x: x[1].completed_at or datetime.min)
            for rid, _ in completed[: len(completed) - self.MAX_COMPLETED_RUNS]:
                del self._active_runs[rid]

    def _build_team(self, config: dict):
        """Build Autogen 0.4 team from config dict.

        Supports team_type: "selector" (default), "round_robin", "swarm".
        """
        from autogen_agentchat.agents import AssistantAgent
        from autogen_agentchat.teams import (
            SelectorGroupChat, RoundRobinGroupChat, Swarm,
        )
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        model_client = OpenAIChatCompletionClient(model=config.get("model", "gpt-4o"))
        agents = []
        for agent_cfg in config.get("agents", []):
            agents.append(AssistantAgent(
                name=agent_cfg["name"],
                system_message=agent_cfg.get("system_message", ""),
                model_client=model_client,
            ))

        team_type = config.get("team_type", "selector")
        team_classes = {
            "selector": SelectorGroupChat,
            "round_robin": RoundRobinGroupChat,
            "swarm": Swarm,
        }
        team_cls = team_classes.get(team_type, SelectorGroupChat)
        return team_cls(participants=agents, model_client=model_client)
```

### Cancellation

Uses Autogen 0.4's native `CancellationToken` passed to `team.run_stream()`. When `stop_run` is called, the token cancels cooperatively at the framework level — no waiting for the next yield between LLM calls.

## 7. Tool Functions

File: `python/spaces/autogen/tools/agentfarm_tools.py`

All tools return `{"success": bool, "message": str, ...}` and call `_broadcast_to_electron()` for UI updates.

### create_team(template_id, team_name, **kwargs)
- Loads template from `external/Autogen_AgentFarm/` or in-memory registry
- Stores team config in a `teams` dict (in-memory, persisted to SQLite later)
- Broadcasts `agentfarm_team_created`
- Returns: `team_id`, `agent_count`, `agent_names`

### run_team(team_id, task, **kwargs)
- Validates team exists
- Calls `TeamRunner.start_run()` — returns immediately
- Returns: `run_id`, `status: "started"`, `response_hint` for voice

### get_farm_status(**kwargs)
- Calls `TeamRunner.get_status()`
- Returns: `active_runs`, `total_teams`, `run_summaries`

### list_teams(**kwargs)
- Returns all registered team configs with agent counts

### stop_run(run_id, **kwargs)
- Calls `TeamRunner.cancel_run()`
- Returns: `success`, `message`

### get_run_results(run_id, **kwargs)
- Returns full message history from `RunState.messages`
- Includes: `step_count`, `status`, `duration`, `messages[]`

### list_templates(**kwargs)

- Scans `external/Autogen_AgentFarm/` for template configs
- Guard: if submodule not initialized, returns `{"success": False, "message": "AgentFarm submodule not found. Run: git submodule update --init external/Autogen_AgentFarm"}`
- Returns: `templates[]` with `id`, `name`, `description`, `agent_count`

### start_collaboration(task, goal, **kwargs)

- Wraps `collaboration_tools.start_collaboration()` from Minibook
- Guard: checks `MINIBOOK_ENABLED` env var; returns clear error if disabled
- Detects needed spaces, posts to Minibook with @mentions
- Returns: `post_id`, `mentioned_agents`, `needed_spaces`

## 8. IPC Handlers (electron_backend.py)

6 new handler methods + message routing entries:

### Message Routing

```python
# In _handle_message() dispatch dict:
"agentfarm_create_team":  self._handle_agentfarm_create_team,
"agentfarm_run":          self._handle_agentfarm_run,
"agentfarm_status":       self._handle_agentfarm_status,
"agentfarm_list_teams":   self._handle_agentfarm_list_teams,
"agentfarm_stop_run":     self._handle_agentfarm_stop_run,
"agentfarm_run_results":  self._handle_agentfarm_run_results,
```

### Handler Pattern

Handlers use `self.send_message()` (NOT `return`) — `sendToPythonAndWait` on the Electron side listens for stdout JSON. Parameterless handlers for queries, `message` param for commands:

```python
# Parameterless (status/list queries)
async def _handle_agentfarm_status(self):
    try:
        from spaces.autogen.tools.agentfarm_tools import get_farm_status
        result = get_farm_status()
        self.send_message({"type": "agentfarm_status_result", **result})
    except Exception as e:
        self.send_message({"type": "agentfarm_status_result", "success": False, "message": str(e)})

async def _handle_agentfarm_list_teams(self):
    try:
        from spaces.autogen.tools.agentfarm_tools import list_teams
        result = list_teams()
        self.send_message({"type": "agentfarm_list_teams_result", **result})
    except Exception as e:
        self.send_message({"type": "agentfarm_list_teams_result", "success": False, "message": str(e)})

# With message param (commands needing input)
async def _handle_agentfarm_run(self, message):
    try:
        from spaces.autogen.tools.agentfarm_tools import run_team
        team_id = message.get("team_id", "")
        task = message.get("task", "")
        result = await run_team(team_id=team_id, task=task)
        self.send_message({"type": "agentfarm_run_result", **result})
    except Exception as e:
        self.send_message({"type": "agentfarm_run_result", "success": False, "message": str(e)})
```

## 9. Electron IPC Additions

### main.js — 6 new ipcMain.handle() entries

```javascript
ipcMain.handle('agentfarm:create-team', async (_, templateId, config) => {
    return await sendToPythonAndWait(
        { type: 'agentfarm_create_team', template_id: templateId, ...config },
        'agentfarm_create_team_result'
    );
});

ipcMain.handle('agentfarm:run-team', async (_, teamId, task) => {
    return await sendToPythonAndWait(
        { type: 'agentfarm_run', team_id: teamId, task },
        'agentfarm_run_result'
    );
});

ipcMain.handle('agentfarm:farm-status', async () => {
    return await sendToPythonAndWait(
        { type: 'agentfarm_status' },
        'agentfarm_status_result'
    );
});

ipcMain.handle('agentfarm:list-teams', async () => {
    return await sendToPythonAndWait(
        { type: 'agentfarm_list_teams' },
        'agentfarm_list_teams_result'
    );
});

ipcMain.handle('agentfarm:stop-run', async (_, runId) => {
    return await sendToPythonAndWait(
        { type: 'agentfarm_stop_run', run_id: runId },
        'agentfarm_stop_run_result'
    );
});

ipcMain.handle('agentfarm:run-results', async (_, runId) => {
    return await sendToPythonAndWait(
        { type: 'agentfarm_run_results', run_id: runId },
        'agentfarm_run_results_result'
    );
});
```

### agentfarm-preload.js — 6 new exposed methods

```javascript
createTeam: (templateId, config) => ipcRenderer.invoke('agentfarm:create-team', templateId, config),
runTeam: (teamId, task) => ipcRenderer.invoke('agentfarm:run-team', teamId, task),
getAgentFarmStatus: () => ipcRenderer.invoke('agentfarm:farm-status'),
listTeams: () => ipcRenderer.invoke('agentfarm:list-teams'),
stopRun: (runId) => ipcRenderer.invoke('agentfarm:stop-run', runId),
getRunResults: (runId) => ipcRenderer.invoke('agentfarm:run-results', runId),
```

### Push Messages (Python → Electron, no request needed)

These are broadcast via `_broadcast_to_electron()` and arrive via `onMessage()`:

| Message Type | When | Payload |
|-------------|------|---------|
| `agentfarm_team_created` | Team created | `team_id`, `team_name`, `agent_count` |
| `agentfarm_run_started` | Run kicked off | `run_id`, `team_id`, `task` |
| `agentfarm_progress` | Each agent message | `run_id`, `agent`, `content`, `step` |
| `agentfarm_run_finished` | Run done/failed/cancelled | `run_id`, `status`, `step_count`, `error` |

## 10. Event Router + Agent Registry

### event_router.py additions

```python
STREAM_TASKS_AGENTFARM = "events:tasks:agentfarm"

# In EVENT_TYPE_TO_STREAM mapping:
"agentfarm.create_team":    STREAM_TASKS_AGENTFARM,
"agentfarm.run":            STREAM_TASKS_AGENTFARM,
"agentfarm.status":         STREAM_TASKS_AGENTFARM,
"agentfarm.list_teams":     STREAM_TASKS_AGENTFARM,
"agentfarm.stop":           STREAM_TASKS_AGENTFARM,
"agentfarm.results":        STREAM_TASKS_AGENTFARM,
"agentfarm.list_templates": STREAM_TASKS_AGENTFARM,
"agentfarm.collaborate":    STREAM_TASKS_AGENTFARM,

# In get_category() method:
elif stream == cls.STREAM_TASKS_AGENTFARM:
    return "agentfarm"

# In all_streams() class method — add to list:
cls.STREAM_TASKS_AGENTFARM,
```

### backend_agents/__init__.py additions

```python
# Top-level getter function:
def get_agentfarm_agent():
    from spaces.autogen.agents.agentfarm_agent import get_agentfarm_agent
    return get_agentfarm_agent()

# In __getattr__ function — add entry:
if name == "AgentFarmBackendAgent":
    from spaces.autogen.agents.agentfarm_agent import AgentFarmBackendAgent
    return AgentFarmBackendAgent

# In __all__ list — add:
"AgentFarmBackendAgent", "get_agentfarm_agent",
```

## 11. Intent Classifier Update

Add to `CLASSIFIER_PROMPT_TEMPLATE` in `intent_classifier.py`:

```
**AgentFarm Events:**
- agentfarm.create_team — Create an agent team (params: template_id, team_name)
- agentfarm.run — Start a team run (params: team_id, task)
- agentfarm.status — Get agent farm overview
- agentfarm.list_teams — List all teams
- agentfarm.stop — Stop a running team (params: run_id)
- agentfarm.results — Get run results (params: run_id)
- agentfarm.list_templates — List available team templates
- agentfarm.collaborate — Multi-space collaboration (params: task, goal)
```

## 12. Dashboard UI Update

### ProjectProgress.tsx → AgentFarmPanel.tsx

Replace the CodingEngine project view with a real Autogen team dashboard:

**Left Panel:** Team list
- Each team shows: name, agent count, status dot (idle/running/done)
- "New Team" button opens template selector

**Right Panel:** Run view (when team selected)
- If idle: task input + "Run" button
- If running: live message stream (agent name + content per step), progress indicator, "Stop" button
- If completed: full message history, duration, step count

**Data flow:**
```
AgentFarmPanel
  → useEffect: listTeams() on mount
  → useEffect: onMessage('agentfarm_progress') for live updates
  → onClick "Run": runTeam(teamId, task)
  → onClick "Stop": stopRun(runId)
```

## 13. Dependencies

Already in requirements.txt:
```
autogen-agentchat~=0.4
autogen-core>=0.4.0
autogen-ext[grpc,ollama]>=0.4.0
```

No new dependencies needed. All imports are lazy to keep startup fast.

## 14. Files to Create/Modify

### New Files (7)
1. `python/spaces/autogen/__init__.py`
2. `python/spaces/autogen/agents/__init__.py`
3. `python/spaces/autogen/agents/agentfarm_agent.py`
4. `python/spaces/autogen/tools/__init__.py`
5. `python/spaces/autogen/tools/agentfarm_tools.py`
6. `python/spaces/autogen/runner/__init__.py`
7. `python/spaces/autogen/runner/team_runner.py`

### Modified Files (7)
1. `python/electron_backend.py` — 6 new handler methods + routing entries
2. `python/swarm/backend_agents/__init__.py` — register `get_agentfarm_agent`
3. `python/swarm/event_team/event_router.py` — 8 new stream mappings
4. `python/swarm/orchestrator/intent_classifier.py` — agentfarm event types
5. `electron-app/main.js` — 6 new ipcMain.handle() entries
6. `electron-app/agentfarm-preload.js` — 6 new exposed methods
7. `electron-app/dashboard/src/features/AgentFarm.tsx` — replace ProjectProgress with AgentFarmPanel

### Submodule (1)
- `external/Autogen_AgentFarm` — git submodule add
