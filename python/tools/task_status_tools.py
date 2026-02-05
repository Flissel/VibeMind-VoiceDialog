"""
Task Status Tools for Rachel.

Provides voice-callable tools for monitoring task execution:
- check_task_status: Check status of a specific task
- list_active_tasks: Show all running tasks
- get_queue_status: Show Redis queue statistics

These tools allow Rachel to answer questions like:
- "Was läuft gerade?"
- "Ist der Task fertig?"
- "Wie voll sind die Queues?"
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Redis connection (lazy initialization)
_redis: Optional[Any] = None


def _get_redis():
    """Get or create Redis connection."""
    global _redis
    if _redis is None:
        try:
            import redis
            _redis = redis.Redis(
                host='localhost',
                port=6379,
                decode_responses=True,
                socket_connect_timeout=2
            )
            # Test connection
            _redis.ping()
            logger.debug("[TaskStatus] Redis connected")
        except Exception as e:
            logger.warning(f"[TaskStatus] Redis not available: {e}")
            return None
    return _redis


def check_task_status(params: Dict[str, Any]) -> str:
    """
    Prüft den Status eines bestimmten Tasks.

    Voice triggers:
    - "Was macht der Task?"
    - "Ist der Task fertig?"
    - "Status von Task X"

    Args:
        params: Dict with 'task_id' key

    Returns:
        Status message for voice output
    """
    task_id = params.get("task_id")
    if not task_id:
        return "Kein Task-ID angegeben. Sag mir welchen Task ich pruefen soll."

    r = _get_redis()
    if r is None:
        # Fallback: check RealTimeState
        try:
            from swarm.context.real_time_state import get_real_time_state
            rt_state = get_real_time_state()
            for task in rt_state.state.active_tasks or []:
                if task["id"] == task_id or task["id"].startswith(task_id):
                    return f"Task {task['intent']} laeuft noch..."
            for comp in rt_state.state.recent_completions or []:
                if comp["id"] == task_id or comp["id"].startswith(task_id):
                    status = "erledigt" if comp.get("success", True) else "fehlgeschlagen"
                    return f"Task {comp['intent']} ist {status}: {comp.get('result', '')[:100]}"
            return f"Task {task_id[:8]}... nicht gefunden."
        except Exception as e:
            logger.debug(f"[TaskStatus] RealTimeState fallback failed: {e}")
            return "Redis nicht verfuegbar. Kann Task-Status nicht pruefen."

    try:
        # Check job hash
        job_data = r.hgetall(f"job:{task_id}")
        if job_data:
            status = job_data.get("status", "unknown")
            intent = job_data.get("intent_type", job_data.get("event_type", "unbekannt"))

            if status == "completed":
                result = job_data.get("result", "")[:100]
                return f"Task {intent} abgeschlossen" + (f": {result}" if result else ".")
            elif status == "running":
                started = job_data.get("started_at", "")
                return f"Task {intent} laeuft noch..." + (f" (gestartet: {started})" if started else "")
            elif status == "failed":
                error = job_data.get("error", "unbekannt")[:50]
                return f"Task {intent} fehlgeschlagen: {error}"
            elif status == "pending":
                return f"Task {intent} wartet auf Ausfuehrung."
            else:
                return f"Task {intent} hat Status: {status}"

        # Try partial match
        for key in r.scan_iter(f"job:{task_id}*", count=10):
            job_data = r.hgetall(key)
            if job_data:
                status = job_data.get("status", "unknown")
                intent = job_data.get("intent_type", "unbekannt")
                return f"Task {intent} gefunden mit Status: {status}"

        return f"Task {task_id[:8]}... nicht gefunden."

    except Exception as e:
        logger.error(f"[TaskStatus] check_task_status error: {e}")
        return f"Fehler beim Pruefen des Tasks: {e}"


def list_active_tasks(params: Dict[str, Any]) -> str:
    """
    Zeigt alle aktuell laufenden Tasks.

    Voice triggers:
    - "Was läuft gerade?"
    - "Aktive Tasks"
    - "Laufende Aufgaben"
    - "Welche Tasks sind aktiv?"

    Returns:
        List of active tasks for voice output
    """
    # First check RealTimeState (always available)
    active_from_state = []
    try:
        from swarm.context.real_time_state import get_real_time_state
        rt_state = get_real_time_state()
        if rt_state.state.active_tasks:
            active_from_state = rt_state.state.active_tasks
    except Exception as e:
        logger.debug(f"[TaskStatus] RealTimeState check failed: {e}")

    # Then check Redis for additional tasks
    active_from_redis = []
    r = _get_redis()
    if r is not None:
        try:
            for key in r.scan_iter("job:*", count=100):
                job = r.hgetall(key)
                if job.get("status") == "running":
                    active_from_redis.append({
                        "id": key.replace("job:", ""),
                        "intent": job.get("intent_type", job.get("event_type", "unknown")),
                        "started": job.get("started_at", "unknown")
                    })
        except Exception as e:
            logger.debug(f"[TaskStatus] Redis scan failed: {e}")

    # Merge and deduplicate
    all_active = []
    seen_ids = set()

    for task in active_from_state:
        if task["id"] not in seen_ids:
            all_active.append(task)
            seen_ids.add(task["id"])

    for task in active_from_redis:
        if task["id"] not in seen_ids:
            all_active.append(task)
            seen_ids.add(task["id"])

    if not all_active:
        return "Keine Tasks laufen gerade. Das System ist bereit."

    # Format for voice
    if len(all_active) == 1:
        task = all_active[0]
        return f"Ein Task laeuft: {task['intent']}"

    lines = [f"{len(all_active)} Tasks laufen:"]
    for i, task in enumerate(all_active[:5], 1):
        lines.append(f"{i}. {task['intent']}")

    if len(all_active) > 5:
        lines.append(f"... und {len(all_active) - 5} weitere.")

    return " ".join(lines)


def get_queue_status(params: Dict[str, Any]) -> str:
    """
    Zeigt den Status aller Task-Queues.

    Voice triggers:
    - "Queue Status"
    - "Wie voll sind die Queues?"
    - "Zeig mir die Warteschlangen"

    Returns:
        Queue statistics for voice output
    """
    r = _get_redis()
    if r is None:
        return "Redis nicht verfuegbar. Queue-Status kann nicht abgerufen werden."

    streams = [
        ("events:tasks", "Allgemein"),
        ("events:tasks:ideas", "Ideas"),
        ("events:tasks:coding", "Coding"),
        ("events:tasks:desktop", "Desktop"),
        ("events:status", "Status"),
    ]

    queue_stats = []
    total_pending = 0

    for stream_name, display_name in streams:
        try:
            info = r.xinfo_stream(stream_name)
            length = info.get("length", 0)
            total_pending += length
            if length > 0:
                queue_stats.append(f"{display_name}: {length}")
        except Exception:
            # Stream might not exist yet
            pass

    if total_pending == 0:
        return "Alle Queues sind leer. Das System ist bereit fuer neue Aufgaben."

    if len(queue_stats) == 1:
        return f"Eine wartende Aufgabe in Queue {queue_stats[0]}."

    return f"{total_pending} wartende Aufgaben. {', '.join(queue_stats)}."


def get_recent_completions(params: Dict[str, Any]) -> str:
    """
    Zeigt kürzlich abgeschlossene Tasks.

    Voice triggers:
    - "Was wurde erledigt?"
    - "Letzte abgeschlossene Tasks"
    - "Was ist fertig geworden?"

    Returns:
        Recent completion summary for voice output
    """
    try:
        from swarm.context.real_time_state import get_real_time_state
        rt_state = get_real_time_state()

        completions = rt_state.state.recent_completions or []
        if not completions:
            return "Keine kuerzlich abgeschlossenen Tasks."

        if len(completions) == 1:
            comp = completions[0]
            status = "erledigt" if comp.get("success", True) else "fehlgeschlagen"
            return f"Letzter Task {comp['intent']} ist {status}."

        lines = [f"{len(completions)} Tasks kuerzlich abgeschlossen:"]
        for comp in completions[-3:]:
            status = "✓" if comp.get("success", True) else "✗"
            lines.append(f"{status} {comp['intent']}")

        return " ".join(lines)

    except Exception as e:
        logger.error(f"[TaskStatus] get_recent_completions error: {e}")
        return "Konnte abgeschlossene Tasks nicht abrufen."


# Tool definitions for registration
TASK_STATUS_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_task_status",
            "description": "Prueft den Status eines bestimmten Tasks. Trigger: 'Was macht der Task?', 'Ist der Task fertig?', 'Task Status'",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Die Task-ID (oder Anfang davon)"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_active_tasks",
            "description": "Zeigt alle aktuell laufenden Tasks. Trigger: 'Was laeuft gerade?', 'Aktive Tasks', 'Laufende Aufgaben'",
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
            "name": "get_queue_status",
            "description": "Zeigt den Status aller Task-Queues. Trigger: 'Queue Status', 'Wie voll sind die Queues?', 'Warteschlangen Status'",
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
            "name": "get_recent_completions",
            "description": "Zeigt kuerzlich abgeschlossene Tasks. Trigger: 'Was wurde erledigt?', 'Letzte Tasks', 'Was ist fertig?'",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

# Export tool functions
TASK_STATUS_TOOLS = {
    "check_task_status": check_task_status,
    "list_active_tasks": list_active_tasks,
    "get_queue_status": get_queue_status,
    "get_recent_completions": get_recent_completions,
}

__all__ = [
    "check_task_status",
    "list_active_tasks",
    "get_queue_status",
    "get_recent_completions",
    "TASK_STATUS_TOOL_DEFINITIONS",
    "TASK_STATUS_TOOLS",
]
