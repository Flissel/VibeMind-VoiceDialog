"""
Base Worker for VibeMind Event Buffer System

Workers are autonomous task executors:
- Queue-based processing
- Progress event publishing
- Interrupt handling
- No user interaction (that's for User Agents)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable, TYPE_CHECKING
from enum import Enum

from swarm.navigation import SpaceType
from swarm.event_buffer import TaskInfo, TaskStatus, get_event_buffer

if TYPE_CHECKING:
    pass  # RedisEventManager removed (legacy event_streams)

logger = logging.getLogger(__name__)


class WorkerState(Enum):
    """State of a worker."""
    IDLE = "idle"
    PROCESSING = "processing"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class WorkerConfig:
    """Configuration for a worker."""
    name: str  # e.g., "bubble_worker"
    space_type: SpaceType
    description: str = ""

    # Processing settings
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    task_timeout_seconds: float = 60.0


@dataclass
class WorkerProgress:
    """Progress update from a worker."""
    worker_name: str
    task_id: str
    progress_percent: int  # 0-100
    message: str
    timestamp: float = field(default_factory=lambda: __import__('time').time())


class BaseWorker(ABC):
    """
    Base class for Worker Agents.

    Workers:
    - Process tasks from their queue autonomously
    - Publish progress events
    - Can be interrupted by user
    - Report results back to User Agent
    """

    def __init__(
        self,
        config: WorkerConfig,
        event_manager: Optional["RedisEventManager"] = None,
    ):
        """
        Initialize worker.

        Args:
            config: Worker configuration
            event_manager: Optional event manager for progress publishing
        """
        self.config = config
        self.event_manager = event_manager

        # State
        self._state = WorkerState.IDLE
        self._current_task: Optional[TaskInfo] = None
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._interrupted = False

        # Callbacks
        self._on_complete: Optional[Callable[[TaskInfo], Any]] = None
        self._on_progress: Optional[Callable[[WorkerProgress], Any]] = None

        logger.info(f"BaseWorker initialized: {self.config.name}")

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def state(self) -> WorkerState:
        return self._state

    @property
    def is_busy(self) -> bool:
        return self._state == WorkerState.PROCESSING

    @abstractmethod
    async def execute_task(self, task: TaskInfo) -> str:
        """
        Execute a task. Must be implemented by subclasses.

        Args:
            task: The task to execute

        Returns:
            Result string
        """
        pass

    async def queue_task(self, task: TaskInfo) -> None:
        """
        Add a task to the worker's queue.

        Args:
            task: Task to queue
        """
        await self._task_queue.put(task)
        logger.debug(f"Worker {self.name}: Queued task {task.task_id}")

    async def run(self) -> None:
        """
        Main worker loop. Processes tasks from queue continuously.
        """
        self._running = True
        logger.info(f"Worker {self.name}: Starting main loop")

        while self._running:
            try:
                # Wait for task with timeout (allows interrupt checking)
                try:
                    task = await asyncio.wait_for(
                        self._task_queue.get(),
                        timeout=0.5
                    )
                except asyncio.TimeoutError:
                    # No task, check if we should stop
                    if self._interrupted:
                        self._interrupted = False
                        logger.info(f"Worker {self.name}: Interrupt handled")
                    continue

                # Process the task
                self._current_task = task
                self._state = WorkerState.PROCESSING

                await self._publish_progress(0, "Starting task...")

                try:
                    # Execute with timeout
                    result = await asyncio.wait_for(
                        self._execute_with_retry(task),
                        timeout=self.config.task_timeout_seconds
                    )

                    # Mark completed
                    task.status = TaskStatus.COMPLETED
                    task.result = result

                    await self._publish_progress(100, "Task completed")

                    # Notify completion
                    if self._on_complete:
                        try:
                            callback_result = self._on_complete(task)
                            if asyncio.iscoroutine(callback_result):
                                await callback_result
                        except Exception as e:
                            logger.error(f"Completion callback error: {e}")

                except asyncio.TimeoutError:
                    task.status = TaskStatus.FAILED
                    task.error = "Task timed out"
                    logger.warning(f"Worker {self.name}: Task {task.task_id} timed out")

                except asyncio.CancelledError:
                    task.status = TaskStatus.CANCELLED
                    logger.info(f"Worker {self.name}: Task {task.task_id} cancelled")
                    raise

                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    logger.error(f"Worker {self.name}: Task failed: {e}")

                finally:
                    self._current_task = None
                    self._state = WorkerState.IDLE

            except asyncio.CancelledError:
                logger.info(f"Worker {self.name}: Cancelled")
                break

        self._state = WorkerState.STOPPED
        logger.info(f"Worker {self.name}: Stopped")

    async def _execute_with_retry(self, task: TaskInfo) -> str:
        """
        Execute task with retry logic.

        Args:
            task: Task to execute

        Returns:
            Result string
        """
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                return await self.execute_task(task)

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Worker {self.name}: Attempt {attempt + 1}/{self.config.max_retries} "
                    f"failed: {e}"
                )

                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay_seconds)

        raise last_error or Exception("Task failed after retries")

    async def _publish_progress(self, percent: int, message: str) -> None:
        """
        Publish progress update.

        Args:
            percent: Progress percentage (0-100)
            message: Progress message
        """
        if not self._current_task:
            return

        progress = WorkerProgress(
            worker_name=self.name,
            task_id=self._current_task.task_id,
            progress_percent=percent,
            message=message,
        )

        # Notify callback
        if self._on_progress:
            try:
                result = self._on_progress(progress)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

        # Publish to event stream (legacy event_streams removed)
        if self.event_manager and hasattr(self.event_manager, 'publish_event'):
            try:
                await self.event_manager.publish_event(
                    self.config.space_type.value,
                    {
                        "event_type": "task_progress",
                        "agent": self.name,
                        "payload": {
                            "task_id": progress.task_id,
                            "progress": percent,
                            "message": message,
                        }
                    }
                )
            except Exception as e:
                logger.debug(f"Could not publish progress: {e}")

    def interrupt(self) -> None:
        """
        Request interrupt of current task.
        """
        if self._current_task:
            self._interrupted = True
            logger.info(f"Worker {self.name}: Interrupt requested")

    async def stop(self) -> None:
        """
        Stop the worker gracefully.
        """
        self._running = False
        self._interrupted = True
        logger.info(f"Worker {self.name}: Stop requested")

    def on_complete(self, callback: Callable[[TaskInfo], Any]) -> None:
        """Set callback for task completion."""
        self._on_complete = callback

    def on_progress(self, callback: Callable[[WorkerProgress], Any]) -> None:
        """Set callback for progress updates."""
        self._on_progress = callback

    def get_queue_size(self) -> int:
        """Get number of pending tasks in queue."""
        return self._task_queue.qsize()


async def create_worker_pool(
    workers: List[BaseWorker],
) -> List[asyncio.Task]:
    """
    Create and start a pool of workers.

    Args:
        workers: List of workers to start

    Returns:
        List of asyncio tasks running the workers
    """
    tasks = []
    for worker in workers:
        task = asyncio.create_task(worker.run())
        tasks.append(task)
        logger.info(f"Started worker: {worker.name}")
    return tasks


__all__ = [
    "BaseWorker",
    "WorkerConfig",
    "WorkerProgress",
    "WorkerState",
    "create_worker_pool",
]
