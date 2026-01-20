"""
Task Seeder - Validates and seeds events to Redis streams

The TaskSeeder is responsible for:
1. Validating tool call payloads
2. Enriching with user/session context
3. Generating job IDs
4. Registering jobs with JobManager
5. Publishing events to Redis via EventBus
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TaskContext:
    """Context for task seeding."""
    user_id: str = "default"
    session_id: Optional[str] = None
    bubble_context: Optional[Dict[str, Any]] = None
    priority: int = 5  # 1=highest, 10=lowest
    metadata: Dict[str, Any] = field(default_factory=dict)
    user_input: str = ""  # Original user input for logging/debugging


class TaskSeeder:
    """
    Validates and seeds events to Redis streams.

    Acts as middleware between Rachel's tools and the Event Bus.
    """

    # Required fields for each task type
    # NOTE: Validation is relaxed - IntentClassifier extracts params from natural language
    # and may use different field names (e.g., "content" vs "title").
    # Only critical fields are validated; empty means no required fields.
    REQUIRED_FIELDS = {
        # Most event types don't require strict validation since
        # the classifier extracts what it can from natural language
    }

    def __init__(self):
        self._bus = None
        self._job_manager = None
        self._router = None

    @property
    def bus(self):
        """Lazy-load EventBus."""
        if self._bus is None:
            from swarm.event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    @property
    def job_manager(self):
        """Lazy-load JobManager."""
        if self._job_manager is None:
            from swarm.event_team.job_manager import get_job_manager
            self._job_manager = get_job_manager()
        return self._job_manager

    @property
    def router(self):
        """Lazy-load EventRouter."""
        if self._router is None:
            from swarm.event_team.event_router import get_event_router
            self._router = get_event_router()
        return self._router

    def validate_payload(self, task_type: str, payload: Dict[str, Any]) -> None:
        """
        Validate required fields for a task type.

        Args:
            task_type: Event type (e.g., "code.generate")
            payload: Task payload to validate

        Raises:
            ValueError: If required fields are missing
        """
        required = self.REQUIRED_FIELDS.get(task_type, [])
        missing = [f for f in required if f not in payload or not payload[f]]

        if missing:
            raise ValueError(f"Missing required fields for {task_type}: {missing}")

    def enrich_payload(
        self,
        payload: Dict[str, Any],
        job_id: str,
        context: TaskContext
    ) -> Dict[str, Any]:
        """
        Enrich payload with context and metadata.

        Args:
            payload: Original payload
            job_id: Generated job ID
            context: Task context

        Returns:
            Enriched payload
        """
        return {
            **payload,
            "job_id": job_id,
            "user_id": context.user_id,
            "session_id": context.session_id,
            "priority": context.priority,
            "bubble_context": context.bubble_context,
            "metadata": context.metadata,
        }

    async def seed_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        context: Optional[TaskContext] = None
    ) -> str:
        """
        Validate, enrich, and seed a task event.

        Args:
            task_type: Event type (e.g., "code.generate")
            payload: Task payload
            context: Optional task context

        Returns:
            job_id: The generated job ID

        Raises:
            ValueError: If validation fails
        """
        context = context or TaskContext()

        # 1. Validate payload
        self.validate_payload(task_type, payload)

        # 2. Generate job_id
        job_id = str(uuid.uuid4())

        # 3. Enrich payload with context
        enriched_payload = self.enrich_payload(payload, job_id, context)

        # 4. Get target stream from router
        stream = self.router.get_stream(task_type)

        # 5. Register job with JobManager
        await self.job_manager.register_job(job_id, task_type, enriched_payload)

        # 6. Publish to Redis
        from swarm.event_bus import SwarmEvent
        event = SwarmEvent(
            stream=stream,
            event_type=task_type,
            payload=enriched_payload,
            job_id=job_id
        )
        await self.bus.publish(event)

        logger.info(f"TaskSeeder: Seeded {task_type} to {stream} (job={job_id})")
        return job_id

    def seed_task_sync(
        self,
        task_type: str,
        payload: Dict[str, Any],
        context: Optional[TaskContext] = None
    ) -> str:
        """Synchronous wrapper for seed_task."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.seed_task(task_type, payload, context)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.seed_task(task_type, payload, context))
        except RuntimeError:
            return asyncio.run(self.seed_task(task_type, payload, context))


# Singleton instance
_task_seeder: Optional[TaskSeeder] = None


def get_task_seeder() -> TaskSeeder:
    """Get or create TaskSeeder singleton."""
    global _task_seeder
    if _task_seeder is None:
        _task_seeder = TaskSeeder()
    return _task_seeder


__all__ = [
    "TaskSeeder",
    "TaskContext",
    "get_task_seeder",
]
