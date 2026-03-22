"""
MiroFish Tools - Voice-controllable tools for MiroFish prediction engine

Each tool wraps a MiroFishClient method and returns a
VibeMind-standard result dict with broadcast to Electron.
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _broadcast_to_electron(message: Dict[str, Any]):
    """Broadcast message to Electron UI."""
    try:
        print(json.dumps(message), flush=True)
    except Exception as e:
        logger.error(f"Broadcast error: {e}")


# ── Status ──────────────────────────────────────────────────────────

def get_status() -> Dict[str, Any]:
    """Check MiroFish connection status."""
    from .mirofish_client import get_mirofish_client

    logger.info("mirofish.status: Checking connection")
    client = get_mirofish_client()
    result = client.get_status()

    _broadcast_to_electron({
        "type": "mirofish_status",
        "status": result.get("status", "unknown"),
        "message": result.get("message", ""),
    })

    return {
        "success": result.get("success", False),
        "message": result.get("message", ""),
        "response_hint": result.get("message", "MiroFish Status unbekannt."),
    }


# ── Prediction (End-to-End) ─────────────────────────────────────────

def simulate(
    requirement: str,
    text: str = None,
    file_path: str = None,
    agent_count: int = 100,
    rounds: int = 10,
) -> Dict[str, Any]:
    """
    Run a full MiroFish prediction simulation.

    Takes seed data (text or file), builds a knowledge graph,
    runs multi-agent simulation, and generates a prediction report.

    Args:
        requirement: What to predict/simulate (e.g., "Public reaction to product launch")
        text: Seed text content
        file_path: Path to a seed document (PDF, MD, TXT)
        agent_count: Number of simulated agents (default 100)
        rounds: Simulation rounds (default 10)

    Returns:
        VibeMind result dict with prediction report
    """
    from .mirofish_client import get_mirofish_client

    logger.info(f"mirofish.simulate: requirement='{requirement}', agents={agent_count}, rounds={rounds}")
    client = get_mirofish_client()

    file_paths = [file_path] if file_path else None

    _broadcast_to_electron({
        "type": "mirofish_status",
        "status": "simulating",
        "message": f"MiroFish Simulation gestartet: {requirement}",
    })

    result = client.run_prediction(
        requirement=requirement,
        text_content=text,
        file_paths=file_paths,
        agent_count=agent_count,
        rounds=rounds,
    )

    if result.get("success"):
        report_content = result.get("report", {}).get("markdown_content", "")
        _broadcast_to_electron({
            "type": "mirofish_result",
            "action": "simulate",
            "requirement": requirement,
            "report_id": result.get("report_id"),
            "graph_id": result.get("graph_id"),
            "simulation_id": result.get("simulation_id"),
        })
        return {
            "success": True,
            "message": report_content or result.get("message", "Simulation abgeschlossen."),
            "response_hint": f"MiroFish Vorhersage-Report fuer '{requirement}' ist fertig.",
            "report_id": result.get("report_id"),
        }
    else:
        _broadcast_to_electron({
            "type": "mirofish_status",
            "status": "error",
            "message": result.get("message", "Simulation fehlgeschlagen"),
        })
        return {
            "success": False,
            "message": result.get("message", "Simulation fehlgeschlagen."),
            "response_hint": "MiroFish Simulation konnte nicht durchgefuehrt werden.",
        }


# ── Graph Operations ────────────────────────────────────────────────

def build_graph(
    requirement: str,
    text: str = None,
    file_path: str = None,
) -> Dict[str, Any]:
    """
    Build a MiroFish knowledge graph from seed data (without simulation).

    Args:
        requirement: Description of the domain
        text: Seed text content
        file_path: Path to a seed document

    Returns:
        VibeMind result dict with project_id and graph status
    """
    from .mirofish_client import get_mirofish_client

    logger.info(f"mirofish.graph.build: requirement='{requirement}'")
    client = get_mirofish_client()

    file_paths = [file_path] if file_path else None

    ontology_result = client.generate_ontology(
        requirement=requirement,
        text_content=text,
        file_paths=file_paths,
    )

    if not ontology_result.get("success"):
        return {
            "success": False,
            "message": ontology_result.get("message", "Ontologie-Erstellung fehlgeschlagen."),
            "response_hint": "MiroFish konnte die Ontologie nicht erstellen.",
        }

    project_id = ontology_result["project_id"]

    build_result = client.build_graph(project_id)
    if not build_result.get("success"):
        return {
            "success": False,
            "message": build_result.get("message", "Graph-Aufbau fehlgeschlagen."),
            "response_hint": "MiroFish konnte den Graph nicht aufbauen.",
        }

    _broadcast_to_electron({
        "type": "mirofish_result",
        "action": "graph_build",
        "project_id": project_id,
        "task_id": build_result.get("task_id"),
    })

    return {
        "success": True,
        "message": f"Graph-Aufbau gestartet fuer Projekt {project_id}.",
        "response_hint": "MiroFish Knowledge Graph wird aufgebaut.",
        "project_id": project_id,
        "task_id": build_result.get("task_id"),
    }


def search_graph(graph_id: str, query: str) -> Dict[str, Any]:
    """
    Search a MiroFish knowledge graph.

    Args:
        graph_id: Graph to search
        query: Search query

    Returns:
        VibeMind result dict with search results
    """
    from .mirofish_client import get_mirofish_client

    logger.info(f"mirofish.graph.search: graph='{graph_id}', query='{query}'")
    client = get_mirofish_client()
    result = client.search_graph(graph_id, query)

    if result.get("success"):
        _broadcast_to_electron({
            "type": "mirofish_result",
            "action": "graph_search",
            "graph_id": graph_id,
            "query": query,
        })
        return {
            "success": True,
            "message": json.dumps(result.get("results", {}), ensure_ascii=False, indent=2),
            "response_hint": f"MiroFish Graph-Suche nach '{query}' abgeschlossen.",
        }
    return {
        "success": False,
        "message": result.get("error", "Suche fehlgeschlagen."),
        "response_hint": "MiroFish Graph-Suche fehlgeschlagen.",
    }


def list_projects() -> Dict[str, Any]:
    """List all MiroFish projects."""
    from .mirofish_client import get_mirofish_client

    logger.info("mirofish.list_projects")
    client = get_mirofish_client()
    result = client.list_projects()

    if result.get("success"):
        projects = result.get("projects", [])
        if not projects:
            return {
                "success": True,
                "message": "Keine MiroFish-Projekte vorhanden.",
                "response_hint": "Es gibt noch keine MiroFish-Projekte.",
            }
        summary = "\n".join(
            f"  - {p.get('name', p.get('id', '?'))}" for p in projects
        )
        return {
            "success": True,
            "message": f"{len(projects)} Projekte:\n{summary}",
            "response_hint": f"Es gibt {len(projects)} MiroFish-Projekte.",
            "projects": projects,
        }
    return {
        "success": False,
        "message": result.get("error", "Projekt-Liste nicht verfuegbar."),
        "response_hint": "MiroFish-Projekte konnten nicht abgerufen werden.",
    }


# ── Report Chat ─────────────────────────────────────────────────────

def chat_report(report_id: str, question: str) -> Dict[str, Any]:
    """
    Chat with MiroFish about a prediction report.

    Args:
        report_id: Report to chat about
        question: Question about the report findings

    Returns:
        VibeMind result dict
    """
    from .mirofish_client import get_mirofish_client

    logger.info(f"mirofish.report.chat: report='{report_id}', q='{question}'")
    client = get_mirofish_client()
    result = client.chat_report(report_id, question)

    if result.get("success"):
        return {
            "success": True,
            "message": result.get("response", ""),
            "response_hint": "MiroFish hat die Frage zum Report beantwortet.",
        }
    return {
        "success": False,
        "message": result.get("error", "Report-Chat fehlgeschlagen."),
        "response_hint": "MiroFish konnte die Frage nicht beantworten.",
    }


# ── Interview ───────────────────────────────────────────────────────

def interview_agent(
    simulation_id: str, agent_name: str, question: str
) -> Dict[str, Any]:
    """
    Interview a simulated agent from a MiroFish simulation.

    Args:
        simulation_id: Simulation containing the agent
        agent_name: Name of the agent to interview
        question: Question to ask

    Returns:
        VibeMind result dict
    """
    from .mirofish_client import get_mirofish_client

    logger.info(f"mirofish.interview: sim='{simulation_id}', agent='{agent_name}'")
    client = get_mirofish_client()
    result = client.interview_agent(simulation_id, agent_name, question)

    if result.get("success"):
        _broadcast_to_electron({
            "type": "mirofish_result",
            "action": "interview",
            "simulation_id": simulation_id,
            "agent_name": agent_name,
        })
        return {
            "success": True,
            "message": result.get("response", ""),
            "response_hint": f"Interview mit Agent '{agent_name}' abgeschlossen.",
        }
    return {
        "success": False,
        "message": result.get("error", "Interview fehlgeschlagen."),
        "response_hint": f"Interview mit '{agent_name}' fehlgeschlagen.",
    }


__all__ = [
    "get_status",
    "simulate",
    "build_graph",
    "search_graph",
    "list_projects",
    "chat_report",
    "interview_agent",
]
