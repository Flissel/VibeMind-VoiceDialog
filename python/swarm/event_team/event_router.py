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
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class EventRouter:
    """
    Routes events to correct Redis streams.

    Maps event types to their target streams for proper
    message routing in the swarm architecture.

    Supports dynamic routes loaded from the PluginManager
    in addition to the static STREAM_MAPPING fallback.
    """

    # Stream names
    STREAM_TASKS = "events:tasks"
    STREAM_TASKS_CODING = "events:tasks:coding"
    STREAM_TASKS_DESKTOP = "events:tasks:desktop"
    STREAM_TASKS_IDEAS = "events:tasks:ideas"
    STREAM_TASKS_BUBBLES = "events:tasks:bubbles"
    STREAM_TASKS_ROARBOOT = "events:tasks:roarboot"
    STREAM_TASKS_ZEROCLAW = "events:tasks:zeroclaw"
    STREAM_TASKS_MINIBOOK = "events:tasks:minibook"
    STREAM_TASKS_SCHEDULE = "events:tasks:schedule"
    STREAM_TASKS_N8N = "events:tasks:n8n"
    STREAM_TASKS_VIDEO = "events:tasks:video"
    STREAM_TASKS_AGENTFARM = "events:tasks:agentfarm"
    STREAM_TASKS_FLOWZEN = "events:tasks:flowzen"
    STREAM_TASKS_MIROFISH = "events:tasks:mirofish_pred"
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

        # Messaging tasks -> desktop stream (OpenClawDesktopAgent)
        "messaging.whatsapp": STREAM_TASKS_DESKTOP,
        "messaging.telegram": STREAM_TASKS_DESKTOP,
        "messaging.send": STREAM_TASKS_DESKTOP,
        "web.search": STREAM_TASKS_DESKTOP,
        "web.fetch": STREAM_TASKS_DESKTOP,
        "openclaw.status": STREAM_TASKS_DESKTOP,
        "openclaw.notifications": STREAM_TASKS_DESKTOP,

        # Bubbles tasks -> bubbles stream (BubblesAgent)
        "bubble.list": STREAM_TASKS_BUBBLES,
        "bubble.create": STREAM_TASKS_BUBBLES,
        "bubble.enter": STREAM_TASKS_BUBBLES,
        "bubble.exit": STREAM_TASKS_BUBBLES,
        "bubble.back": STREAM_TASKS_BUBBLES,
        "bubble.delete": STREAM_TASKS_BUBBLES,
        "bubble.delete_all_except": STREAM_TASKS_BUBBLES,
        "bubble.update": STREAM_TASKS_BUBBLES,
        "bubble.find": STREAM_TASKS_BUBBLES,
        "bubble.stats": STREAM_TASKS_BUBBLES,
        "bubble.score": STREAM_TASKS_BUBBLES,
        "bubble.evaluate": STREAM_TASKS_BUBBLES,
        "bubble.promote": STREAM_TASKS_BUBBLES,
        "bubble.current": STREAM_TASKS_BUBBLES,

        # Ideas tasks -> ideas stream (IdeasAgent)
        "idea.list": STREAM_TASKS_IDEAS,
        "idea.create": STREAM_TASKS_IDEAS,
        "idea.update": STREAM_TASKS_IDEAS,
        "idea.delete": STREAM_TASKS_IDEAS,
        "idea.find": STREAM_TASKS_IDEAS,
        "idea.connect": STREAM_TASKS_IDEAS,
        "idea.auto_link": STREAM_TASKS_IDEAS,
        "idea.add_image": STREAM_TASKS_IDEAS,
        "idea.current_space": STREAM_TASKS_IDEAS,
        # Advanced idea tools (whitepaper, summarize, expand, explain, etc.)
        "idea.format_table": STREAM_TASKS_IDEAS,
        "idea.summarize": STREAM_TASKS_IDEAS,
        "idea.whitepaper": STREAM_TASKS_IDEAS,
        "idea.white_paper": STREAM_TASKS_IDEAS,  # Alias
        "idea.expand": STREAM_TASKS_IDEAS,
        "idea.explain": STREAM_TASKS_IDEAS,
        "idea.analyze_links": STREAM_TASKS_IDEAS,
        # Format conversion tools (format_dispatcher)
        "idea.format_note": STREAM_TASKS_IDEAS,
        "idea.format_action_list": STREAM_TASKS_IDEAS,
        "idea.format_pros_cons": STREAM_TASKS_IDEAS,
        "idea.format_hierarchy": STREAM_TASKS_IDEAS,
        "idea.format_specs": STREAM_TASKS_IDEAS,
        "idea.convert_format": STREAM_TASKS_IDEAS,
        "idea.list_formats": STREAM_TASKS_IDEAS,
        "idea.format_revert": STREAM_TASKS_IDEAS,
        # Idea Exploration (AI-Scientist Tree Search with Human-in-the-Loop)
        "idea.explore.start": STREAM_TASKS_IDEAS,
        "idea.explore.stop": STREAM_TASKS_IDEAS,
        "idea.explore.status": STREAM_TASKS_IDEAS,
        "idea.explore.accept": STREAM_TASKS_IDEAS,
        "idea.explore.reject": STREAM_TASKS_IDEAS,
        "idea.explore.depth": STREAM_TASKS_IDEAS,
        "idea.explore.visualize": STREAM_TASKS_IDEAS,
        "idea.explore.continue": STREAM_TASKS_IDEAS,
        "idea.explore.direction": STREAM_TASKS_IDEAS,
        "idea.explore.respond": STREAM_TASKS_IDEAS,
        # Project documentation export
        "idea.generate_doc": STREAM_TASKS_IDEAS,

        # Research tasks -> zeroclaw stream (ZeroClaw Web Research)
        "research.web": STREAM_TASKS_ZEROCLAW,
        "research.scrape": STREAM_TASKS_ZEROCLAW,
        "research.summarize": STREAM_TASKS_ZEROCLAW,
        "research.to_idea": STREAM_TASKS_ZEROCLAW,
        "research.to_rowboat": STREAM_TASKS_ZEROCLAW,

        # Roarboot tasks -> roarboot stream (Rowboat Knowledge Graph)
        "roarboot.search": STREAM_TASKS_ROARBOOT,
        "roarboot.query": STREAM_TASKS_ROARBOOT,
        "roarboot.email_draft": STREAM_TASKS_ROARBOOT,
        "roarboot.meeting_brief": STREAM_TASKS_ROARBOOT,
        "roarboot.deck": STREAM_TASKS_ROARBOOT,
        "roarboot.voice_note": STREAM_TASKS_ROARBOOT,
        "roarboot.status": STREAM_TASKS_ROARBOOT,
        "roarboot.open": STREAM_TASKS_ROARBOOT,
        "roarboot.reset": STREAM_TASKS_ROARBOOT,
        # Docker management
        "roarboot.docker.start": STREAM_TASKS_ROARBOOT,
        "roarboot.docker.stop": STREAM_TASKS_ROARBOOT,
        "roarboot.docker.restart": STREAM_TASKS_ROARBOOT,
        "roarboot.docker.status": STREAM_TASKS_ROARBOOT,

        # Minibook tasks -> minibook stream (Inter-Space Collaboration)
        "minibook.discuss": STREAM_TASKS_MINIBOOK,
        "minibook.collaborate": STREAM_TASKS_MINIBOOK,
        "minibook.status": STREAM_TASKS_MINIBOOK,
        "minibook.results": STREAM_TASKS_MINIBOOK,
        "minibook.list_projects": STREAM_TASKS_MINIBOOK,
        "minibook.poll": STREAM_TASKS_MINIBOOK,

        # Schedule tasks -> schedule stream (Erinnerungen, Alarme, Zeitplan)
        "schedule.create": STREAM_TASKS_SCHEDULE,
        "schedule.list": STREAM_TASKS_SCHEDULE,
        "schedule.cancel": STREAM_TASKS_SCHEDULE,
        "schedule.modify": STREAM_TASKS_SCHEDULE,
        "schedule.status": STREAM_TASKS_SCHEDULE,
        "schedule.snooze": STREAM_TASKS_SCHEDULE,

        # n8n tasks -> n8n stream (Workflow Builder)
        "n8n.generate": STREAM_TASKS_N8N,
        "n8n.list": STREAM_TASKS_N8N,
        "n8n.status": STREAM_TASKS_N8N,
        "n8n.activate": STREAM_TASKS_N8N,
        "n8n.deactivate": STREAM_TASKS_N8N,
        "n8n.delete": STREAM_TASKS_N8N,
        "n8n.execute": STREAM_TASKS_N8N,
        "n8n.describe": STREAM_TASKS_N8N,

        # agentfarm tasks -> agentfarm stream (Autogen team orchestration)
        "agentfarm.create_team": STREAM_TASKS_AGENTFARM,
        "agentfarm.run": STREAM_TASKS_AGENTFARM,
        "agentfarm.status": STREAM_TASKS_AGENTFARM,
        "agentfarm.list_teams": STREAM_TASKS_AGENTFARM,
        "agentfarm.stop": STREAM_TASKS_AGENTFARM,
        "agentfarm.results": STREAM_TASKS_AGENTFARM,
        "agentfarm.list_templates": STREAM_TASKS_AGENTFARM,
        "agentfarm.collaborate": STREAM_TASKS_AGENTFARM,

        # Video events -> video stream
        "video.status": STREAM_TASKS_VIDEO,
        "video.team_status": STREAM_TASKS_VIDEO,
        "video.team_run": STREAM_TASKS_VIDEO,
        "video.vision": STREAM_TASKS_VIDEO,
        "video.demo_analyze": STREAM_TASKS_VIDEO,
        "video.demo_build": STREAM_TASKS_VIDEO,
        "video.lipsync": STREAM_TASKS_VIDEO,
        "video.lipsync_analyze": STREAM_TASKS_VIDEO,
        "video.voice_clone": STREAM_TASKS_VIDEO,
        "video.voice_tts": STREAM_TASKS_VIDEO,

        # Flowzen (Blaue Rose) — only explicit user queries
        "rose.recommend": STREAM_TASKS_FLOWZEN,
        "rose.status": STREAM_TASKS_FLOWZEN,

        # MiroFish (Prediction Engine) → mirofish stream
        "mirofish.simulate": STREAM_TASKS_MIROFISH,
        "mirofish.predict": STREAM_TASKS_MIROFISH,
        "mirofish.graph.build": STREAM_TASKS_MIROFISH,
        "mirofish.graph.search": STREAM_TASKS_MIROFISH,
        "mirofish.list_projects": STREAM_TASKS_MIROFISH,
        "mirofish.report.chat": STREAM_TASKS_MIROFISH,
        "mirofish.interview": STREAM_TASKS_MIROFISH,
        "mirofish.status": STREAM_TASKS_MIROFISH,
        "mirofish.docker.start": STREAM_TASKS_MIROFISH,
        "mirofish.docker.stop": STREAM_TASKS_MIROFISH,
        "mirofish.docker.restart": STREAM_TASKS_MIROFISH,
        "mirofish.docker.status": STREAM_TASKS_MIROFISH,

        # Status events -> status stream
        "task.started": STREAM_STATUS,
        "task.progress": STREAM_STATUS,
        "task.complete": STREAM_STATUS,
        "task.completed": STREAM_STATUS,
        "task.error": STREAM_STATUS,
        "task.timeout": STREAM_STATUS,
        "task.cancelled": STREAM_STATUS,
    }

    def __init__(self):
        self._plugin_routes: Dict[str, str] = {}
        self._plugin_routes_loaded = False

    def _ensure_plugin_routes(self):
        """Lazy-load plugin routes on first access."""
        if self._plugin_routes_loaded:
            return
        try:
            from plugins.plugin_manager import get_plugin_manager
            pm = get_plugin_manager()
            self._plugin_routes = pm.get_event_routes()
            logger.info(f"EventRouter: loaded {len(self._plugin_routes)} routes from plugins")
        except Exception as e:
            logger.debug(f"EventRouter: plugin routes not available ({e}), using static mapping")
        self._plugin_routes_loaded = True

    def register_plugin_routes(self, routes: Dict[str, str]):
        """Register additional routes at runtime (e.g. after plugin accept)."""
        self._plugin_routes.update(routes)

    def get_stream(self, event_type: str) -> str:
        """
        Get target stream for an event type.

        Checks plugin routes first, then falls back to static STREAM_MAPPING.

        Args:
            event_type: Event type (e.g., "code.generate")

        Returns:
            Stream name
        """
        self._ensure_plugin_routes()

        # Plugin routes take precedence
        if event_type in self._plugin_routes:
            return self._plugin_routes[event_type]

        stream = self.STREAM_MAPPING.get(event_type, self.STREAM_TASKS)

        if event_type not in self.STREAM_MAPPING:
            logger.debug(f"EventRouter: Unknown event type '{event_type}', using default stream")

        return stream

    def get_event_types_for_stream(self, stream: str) -> list:
        """
        Get all event types routed to a specific stream.

        Includes both plugin routes and static mapping.

        Args:
            stream: Stream name

        Returns:
            List of event types
        """
        self._ensure_plugin_routes()
        all_routes = {**self.STREAM_MAPPING, **self._plugin_routes}
        return [
            event_type for event_type, s in all_routes.items()
            if s == stream
        ]

    def get_category(self, event_type: str) -> str:
        """
        Get the category of an event type.

        Categories: "coding", "desktop", "ideas", "bubbles", "status", "general"

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
        elif stream == self.STREAM_TASKS_BUBBLES:
            return "bubbles"
        elif stream == self.STREAM_TASKS_ROARBOOT:
            return "roarboot"
        elif stream == self.STREAM_TASKS_ZEROCLAW:
            return "research"
        elif stream == self.STREAM_TASKS_MINIBOOK:
            return "minibook"
        elif stream == self.STREAM_TASKS_N8N:
            return "n8n"
        elif stream == self.STREAM_TASKS_VIDEO:
            return "video"
        elif stream == self.STREAM_TASKS_AGENTFARM:
            return "agentfarm"
        elif stream == self.STREAM_TASKS_FLOWZEN:
            return "flowzen"
        elif stream == self.STREAM_TASKS_MIROFISH:
            return "mirofish"
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
            cls.STREAM_TASKS_BUBBLES,
            cls.STREAM_TASKS_ROARBOOT,
            cls.STREAM_TASKS_ZEROCLAW,
            cls.STREAM_TASKS_MINIBOOK,
            cls.STREAM_TASKS_SCHEDULE,
            cls.STREAM_TASKS_N8N,
            cls.STREAM_TASKS_VIDEO,
            cls.STREAM_TASKS_AGENTFARM,
            cls.STREAM_TASKS_FLOWZEN,
            cls.STREAM_TASKS_MIROFISH,
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
