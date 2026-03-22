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
    logger.debug("check_task_status called with task_id=%s", params.get("task_id"))
    task_id = params.get("task_id")
    if not task_id:
        return "No task ID provided. Tell me which task to check."

    r = _get_redis()
    if r is None:
        # Fallback: check RealTimeState
        try:
            from swarm.context.real_time_state import get_real_time_state
            rt_state = get_real_time_state()
            for task in rt_state.state.active_tasks or []:
                if task["id"] == task_id or task["id"].startswith(task_id):
                    return f"Task {task['intent']} is still running..."
            for comp in rt_state.state.recent_completions or []:
                if comp["id"] == task_id or comp["id"].startswith(task_id):
                    status = "completed" if comp.get("success", True) else "failed"
                    return f"Task {comp['intent']} is {status}: {comp.get('result', '')[:100]}"
            return f"Task {task_id[:8]}... not found."
        except Exception as e:
            logger.debug(f"[TaskStatus] RealTimeState fallback failed: {e}")
            return "Redis not available. Cannot check task status."

    try:
        # Check job hash
        job_data = r.hgetall(f"job:{task_id}")
        if job_data:
            status = job_data.get("status", "unknown")
            intent = job_data.get("intent_type", job_data.get("event_type", "unknown"))

            if status == "completed":
                result = job_data.get("result", "")[:100]
                return f"Task {intent} completed" + (f": {result}" if result else ".")
            elif status == "running":
                started = job_data.get("started_at", "")
                return f"Task {intent} is still running..." + (f" (started: {started})" if started else "")
            elif status == "failed":
                error = job_data.get("error", "unknown")[:50]
                return f"Task {intent} failed: {error}"
            elif status == "pending":
                return f"Task {intent} is pending execution."
            else:
                return f"Task {intent} hat Status: {status}"

        # Try partial match
        for key in r.scan_iter(f"job:{task_id}*", count=10):
            job_data = r.hgetall(key)
            if job_data:
                status = job_data.get("status", "unknown")
                intent = job_data.get("intent_type", "unknown")
                return f"Task {intent} found with status: {status}"

        return f"Task {task_id[:8]}... not found."

    except Exception as e:
        logger.error(f"[TaskStatus] check_task_status error: {e}")
        return f"Error checking task: {e}"


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
    logger.debug("list_active_tasks called")
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
        return "No tasks running. System is ready."

    # Format for voice
    if len(all_active) == 1:
        task = all_active[0]
        return f"One task running: {task['intent']}"

    lines = [f"{len(all_active)} tasks running:"]
    for i, task in enumerate(all_active[:5], 1):
        lines.append(f"{i}. {task['intent']}")

    if len(all_active) > 5:
        lines.append(f"... and {len(all_active) - 5} more.")

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
    logger.debug("get_queue_status called")
    r = _get_redis()
    if r is None:
        return "Redis not available. Cannot retrieve queue status."

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
        return "All queues empty. System ready for new tasks."

    if len(queue_stats) == 1:
        return f"One pending task in queue {queue_stats[0]}."

    return f"{total_pending} pending tasks. {', '.join(queue_stats)}."


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
    logger.debug("get_recent_completions called")
    try:
        from swarm.context.real_time_state import get_real_time_state
        rt_state = get_real_time_state()

        completions = rt_state.state.recent_completions or []
        if not completions:
            return "No recently completed tasks."

        if len(completions) == 1:
            comp = completions[0]
            status = "completed" if comp.get("success", True) else "failed"
            return f"Last task {comp['intent']} is {status}."

        lines = [f"{len(completions)} tasks recently completed:"]
        for comp in completions[-3:]:
            status = "✓" if comp.get("success", True) else "✗"
            lines.append(f"{status} {comp['intent']}")

        return " ".join(lines)

    except Exception as e:
        logger.error(f"[TaskStatus] get_recent_completions error: {e}")
        return "Could not retrieve completed tasks."


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
