"""
OpenClaw Messaging Tools - ClawedVoice Integration

Tools for messaging (WhatsApp, Telegram), web search, and browser control
via the ClawedVoice bridge to OpenClaw Gateway.

Usage in Desktop Swarm:
    from spaces.OpenClaw.tools.messaging_tools import (
        send_whatsapp,
        send_telegram,
        web_search,
        web_fetch,
        get_openclaw_status,
    )
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def send_whatsapp(recipient: str, message: str) -> str:
    """
    Send a WhatsApp message via OpenClaw.

    Args:
        recipient: Phone number or contact name
        message: Message content to send

    Returns:
        Result message

    Example:
        >>> send_whatsapp("+49123456789", "Hello from VibeMind!")
        "WhatsApp Nachricht an +49123456789 gesendet"
    """
    try:
        from spaces.OpenClaw.clawed_voice import execute_task_sync

        result = execute_task_sync(
            "messaging.whatsapp",
            {"recipient": recipient, "content": message}
        )

        if result.get("success"):
            return f"WhatsApp Nachricht an {recipient} gesendet"
        else:
            return f"Fehler: {result.get('error', 'Unbekannt')}"

    except ImportError:
        return "Fehler: clawed_voice nicht verfuegbar"
    except Exception as e:
        logger.error(f"send_whatsapp failed: {e}")
        return f"Fehler: {str(e)}"


def send_telegram(recipient: str, message: str) -> str:
    """
    Send a Telegram message via OpenClaw.

    Args:
        recipient: Username or chat ID
        message: Message content to send

    Returns:
        Result message

    Example:
        >>> send_telegram("@username", "Hello from VibeMind!")
        "Telegram Nachricht an @username gesendet"
    """
    try:
        from spaces.OpenClaw.clawed_voice import execute_task_sync

        result = execute_task_sync(
            "messaging.telegram",
            {"recipient": recipient, "content": message}
        )

        if result.get("success"):
            return f"Telegram Nachricht an {recipient} gesendet"
        else:
            return f"Fehler: {result.get('error', 'Unbekannt')}"

    except ImportError:
        return "Fehler: clawed_voice nicht verfuegbar"
    except Exception as e:
        logger.error(f"send_telegram failed: {e}")
        return f"Fehler: {str(e)}"


def web_search(query: str) -> str:
    """
    Search the web via OpenClaw.

    Args:
        query: Search query

    Returns:
        Search results summary

    Example:
        >>> web_search("Python asyncio tutorial")
        "Suchergebnisse fuer 'Python asyncio tutorial': ..."
    """
    try:
        from spaces.OpenClaw.clawed_voice import execute_task_sync

        result = execute_task_sync(
            "web.search",
            {"query": query}
        )

        if result.get("success"):
            return f"Suchergebnisse fuer '{query}':\n{result.get('result', '')}"
        else:
            return f"Suchfehler: {result.get('error', 'Unbekannt')}"

    except ImportError:
        return "Fehler: clawed_voice nicht verfuegbar"
    except Exception as e:
        logger.error(f"web_search failed: {e}")
        return f"Fehler: {str(e)}"


def web_fetch(url: str) -> str:
    """
    Fetch and summarize a web page via OpenClaw.

    Args:
        url: URL to fetch

    Returns:
        Page content summary

    Example:
        >>> web_fetch("https://example.com")
        "Inhalt von https://example.com: ..."
    """
    try:
        from spaces.OpenClaw.clawed_voice import execute_task_sync

        result = execute_task_sync(
            "web.fetch",
            {"url": url}
        )

        if result.get("success"):
            return f"Inhalt von {url}:\n{result.get('result', '')}"
        else:
            return f"Abruffehler: {result.get('error', 'Unbekannt')}"

    except ImportError:
        return "Fehler: clawed_voice nicht verfuegbar"
    except Exception as e:
        logger.error(f"web_fetch failed: {e}")
        return f"Fehler: {str(e)}"


def get_pending_notifications(limit: int = 5) -> str:
    """
    Get pending notifications from OpenClaw.

    Args:
        limit: Maximum number of notifications to return

    Returns:
        Summary of pending notifications

    Example:
        >>> get_pending_notifications()
        "2 Benachrichtigungen: ..."
    """
    try:
        from spaces.OpenClaw.clawed_voice import get_notifications_sync

        result = get_notifications_sync(limit=limit)
        count = result.get("count", 0)

        if count == 0:
            return "Keine neuen Benachrichtigungen"

        summaries = []
        for notif in result.get("notifications", []):
            summaries.append(f"- {notif.get('summary', notif.get('task_type'))}")

        return f"{count} Benachrichtigungen:\n" + "\n".join(summaries)

    except ImportError:
        return "Fehler: clawed_voice nicht verfuegbar"
    except Exception as e:
        logger.error(f"get_pending_notifications failed: {e}")
        return f"Fehler: {str(e)}"


def get_openclaw_status() -> str:
    """
    Get OpenClaw Gateway status.

    Returns:
        Status information

    Example:
        >>> get_openclaw_status()
        "OpenClaw: Verbunden, Gateway: Running"
    """
    try:
        from spaces.OpenClaw.clawed_voice import get_status_sync

        status = get_status_sync()

        connected = "Verbunden" if status.get("connected") else "Nicht verbunden"
        gateway = status.get("gateway", {})
        gateway_state = gateway.get("state", "unknown")
        pending = status.get("notifications_pending", 0)

        return (
            f"OpenClaw: {connected}\n"
            f"Gateway: {gateway_state}\n"
            f"Benachrichtigungen: {pending}"
        )

    except ImportError:
        return "Fehler: clawed_voice nicht verfuegbar"
    except Exception as e:
        logger.error(f"get_openclaw_status failed: {e}")
        return f"Fehler: {str(e)}"


# Tool list for AutoGen
MESSAGING_TOOLS = [
    send_whatsapp,
    send_telegram,
    web_search,
    web_fetch,
    get_pending_notifications,
    get_openclaw_status,
]


__all__ = [
    "send_whatsapp",
    "send_telegram",
    "web_search",
    "web_fetch",
    "get_pending_notifications",
    "get_openclaw_status",
    "MESSAGING_TOOLS",
]
