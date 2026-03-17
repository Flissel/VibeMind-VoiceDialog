"""
Task Memory Repository - Database operations for persistent tasks

Phase 15: Task Memory System

Stores and retrieves:
- Persistent tasks (ongoing work Rachel remembers)
- Task status and progress
- Task history for context
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from .database import Database, get_database
from .models import Task, TaskStatus
from .repository_utils import generate_id

logger = logging.getLogger(__name__)


class TaskMemoryRepository:
    """Repository for persistent task memory operations."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure required tables exist."""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS persistent_tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    session_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    intent_type TEXT,
                    payload TEXT,
                    job_id TEXT,
                    progress INTEGER DEFAULT 0,
                    stage TEXT,
                    result TEXT,
                    error TEXT,
                    priority INTEGER DEFAULT 2,
                    tags TEXT,
                    updated_at TEXT
                )
            """)

            # Create indexes
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_user ON persistent_tasks(user_id)
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON persistent_tasks(status)
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_session ON persistent_tasks(session_id)
            """)

            logger.debug("Task memory tables ensured")
        except Exception as e:
            logger.warning(f"Could not ensure task tables: {e}")

    # ==========================================================================
    # TASK CRUD OPERATIONS
    # ==========================================================================

    def create_task(
        self,
        title: str,
        intent_type: str,
        payload: Dict[str, Any],
        user_id: str = "default",
        session_id: Optional[str] = None,
        description: str = "",
        priority: int = 2,
        tags: Optional[List[str]] = None,
    ) -> Task:
        """
        Create a new persistent task.

        Args:
            title: Task title/description
            intent_type: Original event_type (idea.move, code.generate, etc.)
            payload: Original parameters
            user_id: User identifier
            session_id: Session identifier
            description: Longer description
            priority: 1=low, 2=medium, 3=high
            tags: Optional tags for categorization

        Returns:
            Created Task object
        """
        try:
            task_id = generate_id()
            now = datetime.now().isoformat()

            task = Task(
                id=task_id,
                title=title,
                user_id=user_id,
                session_id=session_id,
                description=description,
                status=TaskStatus.PENDING,
                created_at=datetime.now(),
                intent_type=intent_type,
                payload=payload,
                priority=priority,
                tags=tags or [],
            )

            self.db.execute(
                """
                INSERT INTO persistent_tasks
                    (id, user_id, session_id, title, description, status,
                     created_at, intent_type, payload, priority, tags, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    user_id,
                    session_id,
                    title,
                    description,
                    TaskStatus.PENDING,
                    now,
                    intent_type,
                    json.dumps(payload),
                    priority,
                    json.dumps(tags or []),
                    now,
                )
            )

            logger.info(f"Created task: {title} (id={task_id})")
            return task

        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            raise

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        try:
            row = self.db.fetch_one(
                "SELECT * FROM persistent_tasks WHERE id = ?",
                (task_id,)
            )
            if row:
                return Task.from_dict(dict(row))
        except Exception as e:
            logger.warning(f"Failed to get task: {e}")
        return None

    def get_task_by_job_id(self, job_id: str) -> Optional[Task]:
        """Get a task by its job_id."""
        try:
            row = self.db.fetch_one(
                "SELECT * FROM persistent_tasks WHERE job_id = ?",
                (job_id,)
            )
            if row:
                return Task.from_dict(dict(row))
        except Exception as e:
            logger.warning(f"Failed to get task by job_id: {e}")
        return None

    def list_tasks(
        self,
        user_id: str = "default",
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Task]:
        """
        List tasks for a user.

        Args:
            user_id: User identifier
            status: Optional status filter
            limit: Maximum number of tasks to return

        Returns:
            List of Task objects
        """
        try:
            if status:
                rows = self.db.fetch_all(
                    """
                    SELECT * FROM persistent_tasks
                    WHERE user_id = ? AND status = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, status, limit)
                )
            else:
                rows = self.db.fetch_all(
                    """
                    SELECT * FROM persistent_tasks
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit)
                )

            return [Task.from_dict(dict(row)) for row in rows]

        except Exception as e:
            logger.warning(f"Failed to list tasks: {e}")
            return []

    def get_pending_tasks(self, user_id: str = "default") -> List[Task]:
        """Get all pending and in-progress tasks for a user."""
        try:
            rows = self.db.fetch_all(
                """
                SELECT * FROM persistent_tasks
                WHERE user_id = ? AND status IN (?, ?)
                ORDER BY priority DESC, created_at ASC
                """,
                (user_id, TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
            )
            return [Task.from_dict(dict(row)) for row in rows]

        except Exception as e:
            logger.warning(f"Failed to get pending tasks: {e}")
            return []

    def get_tasks_for_context(
        self,
        user_id: str = "default",
        limit: int = 5,
    ) -> List[Task]:
        """
        Get recent tasks for context (pending + recently completed).

        Args:
            user_id: User identifier
            limit: Maximum tasks to return

        Returns:
            List of Task objects for context
        """
        try:
            # Get pending/in-progress first, then recent completed
            rows = self.db.fetch_all(
                """
                SELECT * FROM persistent_tasks
                WHERE user_id = ?
                ORDER BY
                    CASE status
                        WHEN 'in_progress' THEN 0
                        WHEN 'pending' THEN 1
                        WHEN 'completed' THEN 2
                        ELSE 3
                    END,
                    updated_at DESC
                LIMIT ?
                """,
                (user_id, limit)
            )
            return [Task.from_dict(dict(row)) for row in rows]

        except Exception as e:
            logger.warning(f"Failed to get tasks for context: {e}")
            return []

    # ==========================================================================
    # TASK STATUS OPERATIONS
    # ==========================================================================

    def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """
        Update task status.

        Args:
            task_id: Task ID
            status: New status
            result: Optional result string
            error: Optional error string

        Returns:
            True if updated
        """
        try:
            now = datetime.now().isoformat()
            completed_at = now if status == TaskStatus.COMPLETED else None

            self.db.execute(
                """
                UPDATE persistent_tasks
                SET status = ?, result = ?, error = ?,
                    completed_at = COALESCE(?, completed_at),
                    updated_at = ?
                WHERE id = ?
                """,
                (status, result, error, completed_at, now, task_id)
            )

            logger.info(f"Updated task {task_id} status to {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
            return False

    def start_task(self, task_id: str, job_id: Optional[str] = None) -> bool:
        """Mark a task as in-progress."""
        try:
            now = datetime.now().isoformat()

            self.db.execute(
                """
                UPDATE persistent_tasks
                SET status = ?, started_at = ?, job_id = COALESCE(?, job_id),
                    updated_at = ?
                WHERE id = ?
                """,
                (TaskStatus.IN_PROGRESS, now, job_id, now, task_id)
            )

            logger.info(f"Started task {task_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start task: {e}")
            return False

    def complete_task(self, task_id: str, result: str) -> bool:
        """Mark a task as completed."""
        return self.update_task_status(task_id, TaskStatus.COMPLETED, result=result)

    def fail_task(self, task_id: str, error: str) -> bool:
        """Mark a task as blocked/failed."""
        return self.update_task_status(task_id, TaskStatus.BLOCKED, error=error)

    def update_progress(self, task_id: str, progress: int, stage: str = "") -> bool:
        """Update task progress."""
        try:
            now = datetime.now().isoformat()

            self.db.execute(
                """
                UPDATE persistent_tasks
                SET progress = ?, stage = ?, updated_at = ?
                WHERE id = ?
                """,
                (progress, stage, now, task_id)
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to update progress: {e}")
            return False

    # ==========================================================================
    # CLEANUP
    # ==========================================================================

    def cleanup_old_tasks(self, days: int = 7) -> int:
        """
        Clean up completed tasks older than specified days.

        Args:
            days: Number of days to keep completed tasks

        Returns:
            Number of deleted tasks
        """
        try:
            result = self.db.execute(
                """
                DELETE FROM persistent_tasks
                WHERE status = ? AND completed_at < datetime('now', ? || ' days')
                """,
                (TaskStatus.COMPLETED, f"-{days}")
            )
            count = result.rowcount if result else 0
            if count > 0:
                logger.info(f"Cleaned up {count} old tasks")
            return count

        except Exception as e:
            logger.warning(f"Failed to cleanup tasks: {e}")
            return 0


# Singleton
_task_memory_repository: Optional[TaskMemoryRepository] = None


def get_task_memory_repository() -> TaskMemoryRepository:
    """Get or create TaskMemoryRepository singleton."""
    global _task_memory_repository
    if _task_memory_repository is None:
        _task_memory_repository = TaskMemoryRepository()
    return _task_memory_repository


__all__ = [
    "TaskMemoryRepository",
    "get_task_memory_repository",
]
