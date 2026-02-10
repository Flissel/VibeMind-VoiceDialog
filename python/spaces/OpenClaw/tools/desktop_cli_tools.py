"""
Desktop CLI Tools - Wrappers for desktop automation

Re-exports and wraps the existing adapted_desktop_tools for use
in the AutoGen Society of Mind Desktop Swarm.

These tools execute actual desktop actions via MoireTracker v2.
"""

import logging
import sys
from pathlib import Path
from typing import List, Callable

logger = logging.getLogger(__name__)

# Add python/ root to path for imports
_PYTHON_ROOT = Path(__file__).parent.parent.parent.parent
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))


def _load_desktop_tools() -> List[Callable]:
    """
    Load desktop tools from adapted_desktop_tools.

    Returns list of tool functions for use in AutoGen agents.
    """
    tools = []

    try:
        from swarm.tools.adapted_desktop_tools import (
            execute_desktop_task,
            click_element,
            type_text,
            press_key,
            take_screenshot,
            scroll_screen,
            open_app,
            moire_scan,
            moire_find_element,
        )

        tools = [
            execute_desktop_task,
            click_element,
            type_text,
            press_key,
            take_screenshot,
            scroll_screen,
            open_app,
            moire_scan,
            moire_find_element,
        ]
        logger.info(f"[desktop_cli_tools] Loaded {len(tools)} tools from adapted_desktop_tools")

    except ImportError as e:
        logger.warning(f"[desktop_cli_tools] Could not load adapted_desktop_tools: {e}")

        # Try loading from tools/ directly as fallback
        try:
            from tools.quickaction_tools import open_app
            from tools.moire_tools import moire_scan, moire_find_element

            tools = [open_app, moire_scan, moire_find_element]
            logger.info(f"[desktop_cli_tools] Loaded {len(tools)} tools from fallback")

        except ImportError as e2:
            logger.error(f"[desktop_cli_tools] Fallback also failed: {e2}")

    return tools


# Export individual tools for direct import
try:
    from swarm.tools.adapted_desktop_tools import (
        execute_desktop_task,
        click_element,
        type_text,
        press_key,
        take_screenshot,
        scroll_screen,
        open_app,
        moire_scan,
        moire_find_element,
        create_task_node,
        update_task_status,
        get_task_list,
    )

    # Full list of desktop worker tools
    DESKTOP_WORKER_TOOLS = [
        execute_desktop_task,
        click_element,
        type_text,
        press_key,
        take_screenshot,
        scroll_screen,
        open_app,
        moire_scan,
        moire_find_element,
    ]

    # Task management tools (optional)
    TASK_MANAGEMENT_TOOLS = [
        create_task_node,
        update_task_status,
        get_task_list,
    ]

    # All tools combined
    ALL_DESKTOP_TOOLS = DESKTOP_WORKER_TOOLS + TASK_MANAGEMENT_TOOLS

except ImportError as e:
    logger.warning(f"[desktop_cli_tools] Import failed: {e}")

    # Empty fallback
    DESKTOP_WORKER_TOOLS = []
    TASK_MANAGEMENT_TOOLS = []
    ALL_DESKTOP_TOOLS = []

    # Define placeholder functions
    def execute_desktop_task(task_description: str = "") -> str:
        return "Fehler: Desktop-Tools nicht verfuegbar"

    def click_element(element_description: str = "") -> str:
        return "Fehler: Desktop-Tools nicht verfuegbar"

    def type_text(text: str = "") -> str:
        return "Fehler: Desktop-Tools nicht verfuegbar"

    def press_key(key: str = "") -> str:
        return "Fehler: Desktop-Tools nicht verfuegbar"

    def take_screenshot() -> str:
        return "Fehler: Desktop-Tools nicht verfuegbar"

    def scroll_screen(direction: str = "down", amount: int = 3) -> str:
        return "Fehler: Desktop-Tools nicht verfuegbar"

    def open_app(app_name: str = "") -> str:
        return "Fehler: Desktop-Tools nicht verfuegbar"

    def moire_scan() -> str:
        return "Fehler: Desktop-Tools nicht verfuegbar"

    def moire_find_element(element_description: str = "") -> str:
        return "Fehler: Desktop-Tools nicht verfuegbar"


__all__ = [
    # Individual tools
    "execute_desktop_task",
    "click_element",
    "type_text",
    "press_key",
    "take_screenshot",
    "scroll_screen",
    "open_app",
    "moire_scan",
    "moire_find_element",
    # Tool lists
    "DESKTOP_WORKER_TOOLS",
    "TASK_MANAGEMENT_TOOLS",
    "ALL_DESKTOP_TOOLS",
]
