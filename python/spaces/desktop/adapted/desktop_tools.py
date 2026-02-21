"""
Adapted Desktop Tools for AutoGen Swarm

Typed wrappers that route desktop automation through the Automation_ui
FastAPI backend (localhost:8007). Simple actions (type, key, scroll) use
direct REST endpoints; vision-based actions (click_element, execute_task,
moire_scan) use the agentic LLM intent endpoint.

These can be used directly as FunctionTool in AssistantAgent.
"""

import logging

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Vision / Agentic tools (via /api/llm/intent — no local fallback)
# ------------------------------------------------------------------


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

    from spaces.desktop.automation_ui_client import get_automation_client

    client = get_automation_client()
    if not client.is_available():
        return "Desktop-Automation nicht verfuegbar. Automation_ui Backend laeuft nicht auf Port 8007."

    try:
        result = client.llm_intent(task_description)
        if result.get("success"):
            return result.get("summary", "Aufgabe ausgefuehrt.")
        else:
            return f"Aufgabe fehlgeschlagen: {result.get('error', result.get('summary', 'Unbekannter Fehler'))}"
    except Exception as e:
        logger.error("execute_desktop_task error: %s", e)
        return f"Desktop-Automation Fehler: {e}"


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

    from spaces.desktop.automation_ui_client import get_automation_client

    client = get_automation_client()
    if not client.is_available():
        return "Desktop-Automation nicht verfuegbar. Automation_ui Backend laeuft nicht auf Port 8007."

    try:
        result = client.llm_intent(f"Klicke auf: {element_description}")
        if result.get("success"):
            return result.get("summary", f"Klick auf '{element_description}' ausgefuehrt.")
        else:
            return f"Klick fehlgeschlagen: {result.get('error', result.get('summary', 'Unbekannter Fehler'))}"
    except Exception as e:
        logger.error("click_element error: %s", e)
        return f"Desktop-Automation Fehler: {e}"


def take_screenshot() -> str:
    """
    Take a screenshot and describe the current screen.

    Returns:
        Screen description or error message
    """
    from spaces.desktop.automation_ui_client import get_automation_client

    client = get_automation_client()
    if not client.is_available():
        return "Desktop-Automation nicht verfuegbar. Automation_ui Backend laeuft nicht auf Port 8007."

    try:
        result = client.llm_intent("Beschreibe was aktuell auf dem Bildschirm zu sehen ist.")
        if result.get("success"):
            return result.get("summary", "Screenshot analysiert.")
        else:
            return f"Screenshot fehlgeschlagen: {result.get('error', 'Unbekannter Fehler')}"
    except Exception as e:
        logger.error("take_screenshot error: %s", e)
        return f"Screenshot Fehler: {e}"


def moire_scan() -> str:
    """
    Scan the screen using OCR to detect text and UI elements.

    Returns:
        Detected UI elements and text
    """
    from spaces.desktop.automation_ui_client import get_automation_client

    client = get_automation_client()
    if not client.is_available():
        return "Desktop-Automation nicht verfuegbar. Automation_ui Backend laeuft nicht auf Port 8007."

    try:
        result = client.llm_intent("Lies den gesamten Bildschirminhalt mit OCR und liste alle sichtbaren UI-Elemente auf.")
        if result.get("success"):
            return result.get("summary", "Bildschirm gescannt.")
        else:
            return f"Scan fehlgeschlagen: {result.get('error', 'Unbekannter Fehler')}"
    except Exception as e:
        logger.error("moire_scan error: %s", e)
        return f"Scan Fehler: {e}"


def moire_find_element(element_description: str = None) -> str:
    """
    Find a UI element using AI vision.

    Args:
        element_description: Description of element to find

    Returns:
        Element location or 'not found'
    """
    if not element_description:
        return "Fehler: Keine Element-Beschreibung angegeben. Bitte sag mir welches UI-Element ich finden soll."

    from spaces.desktop.automation_ui_client import get_automation_client

    client = get_automation_client()
    if not client.is_available():
        return "Desktop-Automation nicht verfuegbar. Automation_ui Backend laeuft nicht auf Port 8007."

    try:
        result = client.llm_intent(f"Finde das UI-Element: {element_description}")
        if result.get("success"):
            return result.get("summary", f"Element '{element_description}' gefunden.")
        else:
            return f"Element nicht gefunden: {result.get('error', result.get('summary', 'Unbekannter Fehler'))}"
    except Exception as e:
        logger.error("moire_find_element error: %s", e)
        return f"Element-Suche Fehler: {e}"


# ------------------------------------------------------------------
# Direct automation tools (with local pyautogui fallback)
# ------------------------------------------------------------------


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

    from spaces.desktop.automation_ui_client import get_automation_client

    client = get_automation_client()
    if client.is_available():
        try:
            result = client.type_text(text)
            if result.get("success"):
                preview = text[:50] + "..." if len(text) > 50 else text
                return f"Text eingegeben: '{preview}'"
        except Exception as e:
            logger.warning("Automation_ui type_text failed, trying local: %s", e)

    # Fallback: local pyautogui
    try:
        import pyautogui
        pyautogui.write(text, interval=0.02)
        preview = text[:50] + "..." if len(text) > 50 else text
        return f"Text eingegeben (lokal): '{preview}'"
    except ImportError:
        return "Desktop-Automation nicht verfuegbar. Weder Automation_ui noch pyautogui vorhanden."
    except Exception as e:
        return f"Texteingabe Fehler: {e}"


def press_key(key: str = None) -> str:
    """
    Press a keyboard key.

    Args:
        key: Key name (e.g., 'enter', 'tab', 'escape', 'ctrl+s')

    Returns:
        Confirmation
    """
    if not key:
        return "Fehler: Keine Taste angegeben. Bitte sag mir welche Taste ich druecken soll (z.B. enter, tab, escape)."

    from spaces.desktop.automation_ui_client import get_automation_client

    client = get_automation_client()
    if client.is_available():
        try:
            result = client.press_key(key)
            if result.get("success"):
                return f"Taste gedrueckt: {key}"
        except Exception as e:
            logger.warning("Automation_ui press_key failed, trying local: %s", e)

    # Fallback: local pyautogui
    try:
        import pyautogui
        if "+" in key:
            keys = [k.strip() for k in key.split("+")]
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(key)
        return f"Taste gedrueckt (lokal): {key}"
    except ImportError:
        return "Desktop-Automation nicht verfuegbar. Weder Automation_ui noch pyautogui vorhanden."
    except Exception as e:
        return f"Tastendruck Fehler: {e}"


def scroll_screen(direction: str = "down", amount: int = 3) -> str:
    """
    Scroll the screen.

    Args:
        direction: 'up' or 'down'
        amount: Number of scroll units

    Returns:
        Confirmation
    """
    from spaces.desktop.automation_ui_client import get_automation_client

    client = get_automation_client()
    if client.is_available():
        try:
            result = client.scroll(direction, amount)
            if result.get("success"):
                return f"Gescrollt: {amount}x {direction}"
        except Exception as e:
            logger.warning("Automation_ui scroll failed, trying local: %s", e)

    # Fallback: local pyautogui
    try:
        import pyautogui
        scroll_amount = amount if direction == "up" else -amount
        pyautogui.scroll(scroll_amount)
        return f"Gescrollt (lokal): {amount}x {direction}"
    except ImportError:
        return "Desktop-Automation nicht verfuegbar. Weder Automation_ui noch pyautogui vorhanden."
    except Exception as e:
        return f"Scroll Fehler: {e}"


# ------------------------------------------------------------------
# Local-only tools (no Automation_ui needed)
# ------------------------------------------------------------------


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

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
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


# ------------------------------------------------------------------
# Tool registry (consumed by AutoGen AssistantAgent)
# ------------------------------------------------------------------

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
