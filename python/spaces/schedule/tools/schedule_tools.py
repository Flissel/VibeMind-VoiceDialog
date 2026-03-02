"""
Schedule Tools — 6 voice-triggered tools for schedule management.

Events:
    schedule.create  → create_scheduled_task()
    schedule.list    → list_scheduled_tasks()
    schedule.cancel  → cancel_scheduled_task()
    schedule.modify  → modify_scheduled_task()
    schedule.status  → get_schedule_status()
    schedule.snooze  → snooze_scheduled_task()
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from data import (
    ScheduledTask,
    ScheduledTaskRepository,
    ScheduleStatus,
    TriggerType,
    ExecutionMode,
)
from data.repository import generate_id
from spaces.schedule.nlp import parse_time_expression, ParsedTime
from spaces.schedule.config import get_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level references (set by electron_backend at startup)
# ---------------------------------------------------------------------------
_electron_send_message: Optional[Callable[[dict], None]] = None
_schedule_worker = None  # ScheduleWorker instance — set after worker starts


def set_electron_sender(sender: Callable[[dict], None]):
    """Set the Electron IPC message sender callback."""
    global _electron_send_message
    _electron_send_message = sender


def set_schedule_worker(worker):
    """Set the ScheduleWorker reference so tools can add/remove jobs live."""
    global _schedule_worker
    _schedule_worker = worker


def _broadcast_to_electron(message: dict):
    """Send a message to Electron if connected."""
    if _electron_send_message:
        _electron_send_message(message)


# ---------------------------------------------------------------------------
# Execution-mode auto-detection
# ---------------------------------------------------------------------------

def _detect_execution_mode(action_text: str) -> str:
    """
    Decide simple vs complex based on how many spaces the action text touches.

    If >1 space is matched via SPACE_KEYWORDS → complex (Minibook collaboration).
    Otherwise → simple (IntentOrchestrator direct).
    """
    try:
        from spaces.minibook.tools.collaboration_tools import (
            SPACE_KEYWORDS,
            detect_needed_spaces,
        )
        needed = detect_needed_spaces(action_text)
        if len(needed) > 1:
            return ExecutionMode.COMPLEX
    except ImportError:
        logger.debug("Minibook collaboration_tools not available — defaulting to simple")
    return ExecutionMode.SIMPLE


# ===================================================================
# Tool 1: schedule.create
# ===================================================================

def create_scheduled_task(
    user_text: str = "",
    title: str = "",
    **kwargs,
) -> Dict[str, Any]:
    """
    Parse a German time expression from user_text, persist to DB,
    and register with APScheduler.

    Args:
        user_text: Full user utterance ("Erinnere mich in 5 Minuten an den Termin")
        title: Optional explicit title override

    Returns:
        Standard tool result dict with success, message, response_hint
    """
    config = get_config()

    if not user_text:
        return {
            "success": False,
            "message": "No user_text provided",
            "response_hint": "Ich habe keinen Text zum Planen erhalten. Bitte sag mir, was ich wann planen soll.",
        }

    # --- NLP parse ---
    parsed = parse_time_expression(user_text, timezone=config.default_timezone)
    if parsed is None:
        return {
            "success": False,
            "message": f"Could not parse time expression from: {user_text}",
            "response_hint": (
                "Ich konnte keinen Zeitausdruck erkennen. "
                "Versuch zum Beispiel 'in 5 Minuten', 'um 14 Uhr' oder 'jeden Montag um 9'."
            ),
        }

    # --- Build task ---
    action_text = parsed.remaining_text or title or user_text
    task_title = title or parsed.remaining_text or user_text[:60]
    execution_mode = _detect_execution_mode(action_text)

    task = ScheduledTask(
        id=generate_id(),
        title=task_title,
        action_text=action_text,
        trigger_type=parsed.trigger_type,
        trigger_config=parsed.trigger_config,
        execution_mode=execution_mode,
        timezone=config.default_timezone,
        status=ScheduleStatus.ACTIVE,
        max_runs=parsed.max_runs,
    )

    # Compute next_run_at for date triggers
    if parsed.trigger_type == TriggerType.DATE and "run_date" in parsed.trigger_config:
        try:
            task.next_run_at = datetime.fromisoformat(parsed.trigger_config["run_date"])
        except (ValueError, TypeError):
            pass

    # --- Persist ---
    repo = ScheduledTaskRepository()
    repo.create(task)
    logger.info(f"Scheduled task created: {task.id} '{task.title}' ({parsed.trigger_type}, {execution_mode})")

    # --- Register with APScheduler (live) ---
    if _schedule_worker:
        try:
            _schedule_worker.add_job(task)
        except Exception as e:
            logger.error(f"Failed to add APScheduler job for {task.id}: {e}")

    # --- Electron notification ---
    _broadcast_to_electron({
        "type": "schedule_created",
        "schedule_id": task.id,
        "title": task.title,
        "trigger_type": parsed.trigger_type,
        "human_time": parsed.human_description,
        "execution_mode": execution_mode,
    })

    # --- Response ---
    mode_hint = " (mit Minibook-Kollaboration)" if execution_mode == ExecutionMode.COMPLEX else ""
    recurrence = "Wiederkehrend" if parsed.max_runs is None else "Einmalig"

    return {
        "success": True,
        "message": f"Task '{task.title}' scheduled ({parsed.trigger_type})",
        "response_hint": (
            f"Erledigt! Ich habe '{task.title}' geplant: {parsed.human_description}. "
            f"{recurrence}{mode_hint}."
        ),
        "schedule_id": task.id,
        "trigger_type": parsed.trigger_type,
        "human_time": parsed.human_description,
        "execution_mode": execution_mode,
    }


# ===================================================================
# Tool 2: schedule.list
# ===================================================================

def list_scheduled_tasks(
    status: str = "",
    **kwargs,
) -> Dict[str, Any]:
    """
    List scheduled tasks, optionally filtered by status.

    Args:
        status: Optional filter (active, paused, completed, cancelled, failed)

    Returns:
        Tool result with task list
    """
    repo = ScheduledTaskRepository()

    if status and status in (
        ScheduleStatus.ACTIVE, ScheduleStatus.PAUSED,
        ScheduleStatus.COMPLETED, ScheduleStatus.CANCELLED, ScheduleStatus.FAILED,
    ):
        tasks = repo.get_by_status(status)
    else:
        tasks = repo.list_all(limit=30)

    if not tasks:
        return {
            "success": True,
            "message": "No scheduled tasks found",
            "response_hint": "Du hast aktuell keine geplanten Aufgaben.",
            "tasks": [],
        }

    # Build summary
    lines = []
    for i, t in enumerate(tasks, 1):
        status_icon = {
            ScheduleStatus.ACTIVE: "▶",
            ScheduleStatus.PAUSED: "⏸",
            ScheduleStatus.COMPLETED: "✓",
            ScheduleStatus.CANCELLED: "✗",
            ScheduleStatus.FAILED: "⚠",
        }.get(t.status, "?")
        lines.append(f"{i}. {status_icon} {t.title} ({t.trigger_type}, {t.status})")

    active_count = sum(1 for t in tasks if t.status == ScheduleStatus.ACTIVE)
    summary = f"{len(tasks)} Aufgaben gefunden, davon {active_count} aktiv."

    return {
        "success": True,
        "message": f"Found {len(tasks)} scheduled tasks",
        "response_hint": f"Hier sind deine geplanten Aufgaben: {summary}",
        "tasks": [t.to_dict() for t in tasks],
        "summary": summary,
        "task_lines": lines,
    }


# ===================================================================
# Tool 3: schedule.cancel
# ===================================================================

def cancel_scheduled_task(
    task_id: str = "",
    title: str = "",
    **kwargs,
) -> Dict[str, Any]:
    """
    Cancel a scheduled task by ID or fuzzy title match.

    Args:
        task_id: Exact task ID
        title: Fuzzy title for matching (e.g. "Montag Report")

    Returns:
        Tool result
    """
    repo = ScheduledTaskRepository()
    task = None

    if task_id:
        task = repo.get(task_id)
    elif title:
        matches = repo.search_by_title(title)
        # Only cancel active tasks
        active_matches = [m for m in matches if m.status == ScheduleStatus.ACTIVE]
        if active_matches:
            task = active_matches[0]

    if not task:
        return {
            "success": False,
            "message": f"Task not found: id={task_id}, title={title}",
            "response_hint": (
                "Ich konnte diese Aufgabe nicht finden. "
                "Sag 'Zeig meine Erinnerungen' um alle zu sehen."
            ),
        }

    # Cancel in DB
    repo.cancel(task.id)

    # Remove from APScheduler
    if _schedule_worker:
        try:
            _schedule_worker.remove_job(task.id)
        except Exception as e:
            logger.warning(f"Could not remove APScheduler job {task.id}: {e}")

    _broadcast_to_electron({
        "type": "schedule_cancelled",
        "schedule_id": task.id,
        "title": task.title,
    })

    return {
        "success": True,
        "message": f"Task '{task.title}' cancelled",
        "response_hint": f"Erledigt! '{task.title}' wurde abgesagt.",
        "schedule_id": task.id,
    }


# ===================================================================
# Tool 4: schedule.modify
# ===================================================================

def modify_scheduled_task(
    task_id: str = "",
    title: str = "",
    new_time: str = "",
    new_action: str = "",
    **kwargs,
) -> Dict[str, Any]:
    """
    Modify a scheduled task's time and/or action.

    Args:
        task_id: Exact task ID
        title: Fuzzy title for matching
        new_time: New time expression (e.g. "um 15 Uhr")
        new_action: New action text

    Returns:
        Tool result
    """
    config = get_config()
    repo = ScheduledTaskRepository()
    task = None

    if task_id:
        task = repo.get(task_id)
    elif title:
        matches = repo.search_by_title(title)
        active_matches = [m for m in matches if m.status == ScheduleStatus.ACTIVE]
        if active_matches:
            task = active_matches[0]

    if not task:
        return {
            "success": False,
            "message": f"Task not found: id={task_id}, title={title}",
            "response_hint": "Ich konnte diese Aufgabe nicht finden.",
        }

    changes = []

    # Update time if provided
    if new_time:
        parsed = parse_time_expression(new_time, timezone=config.default_timezone)
        if parsed:
            repo.update_trigger(
                task.id,
                trigger_type=parsed.trigger_type,
                trigger_config=parsed.trigger_config,
            )
            changes.append(f"Zeit auf {parsed.human_description}")

            # Re-register with APScheduler
            if _schedule_worker:
                updated_task = repo.get(task.id)
                if updated_task:
                    try:
                        _schedule_worker.remove_job(task.id)
                        _schedule_worker.add_job(updated_task)
                    except Exception as e:
                        logger.warning(f"Could not re-register job {task.id}: {e}")
        else:
            return {
                "success": False,
                "message": f"Could not parse new time: {new_time}",
                "response_hint": "Ich konnte die neue Zeit nicht verstehen.",
            }

    # Update action if provided
    if new_action:
        repo.db.execute(
            "UPDATE scheduled_tasks SET action_text = ?, updated_at = ? WHERE id = ?",
            (new_action, datetime.now().isoformat(), task.id),
        )
        changes.append(f"Aktion auf '{new_action}'")

    if not changes:
        return {
            "success": False,
            "message": "No changes specified",
            "response_hint": "Was moechtest du aendern? Sag mir die neue Zeit oder Aktion.",
        }

    change_str = " und ".join(changes)
    return {
        "success": True,
        "message": f"Task '{task.title}' modified: {change_str}",
        "response_hint": f"'{task.title}' wurde geaendert: {change_str}.",
        "schedule_id": task.id,
        "changes": changes,
    }


# ===================================================================
# Tool 5: schedule.status
# ===================================================================

def get_schedule_status(**kwargs) -> Dict[str, Any]:
    """
    Get a summary of all scheduled tasks.

    Returns:
        Tool result with counts and next upcoming task
    """
    repo = ScheduledTaskRepository()
    active = repo.count(ScheduleStatus.ACTIVE)
    paused = repo.count(ScheduleStatus.PAUSED)
    completed = repo.count(ScheduleStatus.COMPLETED)
    total = repo.count()

    # Find next upcoming active task
    active_tasks = repo.get_active()
    next_task = None
    if active_tasks:
        # Find task with earliest next_run_at
        with_next = [t for t in active_tasks if t.next_run_at]
        if with_next:
            next_task = min(with_next, key=lambda t: t.next_run_at)

    next_hint = ""
    if next_task:
        next_hint = f" Naechste Aufgabe: '{next_task.title}'"
        if next_task.next_run_at:
            next_hint += f" um {next_task.next_run_at.strftime('%H:%M')}"

    return {
        "success": True,
        "message": f"Schedule: {active} active, {paused} paused, {completed} completed, {total} total",
        "response_hint": (
            f"Dein Schedule: {active} aktiv, {paused} pausiert, {completed} erledigt.{next_hint}"
        ),
        "active": active,
        "paused": paused,
        "completed": completed,
        "total": total,
        "next_task": next_task.to_dict() if next_task else None,
    }


# ===================================================================
# Tool 6: schedule.snooze
# ===================================================================

def snooze_scheduled_task(
    task_id: str = "",
    title: str = "",
    minutes: int = 5,
    user_text: str = "",
    **kwargs,
) -> Dict[str, Any]:
    """
    Snooze a task — create a new one-shot DateTrigger for now + X minutes.

    Args:
        task_id: Exact task ID
        title: Fuzzy title for matching
        minutes: Snooze duration in minutes (default: 5)
        user_text: Optional text to parse snooze duration from ("snooze 10 Minuten")

    Returns:
        Tool result
    """
    config = get_config()
    repo = ScheduledTaskRepository()
    task = None

    # Try to parse minutes from user_text
    if user_text:
        parsed = parse_time_expression(user_text, timezone=config.default_timezone)
        if parsed and parsed.trigger_type == TriggerType.DATE and "run_date" in parsed.trigger_config:
            try:
                run_date = datetime.fromisoformat(parsed.trigger_config["run_date"])
                minutes = max(1, int((run_date - datetime.now()).total_seconds() / 60))
            except (ValueError, TypeError):
                pass

    # Find task
    if task_id:
        task = repo.get(task_id)
    elif title:
        matches = repo.search_by_title(title)
        if matches:
            task = matches[0]
    else:
        # Snooze most recent completed/active task
        recent = repo.list_all(limit=5)
        for t in recent:
            if t.status in (ScheduleStatus.ACTIVE, ScheduleStatus.COMPLETED):
                task = t
                break

    if not task:
        return {
            "success": False,
            "message": "No task found to snooze",
            "response_hint": "Ich konnte keine Aufgabe zum Snoozen finden.",
        }

    # Create new one-shot trigger
    new_run = datetime.now() + timedelta(minutes=minutes)
    repo.update_trigger(
        task.id,
        trigger_type=TriggerType.DATE,
        trigger_config={"run_date": new_run.isoformat()},
        next_run_at=new_run.isoformat(),
    )
    repo.update_status(task.id, ScheduleStatus.ACTIVE)

    # Re-register with APScheduler
    if _schedule_worker:
        updated_task = repo.get(task.id)
        if updated_task:
            try:
                _schedule_worker.remove_job(task.id)
                _schedule_worker.add_job(updated_task)
            except Exception as e:
                logger.warning(f"Could not re-register snoozed job {task.id}: {e}")

    return {
        "success": True,
        "message": f"Task '{task.title}' snoozed for {minutes} minutes",
        "response_hint": f"'{task.title}' wurde um {minutes} Minuten verschoben.",
        "schedule_id": task.id,
        "snooze_minutes": minutes,
        "new_run_at": new_run.isoformat(),
    }
