"""
Session Context Service - System-wide context availability.

Provides access to session information from anywhere in the codebase
using Python's contextvars (thread-safe, async-safe).

Usage in tools:
    from swarm.context.session_context import get_session_context

    ctx = get_session_context()
    if ctx.conversation_history:
        # Use conversation history for contextual resolution
        pass
"""

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# Session Context Data
# ============================================================================

@dataclass
class SessionContext:
    """
    Current session context available system-wide.

    Set by IntentOrchestrator at the start of each request.
    Accessible by any tool via get_session_context().
    """
    session_id: str = ""
    user_id: str = "default"

    # Current location
    current_bubble_id: Optional[str] = None
    current_bubble_title: Optional[str] = None

    # Conversation history (last N messages)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)

    # Current user input
    user_input: str = ""

    # Timestamp
    started_at: float = field(default_factory=lambda: datetime.now().timestamp())

    # Recently mentioned items (for "das", "die", "alle" resolution)
    recent_bubbles: List[str] = field(default_factory=list)
    recent_ideas: List[str] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_last_assistant_message(self) -> Optional[str]:
        """Get the most recent assistant/agent message."""
        for msg in reversed(self.conversation_history):
            if msg.get("speaker") in ["rachel", "assistant", "agent"]:
                return msg.get("text", "")
        return None

    def get_mentioned_items(self, item_type: str = "bubble") -> List[str]:
        """
        Extract mentioned items from conversation history.

        Args:
            item_type: "bubble" or "idea"

        Returns:
            List of mentioned item names
        """
        import re
        items = []

        for msg in reversed(self.conversation_history):
            if msg.get("speaker") in ["rachel", "assistant", "agent"]:
                text = msg.get("text", "")

                # Look for list patterns
                # "Du hast: Marketing, Sales, Ideas"
                # "- Marketing\n- Sales"
                list_match = re.findall(
                    r'(?:^|\n)\s*[-•●\d.)\]]\s*([A-Za-zäöüÄÖÜß][A-Za-zäöüÄÖÜß0-9\s-]+?)(?:\s*[-–:(\n]|$)',
                    text
                )
                if list_match:
                    items.extend([i.strip() for i in list_match if i.strip()])
                    break

                # "Marketing, Sales und Ideas"
                comma_pattern = r'([A-Za-zäöüÄÖÜß][A-Za-zäöüÄÖÜß0-9-]+(?:\s*,\s*[A-Za-zäöüÄÖÜß][A-Za-zäöüÄÖÜß0-9-]+)+(?:\s+und\s+[A-Za-zäöüÄÖÜß][A-Za-zäöüÄÖÜß0-9-]+)?)'
                comma_match = re.search(comma_pattern, text)
                if comma_match:
                    parts = re.split(r'\s*,\s*|\s+und\s+', comma_match.group(1))
                    items.extend([i.strip() for i in parts if i.strip()])
                    break

        return items

    def has_context_reference(self, text: str) -> bool:
        """Check if text contains contextual references like 'alle', 'die', 'das'."""
        keywords = ["alle", "die", "das", "sie", "es", "diese", "jene", "davon", "nochmal"]
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)


# ============================================================================
# Context Variable (Thread-safe, Async-safe)
# ============================================================================

_session_context: ContextVar[Optional[SessionContext]] = ContextVar(
    'session_context',
    default=None
)


def get_session_context() -> SessionContext:
    """
    Get the current session context.

    Returns a default empty context if none is set.
    """
    logger.debug("get_session_context called")
    ctx = _session_context.get()
    if ctx is None:
        ctx = SessionContext()
    return ctx


def set_session_context(
    session_id: str = "",
    user_id: str = "default",
    user_input: str = "",
    conversation_history: List[Dict[str, Any]] = None,
    current_bubble_id: str = None,
    current_bubble_title: str = None,
    **kwargs
) -> SessionContext:
    """
    Set the session context for the current execution.

    Called by IntentOrchestrator at the start of each request.

    Args:
        session_id: Current session ID
        user_id: Current user ID
        user_input: Current user input text
        conversation_history: Recent conversation messages
        current_bubble_id: Current bubble/space ID
        current_bubble_title: Current bubble/space title
        **kwargs: Additional metadata

    Returns:
        The created SessionContext
    """
    logger.debug("set_session_context: session_id=%s user_id=%s", session_id, user_id)
    ctx = SessionContext(
        session_id=session_id,
        user_id=user_id,
        user_input=user_input,
        conversation_history=conversation_history or [],
        current_bubble_id=current_bubble_id,
        current_bubble_title=current_bubble_title,
        metadata=kwargs,
    )

    # Extract recently mentioned items from history
    if ctx.conversation_history:
        ctx.recent_bubbles = ctx.get_mentioned_items("bubble")
        ctx.recent_ideas = ctx.get_mentioned_items("idea")

    _session_context.set(ctx)
    logger.debug(f"[SessionContext] Set for session={session_id}, user={user_id}")

    return ctx


def clear_session_context():
    """Clear the current session context."""
    _session_context.set(None)


def update_session_context(**kwargs):
    """Update fields in the current session context."""
    logger.debug("update_session_context: keys=%s", list(kwargs.keys()))
    ctx = get_session_context()
    for key, value in kwargs.items():
        if hasattr(ctx, key):
            setattr(ctx, key, value)
    _session_context.set(ctx)
    return ctx


# ============================================================================
# Helper Functions
# ============================================================================

def resolve_context_reference(text: str, target_type: str = "bubble") -> Optional[List[str]]:
    """
    Resolve contextual references like "alle", "die" to actual items.

    Args:
        text: User input containing reference
        target_type: "bubble" or "idea"

    Returns:
        List of resolved item names, or None if no resolution
    """
    logger.debug("resolve_context_reference: target_type=%s", target_type)
    ctx = get_session_context()

    if not ctx.has_context_reference(text):
        return None

    text_lower = text.lower()

    # "alle" = all recently mentioned items
    if "alle" in text_lower:
        if target_type == "bubble":
            return ctx.recent_bubbles if ctx.recent_bubbles else None
        else:
            return ctx.recent_ideas if ctx.recent_ideas else None

    # "die", "das", "es" = most recently mentioned single item
    if any(kw in text_lower for kw in ["die", "das", "es"]):
        if target_type == "bubble" and ctx.recent_bubbles:
            return [ctx.recent_bubbles[0]]
        elif target_type == "idea" and ctx.recent_ideas:
            return [ctx.recent_ideas[0]]

    return None


__all__ = [
    "SessionContext",
    "get_session_context",
    "set_session_context",
    "clear_session_context",
    "update_session_context",
    "resolve_context_reference",
]
