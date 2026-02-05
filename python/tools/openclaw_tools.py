"""
OpenClaw Integration Tools for VibeMind

Tools that Rachel can use to delegate tasks to OpenClaw.
These tools connect to the clawed_voice bridge to execute
messaging, web, and browser tasks via OpenClaw Gateway.

Usage:
    Rachel: "Sende WhatsApp an Max: Treffen wir uns morgen?"
    → openclaw_send({"task_type": "messaging.whatsapp", "recipient": "Max", "content": "..."})

    Rachel: "OpenClaw Status"
    → openclaw_status({})

    Rachel: "Was hat OpenClaw gemacht?"
    → openclaw_notifications({})
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Add clawed_voice to path
CLAWED_VOICE_PATH = os.getenv(
    "CLAWED_VOICE_PATH",
    str(Path(__file__).parent.parent.parent.parent / "clawed_voice")
)
if CLAWED_VOICE_PATH not in sys.path:
    sys.path.insert(0, CLAWED_VOICE_PATH)


def _get_bridge():
    """Get the clawed_voice bridge, importing lazily."""
    try:
        from clawed_voice import get_bridge
        return get_bridge()
    except ImportError as e:
        logger.error(f"Failed to import clawed_voice: {e}")
        logger.info(f"Looked in: {CLAWED_VOICE_PATH}")
        return None


def openclaw_status(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Check OpenClaw Gateway connection status.

    ElevenLabs Tool Definition:
    {
        "name": "openclaw_status",
        "description": "Prueft den Status der OpenClaw Verbindung. Zeigt ob Gateway laeuft und verbunden ist.",
        "parameters": {}
    }

    Returns:
        Dict with connected status, gateway state, and pending notifications
    """
    try:
        from clawed_voice import get_status_sync
        status = get_status_sync()

        connected = status.get("connected", False)
        gateway = status.get("gateway", {})
        pending = status.get("notifications_pending", 0)

        if connected:
            message = "OpenClaw ist verbunden und bereit"
        elif gateway.get("state") == "running":
            message = "OpenClaw Gateway laeuft, aber nicht verbunden"
        else:
            message = "OpenClaw Gateway ist nicht aktiv"

        return {
            "success": True,
            "connected": connected,
            "gateway_state": gateway.get("state", "unknown"),
            "notifications_pending": pending,
            "message": message,
        }
    except ImportError:
        return {
            "success": False,
            "connected": False,
            "message": "clawed_voice Modul nicht gefunden. Bitte installieren.",
            "error": "ImportError",
        }
    except Exception as e:
        logger.error(f"openclaw_status error: {e}")
        return {
            "success": False,
            "connected": False,
            "message": f"Fehler: {str(e)}",
            "error": str(e),
        }


def openclaw_send(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Send a task to OpenClaw Gateway.

    ElevenLabs Tool Definition:
    {
        "name": "openclaw_send",
        "description": "Sendet eine Aufgabe an OpenClaw. Kann Nachrichten senden (WhatsApp, Telegram, Discord), Websuchen durchfuehren, oder Browser steuern.",
        "parameters": {
            "task_type": {
                "type": "string",
                "description": "Art der Aufgabe: messaging.whatsapp, messaging.telegram, messaging.discord, web.search, web.fetch, browser.navigate, browser.screenshot",
                "required": true
            },
            "recipient": {
                "type": "string",
                "description": "Empfaenger fuer Nachrichten (Telefonnummer, Username, etc.)",
                "required": false
            },
            "content": {
                "type": "string",
                "description": "Nachrichtentext oder Suchbegriff",
                "required": false
            },
            "url": {
                "type": "string",
                "description": "URL fuer web.fetch oder browser.navigate",
                "required": false
            }
        }
    }

    Args:
        params: Task parameters including task_type and task-specific fields

    Returns:
        Dict with success status, job_id, and result/error
    """
    params = params or {}
    task_type = params.get("task_type", "")

    if not task_type:
        return {
            "success": False,
            "message": "Kein task_type angegeben",
            "error": "missing_task_type",
        }

    # Normalize German parameter names
    normalized = _normalize_params(params)

    try:
        from clawed_voice import execute_task_sync

        result = execute_task_sync(task_type, normalized, store_result=True)

        if result.get("success"):
            message = _format_success_message(task_type, normalized)
        else:
            message = f"Fehlgeschlagen: {result.get('error', 'Unbekannter Fehler')}"

        return {
            "success": result.get("success", False),
            "job_id": result.get("job_id"),
            "message": message,
            "result": result.get("result"),
            "error": result.get("error"),
        }

    except ImportError:
        return {
            "success": False,
            "message": "clawed_voice Modul nicht gefunden",
            "error": "ImportError",
        }
    except Exception as e:
        logger.error(f"openclaw_send error: {e}")
        return {
            "success": False,
            "message": f"Fehler: {str(e)}",
            "error": str(e),
        }


def openclaw_notifications(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Retrieve pending OpenClaw notifications.

    ElevenLabs Tool Definition:
    {
        "name": "openclaw_notifications",
        "description": "Ruft ausstehende Benachrichtigungen von OpenClaw ab. Zeigt Ergebnisse von abgeschlossenen Aufgaben.",
        "parameters": {
            "limit": {
                "type": "integer",
                "description": "Maximale Anzahl Benachrichtigungen (Standard: 5)",
                "required": false
            }
        }
    }

    Returns:
        Dict with count and list of notification summaries
    """
    params = params or {}
    limit = params.get("limit", 5)

    try:
        from clawed_voice import get_notifications_sync

        result = get_notifications_sync(limit=limit)
        count = result.get("count", 0)
        notifications = result.get("notifications", [])

        if count == 0:
            message = "Keine neuen Benachrichtigungen von OpenClaw"
        elif count == 1:
            message = f"Eine Benachrichtigung: {notifications[0].get('summary', '')}"
        else:
            summaries = [n.get("summary", "") for n in notifications[:3]]
            message = f"{count} Benachrichtigungen: " + ", ".join(summaries)

        return {
            "success": True,
            "count": count,
            "message": message,
            "notifications": notifications,
        }

    except ImportError:
        return {
            "success": False,
            "count": 0,
            "message": "clawed_voice Modul nicht gefunden",
            "error": "ImportError",
        }
    except Exception as e:
        logger.error(f"openclaw_notifications error: {e}")
        return {
            "success": False,
            "count": 0,
            "message": f"Fehler: {str(e)}",
            "error": str(e),
        }


def openclaw_message(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Send a message via OpenClaw (convenience wrapper).

    ElevenLabs Tool Definition:
    {
        "name": "openclaw_message",
        "description": "Sendet eine Nachricht via WhatsApp, Telegram, Discord oder Slack.",
        "parameters": {
            "platform": {
                "type": "string",
                "description": "Plattform: whatsapp, telegram, discord, slack",
                "required": true
            },
            "recipient": {
                "type": "string",
                "description": "Empfaenger (Telefonnummer, Username, Chat-ID)",
                "required": true
            },
            "content": {
                "type": "string",
                "description": "Nachrichtentext",
                "required": true
            }
        }
    }
    """
    params = params or {}
    platform = params.get("platform", "whatsapp")

    return openclaw_send({
        "task_type": f"messaging.{platform}",
        "recipient": params.get("recipient", params.get("to", "")),
        "content": params.get("content", params.get("message", params.get("text", ""))),
    })


def openclaw_search(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Perform web search via OpenClaw (convenience wrapper).

    ElevenLabs Tool Definition:
    {
        "name": "openclaw_search",
        "description": "Fuehrt eine Websuche via OpenClaw durch.",
        "parameters": {
            "query": {
                "type": "string",
                "description": "Suchbegriff",
                "required": true
            }
        }
    }
    """
    params = params or {}
    query = params.get("query", params.get("q", params.get("suche", "")))

    return openclaw_send({
        "task_type": "web.search",
        "query": query,
    })


# === Helper functions ===

def _normalize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize German parameter names to English."""
    mapping = {
        # Messaging
        "nachricht": "content",
        "text": "content",
        "message": "content",
        "empfaenger": "recipient",
        "an": "recipient",
        "to": "recipient",
        "kanal": "platform",
        "plattform": "platform",
        # Web
        "suche": "query",
        "suchbegriff": "query",
        "frage": "query",
        # General
        "aufgabe": "task",
    }

    normalized = dict(params)
    for german, english in mapping.items():
        if german in normalized and english not in normalized:
            normalized[english] = normalized.pop(german)

    return normalized


def _format_success_message(task_type: str, params: Dict[str, Any]) -> str:
    """Format success message for voice output."""
    if task_type.startswith("messaging."):
        platform = task_type.split(".")[-1].title()
        recipient = params.get("recipient", "")
        return f"{platform} Nachricht an {recipient} wird gesendet"
    elif task_type == "web.search":
        query = params.get("query", "")
        return f"Websuche nach '{query}' gestartet"
    elif task_type == "web.fetch":
        return "Webseite wird abgerufen"
    elif task_type.startswith("browser."):
        action = task_type.split(".")[-1]
        return f"Browser {action} wird ausgefuehrt"
    else:
        return "Aufgabe an OpenClaw gesendet"


# === Tool registry for ClientToolsManager ===

OPENCLAW_TOOLS = {
    "openclaw_status": {
        "function": openclaw_status,
        "description": "Prueft den OpenClaw Verbindungsstatus",
    },
    "openclaw_send": {
        "function": openclaw_send,
        "description": "Sendet Aufgabe an OpenClaw (Nachrichten, Web, Browser)",
    },
    "openclaw_notifications": {
        "function": openclaw_notifications,
        "description": "Ruft OpenClaw Benachrichtigungen ab",
    },
    "openclaw_message": {
        "function": openclaw_message,
        "description": "Sendet Nachricht via WhatsApp/Telegram/Discord",
    },
    "openclaw_search": {
        "function": openclaw_search,
        "description": "Fuehrt Websuche via OpenClaw durch",
    },
}


def register_openclaw_tools(client_tools_manager):
    """
    Register OpenClaw tools with ClientToolsManager.

    Call this during tool initialization to make OpenClaw tools
    available to Rachel.
    """
    for name, tool_def in OPENCLAW_TOOLS.items():
        try:
            client_tools_manager.register_tool(
                name=name,
                function=tool_def["function"],
                description=tool_def["description"],
            )
            logger.info(f"Registered OpenClaw tool: {name}")
        except Exception as e:
            logger.error(f"Failed to register {name}: {e}")


__all__ = [
    "openclaw_status",
    "openclaw_send",
    "openclaw_notifications",
    "openclaw_message",
    "openclaw_search",
    "OPENCLAW_TOOLS",
    "register_openclaw_tools",
]
