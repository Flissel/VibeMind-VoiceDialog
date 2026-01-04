"""
Vibemind Data Layer

SQLite persistence for Ideas, Projects, Canvas nodes, Conversation history, and Shuttles.
"""

from .database import Database, get_database
from .models import Idea, Project, CanvasNode, CanvasEdge, ConversationMessage, ConversationSession, Shuttle, ShuttleStatus, ShuttleStage, STAGE_PROGRESS, GenerationStatus
from .repository import (
    IdeasRepository,
    ProjectsRepository,
    CanvasRepository,
    ConversationRepository,
    ShuttlesRepository,
    promote_idea_to_project,
)

__all__ = [
    "Database",
    "get_database",
    "Idea",
    "Project",
    "CanvasNode",
    "CanvasEdge",
    "ConversationMessage",
    "ConversationSession",
    "Shuttle",
    "ShuttleStatus",
    "ShuttleStage",
    "STAGE_PROGRESS",
    "GenerationStatus",
    "IdeasRepository",
    "ProjectsRepository",
    "CanvasRepository",
    "ConversationRepository",
    "ShuttlesRepository",
    "promote_idea_to_project",
]
