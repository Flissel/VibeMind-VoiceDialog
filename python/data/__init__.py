"""
Vibemind Data Layer

Persistence via Supabase (PostgreSQL + PostgREST + Realtime).
All repositories use the SupabaseDatabase adapter — SQLite is gone.
"""

from .supabase_database import Database, get_database
from .models import (
    Idea, Project, CanvasNode, CanvasEdge, ConversationMessage,
    ConversationSession, Shuttle, ShuttleStatus, ShuttleStage,
    STAGE_PROGRESS, GenerationStatus, Task, TaskStatus,
    ScheduledTask, ScheduleStatus, TriggerType, ExecutionMode,
    FlowzenCheckin, FlowzenActivity, FlowzenDiaryEntry,
)
from .repository import (
    IdeasRepository,
    ProjectsRepository,
    CanvasRepository,
    ConversationRepository,
    ShuttlesRepository,
    ScheduledTaskRepository,
    FlowzenRepository,
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
    "ScheduledTask",
    "ScheduleStatus",
    "TriggerType",
    "ExecutionMode",
    "IdeasRepository",
    "ProjectsRepository",
    "CanvasRepository",
    "ConversationRepository",
    "ShuttlesRepository",
    "ScheduledTaskRepository",
    "FlowzenCheckin",
    "FlowzenActivity",
    "FlowzenDiaryEntry",
    "FlowzenRepository",
    "TaskMemoryRepository",
    "get_task_memory_repository",
    "promote_idea_to_project",
    "IntentRule",
    "IntentRuleRepository",
    "get_intent_rule_repository",
    "INITIAL_INTENT_RULES",
]
