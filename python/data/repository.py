"""
Vibemind Repository Layer — Backwards-compatible re-export shim.

Individual repositories have been split into separate files:
  - ideas_repository.py
  - projects_repository.py
  - canvas_repository.py
  - conversation_repository.py
  - shuttles_repository.py
  - mermaid_repository.py
  - schedule_repository.py

This file re-exports all classes for backwards compatibility.
Import paths like `from data.repository import IdeasRepository` still work.
"""

from .repository_utils import generate_id, normalize_text, _levenshtein
from .ideas_repository import IdeasRepository, promote_idea_to_project
from .projects_repository import ProjectsRepository
from .canvas_repository import CanvasRepository
from .conversation_repository import ConversationRepository
from .shuttles_repository import ShuttlesRepository
from .mermaid_repository import MermaidDiagramsRepository
from .schedule_repository import ScheduledTaskRepository
from .flowzen_repository import FlowzenRepository
from .video_repository import VideoRepository
from .video_project_repository import VideoProjectRepository

__all__ = [
    "generate_id",
    "normalize_text",
    "_levenshtein",
    "IdeasRepository",
    "ProjectsRepository",
    "CanvasRepository",
    "ConversationRepository",
    "ShuttlesRepository",
    "MermaidDiagramsRepository",
    "ScheduledTaskRepository",
    "FlowzenRepository",
    "VideoRepository",
    "VideoProjectRepository",
    "promote_idea_to_project",
]
