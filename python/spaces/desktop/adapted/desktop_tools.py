"""
Adapted Desktop Tools for AutoGen Swarm

Typed wrappers around the original Dict-based desktop automation tools.
These can be used directly as FunctionTool in AssistantAgent.

Note: Desktop tools require MoireTracker v2 or MCP Handoff tools to be available.

Migrated from: swarm/tools/adapted_desktop_tools.py
"""

from typing import Optional


def execute_desktop_task(task_description: str = None) -> str:
    """
    Execute a complex desktop automation task using AI vision.

    Args:
        task_description: Natural language description of what to do

    Returns:
        Task result or error message
    """
    if not task_description:
        return "Fehler: Keine Aufgabenbeschreibung angegeben. Bitte sag mir was du tun moechtest."
    try:
        from spaces.desktop.tools.desktop_tools import execute_desktop_task as _execute
        return _execute({"task_description": task_description})
    except ImportError:
        return "Desktop tools not available. MoireTracker v2 required."


def click_element(element_description: str = None) -> str:
    """
    Click a UI element on screen.

    Args:
        element_description: Description of element to click

    Returns:
        Click result
    """
    if not element_description:
        return "Fehler: Keine Element-Beschreibung angegeben. Bitte sag mir worauf ich klicken soll."
    try:
        from spaces.desktop.tools.desktop_tools import click_element as _click
        return _click({"element_description": element_description})
    except ImportError:
        return "Desktop tools not available."


def type_text(text: str = None) -> str:
    """
    Type text at current cursor position.

    Args:
        text: Text to type

    Returns:
        Confirmation
    """
    if not text:
        return "Fehler: Kein Text angegeben. Bitte sag mir was ich tippen soll."
    try:
        from spaces.desktop.tools.desktop_tools import type_text as _type
        return _type({"text": text})
    except ImportError:
        return "Desktop tools not available."


def press_key(key: str = None) -> str:
    """
    Press a keyboard key.

    Args:
        key: Key name (e.g., 'enter', 'tab', 'escape')

    Returns:
        Confirmation
    """
    if not key:
        return "Fehler: Keine Taste angegeben. Bitte sag mir welche Taste ich druecken soll (z.B. enter, tab, escape)."
    try:
        from spaces.desktop.tools.desktop_tools import press_key as _press
        return _press({"key": key})
    except ImportError:
        return "Desktop tools not available."


def take_screenshot() -> str:
    """
    Take a screenshot of the current screen.

    Returns:
        Screenshot info or path
    """
    try:
        from spaces.desktop.tools.desktop_tools import take_screenshot as _screenshot
        import asyncio

        async def _with_timeout():
            return await asyncio.wait_for(_screenshot(), timeout=15.0)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, _with_timeout()).result(timeout=20)
        else:
            result = asyncio.run(_with_timeout())
        if isinstance(result, dict):
            return result.get("message", str(result))
        return str(result)
    except asyncio.TimeoutError:
        return "Screenshot timeout - MoireTracker nicht erreichbar."
    except ImportError:
        return "Desktop tools not available."
    except Exception as e:
        return f"Screenshot Fehler: {e}"


def scroll_screen(direction: str = "down", amount: int = 3) -> str:
    """
    Scroll the screen.

    Args:
        direction: 'up' or 'down'
        amount: Number of scroll units

    Returns:
        Confirmation
    """
    try:
        from spaces.desktop.tools.desktop_tools import scroll_screen as _scroll
        return _scroll({"direction": direction, "amount": amount})
    except ImportError:
        return "Desktop tools not available."


def open_app(app_name: str = None) -> str:
    """
    Open an application.

    Args:
        app_name: Name of app to open (chrome, word, vscode, notepad, etc.)

    Returns:
        Confirmation
    """
    if not app_name:
        return "Fehler: Kein App-Name angegeben. Bitte sag mir welche App ich oeffnen soll (z.B. chrome, word, vscode, notepad)."
    import asyncio
    try:
        from spaces.desktop.tools.quickaction_tools import open_app as _open_async

        # Run async function synchronously
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In async context - use thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _open_async(app_name))
                    result = future.result()
            else:
                result = loop.run_until_complete(_open_async(app_name))
        except RuntimeError:
            result = asyncio.run(_open_async(app_name))

        if isinstance(result, dict):
            if result.get("success"):
                return result.get("message", f"Opened {app_name}")
            else:
                return result.get("error", "Failed to open app")
        return str(result)
    except ImportError:
        return "Quick action tools not available."


def create_task_node(title: str = None, description: str = "") -> str:
    """
    Create a task widget/node.

    Args:
        title: Task title
        description: Task description

    Returns:
        Confirmation
    """
    if not title:
        return "Fehler: Kein Task-Titel angegeben. Bitte sag mir wie der Task heissen soll."
    try:
        from spaces.desktop.tools.task_tools import create_task_node as _create
        return _create({"title": title, "description": description})
    except ImportError:
        return "Task tools not available."


def update_task_status(task_name: str = None, status: str = None) -> str:
    """
    Update a task's status.

    Args:
        task_name: Name of task
        status: New status ('pending', 'in_progress', 'completed')

    Returns:
        Confirmation
    """
    if not task_name:
        return "Fehler: Kein Task-Name angegeben. Bitte sag mir welchen Task ich aktualisieren soll."
    if not status:
        return "Fehler: Kein Status angegeben. Bitte sag mir auf welchen Status ich den Task setzen soll (pending, in_progress, completed)."
    try:
        from spaces.desktop.tools.task_tools import update_task_status as _update
        return _update({"task_name": task_name, "status": status})
    except ImportError:
        return "Task tools not available."


def get_task_list() -> str:
    """
    Get list of all tasks.

    Returns:
        Formatted task list
    """
    try:
        from spaces.desktop.tools.task_tools import get_task_list as _list
        return _list({})
    except ImportError:
        return "Task tools not available."


def moire_scan() -> str:
    """
    Scan the screen using Moire OCR.

    Returns:
        Detected UI elements
    """
    try:
        from spaces.desktop.tools.moire_tools import moire_scan as _scan
        return _scan({})
    except ImportError:
        return "Moire tools not available. MoireServer required on port 8766."


def moire_find_element(element_description: str = None) -> str:
    """
    Find a UI element using Moire vision.

    Args:
        element_description: Description of element to find

    Returns:
        Element location or 'not found'
    """
    if not element_description:
        return "Fehler: Keine Element-Beschreibung angegeben. Bitte sag mir welches UI-Element ich finden soll."
    try:
        from spaces.desktop.tools.moire_tools import moire_find_element as _find
        return _find({"element_description": element_description})
    except ImportError:
        return "Moire tools not available."


# Collect all tools for export
DESKTOP_TOOLS = [
    execute_desktop_task,
    click_element,
    type_text,
    press_key,
    take_screenshot,
    scroll_screen,
    open_app,
    create_task_node,
    update_task_status,
    get_task_list,
    moire_scan,
    moire_find_element,
]


__all__ = [
    "execute_desktop_task",
    "click_element",
    "type_text",
    "press_key",
    "take_screenshot",
    "scroll_screen",
    "open_app",
    "create_task_node",
    "update_task_status",
    "get_task_list",
    "moire_scan",
    "moire_find_element",
    "DESKTOP_TOOLS",
]
