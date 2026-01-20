"""
Session Router - Manages per-user orchestrator instances for multi-user support.

This module provides:
1. Per-user session isolation
2. Dedicated orchestrator instances per session
3. Per-user Redis stream prefixes
4. Automatic session cleanup on inactivity
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    """
    Represents an isolated user session with dedicated resources.

    Each session has:
    - Unique user_id and session_id
    - Dedicated IntentOrchestrator instance
    - ConversationRouter for context
    - Redis stream prefix for isolation
    """
    user_id: str
    session_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    redis_prefix: str = ""
    _orchestrator: Any = field(default=None, repr=False)
    _conversation_router: Any = field(default=None, repr=False)

    def __post_init__(self):
        """Set redis_prefix if not already set."""
        if not self.redis_prefix:
            self.redis_prefix = f"user:{self.user_id}"

    @property
    def orchestrator(self) -> Any:
        """Get the session's IntentOrchestrator (lazy initialization)."""
        if self._orchestrator is None:
            try:
                from swarm.orchestrator.intent_orchestrator import IntentOrchestrator
                self._orchestrator = IntentOrchestrator()
                # Set conversation router for this session
                if self._conversation_router:
                    self._orchestrator.conversation_router = self._conversation_router
                logger.info(f"[UserSession] Created orchestrator for user:{self.user_id}")
            except Exception as e:
                logger.error(f"[UserSession] Failed to create orchestrator: {e}")
                raise
        return self._orchestrator

    @property
    def conversation_router(self) -> Any:
        """Get the session's ConversationRouter (lazy initialization)."""
        if self._conversation_router is None:
            try:
                from memory.conversation_router import get_conversation_router
                self._conversation_router = get_conversation_router(self.user_id, self.session_id)
                logger.info(f"[UserSession] Created ConversationRouter for user:{self.user_id}")
            except Exception as e:
                logger.warning(f"[UserSession] ConversationRouter not available: {e}")
        return self._conversation_router

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()

    def age_minutes(self) -> float:
        """Get session age in minutes since last activity."""
        return (datetime.utcnow() - self.last_activity).total_seconds() / 60

    async def process_intent(self, intent_text: str, context: Optional[Any] = None) -> Any:
        """
        Process intent through this session's orchestrator.

        Args:
            intent_text: Natural language user request
            context: Optional TaskContext

        Returns:
            OrchestrationResult from the orchestrator
        """
        self.touch()

        # Ensure context has user/session info
        if context:
            from swarm.event_team import TaskContext
            if isinstance(context, TaskContext):
                context.user_id = self.user_id
                context.session_id = self.session_id

        return await self.orchestrator.process_intent(intent_text, context)


class SessionRouter:
    """
    Routes user requests to isolated session instances.

    Features:
    - Creates per-user sessions on demand
    - Provides session isolation for multi-user scenarios
    - Automatic cleanup of inactive sessions
    - Thread-safe session management
    """

    def __init__(self, session_timeout_minutes: int = 30):
        """
        Initialize SessionRouter.

        Args:
            session_timeout_minutes: Minutes of inactivity before session cleanup
        """
        self._sessions: Dict[str, UserSession] = {}
        self._lock = asyncio.Lock()
        self._timeout_minutes = session_timeout_minutes
        self._cleanup_task: Optional[asyncio.Task] = None
        logger.info(f"[SessionRouter] Initialized with {session_timeout_minutes}min timeout")

    async def get_or_create_session(
        self,
        user_id: str,
        session_id: str
    ) -> UserSession:
        """
        Get existing session or create a new one.

        Args:
            user_id: Unique user identifier
            session_id: Session identifier (can be reused across reconnects)

        Returns:
            UserSession instance for this user/session pair
        """
        key = f"{user_id}:{session_id}"

        async with self._lock:
            if key in self._sessions:
                session = self._sessions[key]
                session.touch()
                logger.debug(f"[SessionRouter] Returning existing session: {key}")
                return session

            # Create new session
            session = UserSession(
                user_id=user_id,
                session_id=session_id
            )
            # Initialize conversation router first (needed by orchestrator)
            _ = session.conversation_router
            self._sessions[key] = session

            logger.info(f"[SessionRouter] Created new session: {key}")
            return session

    async def get_session(self, user_id: str, session_id: str) -> Optional[UserSession]:
        """
        Get session without creating if it doesn't exist.

        Args:
            user_id: User identifier
            session_id: Session identifier

        Returns:
            UserSession if exists, None otherwise
        """
        key = f"{user_id}:{session_id}"
        async with self._lock:
            return self._sessions.get(key)

    async def end_session(self, user_id: str, session_id: str) -> bool:
        """
        Explicitly end a session.

        Args:
            user_id: User identifier
            session_id: Session identifier

        Returns:
            True if session was removed, False if not found
        """
        key = f"{user_id}:{session_id}"
        async with self._lock:
            if key in self._sessions:
                session = self._sessions.pop(key)
                # Cleanup conversation router
                if session._conversation_router:
                    try:
                        await session._conversation_router.clear_session()
                    except Exception as e:
                        logger.debug(f"[SessionRouter] Error clearing session router: {e}")
                logger.info(f"[SessionRouter] Ended session: {key}")
                return True
            return False

    async def cleanup_inactive(self) -> int:
        """
        Remove sessions that have been inactive too long.

        Returns:
            Number of sessions removed
        """
        now = datetime.utcnow()
        to_remove = []

        async with self._lock:
            for key, session in self._sessions.items():
                if session.age_minutes() > self._timeout_minutes:
                    to_remove.append(key)

            for key in to_remove:
                session = self._sessions.pop(key)
                logger.info(f"[SessionRouter] Cleaned up inactive session: {key}")

        return len(to_remove)

    async def start_cleanup_task(self, interval_minutes: int = 5) -> None:
        """
        Start background task for periodic cleanup.

        Args:
            interval_minutes: How often to check for inactive sessions
        """
        if self._cleanup_task is not None:
            return

        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval_minutes * 60)
                try:
                    removed = await self.cleanup_inactive()
                    if removed > 0:
                        logger.info(f"[SessionRouter] Cleanup removed {removed} inactive sessions")
                except Exception as e:
                    logger.error(f"[SessionRouter] Cleanup error: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"[SessionRouter] Started cleanup task (interval: {interval_minutes}min)")

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("[SessionRouter] Stopped cleanup task")

    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get info about all active sessions.

        Returns:
            Dict mapping session keys to session info
        """
        return {
            key: {
                "user_id": session.user_id,
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "age_minutes": round(session.age_minutes(), 1),
                "redis_prefix": session.redis_prefix
            }
            for key, session in self._sessions.items()
        }

    @property
    def session_count(self) -> int:
        """Get number of active sessions."""
        return len(self._sessions)


# Singleton instance
_session_router: Optional[SessionRouter] = None


def get_session_router() -> SessionRouter:
    """Get or create the SessionRouter singleton."""
    global _session_router
    if _session_router is None:
        _session_router = SessionRouter()
    return _session_router


def reset_session_router() -> None:
    """Reset the SessionRouter singleton (for testing)."""
    global _session_router
    _session_router = None


__all__ = [
    "SessionRouter",
    "UserSession",
    "get_session_router",
    "reset_session_router",
]
