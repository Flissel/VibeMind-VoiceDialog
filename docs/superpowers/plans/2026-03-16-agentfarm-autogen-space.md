# AgentFarm Autogen Space Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated Autogen 0.4 space with backend agent, non-blocking team runner, IPC handlers, and live Dashboard UI.

**Architecture:** Git submodule for team templates, `AgentFarmBackendAgent` following existing `BaseBackendAgent` pattern, async `TeamRunner` using `asyncio.create_task()` with Autogen 0.4's native streaming, 6 new IPC handlers wired through `electron_backend.py`.

**Tech Stack:** Python 3.12, autogen-agentchat 0.4, autogen-core, Electron IPC (stdin/stdout JSON), React + TypeScript (Dashboard)

**Spec:** `docs/superpowers/specs/2026-03-16-agentfarm-autogen-space-design.md`

---

## Chunk 1: Submodule + Python Space Skeleton

### Task 1: Add Git Submodule

**Files:**
- Create: `external/Autogen_AgentFarm` (submodule)
- Modify: `.gitmodules`

- [ ] **Step 1: Add the submodule**

```bash
cd c:/Users/User/Desktop/Voice_dialog_vibemind/VibeMind-VoiceDialog
git submodule add https://github.com/Flissel/Autogen_AgentFarm.git external/Autogen_AgentFarm
```

- [ ] **Step 2: Verify submodule**

Run: `ls external/Autogen_AgentFarm/`
Expected: Directory listing with repo contents (README, src/, etc.)

- [ ] **Step 3: Commit**

```bash
git add .gitmodules external/Autogen_AgentFarm
git commit -m "feat: add Autogen_AgentFarm as git submodule"
```

---

### Task 2: Create Space Directory Skeleton

**Files:**
- Create: `python/spaces/autogen/__init__.py`
- Create: `python/spaces/autogen/agents/__init__.py`
- Create: `python/spaces/autogen/tools/__init__.py`
- Create: `python/spaces/autogen/runner/__init__.py`

- [ ] **Step 1: Create directory structure and empty init files**

```bash
mkdir -p python/spaces/autogen/agents python/spaces/autogen/tools python/spaces/autogen/runner
```

- [ ] **Step 2: Write `python/spaces/autogen/__init__.py`**

```python
"""Autogen AgentFarm space — multi-agent team orchestration via Autogen 0.4."""
```

- [ ] **Step 3: Write `python/spaces/autogen/agents/__init__.py`**

```python
"""AgentFarm backend agent."""
```

- [ ] **Step 4: Write `python/spaces/autogen/tools/__init__.py`**

```python
"""AgentFarm tool functions."""
```

- [ ] **Step 5: Write `python/spaces/autogen/runner/__init__.py`**

```python
"""Async team runner for Autogen 0.4."""
```

- [ ] **Step 6: Commit**

```bash
git add python/spaces/autogen/
git commit -m "feat: scaffold autogen space directory structure"
```

---

## Chunk 2: Team Runner (Core Async Engine)

### Task 3: Write TeamRunner Tests

**Files:**
- Create: `python/tests/test_team_runner.py`

- [ ] **Step 1: Write failing tests for TeamRunner**

```python
"""Tests for TeamRunner — async Autogen 0.4 team executor."""
import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


class TestTeamRunner(unittest.TestCase):
    """Test TeamRunner singleton and run lifecycle."""

    def setUp(self):
        # Reset singleton between tests
        from spaces.autogen.runner.team_runner import TeamRunner
        TeamRunner._instance = None
        self.runner = TeamRunner.get_instance()

    def test_singleton(self):
        from spaces.autogen.runner.team_runner import TeamRunner
        runner2 = TeamRunner.get_instance()
        self.assertIs(self.runner, runner2)

    def test_get_status_empty(self):
        status = self.runner.get_status()
        self.assertEqual(status, {})

    def test_cancel_nonexistent_run(self):
        result = self.runner.cancel_run("nonexistent-id")
        self.assertFalse(result)

    def test_prune_completed_under_limit(self):
        """Pruning does nothing when under MAX_COMPLETED_RUNS."""
        from spaces.autogen.runner.team_runner import RunState
        state = RunState(
            run_id="r1", team_id="t1", task="test",
            status="completed", completed_at=datetime.now(),
        )
        self.runner._active_runs["r1"] = state
        self.runner._prune_completed()
        self.assertIn("r1", self.runner._active_runs)


class TestTeamRunnerAsync(unittest.IsolatedAsyncioTestCase):
    """Test async run execution."""

    async def asyncSetUp(self):
        from spaces.autogen.runner.team_runner import TeamRunner
        TeamRunner._instance = None
        self.runner = TeamRunner.get_instance()

    @patch("spaces.autogen.runner.team_runner._broadcast_to_electron")
    @patch("spaces.autogen.runner.team_runner.TeamRunner._build_team")
    async def test_start_run_returns_run_id(self, mock_build, mock_broadcast):
        """start_run returns a run_id immediately."""
        mock_team = AsyncMock()
        mock_team.run_stream = AsyncMock(return_value=AsyncMock(__aiter__=lambda s: s, __anext__=AsyncMock(side_effect=StopAsyncIteration)))
        mock_build.return_value = mock_team

        run_id = await self.runner.start_run(
            team_id="team-1",
            team_config={"agents": [], "model": "gpt-4o"},
            task="Build a REST API",
        )
        self.assertIsInstance(run_id, str)
        self.assertIn(run_id, self.runner._active_runs)
        # Let background task complete
        await asyncio.sleep(0.1)

    @patch("spaces.autogen.runner.team_runner._broadcast_to_electron")
    async def test_cancel_running_run(self, mock_broadcast):
        """cancel_run sets cancel token on running state."""
        from spaces.autogen.runner.team_runner import RunState
        from unittest.mock import MagicMock

        cancel_token = MagicMock()
        state = RunState(
            run_id="r1", team_id="t1", task="test",
            status="running", cancel_token=cancel_token,
        )
        self.runner._active_runs["r1"] = state

        result = self.runner.cancel_run("r1")
        self.assertTrue(result)
        cancel_token.cancel.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python && python -m pytest tests/test_team_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'spaces.autogen.runner.team_runner'`

---

### Task 4: Implement TeamRunner

**Files:**
- Create: `python/spaces/autogen/runner/team_runner.py`

- [ ] **Step 1: Write the TeamRunner implementation**

```python
"""Async team runner for Autogen 0.4 multi-agent teams.

Non-blocking: uses asyncio.create_task() since Autogen 0.4 is async-native.
LLM API calls are I/O-bound, so the event loop stays free for voice and other agents.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

try:
    from tools.workspace_tools import _broadcast_to_electron
except ImportError:
    def _broadcast_to_electron(msg):
        pass


@dataclass
class RunState:
    """State for a single team run."""
    run_id: str
    team_id: str
    task: str
    status: str = "running"
    step_count: int = 0
    messages: List[Dict] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    cancel_token: object = None  # autogen_core.CancellationToken, set in start_run


class TeamRunner:
    """Singleton manager for async Autogen 0.4 team runs."""

    _instance: Optional["TeamRunner"] = None
    MAX_COMPLETED_RUNS = 50

    def __init__(self):
        self._active_runs: Dict[str, RunState] = {}

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
                entry = {
                    "source": getattr(message, "source", "unknown"),
                    "content": getattr(message, "content", str(message)),
                }
                state.messages.append(entry)
                _broadcast_to_electron({
                    "type": "agentfarm_progress",
                    "run_id": state.run_id,
                    "agent": entry["source"],
                    "content": entry["content"],
                    "step": state.step_count,
                })
            state.status = "completed"
        except asyncio.CancelledError:
            state.status = "cancelled"
        except Exception as e:
            state.status = "failed"
            state.error = str(e)
            logger.error(f"TeamRunner run {state.run_id} failed: {e}")
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
        """Cancel a running team. Returns True if cancelled."""
        state = self._active_runs.get(run_id)
        if state and state.status == "running" and state.cancel_token:
            state.cancel_token.cancel()
            return True
        return False

    def get_status(self) -> Dict:
        """Return status of all runs."""
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

    def get_run(self, run_id: str) -> Optional[RunState]:
        """Get a specific run state."""
        return self._active_runs.get(run_id)

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

        model_client = OpenAIChatCompletionClient(
            model=config.get("model", "gpt-4o"),
        )
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

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd python && python -m pytest tests/test_team_runner.py -v`
Expected: All 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add python/spaces/autogen/runner/team_runner.py python/tests/test_team_runner.py
git commit -m "feat: implement TeamRunner for async Autogen 0.4 team execution"
```

---

## Chunk 3: Tool Functions + Backend Agent

### Task 5: Write AgentFarm Tool Tests

**Files:**
- Create: `python/tests/test_agentfarm_tools.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for AgentFarm tool functions."""
import os
import unittest
from unittest.mock import patch, MagicMock


class TestAgentFarmTools(unittest.TestCase):

    @patch("spaces.autogen.tools.agentfarm_tools._broadcast_to_electron")
    def test_create_team_from_config(self, mock_broadcast):
        from spaces.autogen.tools.agentfarm_tools import create_team
        result = create_team(
            template_id=None,
            team_name="TestTeam",
            team_config={
                "agents": [
                    {"name": "planner", "system_message": "You plan."},
                    {"name": "coder", "system_message": "You code."},
                ],
                "team_type": "selector",
                "model": "gpt-4o",
            },
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["agent_count"], 2)
        self.assertIn("team_id", result)

    def test_list_teams_empty(self):
        from spaces.autogen.tools.agentfarm_tools import _team_registry
        _team_registry.clear()
        from spaces.autogen.tools.agentfarm_tools import list_teams
        result = list_teams()
        self.assertTrue(result["success"])
        self.assertEqual(result["team_count"], 0)

    def test_get_farm_status(self):
        from spaces.autogen.tools.agentfarm_tools import get_farm_status
        result = get_farm_status()
        self.assertTrue(result["success"])
        self.assertIn("total_teams", result)

    def test_stop_run_nonexistent(self):
        from spaces.autogen.tools.agentfarm_tools import stop_run
        result = stop_run(run_id="nonexistent")
        self.assertFalse(result["success"])

    def test_get_run_results_nonexistent(self):
        from spaces.autogen.tools.agentfarm_tools import get_run_results
        result = get_run_results(run_id="nonexistent")
        self.assertFalse(result["success"])

    def test_list_templates_no_submodule(self):
        from spaces.autogen.tools.agentfarm_tools import list_templates, _SUBMODULE_PATH
        with patch.object(type(_SUBMODULE_PATH), "is_dir", return_value=False):
            result = list_templates()
            self.assertFalse(result["success"])
            self.assertIn("submodule", result["message"].lower())

    @patch.dict(os.environ, {"MINIBOOK_ENABLED": "false"})
    def test_start_collaboration_minibook_disabled(self):
        from spaces.autogen.tools.agentfarm_tools import start_collaboration
        result = start_collaboration(task="test", goal="test")
        self.assertFalse(result["success"])
        self.assertIn("minibook", result["message"].lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python && python -m pytest tests/test_agentfarm_tools.py -v`
Expected: FAIL — `ModuleNotFoundError`

---

### Task 6: Implement Tool Functions

**Files:**
- Create: `python/spaces/autogen/tools/agentfarm_tools.py`

- [ ] **Step 1: Write the tool implementations**

```python
"""AgentFarm tool functions for Autogen 0.4 team orchestration.

All tools return {"success": bool, "message": str, ...} and broadcast
UI updates via _broadcast_to_electron().
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

try:
    from tools.workspace_tools import _broadcast_to_electron
except ImportError:
    def _broadcast_to_electron(msg):
        pass

# In-memory team registry: team_id -> team_config
_team_registry: Dict[str, Dict[str, Any]] = {}

# Path to submodule
_SUBMODULE_PATH = Path(__file__).resolve().parents[4] / "external" / "Autogen_AgentFarm"


def create_team(
    template_id: Optional[str] = None,
    team_name: Optional[str] = None,
    team_config: Optional[Dict] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Create a new agent team from template or config."""
    if template_id and not team_config:
        tpl = _load_template(template_id)
        if not tpl:
            return {"success": False, "message": f"Template '{template_id}' not found."}
        team_config = tpl

    if not team_config or "agents" not in team_config:
        return {"success": False, "message": "No team config or template_id provided."}

    team_id = str(uuid4())
    name = team_name or team_config.get("name", f"Team-{team_id[:8]}")
    team_config["name"] = name

    _team_registry[team_id] = team_config
    agent_names = [a["name"] for a in team_config.get("agents", [])]

    _broadcast_to_electron({
        "type": "agentfarm_team_created",
        "team_id": team_id,
        "team_name": name,
        "agent_count": len(agent_names),
    })

    return {
        "success": True,
        "message": f"Team '{name}' created with {len(agent_names)} agents.",
        "team_id": team_id,
        "team_name": name,
        "agent_count": len(agent_names),
        "agent_names": agent_names,
        "response_hint": f"Team {name} mit {len(agent_names)} Agents erstellt.",
    }


async def run_team(team_id: str = "", task: str = "", **kwargs) -> Dict[str, Any]:
    """Start an async team run. Returns immediately with run_id."""
    if not team_id or team_id not in _team_registry:
        return {"success": False, "message": f"Team '{team_id}' not found."}
    if not task:
        return {"success": False, "message": "No task provided."}

    from spaces.autogen.runner.team_runner import TeamRunner
    runner = TeamRunner.get_instance()
    run_id = await runner.start_run(team_id, _team_registry[team_id], task)

    return {
        "success": True,
        "message": f"Team run started.",
        "run_id": run_id,
        "team_id": team_id,
        "status": "started",
        "response_hint": f"Team-Run gestartet. Run-ID: {run_id[:8]}",
    }


def get_farm_status(**kwargs) -> Dict[str, Any]:
    """Get overview of all teams and runs."""
    from spaces.autogen.runner.team_runner import TeamRunner
    runner = TeamRunner.get_instance()
    runs = runner.get_status()

    running = [r for r in runs.values() if r["status"] == "running"]

    return {
        "success": True,
        "message": f"{len(_team_registry)} teams, {len(running)} active runs.",
        "total_teams": len(_team_registry),
        "active_runs": len(running),
        "runs": runs,
        "response_hint": f"{len(_team_registry)} Teams registriert, {len(running)} laufende Runs.",
    }


def list_teams(**kwargs) -> Dict[str, Any]:
    """List all registered teams."""
    teams = []
    for tid, cfg in _team_registry.items():
        teams.append({
            "team_id": tid,
            "name": cfg.get("name", "unnamed"),
            "agent_count": len(cfg.get("agents", [])),
            "team_type": cfg.get("team_type", "selector"),
            "agent_names": [a["name"] for a in cfg.get("agents", [])],
        })

    return {
        "success": True,
        "message": f"{len(teams)} teams registered.",
        "team_count": len(teams),
        "teams": teams,
        "response_hint": f"{len(teams)} Teams registriert.",
    }


def stop_run(run_id: str = "", **kwargs) -> Dict[str, Any]:
    """Stop a running team."""
    if not run_id:
        return {"success": False, "message": "No run_id provided."}

    from spaces.autogen.runner.team_runner import TeamRunner
    runner = TeamRunner.get_instance()
    cancelled = runner.cancel_run(run_id)

    if cancelled:
        return {
            "success": True,
            "message": f"Run {run_id[:8]} cancelled.",
            "response_hint": "Run gestoppt.",
        }
    return {
        "success": False,
        "message": f"Run '{run_id[:8]}' not found or not running.",
    }


def get_run_results(run_id: str = "", **kwargs) -> Dict[str, Any]:
    """Get results of a completed or running team run."""
    if not run_id:
        return {"success": False, "message": "No run_id provided."}

    from spaces.autogen.runner.team_runner import TeamRunner
    runner = TeamRunner.get_instance()
    state = runner.get_run(run_id)

    if not state:
        return {"success": False, "message": f"Run '{run_id[:8]}' not found."}

    duration = None
    if state.completed_at and state.started_at:
        duration = (state.completed_at - state.started_at).total_seconds()

    return {
        "success": True,
        "message": f"Run {run_id[:8]}: {state.status}, {state.step_count} steps.",
        "run_id": run_id,
        "status": state.status,
        "step_count": state.step_count,
        "duration_seconds": duration,
        "messages": state.messages,
        "error": state.error,
        "response_hint": f"Run {state.status}: {state.step_count} Schritte.",
    }


def list_templates(**kwargs) -> Dict[str, Any]:
    """List available team templates from the AgentFarm submodule."""
    if not _SUBMODULE_PATH.is_dir():
        return {
            "success": False,
            "message": "AgentFarm submodule not found. Run: git submodule update --init external/Autogen_AgentFarm",
        }

    templates = []
    # Scan for JSON template files in submodule
    for p in _SUBMODULE_PATH.rglob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if "agents" in data:
                templates.append({
                    "id": p.stem,
                    "name": data.get("name", p.stem),
                    "description": data.get("description", ""),
                    "agent_count": len(data.get("agents", [])),
                    "path": str(p.relative_to(_SUBMODULE_PATH)),
                })
        except (json.JSONDecodeError, OSError):
            continue

    return {
        "success": True,
        "message": f"{len(templates)} templates found.",
        "templates": templates,
        "response_hint": f"{len(templates)} Team-Templates verfuegbar.",
    }


def start_collaboration(task: str = "", goal: str = "", **kwargs) -> Dict[str, Any]:
    """Start multi-space collaboration via Minibook."""
    enabled = os.getenv("MINIBOOK_ENABLED", "false").lower() == "true"
    if not enabled:
        return {
            "success": False,
            "message": "Minibook is disabled. Set MINIBOOK_ENABLED=true in .env.",
        }

    try:
        from spaces.minibook.tools.collaboration_tools import start_collaboration as _collab
        return _collab(task=task, goal=goal)
    except ImportError as e:
        return {"success": False, "message": f"Minibook not available: {e}"}


def _load_template(template_id: str) -> Optional[Dict]:
    """Load a template from the submodule by ID."""
    if not _SUBMODULE_PATH.is_dir():
        return None
    for p in _SUBMODULE_PATH.rglob("*.json"):
        if p.stem == template_id:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if "agents" in data:
                    return data
            except (json.JSONDecodeError, OSError):
                pass
    return None
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd python && python -m pytest tests/test_agentfarm_tools.py -v`
Expected: All 7 tests PASS

- [ ] **Step 3: Commit**

```bash
git add python/spaces/autogen/tools/agentfarm_tools.py python/tests/test_agentfarm_tools.py
git commit -m "feat: implement AgentFarm tool functions with template loading and collaboration"
```

---

### Task 7: Implement AgentFarmBackendAgent

**Files:**
- Create: `python/spaces/autogen/agents/agentfarm_agent.py`
- Reference: `python/spaces/n8n/agents/n8n_agent.py` (identical pattern)

- [ ] **Step 1: Write the agent**

```python
"""AgentFarm backend agent for Autogen 0.4 team orchestration.

Follows the BaseBackendAgent pattern — routes agentfarm.* events to tool functions.
"""
import logging
from typing import Callable, Dict, Optional

from swarm.backend_agents.base_agent import BaseBackendAgent

logger = logging.getLogger(__name__)


class AgentFarmBackendAgent(BaseBackendAgent):
    """Backend agent for the Autogen AgentFarm space."""

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

    @property
    def name(self) -> str:
        return "AgentFarmAgent"

    @property
    def stream(self) -> str:
        return "events:tasks:agentfarm"

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

- [ ] **Step 2: Verify import works**

Run: `cd python && python -c "from spaces.autogen.agents.agentfarm_agent import get_agentfarm_agent; a = get_agentfarm_agent(); print(a.name, a.stream)"`
Expected: `AgentFarmAgent events:tasks:agentfarm`

- [ ] **Step 3: Commit**

```bash
git add python/spaces/autogen/agents/agentfarm_agent.py
git commit -m "feat: implement AgentFarmBackendAgent with EVENT_TO_TOOL mapping"
```

---

## Chunk 4: Swarm Registration (Event Router + Agent Registry)

### Task 8: Register in Event Router

**Files:**
- Modify: `python/swarm/event_team/event_router.py`
  - Add `STREAM_TASKS_AGENTFARM` constant (~line 41, after `STREAM_TASKS_N8N`)
  - Add 8 event mappings in `STREAM_MAPPING` (~line 185, after n8n entries)
  - Add `get_category()` branch (~line 255, after n8n category)
  - Add to `all_streams()` list (~line 277, after `STREAM_TASKS_N8N`)

- [ ] **Step 1: Add stream constant**

After `STREAM_TASKS_N8N = "events:tasks:n8n"` (line 40), add:

```python
STREAM_TASKS_AGENTFARM = "events:tasks:agentfarm"
```

- [ ] **Step 2: Add event-to-stream mappings**

After the n8n entries (line 184), add:

```python
# agentfarm tasks -> agentfarm stream (Autogen team orchestration)
"agentfarm.create_team": STREAM_TASKS_AGENTFARM,
"agentfarm.run": STREAM_TASKS_AGENTFARM,
"agentfarm.status": STREAM_TASKS_AGENTFARM,
"agentfarm.list_teams": STREAM_TASKS_AGENTFARM,
"agentfarm.stop": STREAM_TASKS_AGENTFARM,
"agentfarm.results": STREAM_TASKS_AGENTFARM,
"agentfarm.list_templates": STREAM_TASKS_AGENTFARM,
"agentfarm.collaborate": STREAM_TASKS_AGENTFARM,
```

- [ ] **Step 3: Add get_category() branch**

In the `get_category()` method (instance method, uses `self` not `cls`), after the n8n branch, add:

```python
elif stream == self.STREAM_TASKS_AGENTFARM:
    return "agentfarm"
```

- [ ] **Step 4: Add to all_streams()**

In the `all_streams()` list, add `cls.STREAM_TASKS_AGENTFARM` after the n8n entry.

- [ ] **Step 5: Commit**

```bash
git add python/swarm/event_team/event_router.py
git commit -m "feat: register agentfarm stream and event mappings in event router"
```

---

### Task 9: Register in Agent Registry

**Files:**
- Modify: `python/swarm/backend_agents/__init__.py`
  - Add `get_agentfarm_agent` function (~line 60, after `get_n8n_agent`)
  - Add `__getattr__` entry for `AgentFarmBackendAgent`
  - Add to `__all__` list

- [ ] **Step 1: Add getter function**

After the existing `get_n8n_agent()` function (around line 59), add:

```python
def get_agentfarm_agent():
    """Lazy-load AgentFarm backend agent."""
    from spaces.autogen.agents.agentfarm_agent import get_agentfarm_agent as _get
    return _get()
```

- [ ] **Step 2: Add __getattr__ entry**

In the `__getattr__` function, add a new `elif` branch:

```python
if name == "AgentFarmBackendAgent":
    from spaces.autogen.agents.agentfarm_agent import AgentFarmBackendAgent
    return AgentFarmBackendAgent
```

- [ ] **Step 3: Update __all__**

Add `"AgentFarmBackendAgent"` and `"get_agentfarm_agent"` to the `__all__` list.

- [ ] **Step 4: Verify import**

Run: `cd python && python -c "from swarm.backend_agents import get_agentfarm_agent; print(get_agentfarm_agent().name)"`
Expected: `AgentFarmAgent`

- [ ] **Step 5: Commit**

```bash
git add python/swarm/backend_agents/__init__.py
git commit -m "feat: register AgentFarmBackendAgent in agent registry"
```

---

## Chunk 5: IPC Handlers (Python + Electron)

### Task 10: Add Python IPC Handlers

**Files:**
- Modify: `python/electron_backend.py`
  - Add 6 handler methods (after existing n8n handlers, ~line 2960)
  - Add 6 routing entries in message dispatch (~line 2550, after n8n entries)

- [ ] **Step 1: Add message routing entries**

In the `_handle_message()` method, after the n8n dispatch entries (around line 2550), add:

```python
elif msg_type == "agentfarm_create_team":
    asyncio.create_task(self._handle_agentfarm_create_team(message))

elif msg_type == "agentfarm_run":
    asyncio.create_task(self._handle_agentfarm_run(message))

elif msg_type == "agentfarm_status":
    asyncio.create_task(self._handle_agentfarm_status())

elif msg_type == "agentfarm_list_teams":
    asyncio.create_task(self._handle_agentfarm_list_teams())

elif msg_type == "agentfarm_stop_run":
    asyncio.create_task(self._handle_agentfarm_stop_run(message))

elif msg_type == "agentfarm_run_results":
    asyncio.create_task(self._handle_agentfarm_run_results(message))
```

- [ ] **Step 2: Add handler implementations**

After the existing n8n handler implementations (~line 2960), add:

```python
# ── AgentFarm Handlers ──────────────────────────────────────────

async def _handle_agentfarm_create_team(self, message):
    try:
        from spaces.autogen.tools.agentfarm_tools import create_team
        result = create_team(
            template_id=message.get("template_id"),
            team_name=message.get("team_name"),
            team_config=message.get("team_config"),
        )
        self.send_message({"type": "agentfarm_create_team_result", **result})
    except Exception as e:
        self.send_message({"type": "agentfarm_create_team_result", "success": False, "message": str(e)})

async def _handle_agentfarm_run(self, message):
    try:
        from spaces.autogen.tools.agentfarm_tools import run_team
        result = await run_team(
            team_id=message.get("team_id", ""),
            task=message.get("task", ""),
        )
        self.send_message({"type": "agentfarm_run_result", **result})
    except Exception as e:
        self.send_message({"type": "agentfarm_run_result", "success": False, "message": str(e)})

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

async def _handle_agentfarm_stop_run(self, message):
    try:
        from spaces.autogen.tools.agentfarm_tools import stop_run
        result = stop_run(run_id=message.get("run_id", ""))
        self.send_message({"type": "agentfarm_stop_run_result", **result})
    except Exception as e:
        self.send_message({"type": "agentfarm_stop_run_result", "success": False, "message": str(e)})

async def _handle_agentfarm_run_results(self, message):
    try:
        from spaces.autogen.tools.agentfarm_tools import get_run_results
        result = get_run_results(run_id=message.get("run_id", ""))
        self.send_message({"type": "agentfarm_run_results_result", **result})
    except Exception as e:
        self.send_message({"type": "agentfarm_run_results_result", "success": False, "message": str(e)})
```

- [ ] **Step 3: Commit**

```bash
git add python/electron_backend.py
git commit -m "feat: add AgentFarm IPC handlers in electron_backend.py"
```

---

### Task 11: Add Electron IPC Handlers

**Files:**
- Modify: `electron-app/main.js` (~line 1798, after existing agentfarm handlers)
- Modify: `electron-app/agentfarm-preload.js` (add 6 new methods)

- [ ] **Step 1: Add main.js ipcMain.handle() entries**

After the existing `agentfarm:n8n-delete` handler (line ~1798), add:

```javascript
// ── AgentFarm Autogen Handlers ──────────────────────────────
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

- [ ] **Step 2: Add preload.js methods**

In `electron-app/agentfarm-preload.js`, add inside the `contextBridge.exposeInMainWorld` object, after the existing n8n methods (before `onMessage`):

```javascript
// Autogen team management
createTeam: (templateId, config) => ipcRenderer.invoke('agentfarm:create-team', templateId, config),
runTeam: (teamId, task) => ipcRenderer.invoke('agentfarm:run-team', teamId, task),
getAgentFarmStatus: () => ipcRenderer.invoke('agentfarm:farm-status'),
listTeams: () => ipcRenderer.invoke('agentfarm:list-teams'),
stopRun: (runId) => ipcRenderer.invoke('agentfarm:stop-run', runId),
getRunResults: (runId) => ipcRenderer.invoke('agentfarm:run-results', runId),
```

- [ ] **Step 3: Commit**

```bash
git add electron-app/main.js electron-app/agentfarm-preload.js
git commit -m "feat: add Electron IPC handlers for AgentFarm Autogen operations"
```

---

## Chunk 6: Intent Classifier + Dashboard UI

### Task 12: Update Intent Classifier

**Files:**
- Modify: `python/swarm/orchestrator/intent_classifier.py` (~line 394, after n8n section)

- [ ] **Step 1: Add AgentFarm event types to classifier prompt**

After the N8N section (line ~394), add:

```
### 9. AGENTFARM SPACE (Multi-Agent Teams via Autogen)
Der Bereich fuer Autogen Multi-Agent Teams. Erstellt, startet und verwaltet Teams aus mehreren KI-Agenten.

**Schluesselwoerter:** agent team, agentfarm, autogen, multi-agent, team erstellen, team starten, zusammenarbeit, collaboration

**Event-Types:**
- agentfarm.create_team: Neues Agent-Team erstellen (params: template_id, team_name)
- agentfarm.run: Team-Run starten mit einer Aufgabe (params: team_id, task)
- agentfarm.status: AgentFarm Uebersicht aller Teams und Runs
- agentfarm.list_teams: Alle Teams auflisten
- agentfarm.stop: Laufenden Run stoppen (params: run_id)
- agentfarm.results: Ergebnisse eines Runs abrufen (params: run_id)
- agentfarm.list_templates: Verfuegbare Team-Templates auflisten
- agentfarm.collaborate: Multi-Space Zusammenarbeit starten (params: task, goal)
```

- [ ] **Step 2: Commit**

```bash
git add python/swarm/orchestrator/intent_classifier.py
git commit -m "feat: add AgentFarm event types to intent classifier"
```

---

### Task 13: Update Dashboard AgentFarm Tab

**Files:**
- Modify: `electron-app/dashboard/src/features/AgentFarm.tsx`

- [ ] **Step 1: Replace ProjectProgress import with inline AgentFarm panel**

Update `AgentFarm.tsx` to show real Autogen teams instead of CodingEngine projects. The component should:

1. Call `listTeams()` on mount
2. Listen for `agentfarm_progress` push messages
3. Show team list (left) with status dots
4. Show run view (right) with live message stream
5. "New Team" button → template selector
6. Task input + "Run" button for selected team
7. "Stop" button for running teams

Use the same CSS design system from `electron-app/dashboard/src/styles/globals.css` (glass morphism, status dots, card layout) that the other Dashboard tabs use.

Note: The IPC bridge for the Dashboard (not the standalone agentfarm BrowserView) uses `window.vibemindDashboard` from `electron-app/clawport-preload.js`. The new team management IPC calls need to be added there too, or the AgentFarm tab should use the standalone BrowserView's `window.vibemindAgentFarm` API.

Check which preload the Dashboard uses and wire accordingly.

- [ ] **Step 2: Build and verify**

Run: `cd electron-app && npm run dashboard:build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add electron-app/dashboard/src/features/AgentFarm.tsx
git commit -m "feat: update AgentFarm dashboard tab with live Autogen team management"
```

---

### Task 14: Integration Smoke Test

- [ ] **Step 1: Start the full system**

```bash
cd electron-app && npm start
```

- [ ] **Step 2: Test via Dashboard**

1. Open the AgentFarm tab in the Dashboard
2. Verify "Autogen" sub-tab shows team list (empty initially)
3. Create a team (if templates available from submodule)
4. Verify team appears in the list

- [ ] **Step 3: Test via Voice (if voice is configured)**

Say: "Wie ist der Status der Agent Farm?"
Expected: Rachel responds with team/run overview

- [ ] **Step 4: Review and commit any remaining changes**

```bash
git status
# Review changes, then add only relevant files:
git add python/spaces/autogen/ python/swarm/ python/electron_backend.py electron-app/main.js electron-app/agentfarm-preload.js electron-app/dashboard/src/features/AgentFarm.tsx
git commit -m "feat: AgentFarm Autogen space — complete integration"
```

---

### Task 15: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add AgentFarm to the Ten Spaces table**

In the "Ten Spaces (Domains)" table, add after the Brain row:

```markdown
| AgentFarm | `events:tasks:agentfarm` | AgentFarmAgent | `agentfarm.*` | `python/spaces/autogen/agents/agentfarm_agent.py` |
```

Update the table title from "Ten Spaces" to "Eleven Spaces".

- [ ] **Step 2: Add agentfarm event examples to Intent Classification section**

Add after the N8n Events block:

```
**AgentFarm Events:**
"Erstelle ein Agent-Team"       → agentfarm.create_team {"team_name": "..."}
"Starte das Team"               → agentfarm.run         {"team_id": "...", "task": "..."}
"Agent Farm Status"             → agentfarm.status
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add AgentFarm space to CLAUDE.md architecture docs"
```
