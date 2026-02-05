"""
Vibemind Data Layer

SQLite persistence for Ideas, Projects, Canvas nodes, Conversation history, Shuttles, and Tasks.
"""

from .database import Database, get_database
from .models import (
    Idea, Project, CanvasNode, CanvasEdge, ConversationMessage,
    ConversationSession, Shuttle, ShuttleStatus, ShuttleStage,
    STAGE_PROGRESS, GenerationStatus, Task, TaskStatus
)
from .repository import (
    IdeasRepository,
    ProjectsRepository,
    CanvasRepository,
    ConversationRepository,
    ShuttlesRepository,
    promote_idea_to_project,
)
from .task_memory_repository import TaskMemoryRepository, get_task_memory_repository
from .intent_rule_repository import (
    IntentRule,
    IntentRuleRepository,
    get_intent_rule_repository,
    INITIAL_INTENT_RULES,
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
    "Task",
    "TaskStatus",
    "IdeasRepository",
    "ProjectsRepository",
    "CanvasRepository",
    "ConversationRepository",
    "ShuttlesRepository",
    "TaskMemoryRepository",
    "get_task_memory_repository",
    "promote_idea_to_project",
    "IntentRule",
    "IntentRuleRepository",
    "get_intent_rule_repository",
    "INITIAL_INTENT_RULES",
]
