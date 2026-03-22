"""
Worker Queue - Fast Voice Task Seeding

These tools return IMMEDIATELY while seeding tasks to the Claude worker.
Designed to prevent voice audio stream timeouts on long-running operations.

Tools:
- seed_task: Queue a desktop automation task (returns instantly)
- get_task_status: Check task progress
- get_last_result: Get the most recent task result
- cancel_task: Cancel a running task
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class WorkerTask:
    """Task for the Claude worker."""
    id: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: str = "queued"  # queued, planning, executing, completed, failed, cancelled
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    current_step: int = 0
    total_steps: int = 0
    progress_message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class StepReport:
    """Report from Claude worker every 3 steps."""
    task_id: str
    report_number: int  # 1, 2, 3...
    steps_completed: int
    steps: List[Dict[str, Any]]  # Last 3 steps with tool/result/thought
    summary: str  # Natural language summary
    timestamp: float = field(default_factory=time.time)
    is_final: bool = False


class ReportQueue:
    """
    Queue for step reports from Claude worker to voice agent.

    Worker pushes reports every 3 steps. Voice agent polls for latest.
    """

    def __init__(self):
        self._reports: Dict[str, List[StepReport]] = {}  # task_id -> reports
        self._latest: Optional[StepReport] = None

    def push_report(self, report: StepReport):
        """Worker pushes report every 3 steps."""
        if report.task_id not in self._reports:
            self._reports[report.task_id] = []
        self._reports[report.task_id].append(report)
        self._latest = report
        logger.info(f"Report pushed: task={report.task_id} report={report.report_number} steps={report.steps_completed}")

    def get_latest_report(self) -> Dict[str, Any]:
        """Voice agent calls this to get latest report."""
        if not self._latest:
            return {"success": True, "message": "No reports yet. Worker may still be starting."}
        return {
            "success": True,
            "task_id": self._latest.task_id,
            "report_number": self._latest.report_number,
            "steps_completed": self._latest.steps_completed,
            "summary": self._latest.summary,
            "is_final": self._latest.is_final,
            "timestamp": self._latest.timestamp
        }

    def get_reports_for_task(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all reports for a specific task."""
        reports = self._reports.get(task_id, [])
        return [
            {
                "report_number": r.report_number,
                "steps_completed": r.steps_completed,
                "summary": r.summary,
                "is_final": r.is_final
            }
            for r in reports
        ]

    def clear_task_reports(self, task_id: str):
        """Clear reports for a completed task."""
        if task_id in self._reports:
            del self._reports[task_id]


# Singleton report queue
_report_queue: Optional[ReportQueue] = None


def get_report_queue() -> ReportQueue:
    """Get singleton ReportQueue instance."""
    global _report_queue
    if _report_queue is None:
        _report_queue = ReportQueue()
    return _report_queue


class TaskQueue:
    """
    Simple task queue for voice-to-worker communication.

    Voice agents seed tasks here, Claude worker picks them up.
    """

    def __init__(self):
        self._tasks: Dict[str, WorkerTask] = {}
        self._queue: asyncio.Queue[WorkerTask] = None
        self._completed: List[WorkerTask] = []
        self._max_completed = 10  # Keep last N completed tasks
        self._task_counter = 0

    def _ensure_queue(self):
        """Ensure queue exists (create in current event loop)."""
        if self._queue is None:
            try:
                self._queue = asyncio.Queue()
            except RuntimeError:
                # No event loop, will create later
                pass

    def seed_task(self, description: str, priority: str = "normal") -> WorkerTask:
        """
        Add a task to the queue. Returns immediately.

        Args:
            description: What to do (e.g., "Open Chrome and search for Python docs")
            priority: Task priority ("low", "normal", "high", "urgent")

        Returns:
            WorkerTask with id for status tracking
        """
        self._ensure_queue()
        self._task_counter += 1

        # Parse priority
        priority_map = {
            "low": TaskPriority.LOW,
            "normal": TaskPriority.NORMAL,
            "high": TaskPriority.HIGH,
            "urgent": TaskPriority.URGENT
        }
        task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)

        # Create task
        task = WorkerTask(
            id=f"task_{self._task_counter}_{uuid.uuid4().hex[:8]}",
            description=description,
            priority=task_priority
        )

        self._tasks[task.id] = task

        # Add to queue if available
        if self._queue is not None:
            try:
                self._queue.put_nowait(task)
            except:
                pass  # Queue might not be ready

        logger.info(f"Task seeded: {task.id} - {description[:50]}...")
        return task

    async def get_next_task(self, timeout: float = 1.0) -> Optional[WorkerTask]:
        """
        Get next task from queue (for worker).

        Args:
            timeout: How long to wait for a task

        Returns:
            WorkerTask or None if timeout
        """
        self._ensure_queue()

        try:
            task = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            return task
        except asyncio.TimeoutError:
            return None
        except:
            return None

    def has_pending_tasks(self) -> bool:
        """Check if there are tasks waiting."""
        return any(t.status == "queued" for t in self._tasks.values())

    def has_higher_priority_task(self, current_priority: TaskPriority) -> bool:
        """Check if there's a higher priority task waiting."""
        for task in self._tasks.values():
            if task.status == "queued" and task.priority.value > current_priority.value:
                return True
        return False

    def get_task(self, task_id: str) -> Optional[WorkerTask]:
        """Get task by ID."""
        return self._tasks.get(task_id)

    def get_last_completed(self) -> Optional[WorkerTask]:
        """Get the most recently completed task."""
        if self._completed:
            return self._completed[-1]
        # Also check main tasks dict
        completed = [t for t in self._tasks.values()
                    if t.status in ("completed", "failed")]
        if completed:
            return max(completed, key=lambda t: t.completed_at or 0)
        return None

    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        current_step: Optional[int] = None,
        total_steps: Optional[int] = None,
        progress_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """Update task progress."""
        task = self._tasks.get(task_id)
        if not task:
            return

        if status:
            task.status = status
            if status == "executing" and task.started_at is None:
                task.started_at = time.time()
            elif status in ("completed", "failed", "cancelled"):
                task.completed_at = time.time()
                self._completed.append(task)
                if len(self._completed) > self._max_completed:
                    self._completed.pop(0)

        if current_step is not None:
            task.current_step = current_step
        if total_steps is not None:
            task.total_steps = total_steps
        if progress_message is not None:
            task.progress_message = progress_message
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        task = self._tasks.get(task_id)
        if task and task.status in ("queued", "planning", "executing"):
            task.status = "cancelled"
            task.completed_at = time.time()
            return True
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get queue status."""
        return {
            "total_tasks": len(self._tasks),
            "queued": sum(1 for t in self._tasks.values() if t.status == "queued"),
            "executing": sum(1 for t in self._tasks.values() if t.status == "executing"),
            "completed": sum(1 for t in self._tasks.values() if t.status == "completed"),
            "failed": sum(1 for t in self._tasks.values() if t.status == "failed"),
            "queue_size": self._queue.qsize() if self._queue else 0
        }


# Singleton instance
_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """Get singleton TaskQueue instance."""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue


# =============================================================================
# TOOL IMPLEMENTATIONS (Fast - for voice agents)
# =============================================================================

def seed_task(description: str, priority: str = "normal") -> Dict[str, Any]:
    """
    Seed a task for the Claude worker. Returns IMMEDIATELY.

    The Claude worker will execute this task asynchronously.
    Use get_task_status() to check progress.

    Args:
        description: What to do (e.g., "Open Chrome and search for Python docs")
        priority: "low", "normal", "high", or "urgent"

    Returns:
        {"task_id": "xxx", "status": "queued", "message": "..."}
    """
    logger.debug("seed_task called with description=%s priority=%s", description[:50], priority)
    queue = get_task_queue()
    task = queue.seed_task(description, priority)

    return {
        "success": True,
        "task_id": task.id,
        "status": "queued",
        "priority": priority,
        "message": f"Task queued. I'll work on that now."
    }


def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Check the status of a task.

    Args:
        task_id: The task ID from seed_task()

    Returns:
        Task status and progress info
    """
    logger.debug("get_task_status called with task_id=%s", task_id)
    queue = get_task_queue()
    task = queue.get_task(task_id)

    if not task:
        return {
            "success": False,
            "error": f"Task {task_id} not found"
        }

    progress = ""
    if task.total_steps > 0:
        progress = f"Step {task.current_step}/{task.total_steps}"
        if task.progress_message:
            progress += f": {task.progress_message}"
    elif task.progress_message:
        progress = task.progress_message

    result = {
        "success": True,
        "task_id": task.id,
        "status": task.status,
        "progress": progress,
        "description": task.description[:100]
    }

    if task.status == "completed" and task.result:
        result["result"] = task.result
    elif task.status == "failed" and task.error:
        result["error"] = task.error

    # Calculate duration
    if task.started_at:
        if task.completed_at:
            result["duration_seconds"] = round(task.completed_at - task.started_at, 1)
        else:
            result["running_seconds"] = round(time.time() - task.started_at, 1)

    return result


def get_last_result() -> Dict[str, Any]:
    """
    Get the result of the most recently completed task.

    Returns:
        Last task result or status
    """
    logger.debug("get_last_result called")
    queue = get_task_queue()
    task = queue.get_last_completed()

    if not task:
        return {
            "success": True,
            "message": "No completed tasks yet"
        }

    result = {
        "success": True,
        "task_id": task.id,
        "status": task.status,
        "description": task.description[:100]
    }

    if task.result:
        result["result"] = task.result
    if task.error:
        result["error"] = task.error
    if task.completed_at and task.started_at:
        result["duration_seconds"] = round(task.completed_at - task.started_at, 1)

    return result


def cancel_task(task_id: str) -> Dict[str, Any]:
    """
    Cancel a running or queued task.

    Args:
        task_id: The task ID to cancel

    Returns:
        Success/failure status
    """
    logger.debug("cancel_task called with task_id=%s", task_id)
    queue = get_task_queue()

    if queue.cancel_task(task_id):
        return {
            "success": True,
            "task_id": task_id,
            "message": "Task cancelled"
        }
    else:
        task = queue.get_task(task_id)
        if task:
            return {
                "success": False,
                "task_id": task_id,
                "message": f"Cannot cancel task in '{task.status}' status"
            }
        return {
            "success": False,
            "error": f"Task {task_id} not found"
        }


def get_queue_status() -> Dict[str, Any]:
    """
    Get overall queue status.

    Returns:
        Queue statistics
    """
    queue = get_task_queue()
    return {
        "success": True,
        **queue.get_status()
    }


def get_worker_report() -> Dict[str, Any]:
    """
    Get the latest progress report from the Claude worker.

    Call this when the user asks "what's happening?" or "how's it going?"
    The worker pushes a report every 3 steps with a summary.

    Returns:
        Latest report with summary of last 3 steps completed
    """
    logger.debug("get_worker_report called")
    report_queue = get_report_queue()
    return report_queue.get_latest_report()


def get_all_reports(task_id: str) -> Dict[str, Any]:
    """
    Get all reports for a specific task.

    Args:
        task_id: The task ID from seed_task()

    Returns:
        List of all reports for the task
    """
    report_queue = get_report_queue()
    reports = report_queue.get_reports_for_task(task_id)
    return {
        "success": True,
        "task_id": task_id,
        "reports": reports,
        "total_reports": len(reports)
    }


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

WORKER_QUEUE_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "seed_task",
            "description": "Queue a desktop automation task. Returns immediately - the Claude worker executes it asynchronously. Use for: opening apps, clicking buttons, typing text, web browsing, file operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "What to do. Be specific. Examples: 'Open Chrome and search for Python documentation', 'Click the Start button', 'Type hello world in Notepad'"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high", "urgent"],
                        "description": "Task priority. Use 'urgent' only for time-sensitive tasks."
                    }
                },
                "required": ["description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_task_status",
            "description": "Check the progress of a task. Use this when the user asks 'is it done?' or 'how's it going?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID from seed_task()"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_last_result",
            "description": "Get the result of the most recent task. Use when the user asks about the last thing you did.",
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
            "name": "cancel_task",
            "description": "Cancel a running task. Use when the user says 'stop' or 'cancel'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID to cancel"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_worker_report",
            "description": "Get the latest progress report from the Claude worker. Returns a summary of the last 3 steps completed. Use when user asks 'what's happening?', 'how's it going?', or 'what have you done so far?'",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


# =============================================================================
# REGISTRATION FOR VIBEMIND
# =============================================================================

def register_worker_queue_tools(tools_manager) -> None:
    """
    Register worker queue tools with the ClientToolsManager.

    Args:
        tools_manager: ClientToolsManager instance
    """
    print("Registering Worker Queue tools...")

    tools_manager.register_with_observer("seed_task",
        lambda description, priority="normal": seed_task(description, priority))
    print("  - seed_task")

    tools_manager.register_with_observer("get_task_status",
        lambda task_id: get_task_status(task_id))
    print("  - get_task_status")

    tools_manager.register_with_observer("get_last_result",
        lambda: get_last_result())
    print("  - get_last_result")

    tools_manager.register_with_observer("cancel_task",
        lambda task_id: cancel_task(task_id))
    print("  - cancel_task")

    tools_manager.register_with_observer("get_worker_report",
        lambda: get_worker_report())
    print("  - get_worker_report")

    print(f"Worker Queue tools registered (5 tools)")


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    # Test the worker queue tools
    print("Testing Worker Queue Tools...\n")

    # Seed a task
    result = seed_task("Open Chrome and search for Python docs")
    print(f"seed_task: {result}")
    task_id = result["task_id"]

    # Check status
    result = get_task_status(task_id)
    print(f"get_task_status: {result}")

    # Get last result (none yet)
    result = get_last_result()
    print(f"get_last_result: {result}")

    # Queue status
    result = get_queue_status()
    print(f"get_queue_status: {result}")

    # Cancel
    result = cancel_task(task_id)
    print(f"cancel_task: {result}")

    print("\nWorker Queue tools test completed")
