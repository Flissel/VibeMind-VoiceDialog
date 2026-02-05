"""
Voice-callable tools for task memory queries.

These tools allow users to query their task history via voice:
- "Was habe ich heute gemacht?" -> task.list_today
- "Zeig meine Task-Historie" -> task.search
- "Was war der letzte Task?" -> task.recent
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine synchronously."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=10)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def get_tasks_today(params: Dict[str, Any]) -> str:
    """
    Was habe ich heute gemacht?

    Returns list of tasks executed today.
    """
    try:
        from memory import get_task_memory_service
        service = get_task_memory_service()

        if not service or not service.is_available:
            return "Task-Gedaechtnis ist nicht verfuegbar."

        async def _fetch():
            return await service.get_tasks_today()

        tasks = _run_async(_fetch())

        if not tasks:
            return "Heute wurden noch keine Tasks ausgefuehrt."

        # Format for voice output
        lines = [f"Heute {len(tasks)} Tasks ausgefuehrt:"]
        for i, t in enumerate(tasks[:10], 1):
            meta = t.get("metadata", {})
            intent = meta.get("intent_type", "unbekannt")
            event = meta.get("event_type", "")
            if event == "task_completed":
                lines.append(f"{i}. {intent} - erledigt")
            elif event == "task_failed":
                lines.append(f"{i}. {intent} - fehlgeschlagen")
            else:
                lines.append(f"{i}. {intent}")

        if len(tasks) > 10:
            lines.append(f"... und {len(tasks) - 10} weitere.")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"get_tasks_today failed: {e}")
        return f"Fehler beim Abrufen der Tasks: {e}"


def get_recent_tasks(params: Dict[str, Any]) -> str:
    """
    Was war der letzte Task? / Zeig mir die letzten Tasks.

    Returns most recent tasks.
    """
    limit = params.get("limit", 5)

    try:
        from memory import get_task_memory_service
        service = get_task_memory_service()

        if not service or not service.is_available:
            return "Task-Gedaechtnis ist nicht verfuegbar."

        async def _fetch():
            return await service.get_recent_tasks(limit=limit)

        tasks = _run_async(_fetch())

        if not tasks:
            return "Keine kuerzlichen Tasks gefunden."

        if len(tasks) == 1:
            meta = tasks[0].get("metadata", {})
            intent = meta.get("intent_type", "unbekannt")
            result = meta.get("result", "")[:50]
            return f"Letzter Task: {intent}" + (f" - {result}" if result else "")

        lines = [f"Die letzten {len(tasks)} Tasks:"]
        for i, t in enumerate(tasks[:limit], 1):
            meta = t.get("metadata", {})
            intent = meta.get("intent_type", "unbekannt")
            lines.append(f"{i}. {intent}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"get_recent_tasks failed: {e}")
        return f"Fehler beim Abrufen der Tasks: {e}"


def search_task_history(params: Dict[str, Any]) -> str:
    """
    Suche in der Task-Historie.

    Args:
        query: Search query (e.g., "ideen erstellt", "marketing")
    """
    query = params.get("query", "")

    if not query:
        return "Bitte gib einen Suchbegriff an."

    try:
        from memory import get_task_memory_service
        service = get_task_memory_service()

        if not service or not service.is_available:
            return "Task-Gedaechtnis ist nicht verfuegbar."

        async def _fetch():
            return await service.search_tasks(query, limit=10)

        tasks = _run_async(_fetch())

        if not tasks:
            return f"Keine Tasks gefunden fuer: {query}"

        lines = [f"Gefundene Tasks fuer '{query}':"]
        for i, t in enumerate(tasks[:10], 1):
            meta = t.get("metadata", {})
            intent = meta.get("intent_type", "unbekannt")
            timestamp = meta.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    time_str = dt.strftime("%d.%m. %H:%M")
                except Exception:
                    time_str = ""
                lines.append(f"{i}. {intent}" + (f" ({time_str})" if time_str else ""))
            else:
                lines.append(f"{i}. {intent}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"search_task_history failed: {e}")
        return f"Fehler bei der Suche: {e}"


def get_task_stats(params: Dict[str, Any]) -> str:
    """
    Zeig mir meine Task-Statistiken.

    Returns summary of task activity.
    """
    try:
        from memory import get_task_memory_service, get_user_profile_service
        task_service = get_task_memory_service()
        profile_service = get_user_profile_service()

        lines = ["Task-Statistiken:"]

        # Get today's tasks
        if task_service and task_service.is_available:
            async def _fetch_today():
                return await task_service.get_tasks_today()

            tasks_today = _run_async(_fetch_today())
            completed = sum(1 for t in tasks_today if t.get("metadata", {}).get("event_type") == "task_completed")
            failed = sum(1 for t in tasks_today if t.get("metadata", {}).get("event_type") == "task_failed")

            lines.append(f"Heute: {completed} erledigt, {failed} fehlgeschlagen")
        else:
            lines.append("Task-Gedaechtnis nicht verfuegbar")

        # Get top intents from user profile
        if profile_service and profile_service.is_available:
            async def _fetch_top():
                return await profile_service.get_top_intents(limit=5)

            top_intents = _run_async(_fetch_top())
            if top_intents:
                lines.append("Meistgenutzte Befehle: " + ", ".join(top_intents))

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"get_task_stats failed: {e}")
        return f"Fehler beim Abrufen der Statistiken: {e}"


# Tool definitions for registration
TASK_MEMORY_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_tasks_today",
            "description": "Zeigt alle heute ausgefuehrten Tasks an. Trigger: 'Was habe ich heute gemacht?', 'Heutige Tasks'",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_tasks",
            "description": "Zeigt die letzten ausgefuehrten Tasks. Trigger: 'Was war der letzte Task?', 'Letzte Tasks', 'Was hab ich zuletzt gemacht?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Anzahl der Tasks (default: 5)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_task_history",
            "description": "Sucht in der Task-Historie nach bestimmten Aktionen. Trigger: 'Suche nach...', 'Finde Tasks mit...', 'Wann habe ich X gemacht?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Suchbegriff (z.B. 'ideen erstellt', 'marketing')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_task_stats",
            "description": "Zeigt Task-Statistiken und meistgenutzte Befehle. Trigger: 'Task Statistiken', 'Meine Nutzung'",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

# Export tool functions
TASK_MEMORY_TOOLS = {
    "get_tasks_today": get_tasks_today,
    "get_recent_tasks": get_recent_tasks,
    "search_task_history": search_task_history,
    "get_task_stats": get_task_stats,
}

__all__ = [
    "get_tasks_today",
    "get_recent_tasks",
    "search_task_history",
    "get_task_stats",
    "TASK_MEMORY_TOOL_DEFINITIONS",
    "TASK_MEMORY_TOOLS",
]
