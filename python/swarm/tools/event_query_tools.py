"""
Event Query Tools for AutoGen Swarm

Tools for querying event streams and task status.
Used by Voice Agent to report on background task progress.
"""

from typing import Optional, List
import asyncio
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def get_task_status_summary() -> str:
    """
    Get a summary of recent task status across all spaces.

    Returns:
        Human-readable summary of active/recent tasks
    """
    from swarm.event_streams import get_event_manager_sync

    manager = get_event_manager_sync()

    # Run async in sync context
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context, can't use run()
            return "Status query pending - check again shortly."
        return loop.run_until_complete(manager.get_task_status_summary())
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(manager.get_task_status_summary())


def get_space_events(space_id: str, limit: int = 5) -> str:
    """
    Get recent events from a specific space.

    Args:
        space_id: Space/bubble ID to query
        limit: Maximum events to return

    Returns:
        Formatted event list
    """
    from swarm.event_streams import get_event_manager_sync

    manager = get_event_manager_sync()

    async def _query():
        events = await manager.query_events(space_id, limit=limit)
        if not events:
            return f"No recent events in {space_id}"

        lines = [f"Recent events in {space_id}:"]
        for event in events:
            lines.append(f"  - {event.event_type} by {event.agent}")
        return "\n".join(lines)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return f"Querying events for {space_id}..."
        return loop.run_until_complete(_query())
    except RuntimeError:
        return asyncio.run(_query())


def list_active_tasks(space_id: str = "") -> str:
    """
    List all currently active/running tasks.

    Args:
        space_id: Optional space filter

    Returns:
        Formatted list of active tasks
    """
    from swarm.event_streams import get_event_manager_sync

    manager = get_event_manager_sync()

    async def _list():
        tasks = await manager.list_active_tasks(space_id if space_id else None)
        if not tasks:
            return "No active tasks."

        lines = ["Active tasks:"]
        for task in tasks:
            progress = f"{task.progress * 100:.0f}%" if task.progress > 0 else "starting"
            lines.append(f"  - [{task.status}] {task.message or task.task_id} ({progress})")
        return "\n".join(lines)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return "Checking active tasks..."
        return loop.run_until_complete(_list())
    except RuntimeError:
        return asyncio.run(_list())


def get_latest_events(limit: int = 10) -> str:
    """
    Get latest events across all spaces.

    Args:
        limit: Maximum events per space

    Returns:
        Formatted event summary
    """
    from swarm.event_streams import get_event_manager_sync

    manager = get_event_manager_sync()

    async def _get_latest():
        all_events = await manager.get_latest_events(limit=limit)
        if not all_events:
            return "No recent activity."

        lines = ["Recent activity:"]
        for space_id, events in all_events.items():
            if events:
                latest = events[0]
                lines.append(f"  {space_id}: {latest.event_type} by {latest.agent}")
        return "\n".join(lines)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return "Checking recent events..."
        return loop.run_until_complete(_get_latest())
    except RuntimeError:
        return asyncio.run(_get_latest())


# Collect all tools for export
EVENT_TOOLS = [
    get_task_status_summary,
    get_space_events,
    list_active_tasks,
    get_latest_events,
]


__all__ = [
    "get_task_status_summary",
    "get_space_events",
    "list_active_tasks",
    "get_latest_events",
    "EVENT_TOOLS",
]
