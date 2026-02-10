"""
Task Tools - BACKWARD COMPATIBILITY STUB

Real implementation migrated to: spaces/desktop/tools/task_tools.py
This file re-exports for backward compatibility.
"""

from spaces.desktop.tools.task_tools import (
    create_task_node,
    update_task_status,
    get_task_list,
    mark_task_complete,
    watch_task_progress,
    TASK_TOOLS,
    register_task_tools,
    set_electron_sender,
    TaskStatus,
    DesktopTask,
)

__all__ = [
    "create_task_node",
    "update_task_status",
    "get_task_list",
    "mark_task_complete",
    "watch_task_progress",
    "TASK_TOOLS",
    "register_task_tools",
    "set_electron_sender",
    "TaskStatus",
    "DesktopTask",
]
