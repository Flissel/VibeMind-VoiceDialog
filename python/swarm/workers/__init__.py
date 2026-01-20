"""
Worker Agents for VibeMind Event Buffer System

Workers handle autonomous task execution:
- Queue-based processing
- Progress event publishing
- Interrupt handling

Available workers:
- Ideas: BubbleWorker, IdeaWorker, ScoreWorker
- Coding: GenerateWorker, PreviewWorker, FileWorker
- Desktop: ClickWorker, TypeWorker, AppWorker
"""

from swarm.workers.base_worker import (
    BaseWorker,
    WorkerConfig,
    WorkerProgress,
    WorkerState,
    create_worker_pool,
)
from swarm.workers.ideas_workers import (
    BubbleWorker,
    IdeaWorker,
    ScoreWorker,
    create_ideas_workers,
)
from swarm.workers.coding_workers import (
    GenerateWorker,
    PreviewWorker,
    FileWorker,
    create_coding_workers,
)
from swarm.workers.desktop_workers import (
    ClickWorker,
    TypeWorker,
    AppWorker,
    create_desktop_workers,
)

__all__ = [
    # Base
    "BaseWorker",
    "WorkerConfig",
    "WorkerProgress",
    "WorkerState",
    "create_worker_pool",
    # Ideas
    "BubbleWorker",
    "IdeaWorker",
    "ScoreWorker",
    "create_ideas_workers",
    # Coding
    "GenerateWorker",
    "PreviewWorker",
    "FileWorker",
    "create_coding_workers",
    # Desktop
    "ClickWorker",
    "TypeWorker",
    "AppWorker",
    "create_desktop_workers",
]
