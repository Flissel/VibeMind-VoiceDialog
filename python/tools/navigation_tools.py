"""
VibeMind Navigation Tools

Client tools for voice-controlled UI navigation.
These tools enable agents to navigate the multiverse, select items,
and enter/exit views without keyboard interaction.

Tool Categories:
- Space Navigation: navigate_to_space
- Item Selection: select_item, select_by_name
- View Control: enter_selection, exit_view

Usage:
    User says: "Go to the Projects Space"
    Multiverse calls: navigate_to_space(space="projects")
    
    User says: "Select the next bubble"
    Multiverse calls: select_item(direction="next")
    
    User says: "Enter this bubble"
    Multiverse calls: enter_selection()
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional, Callable

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Global reference to Electron IPC sender (set by electron_backend.py)
_electron_send_message: Optional[Callable[[dict], None]] = None

# Global state tracking
_current_space: str = "ideas"
_selected_index: int = -1


def set_electron_sender(sender: Callable[[dict], None]):
    """Set the Electron IPC message sender callback."""
    global _electron_send_message
    _electron_send_message = sender


def _broadcast_to_electron(message: dict):
    """Send a message to Electron if connected."""
    if _electron_send_message:
        _electron_send_message(message)


def _update_current_space(space: str):
    """Update the tracked current space."""
    global _current_space
    _current_space = space


def _update_selected_index(index: int):
    """Update the tracked selected index."""
    global _selected_index
    _selected_index = index


# ==============================================================================
# SPACE NAVIGATION TOOLS
# ==============================================================================

def navigate_to_space(params: Dict[str, Any]) -> str:
    """
    Navigate to a specific space in the multiverse.

    Called when user says things like:
    - "Go to the Ideas Space"
    - "Show me the Projects"
    - "Take me to Desktop"
    - "Navigate to ideas"

    Args (via params):
        space: Target space - 'ideas', 'projects', or 'desktop' (required)

    Returns:
        Confirmation message
    """
    space = params.get("space", "").lower().strip()
    
    # Normalize aliases
    space_aliases = {
        "idea": "ideas",
        "bubble": "ideas",
        "bubbles": "ideas",
        "rachel": "ideas",
        "project": "projects",
        "dna": "projects",
        "helix": "projects",
        "sofia": "projects",
        "adam": "desktop",
        "light planet": "desktop",
        "automation": "desktop",
    }
    
    space = space_aliases.get(space, space)
    
    valid_spaces = ["ideas", "projects", "desktop"]
    if space not in valid_spaces:
        return f"Unknown space '{space}'. Available spaces are: Ideas, Projects, Desktop."
    
    # Send navigation command to Electron
    _broadcast_to_electron({
        "type": "navigate_space",
        "space": space,
    })
    
    _update_current_space(space)
    
    space_names = {
        "ideas": "Ideas Universe",
        "projects": "Projects Space", 
        "desktop": "Desktop Automation",
    }
    
    return f"Navigating to {space_names[space]}."


# ==============================================================================
# ITEM SELECTION TOOLS
# ==============================================================================

def select_item(params: Dict[str, Any]) -> str:
    """
    Select the next or previous item in the current space.

    Called when user says things like:
    - "Select the next bubble"
    - "Previous project"
    - "Next one"
    - "Go to the previous"

    Args (via params):
        direction: 'next' or 'previous' (default: 'next')
        space_type: 'bubble' or 'project' (auto-detected if not provided)

    Returns:
        Confirmation of selection
    """
    direction = params.get("direction", "next").lower()
    space_type = params.get("space_type", "").lower()
    
    # Determine direction value
    dir_value = 1 if direction in ["next", "forward", "down"] else -1
    
    # Auto-detect space type from current space
    if not space_type:
        space_type = "project" if _current_space == "projects" else "bubble"
    
    # Send selection command to Electron
    _broadcast_to_electron({
        "type": "select_item",
        "direction": dir_value,
        "item_type": space_type,
    })
    
    direction_text = "next" if dir_value > 0 else "previous"
    item_text = "project" if space_type == "project" else "bubble"
    
    return f"Selecting {direction_text} {item_text}."


def select_by_name(params: Dict[str, Any]) -> str:
    """
    Select an item by name or index.

    Called when user says things like:
    - "Select the Todo App bubble"
    - "Focus on Research Hub"
    - "Select project number 2"
    - "Go to Universe Alpha"

    Args (via params):
        name: Name of the item to select (partial match supported)
        index: Numeric index (1-based) as alternative

    Returns:
        Confirmation or not found message
    """
    name = params.get("name", "").strip()
    index = params.get("index")
    
    if not name and index is None:
        return "What should I select? Give me a name or number."
    
    # Send selection command to Electron
    if name:
        _broadcast_to_electron({
            "type": "select_by_name",
            "name": name,
        })
        return f"Looking for '{name}'..."
    else:
        # Convert to 0-based index
        idx = int(index) - 1 if index else 0
        _broadcast_to_electron({
            "type": "select_by_index",
            "index": idx,
        })
        return f"Selecting item {index}."


# ==============================================================================
# VIEW CONTROL TOOLS
# ==============================================================================

def enter_selection(params: Dict[str, Any]) -> str:
    """
    Enter the currently selected bubble or project.

    Called when user says things like:
    - "Enter this bubble"
    - "Go inside"
    - "Open this"
    - "Enter"
    - "Let's go in"

    Args (via params):
        None required

    Returns:
        Confirmation message
    """
    # Send enter command to Electron
    _broadcast_to_electron({
        "type": "enter_selection",
    })
    
    return "Entering the selected item."


def exit_view(params: Dict[str, Any]) -> str:
    """
    Exit the current view and return to overview.

    Called when user says things like:
    - "Go back"
    - "Exit"
    - "Return to overview"
    - "Leave this bubble"
    - "Back out"

    Args (via params):
        None required

    Returns:
        Confirmation message
    """
    # Send exit command to Electron
    _broadcast_to_electron({
        "type": "exit_view",
    })
    
    return "Returning to the overview."


def get_current_view(params: Dict[str, Any]) -> str:
    """
    Get information about the current view state.

    Called when user says things like:
    - "Where am I?"
    - "What space is this?"
    - "What's selected?"

    Args (via params):
        None required

    Returns:
        Current view information
    """
    # Request current state from Electron
    _broadcast_to_electron({
        "type": "get_view_state",
    })

    space_names = {
        "ideas": "Ideas Universe",
        "projects": "Projects Space",
        "desktop": "Desktop Automation",
    }

    return f"You're currently in the {space_names.get(_current_space, _current_space)}."


# ==============================================================================
# SHUTTLE NAVIGATION TOOLS
# ==============================================================================

def select_shuttle(params: Dict[str, Any]) -> str:
    """
    Select a requirement shuttle by name or direction.

    Called when user says things like:
    - "Select the e-ticketing shuttle"
    - "Next shuttle"
    - "Show me the shuttles"

    Args (via params):
        name: Name of the shuttle/bubble to select (optional)
        direction: 'next' or 'previous' (optional)

    Returns:
        Confirmation of selection
    """
    name = params.get("name", "").strip()
    direction = params.get("direction", "").lower()

    if name:
        _broadcast_to_electron({
            "type": "select_shuttle_by_name",
            "name": name,
        })
        return f"Looking for shuttle '{name}'..."
    elif direction:
        dir_value = 1 if direction in ["next", "forward"] else -1
        _broadcast_to_electron({
            "type": "select_shuttle",
            "direction": dir_value,
        })
        direction_text = "next" if dir_value > 0 else "previous"
        return f"Selecting {direction_text} shuttle."
    else:
        # List available shuttles
        _broadcast_to_electron({
            "type": "list_shuttles",
        })
        return "Showing available requirement shuttles."


def enter_shuttle(params: Dict[str, Any]) -> str:
    """
    Enter the selected shuttle to view its requirements.

    Called when user says things like:
    - "Enter the shuttle"
    - "Zoom into the shuttle"
    - "Show me inside the shuttle"
    - "Enter shuttle"

    Args (via params):
        shuttle_name: Optional name of shuttle to enter directly

    Returns:
        Confirmation message
    """
    shuttle_name = params.get("shuttle_name", "").strip()

    if shuttle_name:
        _broadcast_to_electron({
            "type": "enter_shuttle_by_name",
            "name": shuttle_name,
        })
        return f"Entering shuttle '{shuttle_name}'..."
    else:
        _broadcast_to_electron({
            "type": "enter_shuttle",
        })
        return "Entering the selected shuttle."


def exit_shuttle(params: Dict[str, Any]) -> str:
    """
    Exit the shuttle view and return to the multiverse overview.

    Called when user says things like:
    - "Exit shuttle"
    - "Leave the shuttle"
    - "Back to multiverse"
    - "Zoom out"

    Args (via params):
        None required

    Returns:
        Confirmation message
    """
    _broadcast_to_electron({
        "type": "exit_shuttle",
    })
    return "Exiting the shuttle, returning to multiverse view."


def continue_to_project(params: Dict[str, Any]) -> str:
    """
    Continue from shuttle to create a project in the Projects Space.

    Called when user says things like:
    - "Continue to projects"
    - "Create the project"
    - "Finish the shuttle journey"
    - "Convert to project"

    Args (via params):
        None required

    Returns:
        Confirmation message
    """
    _broadcast_to_electron({
        "type": "shuttle_continue_to_project",
    })
    return "Creating project from validated requirements and navigating to Projects Space."


# ==============================================================================
# TOOL REGISTRY
# ==============================================================================

# All available tools
NAVIGATION_TOOLS = {
    # Space Navigation
    "navigate_to_space": navigate_to_space,
    # Item Selection
    "select_item": select_item,
    "select_by_name": select_by_name,
    # View Control
    "enter_selection": enter_selection,
    "exit_view": exit_view,
    "get_current_view": get_current_view,
    # Shuttle Navigation
    "select_shuttle": select_shuttle,
    "enter_shuttle": enter_shuttle,
    "exit_shuttle": exit_shuttle,
    "continue_to_project": continue_to_project,
}


def register_navigation_tools(tools_manager) -> None:
    """
    Register all navigation tools with the ClientToolsManager.

    Args:
        tools_manager: ClientToolsManager instance
    """
    print("Registering navigation tools...")
    for tool_name, tool_func in NAVIGATION_TOOLS.items():
        tools_manager.register_with_observer(tool_name, tool_func)
        print(f"  - {tool_name}")


__all__ = [
    "navigate_to_space",
    "select_item",
    "select_by_name",
    "enter_selection",
    "exit_view",
    "get_current_view",
    "select_shuttle",
    "enter_shuttle",
    "exit_shuttle",
    "continue_to_project",
    "NAVIGATION_TOOLS",
    "register_navigation_tools",
    "set_electron_sender",
]