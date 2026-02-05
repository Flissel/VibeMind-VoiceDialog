"""
VibeMind Core Memory Module

Memory services (Supermemory integration) for task tracking,
conversation memory, and user profiles.
Re-exports from legacy memory/ module for backward compatibility.
"""

# Re-export from legacy memory module
from memory.task_memory_service import (
    TaskMemoryService,
    get_task_memory_service,
)
from memory.conversation_memory_service import (
    ConversationMemoryService,
    get_conversation_memory_service,
)
from memory.user_profile_service import (
    UserProfileService,
    get_user_profile_service,
)
from memory.conversation_router import (
    ConversationRouter,
    get_conversation_router,
)

__all__ = [
    # Task Memory
    "TaskMemoryService",
    "get_task_memory_service",
    # Conversation Memory
    "ConversationMemoryService",
    "get_conversation_memory_service",
    # User Profile
    "UserProfileService",
    "get_user_profile_service",
    # Conversation Router
    "ConversationRouter",
    "get_conversation_router",
]
