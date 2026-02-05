"""
Context providers for VibeMind swarm.

Provides contextual information about the current state
(current bubble, ideas, etc.) for use in intent classification
and response generation.
"""

from .bubble_context_provider import (
    BubbleContextProvider,
    get_bubble_context_provider,
)

from .real_time_state import (
    SystemState,
    RealTimeStateStore,
    get_real_time_state,
    reset_real_time_state,
)

from .session_context import (
    SessionContext,
    get_session_context,
    set_session_context,
    clear_session_context,
    update_session_context,
    resolve_context_reference,
)

__all__ = [
    # Bubble context
    "BubbleContextProvider",
    "get_bubble_context_provider",
    # Real-time state
    "SystemState",
    "RealTimeStateStore",
    "get_real_time_state",
    "reset_real_time_state",
    # Session context (system-wide)
    "SessionContext",
    "get_session_context",
    "set_session_context",
    "clear_session_context",
    "update_session_context",
    "resolve_context_reference",
]
