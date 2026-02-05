"""
VibeMind Core Event Bus Module

Event system for Redis streams, input buffering, and event routing.
Re-exports from legacy swarm/ module for backward compatibility.
"""

# Re-export from legacy swarm module
from swarm.event_bus import EventBus, SwarmEvent, get_event_bus
from swarm.event_buffer import InputEvent, TaskInfo, get_event_buffer
from swarm.event_team import (
    TaskSeeder,
    TaskContext,
    get_task_seeder,
    EventRouter,
    get_event_router,
    JobManager,
    JobStatus,
    get_job_manager,
)

__all__ = [
    # Event Bus
    "EventBus",
    "SwarmEvent",
    "get_event_bus",
    # Event Buffer
    "InputEvent",
    "TaskInfo",
    "get_event_buffer",
    # Task Seeder
    "TaskSeeder",
    "TaskContext",
    "get_task_seeder",
    # Event Router
    "EventRouter",
    "get_event_router",
    # Job Manager
    "JobManager",
    "JobStatus",
    "get_job_manager",
]
