"""
Memory Module - Supermemory integration for VibeMind

Provides persistent memory capabilities via Supermemory API:
- TaskMemoryService: Track task execution history
- ConversationMemoryService: Store conversation context (v4 API)
- UserProfileService: Learn user preferences and habits
- ConversationRouter: Route intents using past conversation context
- SupermemoryClient: Legacy client for backward compatibility
"""

from .supermemory_client import SupermemoryClient

# Task Memory Service
from .task_memory_service import (
    TaskMemoryService,
    TaskEvent,
    get_task_memory_service,
    reset_task_memory_service,
)

# Conversation Memory Service
from .conversation_memory_service import (
    ConversationMemoryService,
    get_conversation_memory_service,
    reset_conversation_memory_service,
)

# User Profile Service
from .user_profile_service import (
    UserProfileService,
    UserProfile,
    get_user_profile_service,
    reset_user_profile_service,
)

# Conversation Router (for intent routing with past context)
from .conversation_router import (
    ConversationRouter,
    PastIntent,
    get_conversation_router,
    reset_conversation_routers,
)

__all__ = [
    # Legacy
    "SupermemoryClient",
    # Task Memory
    "TaskMemoryService",
    "TaskEvent",
    "get_task_memory_service",
    "reset_task_memory_service",
    # Conversation Memory
    "ConversationMemoryService",
    "get_conversation_memory_service",
    "reset_conversation_memory_service",
    # User Profiles
    "UserProfileService",
    "UserProfile",
    "get_user_profile_service",
    "reset_user_profile_service",
    # Conversation Router
    "ConversationRouter",
    "PastIntent",
    "get_conversation_router",
    "reset_conversation_routers",
]
