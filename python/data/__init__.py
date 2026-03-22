"""
Vibemind Data Layer

SQLite persistence for Ideas, Projects, Canvas nodes, Conversation history,
Shuttles, Tasks, and Scheduled Tasks.
"""

from .database import Database, get_database
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
    MermaidDiagramsRepository,
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
    "MermaidDiagramsRepository",
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
