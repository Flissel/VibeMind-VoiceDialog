"""
VibeMind Desktop Space Tools

Tools for desktop automation and system control.
Re-exports from legacy tools/ module.
"""

# Re-export from legacy tools module
from tools.desktop_tools import (
    execute_desktop_task,
    click_element,
    type_text,
    press_key,
    take_screenshot,
    scroll_screen,
    handle_desktop_tool_call,
)

__all__ = [
    "execute_desktop_task",
    "click_element",
    "type_text",
    "press_key",
    "take_screenshot",
    "scroll_screen",
    "handle_desktop_tool_call",
]
