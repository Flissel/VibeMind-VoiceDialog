"""
Event Router - Routes events to correct Redis streams

The EventRouter determines which Redis stream an event should be
published to based on its event type.

Stream hierarchy:
- events:tasks - Main task stream (general)
- events:tasks:coding - Coding-specific tasks
- events:tasks:desktop - Desktop automation tasks
- events:tasks:ideas - Idea/bubble tasks
- events:status - Status updates from backend
- events:jobs - Job state tracking
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EventRouter:
    """
    Routes events to correct Redis streams.

    Maps event types to their target streams for proper
    message routing in the swarm architecture.
    """

    # Stream names
    STREAM_TASKS = "events:tasks"
    STREAM_TASKS_CODING = "events:tasks:coding"
    STREAM_TASKS_DESKTOP = "events:tasks:desktop"
    STREAM_TASKS_IDEAS = "events:tasks:ideas"
    STREAM_STATUS = "events:status"
    STREAM_JOBS = "events:jobs"

    # Event type to stream mapping
    STREAM_MAPPING = {
        # Coding tasks -> coding stream (req-orchestrator, Coding Engine)
        "code.generate": STREAM_TASKS_CODING,
        "code.modify": STREAM_TASKS_CODING,
        "code.status": STREAM_TASKS_CODING,
        "code.show": STREAM_TASKS_CODING,
        "code.preview.start": STREAM_TASKS_CODING,
        "code.preview.stop": STREAM_TASKS_CODING,
        "code.list": STREAM_TASKS_CODING,
        "code.cancel": STREAM_TASKS_CODING,
        "idea.to_project": STREAM_TASKS_CODING,

        # Desktop tasks -> desktop stream (Desktop Automation)
        "desktop.open_app": STREAM_TASKS_DESKTOP,
        "desktop.click": STREAM_TASKS_DESKTOP,
        "desktop.type": STREAM_TASKS_DESKTOP,
        "desktop.press_key": STREAM_TASKS_DESKTOP,
        "desktop.screenshot": STREAM_TASKS_DESKTOP,
        "desktop.scroll": STREAM_TASKS_DESKTOP,
        "desktop.task": STREAM_TASKS_DESKTOP,
        "desktop.task.create": STREAM_TASKS_DESKTOP,
        "desktop.task.update": STREAM_TASKS_DESKTOP,
        "desktop.task.list": STREAM_TASKS_DESKTOP,
        "desktop.moire.scan": STREAM_TASKS_DESKTOP,
        "desktop.moire.find": STREAM_TASKS_DESKTOP,

        # Ideas/bubbles tasks -> ideas stream
        "bubble.list": STREAM_TASKS_IDEAS,
        "bubble.create": STREAM_TASKS_IDEAS,
        "bubble.enter": STREAM_TASKS_IDEAS,
        "bubble.exit": STREAM_TASKS_IDEAS,
        "bubble.delete": STREAM_TASKS_IDEAS,
        "bubble.update": STREAM_TASKS_IDEAS,
        "bubble.stats": STREAM_TASKS_IDEAS,
        "bubble.score": STREAM_TASKS_IDEAS,
        "bubble.evaluate": STREAM_TASKS_IDEAS,
        "bubble.promote": STREAM_TASKS_IDEAS,
        "idea.list": STREAM_TASKS_IDEAS,
        "idea.create": STREAM_TASKS_IDEAS,
        "idea.update": STREAM_TASKS_IDEAS,
        "idea.delete": STREAM_TASKS_IDEAS,
        "idea.find": STREAM_TASKS_IDEAS,
        "idea.connect": STREAM_TASKS_IDEAS,
        "idea.auto_link": STREAM_TASKS_IDEAS,
        "idea.add_image": STREAM_TASKS_IDEAS,
        "idea.current_space": STREAM_TASKS_IDEAS,
        # Advanced idea tools (whitepaper, summarize, expand, etc.)
        "idea.format_table": STREAM_TASKS_IDEAS,
        "idea.summarize": STREAM_TASKS_IDEAS,
        "idea.whitepaper": STREAM_TASKS_IDEAS,
        "idea.expand": STREAM_TASKS_IDEAS,
        "idea.analyze_links": STREAM_TASKS_IDEAS,
        # Format conversion tools (format_dispatcher)
        "idea.format_note": STREAM_TASKS_IDEAS,
        "idea.format_action_list": STREAM_TASKS_IDEAS,
        "idea.format_pros_cons": STREAM_TASKS_IDEAS,
        "idea.format_hierarchy": STREAM_TASKS_IDEAS,
        "idea.format_specs": STREAM_TASKS_IDEAS,
        "idea.convert_format": STREAM_TASKS_IDEAS,
        "idea.list_formats": STREAM_TASKS_IDEAS,

        # Status events -> status stream
        "task.started": STREAM_STATUS,
        "task.progress": STREAM_STATUS,
        "task.complete": STREAM_STATUS,
        "task.completed": STREAM_STATUS,
        "task.error": STREAM_STATUS,
        "task.timeout": STREAM_STATUS,
        "task.cancelled": STREAM_STATUS,
    }

    def get_stream(self, event_type: str) -> str:
        """
        Get target stream for an event type.

        Args:
            event_type: Event type (e.g., "code.generate")

        Returns:
            Stream name
        """
        stream = self.STREAM_MAPPING.get(event_type, self.STREAM_TASKS)

        if event_type not in self.STREAM_MAPPING:
            logger.debug(f"EventRouter: Unknown event type '{event_type}', using default stream")

        return stream

    def get_event_types_for_stream(self, stream: str) -> list:
        """
        Get all event types routed to a specific stream.

        Args:
            stream: Stream name

        Returns:
            List of event types
        """
        return [
            event_type for event_type, s in self.STREAM_MAPPING.items()
            if s == stream
        ]

    def get_category(self, event_type: str) -> str:
        """
        Get the category of an event type.

        Categories: "coding", "desktop", "ideas", "status", "general"

        Args:
            event_type: Event type

        Returns:
            Category name
        """
        stream = self.get_stream(event_type)

        if stream == self.STREAM_TASKS_CODING:
            return "coding"
        elif stream == self.STREAM_TASKS_DESKTOP:
            return "desktop"
        elif stream == self.STREAM_TASKS_IDEAS:
            return "ideas"
        elif stream == self.STREAM_STATUS:
            return "status"
        else:
            return "general"

    @classmethod
    def all_streams(cls) -> list:
        """Get list of all stream names."""
        return [
            cls.STREAM_TASKS,
            cls.STREAM_TASKS_CODING,
            cls.STREAM_TASKS_DESKTOP,
            cls.STREAM_TASKS_IDEAS,
            cls.STREAM_STATUS,
            cls.STREAM_JOBS,
        ]


# Singleton instance
_event_router: Optional[EventRouter] = None


def get_event_router() -> EventRouter:
    """Get or create EventRouter singleton."""
    global _event_router
    if _event_router is None:
        _event_router = EventRouter()
    return _event_router


__all__ = [
    "EventRouter",
    "get_event_router",
]
