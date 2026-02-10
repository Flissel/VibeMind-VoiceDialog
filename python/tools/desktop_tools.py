"""
Desktop Tools - BACKWARD COMPATIBILITY STUB

Real implementation migrated to: spaces/desktop/tools/desktop_tools.py
This file re-exports for backward compatibility.
"""

from spaces.desktop.tools.desktop_tools import (
    execute_desktop_task,
    click_element,
    type_text,
    press_key,
    take_screenshot,
    scroll_screen,
    handle_desktop_tool_call,
    cleanup_desktop_tools,
    register_desktop_tools,
    DESKTOP_TOOLS,
)

__all__ = [
    "execute_desktop_task",
    "click_element",
    "type_text",
    "press_key",
    "take_screenshot",
    "scroll_screen",
    "handle_desktop_tool_call",
    "cleanup_desktop_tools",
    "register_desktop_tools",
    "DESKTOP_TOOLS",
]
