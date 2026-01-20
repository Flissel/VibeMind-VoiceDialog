"""
Event Team - Middleware between Rachel and Redis Event Bus

The Event Team validates, enriches, and routes events from Rachel's tools
to the correct Redis streams for backend swarm processing.

Components:
- TaskSeeder: Validates tool calls, enriches with context, seeds to Redis
- JobManager: Tracks job state, handles timeouts
- EventRouter: Routes events to correct streams based on event type
"""

from swarm.event_team.task_seeder import TaskSeeder, TaskContext, get_task_seeder
from swarm.event_team.job_manager import JobManager, JobStatus, get_job_manager
from swarm.event_team.event_router import EventRouter, get_event_router

__all__ = [
    # TaskSeeder
    "TaskSeeder",
    "TaskContext",
    "get_task_seeder",
    # JobManager
    "JobManager",
    "JobStatus",
    "get_job_manager",
    # EventRouter
    "EventRouter",
    "get_event_router",
]
