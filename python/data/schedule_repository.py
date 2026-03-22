"""Schedule Repository — CRUD operations for APScheduler tasks."""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from .database import Database, get_database
from .models import ScheduledTask, ScheduleStatus
from .repository_utils import generate_id, normalize_text

logger = logging.getLogger(__name__)


class ScheduledTaskRepository:
    """Repository for Scheduled Task CRUD operations."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    def create(self, task: ScheduledTask) -> ScheduledTask:
        """
        Create a new scheduled task.

        Args:
            task: ScheduledTask object to persist

        Returns:
            The persisted ScheduledTask
        """
        import json

        data = task.to_dict()
        self.db.execute(
            """
            INSERT INTO scheduled_tasks (
                id, title, description, action_text, execution_mode,
                trigger_type, trigger_config, timezone, status,
                next_run_at, last_run_at, run_count, max_runs,
                last_result, last_error, created_at, updated_at, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["title"],
                data["description"],
                data["action_text"],
                data["execution_mode"],
                data["trigger_type"],
                data["trigger_config"],
                data["timezone"],
                data["status"],
                data["next_run_at"],
                data["last_run_at"],
                data["run_count"],
                data["max_runs"],
                data["last_result"],
                data["last_error"],
                data["created_at"],
                data["updated_at"],
                data["metadata"],
            ),
        )

        return task

    def get(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a scheduled task by ID."""
        row = self.db.fetch_one(
            "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
        )
        return ScheduledTask.from_dict(dict(row)) if row else None

    def get_active(self) -> List[ScheduledTask]:
        """Get all active scheduled tasks (for loading into APScheduler on startup)."""
        rows = self.db.fetch_all(
            "SELECT * FROM scheduled_tasks WHERE status = ? ORDER BY next_run_at ASC",
            (ScheduleStatus.ACTIVE,),
        )
        return [ScheduledTask.from_dict(dict(row)) for row in rows]

    def get_by_status(self, status: str) -> List[ScheduledTask]:
        """Get tasks by status."""
        rows = self.db.fetch_all(
            "SELECT * FROM scheduled_tasks WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
        return [ScheduledTask.from_dict(dict(row)) for row in rows]

    def list_all(self, limit: int = 50, offset: int = 0) -> List[ScheduledTask]:
        """List all scheduled tasks (newest first)."""
        rows = self.db.fetch_all(
            "SELECT * FROM scheduled_tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [ScheduledTask.from_dict(dict(row)) for row in rows]

    def search_by_title(self, query: str) -> List[ScheduledTask]:
        """Fuzzy-search tasks by title (case-insensitive)."""
        normalized = normalize_text(query)
        rows = self.db.fetch_all(
            "SELECT * FROM scheduled_tasks ORDER BY created_at DESC",
        )
        results = []
        for row in rows:
            d = dict(row)
            if normalized in normalize_text(d.get("title", "")):
                results.append(ScheduledTask.from_dict(d))
        return results

    def update_after_run(
        self,
        task_id: str,
        *,
        last_result: Optional[str] = None,
        last_error: Optional[str] = None,
        next_run_at: Optional[str] = None,
        new_status: Optional[str] = None,
    ) -> Optional[ScheduledTask]:
        """
        Update task after APScheduler execution.

        Increments run_count, sets last_run_at, optionally updates status.
        Auto-completes one-shot tasks (max_runs == run_count).
        """
        task = self.get(task_id)
        if not task:
            return None

        task.run_count += 1
        task.last_run_at = datetime.now()
        task.updated_at = datetime.now()
        task.last_result = last_result
        task.last_error = last_error

        if next_run_at is not None:
            task.next_run_at = datetime.fromisoformat(next_run_at) if isinstance(next_run_at, str) else next_run_at

        # Auto-complete one-shot tasks
        if new_status:
            task.status = new_status
        elif task.max_runs is not None and task.run_count >= task.max_runs:
            task.status = ScheduleStatus.COMPLETED

        self.db.execute(
            """
            UPDATE scheduled_tasks SET
                run_count = ?,
                last_run_at = ?,
                last_result = ?,
                last_error = ?,
                next_run_at = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                task.run_count,
                task.last_run_at.isoformat() if task.last_run_at else None,
                task.last_result,
                task.last_error,
                task.next_run_at.isoformat() if task.next_run_at else None,
                task.status,
                task.updated_at.isoformat() if task.updated_at else None,
                task.id,
            ),
        )

        return task

    def update_status(self, task_id: str, status: str) -> Optional[ScheduledTask]:
        """Update task status."""
        now = datetime.now()
        self.db.execute(
            "UPDATE scheduled_tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, now.isoformat(), task_id),
        )
        return self.get(task_id)

    def update_trigger(
        self,
        task_id: str,
        trigger_type: str,
        trigger_config: Dict[str, Any],
        next_run_at: Optional[str] = None,
    ) -> Optional[ScheduledTask]:
        """Update trigger configuration (for modify/snooze)."""
        import json

        now = datetime.now()
        self.db.execute(
            """
            UPDATE scheduled_tasks SET
                trigger_type = ?,
                trigger_config = ?,
                next_run_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                trigger_type,
                json.dumps(trigger_config),
                next_run_at,
                now.isoformat(),
                task_id,
            ),
        )
        return self.get(task_id)

    def cancel(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        result = self.update_status(task_id, ScheduleStatus.CANCELLED)
        return result is not None

    def delete(self, task_id: str) -> bool:
        """Permanently delete a scheduled task."""
        self.db.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
        return True

    def count(self, status: Optional[str] = None) -> int:
        """Count tasks, optionally filtered by status."""
        if status:
            row = self.db.fetch_one(
                "SELECT COUNT(*) FROM scheduled_tasks WHERE status = ?",
                (status,),
            )
        else:
            row = self.db.fetch_one("SELECT COUNT(*) FROM scheduled_tasks")
        return row[0] if row else 0
