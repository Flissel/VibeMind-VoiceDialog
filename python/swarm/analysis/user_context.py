"""
UserContext - User profiling and context aggregation for VibeMind

Aggregates user context from multiple sources:
- SystemContextStore (recent actions)
- Database (preferences, history)
- Conversation history (current topic, entities)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from data.models import Task

logger = logging.getLogger(__name__)


@dataclass
class ContextEntry:
    """A single context entry from recent actions."""
    event_type: str
    result: str
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserContext:
    """
    Aggregated user context for intent analysis.

    Contains information from multiple sources to help
    understand the user's current situation and preferences.
    """
    user_id: str
    session_id: str

    # From SystemContextStore - recent actions in this session
    recent_actions: List[ContextEntry] = field(default_factory=list)

    # From Database/Supermemory - learned preferences
    preferences: Dict[str, Any] = field(default_factory=dict)

    # Interaction style detected from history
    interaction_style: str = "concise"  # "concise" | "detailed" | "casual"

    # From conversation history
    current_topic: Optional[str] = None
    mentioned_entities: List[str] = field(default_factory=list)

    # Current space context
    current_space: Optional[str] = None

    # Task Memory - persistent tasks across sessions
    pending_tasks: List[Any] = field(default_factory=list)  # List[Task]
    recent_completed_tasks: List[Any] = field(default_factory=list)  # List[Task]

    def get_recent_event_types(self) -> List[str]:
        """Get list of recent event types for pattern detection."""
        return [a.event_type for a in self.recent_actions[-10:]]

    def has_recent_action(self, event_type: str, within_seconds: float = 120) -> bool:
        """Check if a specific action type occurred recently."""
        now = time.time()
        for action in reversed(self.recent_actions):
            if now - action.timestamp > within_seconds:
                break
            if action.event_type == event_type:
                return True
        return False

    def get_last_result(self) -> Optional[str]:
        """Get the result of the most recent action."""
        if self.recent_actions:
            return self.recent_actions[-1].result
        return None

    def has_pending_tasks(self) -> bool:
        """Check if there are pending tasks."""
        return len(self.pending_tasks) > 0

    def get_pending_task_titles(self) -> List[str]:
        """Get titles of pending tasks for context injection."""
        return [t.title for t in self.pending_tasks if hasattr(t, 'title')]

    def get_task_context_string(self) -> Optional[str]:
        """Get a string summarizing task state for prompt injection."""
        parts = []
        if self.pending_tasks:
            titles = self.get_pending_task_titles()
            if titles:
                parts.append(f"Laufende Aufgaben: {', '.join(titles[:3])}")
        if self.recent_completed_tasks:
            recent = [t.title for t in self.recent_completed_tasks[:2] if hasattr(t, 'title')]
            if recent:
                parts.append(f"Zuletzt erledigt: {', '.join(recent)}")
        return " | ".join(parts) if parts else None


class UserContextBuilder:
    """
    Builds UserContext by aggregating data from multiple sources.

    Sources:
    - SystemContextStore: Recent actions in session
    - Database: User preferences (if available)
    - Conversation tools: Current topic, entities
    """

    def __init__(self):
        self._context_store = None
        self._preference_repo = None

    @property
    def context_store(self):
        """Lazy load SystemContextStore."""
        if self._context_store is None:
            try:
                from swarm.orchestrator.system_context_store import get_system_context_store
                self._context_store = get_system_context_store()
            except ImportError:
                logger.warning("SystemContextStore not available")
        return self._context_store

    async def build(self, user_id: str = "default", session_id: str = "default") -> UserContext:
        """
        Build UserContext by aggregating data from all sources.

        Args:
            user_id: User identifier (default for single-user)
            session_id: Current session identifier

        Returns:
            Populated UserContext
        """
        context = UserContext(
            user_id=user_id,
            session_id=session_id,
        )

        # 1. Get recent actions from SystemContextStore
        await self._load_recent_actions(context)

        # 2. Get preferences from database (if available)
        await self._load_preferences(context)

        # 3. Extract conversation context
        await self._load_conversation_context(context)

        # 4. Get current space
        await self._load_current_space(context)

        # 5. Detect interaction style
        context.interaction_style = self._detect_style(context)

        # 6. Load task memory (persistent across sessions)
        await self._load_task_memory(context)

        logger.debug(f"Built context: {len(context.recent_actions)} recent actions, "
                    f"style={context.interaction_style}, space={context.current_space}, "
                    f"pending_tasks={len(context.pending_tasks)}")

        return context

    async def _load_recent_actions(self, context: UserContext) -> None:
        """Load recent actions from SystemContextStore."""
        if self.context_store is None:
            return

        try:
            recent = self.context_store.get_recent(limit=10)
            context.recent_actions = [
                ContextEntry(
                    event_type=e.event_type,
                    result=e.result,
                    timestamp=e.timestamp,
                    tags=e.tags,
                    metadata=e.metadata
                )
                for e in recent
            ]
        except Exception as e:
            logger.warning(f"Failed to load recent actions: {e}")

    async def _load_preferences(self, context: UserContext) -> None:
        """Load user preferences from database."""
        try:
            # Future: Load from conversion_ai_repository
            # For now, use sensible defaults
            context.preferences = {
                "language": "de",
                "verbosity": "concise",
                "confirm_destructive": True,
            }
        except Exception as e:
            logger.warning(f"Failed to load preferences: {e}")

    async def _load_conversation_context(self, context: UserContext) -> None:
        """Extract context from conversation history."""
        try:
            from tools.conversation_tools import get_conversation_transcript

            transcript = get_conversation_transcript()
            if transcript:
                # Extract mentioned entities (simple heuristic)
                context.mentioned_entities = self._extract_entities(transcript)

                # Extract current topic (last few exchanges)
                context.current_topic = self._extract_topic(transcript)
        except ImportError:
            logger.debug("Conversation tools not available")
        except Exception as e:
            logger.warning(f"Failed to load conversation context: {e}")

    async def _load_current_space(self, context: UserContext) -> None:
        """Load current space/bubble context."""
        try:
            from tools.bubble_tools import get_current_space
            result = get_current_space({})
            if result and "current" not in result.lower():
                context.current_space = result
        except ImportError:
            logger.debug("Bubble tools not available")
        except Exception as e:
            logger.warning(f"Failed to load current space: {e}")

    async def _load_task_memory(self, context: UserContext) -> None:
        """Load persistent task memory from database."""
        try:
            from data.task_memory_repository import get_task_memory_repository

            task_repo = get_task_memory_repository()

            # Load pending tasks (not completed/cancelled)
            context.pending_tasks = task_repo.get_pending_tasks(context.user_id)

            # Load recently completed tasks for context
            context.recent_completed_tasks = task_repo.list_tasks(
                user_id=context.user_id,
                status="completed",
                limit=5
            )

            if context.pending_tasks:
                logger.debug(f"Loaded {len(context.pending_tasks)} pending tasks")

        except ImportError:
            logger.debug("TaskMemoryRepository not available")
        except Exception as e:
            logger.warning(f"Failed to load task memory: {e}")

    def _detect_style(self, context: UserContext) -> str:
        """Detect user's preferred interaction style from history."""
        # Future: Analyze past interactions to detect style
        # For now, return default
        return context.preferences.get("verbosity", "concise")

    def _extract_entities(self, transcript: str) -> List[str]:
        """Extract mentioned entities (idea names, space names) from transcript."""
        entities = []

        # Simple keyword extraction (can be enhanced with NLP)
        keywords = ["Space", "Bubble", "Idee", "Notiz", "Projekt"]

        for line in transcript.split('\n'):
            for keyword in keywords:
                if keyword in line:
                    # Try to extract the name following the keyword
                    # This is a simple heuristic
                    parts = line.split(keyword)
                    if len(parts) > 1:
                        name = parts[1].strip().split()[0] if parts[1].strip() else None
                        if name and len(name) > 2:
                            entities.append(name.strip('.,!?'))

        return list(set(entities))[:10]  # Dedupe and limit

    def _extract_topic(self, transcript: str) -> Optional[str]:
        """Extract current conversation topic from recent exchanges."""
        lines = transcript.strip().split('\n')

        # Get last few exchanges
        recent_lines = lines[-6:] if len(lines) > 6 else lines

        # Simple topic detection based on keywords
        topic_keywords = {
            "space": ["Space", "Bubble", "erstellen", "loeschen", "betreten"],
            "idee": ["Idee", "Notiz", "verbinden", "verlinken"],
            "desktop": ["oeffnen", "klicken", "App", "Desktop"],
            "code": ["Code", "generieren", "Projekt", "App entwickeln"],
        }

        recent_text = ' '.join(recent_lines).lower()

        for topic, keywords in topic_keywords.items():
            for keyword in keywords:
                if keyword.lower() in recent_text:
                    return topic

        return None


# Singleton
_context_builder: Optional[UserContextBuilder] = None


def get_user_context_builder() -> UserContextBuilder:
    """Get or create UserContextBuilder singleton."""
    global _context_builder
    if _context_builder is None:
        _context_builder = UserContextBuilder()
    return _context_builder


__all__ = [
    "UserContext",
    "ContextEntry",
    "UserContextBuilder",
    "get_user_context_builder",
]
