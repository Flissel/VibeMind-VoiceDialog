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

# All domain workers loaded lazily to avoid circular import
# (spaces.*.workers imports swarm.workers.base_worker which triggers this __init__)

_LAZY_IMPORTS = {
    # Ideas workers
    "BubbleWorker": ("spaces.ideas.workers.ideas_workers", "BubbleWorker"),
    "IdeaWorker": ("spaces.ideas.workers.ideas_workers", "IdeaWorker"),
    "ScoreWorker": ("spaces.ideas.workers.ideas_workers", "ScoreWorker"),
    "create_ideas_workers": ("spaces.ideas.workers.ideas_workers", "create_ideas_workers"),
    # Coding workers
    "GenerateWorker": ("spaces.coding.workers.coding_workers", "GenerateWorker"),
    "PreviewWorker": ("spaces.coding.workers.coding_workers", "PreviewWorker"),
    "FileWorker": ("spaces.coding.workers.coding_workers", "FileWorker"),
    "create_coding_workers": ("spaces.coding.workers.coding_workers", "create_coding_workers"),
    # Desktop workers
    "ClickWorker": ("spaces.desktop.workers.desktop_workers", "ClickWorker"),
    "TypeWorker": ("spaces.desktop.workers.desktop_workers", "TypeWorker"),
    "AppWorker": ("spaces.desktop.workers.desktop_workers", "AppWorker"),
    "create_desktop_workers": ("spaces.desktop.workers.desktop_workers", "create_desktop_workers"),
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Base
    "BaseWorker",
    "WorkerConfig",
    "WorkerProgress",
    "WorkerState",
    "create_worker_pool",
    # Ideas (lazy)
    "BubbleWorker",
    "IdeaWorker",
    "ScoreWorker",
    "create_ideas_workers",
    # Coding (lazy)
    "GenerateWorker",
    "PreviewWorker",
    "FileWorker",
    "create_coding_workers",
    # Desktop (lazy)
    "ClickWorker",
    "TypeWorker",
    "AppWorker",
    "create_desktop_workers",
]
