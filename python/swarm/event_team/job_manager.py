"""
Job Manager - Tracks job state and handles timeouts

The JobManager is responsible for:
1. Registering new jobs
2. Tracking job status
3. Handling timeouts
4. Publishing status updates
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, Callable, List

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job status states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class JobInfo:
    """Information about a job."""
    job_id: str
    task_type: str
    status: JobStatus
    payload: Dict[str, Any]
    created_at: float
    updated_at: float = field(default_factory=time.time)
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: int = 0
    stage: str = ""


class JobManager:
    """
    Tracks job state and handles timeouts.

    Maintains an in-memory registry of jobs and their status.
    Publishes timeout events when jobs exceed their timeout.
    """

    def __init__(self, default_timeout: int = 300):
        """
        Initialize JobManager.

        Args:
            default_timeout: Default timeout in seconds (default: 5 minutes)
        """
        self.jobs: Dict[str, JobInfo] = {}
        self.default_timeout = default_timeout
        self._bus = None
        self._status_callbacks: List[Callable] = []

    @property
    def bus(self):
        """Lazy-load EventBus."""
        if self._bus is None:
            from swarm.event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    def add_status_callback(self, callback: Callable[[JobInfo], Any]):
        """Add a callback for status updates."""
        self._status_callbacks.append(callback)

    async def register_job(
        self,
        job_id: str,
        task_type: str,
        payload: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> JobInfo:
        """
        Register a new job.

        Args:
            job_id: Unique job ID
            task_type: Type of task (e.g., "code.generate")
            payload: Job payload
            timeout: Optional custom timeout in seconds

        Returns:
            JobInfo for the registered job
        """
        now = time.time()
        job = JobInfo(
            job_id=job_id,
            task_type=task_type,
            status=JobStatus.PENDING,
            payload=payload,
            created_at=now,
            updated_at=now,
        )
        self.jobs[job_id] = job

        logger.info(f"JobManager: Registered job {job_id} ({task_type})")

        # Start timeout watcher
        timeout_seconds = timeout or self.default_timeout
        asyncio.create_task(self._watch_timeout(job_id, timeout_seconds))

        return job

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        result: Any = None,
        error: Optional[str] = None,
        progress: int = 0,
        stage: str = ""
    ) -> Optional[JobInfo]:
        """
        Update job status.

        Args:
            job_id: Job ID to update
            status: New status
            result: Optional result data
            error: Optional error message
            progress: Progress percentage (0-100)
            stage: Current stage description

        Returns:
            Updated JobInfo or None if not found
        """
        job = self.jobs.get(job_id)
        if not job:
            logger.warning(f"JobManager: Job {job_id} not found")
            return None

        job.status = status
        job.updated_at = time.time()
        job.result = result
        job.error = error
        job.progress = progress
        job.stage = stage

        logger.info(f"JobManager: Updated job {job_id} -> {status.value} ({progress}%)")

        # Notify callbacks
        for callback in self._status_callbacks:
            try:
                result = callback(job)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Status callback error: {e}")

        return job

    async def get_job(self, job_id: str) -> Optional[JobInfo]:
        """Get job info by ID."""
        return self.jobs.get(job_id)

    async def list_jobs(
        self,
        status_filter: Optional[JobStatus] = None,
        limit: int = 50
    ) -> List[JobInfo]:
        """
        List jobs, optionally filtered by status.

        Args:
            status_filter: Optional status to filter by
            limit: Maximum number of jobs to return

        Returns:
            List of JobInfo
        """
        logger.debug("list_jobs called: status_filter=%s, limit=%s", status_filter, limit)
        jobs = list(self.jobs.values())

        if status_filter:
            jobs = [j for j in jobs if j.status == status_filter]

        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if cancelled, False if not found or already finished
        """
        logger.debug("cancel_job called: job_id=%s", job_id)
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False

        await self.update_status(job_id, JobStatus.CANCELLED, error="Cancelled by user")

        # Publish cancel event
        from swarm.event_bus import SwarmEvent
        event = SwarmEvent(
            stream="events:status",
            event_type="task.cancelled",
            payload={"job_id": job_id},
            job_id=job_id
        )
        await self.bus.publish(event)

        return True

    async def _watch_timeout(self, job_id: str, timeout_seconds: int):
        """
        Watch for job timeout.

        Args:
            job_id: Job ID to watch
            timeout_seconds: Timeout in seconds
        """
        await asyncio.sleep(timeout_seconds)

        job = self.jobs.get(job_id)
        if not job:
            return

        # Check if job is still pending or running
        if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
            logger.warning(f"JobManager: Job {job_id} timed out after {timeout_seconds}s")

            await self.update_status(
                job_id,
                JobStatus.TIMEOUT,
                error=f"Timeout after {timeout_seconds} seconds"
            )

            # Publish timeout event
            from swarm.event_bus import SwarmEvent
            event = SwarmEvent(
                stream="events:status",
                event_type="task.timeout",
                payload={"job_id": job_id, "timeout": timeout_seconds},
                job_id=job_id
            )
            await self.bus.publish(event)

    def cleanup_old_jobs(self, max_age_seconds: int = 3600):
        """
        Remove jobs older than max_age_seconds.

        Args:
            max_age_seconds: Maximum age in seconds (default: 1 hour)
        """
        now = time.time()
        old_jobs = [
            job_id for job_id, job in self.jobs.items()
            if now - job.created_at > max_age_seconds
            and job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.TIMEOUT, JobStatus.CANCELLED]
        ]

        for job_id in old_jobs:
            del self.jobs[job_id]

        if old_jobs:
            logger.info(f"JobManager: Cleaned up {len(old_jobs)} old jobs")


# Singleton instance
_job_manager: Optional[JobManager] = None


def get_job_manager(default_timeout: int = 300) -> JobManager:
    """Get or create JobManager singleton."""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager(default_timeout)
    return _job_manager


__all__ = [
    "JobManager",
    "JobStatus",
    "JobInfo",
    "get_job_manager",
]
