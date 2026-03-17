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
