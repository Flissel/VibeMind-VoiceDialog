"""
Minibook Tools - Direct voice-controllable tool functions

These are the sync tool functions mapped to minibook.* event types
in the IntentOrchestrator. They follow the standard VibeMind tool
return pattern: {"success": bool, "message": str, ...}
"""

import logging
import sys
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _debug_print(msg: str):
    print(f"[Python DEBUG] [MinibookTools] {msg}", file=sys.stderr, flush=True)


def get_minibook_status() -> Dict[str, Any]:
    """
    Check Minibook connection status.

    Event: minibook.status
    Voice: "Minibook Status", "Ist Minibook verbunden?"
    """
    from .minibook_client import get_minibook_client

    client = get_minibook_client()
    status = client.get_status()

    if status.get("success"):
        agent_count = status.get("agent_count", 0)
        registered = status.get("registered_agents", [])
        reg_str = ", ".join(registered) if registered else "keine"
        return {
            "success": True,
            "message": f"Minibook verbunden ({status['url']})",
            "response_hint": (
                f"Minibook ist verbunden. "
                f"{agent_count} Agents insgesamt, "
                f"davon {len(registered)} von VibeMind registriert: {reg_str}."
            ),
            **status,
        }
    else:
        return {
            "success": False,
            "message": f"Minibook nicht erreichbar: {status.get('error', '?')}",
            "response_hint": (
                f"Minibook ist gerade nicht erreichbar unter {status.get('url', '?')}. "
                "Stelle sicher dass Minibook laeuft."
            ),
            **status,
        }


def start_discussion(
    message: str = "",
    topic: str = "",
) -> Dict[str, Any]:
    """
    Start a discussion in Minibook.

    Event: minibook.discuss
    Voice: "Bespreche X in Minibook", "Starte eine Diskussion zu X"
    """
    from .minibook_client import get_minibook_client

    client = get_minibook_client()

    # Check connection
    status = client.get_status()
    if not status.get("success"):
        return {
            "success": False,
            "response_hint": "Minibook ist nicht erreichbar.",
        }

    project_id = client.project_id
    if not project_id:
        return {
            "success": False,
            "response_hint": "Kein Minibook-Projekt konfiguriert.",
        }

    content = message or topic or "Neue Diskussion"

    try:
        post_data = client.create_post(
            project_id=project_id,
            content=content,
            agent_name="vibemind_orchestrator",
            post_type="discussion",
        )
        post_id = post_data.get("id", "")
        _debug_print(f"Discussion started: post_id={post_id}")

        return {
            "success": True,
            "post_id": post_id,
            "response_hint": f"Diskussion gestartet: {content[:100]}",
        }

    except Exception as e:
        logger.error(f"Failed to start discussion: {e}")
        return {
            "success": False,
            "response_hint": f"Konnte Diskussion nicht starten: {e}",
        }


def get_discussion_results(discussion_id: str = "") -> Dict[str, Any]:
    """
    Get results of a Minibook discussion.

    Event: minibook.results
    Voice: "Was kam bei der Diskussion raus?", "Ergebnisse der Zusammenarbeit"
    """
    from .minibook_client import get_minibook_client

    client = get_minibook_client()

    if not discussion_id:
        # Try to get the most recent discussion
        project_id = client.project_id
        if not project_id:
            return {
                "success": False,
                "response_hint": "Kein Projekt konfiguriert.",
            }

        try:
            posts = client.get_posts(project_id)
            if not posts:
                return {
                    "success": True,
                    "response_hint": "Keine Diskussionen vorhanden.",
                }
            # Take the most recent post
            discussion_id = posts[-1].get("id", "")
        except Exception as e:
            return {
                "success": False,
                "response_hint": f"Fehler beim Abrufen der Diskussionen: {e}",
            }

    if not discussion_id:
        return {
            "success": False,
            "response_hint": "Keine Diskussions-ID verfuegbar.",
        }

    try:
        comments = client.get_comments(discussion_id)

        if not comments:
            return {
                "success": True,
                "discussion_id": discussion_id,
                "comment_count": 0,
                "response_hint": "Noch keine Antworten auf diese Diskussion.",
            }

        # Format results
        results = []
        for comment in comments:
            agent = comment.get("agent_name", "unknown")
            content = comment.get("content", "")
            results.append(f"{agent}: {content[:200]}")

        results_str = "\n".join(results)
        return {
            "success": True,
            "discussion_id": discussion_id,
            "comment_count": len(comments),
            "results": results,
            "response_hint": (
                f"Die Diskussion hat {len(comments)} Antworten:\n{results_str}"
            ),
        }

    except Exception as e:
        logger.error(f"Failed to get discussion results: {e}")
        return {
            "success": False,
            "response_hint": f"Fehler beim Abrufen der Ergebnisse: {e}",
        }


def list_projects() -> Dict[str, Any]:
    """
    List all Minibook projects.

    Event: minibook.list_projects
    Voice: "Welche Minibook-Projekte gibt es?"
    """
    from .minibook_client import get_minibook_client

    client = get_minibook_client()

    status = client.get_status()
    if not status.get("success"):
        return {
            "success": False,
            "response_hint": "Minibook ist nicht erreichbar.",
        }

    try:
        projects = client.list_projects()

        if not projects:
            return {
                "success": True,
                "projects": [],
                "response_hint": "Keine Projekte vorhanden.",
            }

        names = [p.get("name", "?") for p in projects]
        return {
            "success": True,
            "projects": projects,
            "project_count": len(projects),
            "response_hint": f"Es gibt {len(projects)} Projekte: {', '.join(names)}",
        }

    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        return {
            "success": False,
            "response_hint": f"Fehler beim Abrufen der Projekte: {e}",
        }


__all__ = [
    "get_minibook_status",
    "start_discussion",
    "get_discussion_results",
    "list_projects",
]
