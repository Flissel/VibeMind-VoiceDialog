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


# ---------------------------------------------------------------------------
# Pipeline State (module-level singleton for status tracking)
# ---------------------------------------------------------------------------

_active_pipeline: Optional[Dict[str, Any]] = None
_active_forge: Optional[Dict[str, Any]] = None


async def _ensure_minibook_setup() -> Dict[str, Any]:
    """Register agents + create project at Minibook. Returns {agents, project_id}."""
    import aiohttp
    from spaces.autogen.swarm.api_client import register_agent, load_credentials, save_credentials, api_post
    from spaces.autogen.swarm.knowledge import AGENT_ROLES

    creds = load_credentials()
    async with aiohttp.ClientSession() as session:
        agents = {}
        for name in AGENT_ROLES.keys():
            agent = await register_agent(session, name, creds)
            agents[name] = agent
        save_credentials(creds)

        # Create or find project
        lead_key = list(agents.keys())[0]
        lead_api_key = agents[lead_key].get("api_key", "")
        project = await api_post(session, "/api/v1/projects", {
            "name": f"pipeline-{uuid4().hex[:6]}",
            "description": "Auto-created by VibeMind pipeline trigger",
        }, api_key=lead_api_key)
        project_id = project.get("id", project.get("project_id", ""))

    return {"agents": agents, "project_id": project_id}


def run_pipeline(task_description: str = "", **kwargs) -> Dict[str, Any]:
    """Start the 11-agent SwarmPipeline for code generation.

    Automatically registers agents at Minibook and creates a project.
    Requires Minibook server running (docker compose -f docker-compose.minibook.yml up).
    """
    global _active_pipeline
    if not task_description:
        return {"success": False, "message": "task_description required — beschreibe was generiert werden soll."}

    try:
        import asyncio
        loop = asyncio.new_event_loop()

        # Step 1: Register agents + project at Minibook
        setup = loop.run_until_complete(_ensure_minibook_setup())
        agents = setup["agents"]
        project_id = setup["project_id"]

        # Step 2: Create and run pipeline with aiohttp session
        from spaces.autogen.swarm.pipeline import SwarmPipeline

        async def _run():
            import aiohttp
            async with aiohttp.ClientSession() as session:
                pipeline = SwarmPipeline(agents=agents, project_id=project_id, task_name=task_description[:80])
                return await pipeline.run(session, task_description)

        _active_pipeline = {"status": "running", "task": task_description, "project_id": project_id}
        _broadcast_to_electron({"type": "agentfarm_pipeline_started", "task": task_description[:100], "project_id": project_id})

        result = loop.run_until_complete(_run())
        loop.close()

        _active_pipeline = {"status": "completed", "task": task_description, "project_id": project_id, "result": str(result)[:500]}
        _broadcast_to_electron({"type": "agentfarm_pipeline_completed", "project_id": project_id})

        return {"success": True, "message": f"Pipeline completed for: {task_description[:100]}", "project_id": project_id, "result": str(result)[:500]}
    except Exception as e:
        _active_pipeline = {"status": "error", "error": str(e)}
        logger.error(f"Pipeline failed: {e}")
        return {"success": False, "message": f"Pipeline failed: {e}"}


def get_pipeline_status(**kwargs) -> Dict[str, Any]:
    """Get current pipeline run status."""
    if _active_pipeline:
        return {"success": True, **_active_pipeline, "message": f"Pipeline: {_active_pipeline.get('status', 'unknown')}"}
    return {"success": True, "status": "idle", "message": "Keine Pipeline aktiv."}


def start_forge(project_id: str = "", **kwargs) -> Dict[str, Any]:
    """Start ForgeOrchestrator for continuous improvement.

    Requires Minibook server running. Auto-registers agents if needed.
    """
    global _active_forge
    try:
        import asyncio
        loop = asyncio.new_event_loop()

        setup = loop.run_until_complete(_ensure_minibook_setup())
        agents = setup["agents"]
        pid = project_id or setup["project_id"]

        from spaces.autogen.swarm.forge_orchestrator import ForgeOrchestrator
        import threading

        forge = ForgeOrchestrator(agents=agents, project_id=pid)

        _active_forge = {"status": "running", "project_id": pid}
        _broadcast_to_electron({"type": "agentfarm_forge_started", "project_id": pid})

        # Forge runs its own web server — start in background thread
        def _run_forge():
            global _active_forge
            try:
                bg_loop = asyncio.new_event_loop()
                bg_loop.run_until_complete(forge.start())
            except Exception as e:
                _active_forge = {"status": "error", "error": str(e)}
                logger.error(f"Forge background error: {e}")

        thread = threading.Thread(target=_run_forge, daemon=True, name="forge-server")
        thread.start()
        loop.close()

        return {"success": True, "message": f"Forge gestartet auf Port 8890. Dashboard: http://localhost:8890/forge/status", "project_id": pid}
    except Exception as e:
        _active_forge = {"status": "error", "error": str(e)}
        logger.error(f"Forge failed: {e}")
        return {"success": False, "message": f"Forge failed: {e}"}


def get_forge_status(**kwargs) -> Dict[str, Any]:
    """Get ForgeOrchestrator status."""
    if _active_forge:
        return {"success": True, **_active_forge, "message": f"Forge: {_active_forge.get('status', 'unknown')}"}
    return {"success": True, "status": "idle", "message": "Kein Forge aktiv."}
