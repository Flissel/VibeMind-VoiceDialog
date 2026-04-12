"""
VibeMind Core Database Module

Re-exports from legacy data/ module for backward compatibility.
New code should import from core.database.
"""

# Re-export from the Supabase-backed data module
from data.supabase_database import (
    Database,
    get_database,
    reset_database,
    DEFAULT_DB_PATH,
)
from data.models import (
    Idea,
    Project,
    CanvasNode,
    CanvasEdge,
    ConversationSession,
    ConversationMessage,
    Shuttle,
    Task,
)
from data.repository import (
    IdeasRepository,
    ProjectsRepository,
    CanvasRepository,
    ConversationRepository,
    ShuttlesRepository,
)

__all__ = [
    # Database
    "Database",
    "get_database",
    "reset_database",
    "DEFAULT_DB_PATH",
    # Models
    "Idea",
    "Project",
    "CanvasNode",
    "CanvasEdge",
    "ConversationSession",
    "ConversationMessage",
    "Shuttle",
    "Task",
    # Repositories
    "IdeasRepository",
    "ProjectsRepository",
    "CanvasRepository",
    "ConversationRepository",
    "ShuttlesRepository",
]
