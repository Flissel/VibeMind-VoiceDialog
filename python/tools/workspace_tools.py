"""
Vibemind Workspace Tools

ElevenLabs client tools for Ideas, Projects, and Canvas operations.
These tools are called directly by ElevenLabs agents via voice commands.

Tool Categories:
- Ideas: capture_idea, list_ideas, score_idea, get_idea
- Projects: create_project, list_projects, promote_idea, update_project
- Canvas: add_to_canvas, connect_nodes, list_canvas
- Bubbles: add_to_bubble (for Electron multiverse canvas)
"""

import sys

import json

from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data import (
    IdeasRepository,
    ProjectsRepository,
    CanvasRepository,
    Idea,
    Project,
    promote_idea_to_project,
)

# Global reference to Electron IPC sender (set by electron_backend.py)
_electron_send_message: Optional[Callable[[dict], None]] = None

# Global reference to bubble position getter (set by electron_backend.py)
_get_bubble_position_func: Optional[Callable[[str], Optional[dict]]] = None

def set_electron_sender(sender: Callable[[dict], None]):
    """Set the Electron IPC message sender callback."""
    global _electron_send_message
    _electron_send_message = sender

def set_bubble_position_getter(getter: Callable[[str], Optional[dict]]):
    """Set the bubble position getter callback."""
    global _get_bubble_position_func
    _get_bubble_position_func = getter

def get_bubble_position(bubble_db_id: str) -> Optional[dict]:
    """Get bubble position by database ID."""
    if _get_bubble_position_func:
        return _get_bubble_position_func(bubble_db_id)
    return None

def _broadcast_to_electron(message: dict):
    """Send a message to Electron if connected."""
    if _electron_send_message:
        _electron_send_message(message)


# ==============================================================================
# IDEAS TOOLS
# ==============================================================================

def capture_idea(params: Dict[str, Any]) -> str:
    """
    Capture a new idea from voice or text input.

    Called when user says things like:
    - "I have an idea about..."
    - "Let me capture this thought..."
    - "Save this idea: ..."

    Args (via params):
        title: Brief title for the idea (required)
        description: Detailed description (optional)
        tags: List of tags for categorization (optional)

    Returns:
        Success message with idea title
    """
    title = params.get("title", "").strip()

    if not title:
        return "I need a title for your idea. What should I call it?"

    description = params.get("description", "")
    tags = params.get("tags", [])

    # Ensure tags is a list
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    repo = IdeasRepository()
    idea = repo.create(
        title=title,
        description=description,
        source="voice",
        tags=tags,
    )

    if description:
        return f"Saved idea: '{idea.title}'. I've captured the details you provided."
    else:
        return f"Saved idea: '{idea.title}'. Want to add more details?"


def list_ideas(params: Dict[str, Any]) -> str:
    """
    List all ideas or filter by criteria.

    Called when user says things like:
    - "What ideas do I have?"
    - "Show me my ideas"
    - "List my top ideas"

    Args (via params):
        filter_by: Text to search in title/description (optional)
        status: Filter by status: raw, scored, promoted, archived (optional)
        limit: Maximum number to return (default: 5)
        top_scored: If true, return top scored ideas (optional)

    Returns:
        Formatted list of ideas
    """
    filter_by = params.get("filter_by")
    status = params.get("status")
    limit = int(params.get("limit", 5))
    top_scored = params.get("top_scored", False)

    repo = IdeasRepository()

    if top_scored:
        ideas = repo.list_top_scored(limit=limit)
    else:
        ideas = repo.list(filter_by=filter_by, status=status, limit=limit)

    if not ideas:
        if filter_by:
            return f"No ideas found matching '{filter_by}'."
        elif status:
            return f"No {status} ideas found."
        else:
            return "You don't have any ideas yet. Say 'I have an idea about...' to capture one."

    # Format ideas for voice output
    result_parts = [f"You have {len(ideas)} idea{'s' if len(ideas) > 1 else ''}:"]

    for i, idea in enumerate(ideas, 1):
        score_text = f" (score: {idea.score:.0f})" if idea.score > 0 else ""
        result_parts.append(f"{i}. {idea.title}{score_text}")

    return " ".join(result_parts)


def get_idea(params: Dict[str, Any]) -> str:
    """
    Get details about a specific idea.

    Called when user says things like:
    - "Tell me about idea X"
    - "What's the status of idea Y?"
    - "Details on my idea about..."

    Args (via params):
        title: Title or partial title to search for
        id: Direct ID lookup (optional)

    Returns:
        Detailed information about the idea
    """
    idea_id = params.get("id")
    title = params.get("title", "").strip()

    repo = IdeasRepository()
    idea = None

    if idea_id:
        idea = repo.get(idea_id)
    elif title:
        idea = repo.get_by_title(title)

    if not idea:
        return f"I couldn't find an idea called '{title}'. Would you like to capture it as a new idea?"

    # Build detailed response
    parts = [f"'{idea.title}'"]

    if idea.description:
        parts.append(f"Description: {idea.description}")

    if idea.score > 0:
        parts.append(f"Score: {idea.score:.0f} out of 100")

    parts.append(f"Status: {idea.status}")

    if idea.tags:
        parts.append(f"Tags: {', '.join(idea.tags)}")

    if idea.promoted_to_project_id:
        parts.append("This idea has been promoted to a project.")

    return ". ".join(parts)


def score_idea(params: Dict[str, Any]) -> str:
    """
    Score an idea across multiple dimensions.

    Called when user says things like:
    - "Score this idea"
    - "How ready is idea X?"
    - "Evaluate my idea about..."

    Args (via params):
        title: Title or partial title to search for (or id)
        feasibility: 0-10 score for how achievable (optional)
        impact: 0-10 score for potential impact (optional)
        novelty: 0-10 score for uniqueness (optional)
        urgency: 0-10 score for time sensitivity (optional)

    Returns:
        Scoring result with recommendation
    """
    idea_id = params.get("id")
    title = params.get("title", "").strip()

    repo = IdeasRepository()
    idea = None

    if idea_id:
        idea = repo.get(idea_id)
    elif title:
        idea = repo.get_by_title(title)

    if not idea:
        return f"I couldn't find an idea called '{title}'."

    # Update scores if provided
    if "feasibility" in params:
        idea.feasibility = min(10.0, max(0.0, float(params["feasibility"])))
    if "impact" in params:
        idea.impact = min(10.0, max(0.0, float(params["impact"])))
    if "novelty" in params:
        idea.novelty = min(10.0, max(0.0, float(params["novelty"])))
    if "urgency" in params:
        idea.urgency = min(10.0, max(0.0, float(params["urgency"])))

    # Calculate and save
    idea = repo.update(idea)

    # Generate recommendation
    if idea.score >= 70:
        recommendation = "This idea is ready for promotion to a project!"
    elif idea.score >= 50:
        recommendation = "Good potential. Consider refining the approach."
    elif idea.score >= 30:
        recommendation = "Needs more development before becoming a project."
    else:
        recommendation = "Early stage idea. Keep exploring."

    return f"'{idea.title}' scored {idea.score:.0f} out of 100. {recommendation}"


# ==============================================================================
# PROJECTS TOOLS
# ==============================================================================

def create_project(params: Dict[str, Any]) -> str:
    """
    Create a new project directly (not from an idea).

    Called when user says things like:
    - "Create a project called..."
    - "Start a new project about..."
    - "I want to work on a project for..."

    Args (via params):
        name: Project name (required)
        description: Project description (optional)

    Returns:
        Success message with project name
    """
    name = params.get("name", "").strip()

    if not name:
        return "What should we call this project?"

    description = params.get("description", "")

    repo = ProjectsRepository()
    project = repo.create(name=name, description=description)

    return f"Created project: '{project.name}'. Ready to track progress."


def list_projects(params: Dict[str, Any]) -> str:
    """
    List all projects or filter by status.

    Called when user says things like:
    - "What projects am I working on?"
    - "Show my active projects"
    - "List completed projects"

    Args (via params):
        status: Filter by status: active, paused, completed, archived (optional)
        limit: Maximum number to return (default: 5)

    Returns:
        Formatted list of projects
    """
    status = params.get("status")
    limit = int(params.get("limit", 5))

    repo = ProjectsRepository()
    projects = repo.list(status=status, limit=limit)

    if not projects:
        if status:
            return f"No {status} projects found."
        else:
            return "You don't have any projects yet. Promote an idea or create a project directly."

    result_parts = [f"You have {len(projects)} project{'s' if len(projects) > 1 else ''}:"]

    for i, project in enumerate(projects, 1):
        progress_text = f" ({project.progress:.0f}% done)" if project.progress > 0 else ""
        result_parts.append(f"{i}. {project.name}{progress_text}")

    return " ".join(result_parts)


def promote_idea(params: Dict[str, Any]) -> str:
    """
    Promote an idea to a project.

    Called when user says things like:
    - "Promote idea X to a project"
    - "Turn my idea about X into a project"
    - "Make idea X a project"

    Args (via params):
        title: Title or partial title of idea to promote
        id: Direct ID lookup (optional)

    Returns:
        Success message or error
    """
    idea_id = params.get("id")
    title = params.get("title", "").strip()

    ideas_repo = IdeasRepository()
    idea = None

    if idea_id:
        idea = ideas_repo.get(idea_id)
    elif title:
        idea = ideas_repo.get_by_title(title)

    if not idea:
        return f"I couldn't find an idea called '{title}'."

    if idea.status == "promoted":
        return f"'{idea.title}' has already been promoted to a project."

    project = promote_idea_to_project(idea.id)

    if project:
        return f"Promoted '{idea.title}' to project '{project.name}'. Ready to start working!"
    else:
        return f"Failed to promote idea '{idea.title}'."


def update_project(params: Dict[str, Any]) -> str:
    """
    Update a project's status or progress.

    Called when user says things like:
    - "Update project X progress to 50%"
    - "Mark project X as completed"
    - "Pause project X"

    Args (via params):
        name: Project name or partial name (or id)
        status: New status: active, paused, completed, archived (optional)
        progress: Progress percentage 0-100 (optional)

    Returns:
        Confirmation of update
    """
    project_id = params.get("id")
    name = params.get("name", "").strip()

    repo = ProjectsRepository()
    project = None

    if project_id:
        project = repo.get(project_id)
    elif name:
        project = repo.get_by_name(name)

    if not project:
        return f"I couldn't find a project called '{name}'."

    changes = []

    if "status" in params:
        new_status = params["status"]
        if new_status in ["active", "paused", "completed", "archived"]:
            project.status = new_status
            changes.append(f"status to {new_status}")

    if "progress" in params:
        project.progress = min(100.0, max(0.0, float(params["progress"])))
        changes.append(f"progress to {project.progress:.0f}%")

    if not changes:
        return f"What would you like to update for '{project.name}'? Status or progress?"

    repo.update(project)

    return f"Updated '{project.name}': {' and '.join(changes)}."


# ==============================================================================
# CANVAS TOOLS
# ==============================================================================

def _signal_canvas_refresh():
    """Signal the canvas to refresh from database (if running)"""
    # Signal Electron to refresh canvas
    _broadcast_to_electron({"type": "canvas_refresh"})

    # Also try cosmic_canvas if available (legacy support)
    try:
        from cosmic_canvas import get_canvas_instance
        canvas = get_canvas_instance()
        if canvas:
            canvas.refresh_from_database()
    except ImportError:
        pass  # Canvas not available
    except Exception:
        pass  # Canvas not running


def add_to_canvas(params: Dict[str, Any]) -> str:
    """
    Add an idea or project to the visual canvas.

    Called when user says things like:
    - "Add this to my canvas"
    - "Pin idea X to the canvas"
    - "Put project Y on the canvas"

    Args (via params):
        idea_title: Title of idea to pin (optional)
        project_name: Name of project to pin (optional)
        note: Custom note text to add (optional)
        x: X position (optional, auto-placed if not provided)
        y: Y position (optional, auto-placed if not provided)

    Returns:
        Success message
    """
    idea_title = params.get("idea_title")
    project_name = params.get("project_name")
    note = params.get("note")
    x = float(params.get("x", 0))
    y = float(params.get("y", 0))

    canvas_repo = CanvasRepository()
    ideas_repo = IdeasRepository()
    projects_repo = ProjectsRepository()

    if idea_title:
        idea = ideas_repo.get_by_title(idea_title)
        if not idea:
            return f"Couldn't find idea '{idea_title}'."

        node = canvas_repo.create_node(
            node_type="idea",
            title=idea.title,
            content=idea.description,
            x=x, y=y,
            linked_idea_id=idea.id,
        )
        _signal_canvas_refresh()
        return f"Added '{idea.title}' to the canvas."

    elif project_name:
        project = projects_repo.get_by_name(project_name)
        if not project:
            return f"Couldn't find project '{project_name}'."

        node = canvas_repo.create_node(
            node_type="project",
            title=project.name,
            content=project.description,
            x=x, y=y,
            linked_project_id=project.id,
        )
        _signal_canvas_refresh()
        return f"Added '{project.name}' to the canvas."

    elif note:
        node = canvas_repo.create_node(
            node_type="note",
            title="Note",
            content=note,
            x=x, y=y,
        )
        _signal_canvas_refresh()
        return "Added note to the canvas."

    else:
        return "What would you like to add to the canvas? An idea, project, or a note?"


def connect_nodes(params: Dict[str, Any]) -> str:
    """
    Connect two nodes on the canvas.

    Called when user says things like:
    - "Connect idea X to project Y"
    - "Link these two on the canvas"

    Args (via params):
        from_title: Title of source node (idea or project)
        to_title: Title of target node (idea or project)
        edge_type: Type of connection: default, dependency, reference, flow (optional)

    Returns:
        Success message or error
    """
    from_title = params.get("from_title", "").strip()
    to_title = params.get("to_title", "").strip()
    edge_type = params.get("edge_type", "default")

    if not from_title or not to_title:
        return "I need both items to connect. Which two things should I link?"

    canvas_repo = CanvasRepository()
    nodes = canvas_repo.list_nodes()

    # Find source and target nodes
    from_node = None
    to_node = None

    for node in nodes:
        if from_title.lower() in node.title.lower():
            from_node = node
        if to_title.lower() in node.title.lower():
            to_node = node

    if not from_node:
        return f"Couldn't find '{from_title}' on the canvas. Add it first."
    if not to_node:
        return f"Couldn't find '{to_title}' on the canvas. Add it first."

    edge = canvas_repo.create_edge(from_node.id, to_node.id, edge_type)
    _signal_canvas_refresh()

    return f"Connected '{from_node.title}' to '{to_node.title}'."


def list_canvas(params: Dict[str, Any]) -> str:
    """
    List items on the canvas.

    Called when user says things like:
    - "What's on my canvas?"
    - "Show me my canvas"

    Args (via params):
        None

    Returns:
        List of canvas items
    """
    canvas_repo = CanvasRepository()
    nodes = canvas_repo.list_nodes()

    if not nodes:
        return "Your canvas is empty. Say 'add X to canvas' to start."

    result_parts = [f"Your canvas has {len(nodes)} item{'s' if len(nodes) > 1 else ''}:"]

    for i, node in enumerate(nodes, 1):
        result_parts.append(f"{i}. {node.title} ({node.node_type})")

    return " ".join(result_parts)


# ==============================================================================
# BUBBLE TOOLS (Electron Multiverse Canvas)
# ==============================================================================

def add_to_bubble(params: Dict[str, Any]) -> str:
    """
    Add a node to a specific bubble in the Electron multiverse canvas.

    Called when user says things like:
    - "Add a note to Universe A"
    - "Put this image in the Creative Space"
    - "Add my idea to the Research Hub"

    Args (via params):
        bubble_id: ID of the bubble to add to (required if no bubble_name)
        bubble_name: Name of the bubble to add to (e.g. "Universe A", "Research Hub")
        node_type: Type of node: note, image, link (default: note)
        title: Title for the node (optional)
        text: Text content (for note type)
        url: URL (for link or image type)
        x: X position (optional, auto-placed if not provided)
        y: Y position (optional, auto-placed if not provided)

    Returns:
        Success message
    """
    bubble_id = params.get("bubble_id")
    bubble_name = params.get("bubble_name", "").strip()
    node_type = params.get("node_type", "note")
    title = params.get("title", "")
    text = params.get("text", "")
    url = params.get("url", "")
    x = float(params.get("x", 100 + __import__("random").random() * 300))
    y = float(params.get("y", 100 + __import__("random").random() * 200))

    if not bubble_id and not bubble_name:
        return "Which bubble should I add this to? Say the bubble name like 'Universe A' or 'Research Hub'."

    # Build content based on type
    content = {"title": title or f"New {node_type.title()}"}
    if node_type == "note":
        content["text"] = text
    elif node_type == "link":
        content["url"] = url or "https://"
    elif node_type == "image":
        content["url"] = url
        content["caption"] = title or "Image"

    # Save to database with bubble info in metadata
    canvas_repo = CanvasRepository()
    metadata = {
        "bubble_id": bubble_id,
        "bubble_name": bubble_name,
    }

    node = canvas_repo.create_node(
        node_type=node_type,
        title=title or f"New {node_type.title()}",
        content=text or url or "",
        x=x, y=y,
        metadata=metadata
    )

    # Broadcast to Electron
    _broadcast_to_electron({
        "type": "tool_add_node",
        "bubble_name": bubble_name,
        "bubble_id": bubble_id,
        "node": {
            "type": node_type,
            "position": {"x": x, "y": y},
            "content": content
        }
    })

    bubble_label = bubble_name or f"bubble {bubble_id}"
    return f"Added {node_type} to {bubble_label}."


def add_image_to_bubble(params: Dict[str, Any]) -> str:
    """
    Add an image to a bubble in the Electron multiverse canvas.

    Called when user says things like:
    - "Add this image to my canvas"
    - "Put this picture in Universe A"

    Args (via params):
        bubble_name: Name of the bubble (e.g. "Research Hub")
        bubble_id: ID of the bubble (if known)
        url: Image URL (required)
        caption: Caption for the image (optional)
        x: X position (optional)
        y: Y position (optional)

    Returns:
        Success message
    """
    params["node_type"] = "image"
    if params.get("caption"):
        params["title"] = params["caption"]
    return add_to_bubble(params)


def list_bubble_nodes(params: Dict[str, Any]) -> str:
    """
    List nodes in a specific bubble.

    Called when user says things like:
    - "What's in Universe A?"
    - "Show me the contents of Research Hub"

    Args (via params):
        bubble_name: Name of the bubble
        bubble_id: ID of the bubble (optional)

    Returns:
        List of nodes in the bubble
    """
    bubble_name = params.get("bubble_name", "").strip()
    bubble_id = params.get("bubble_id")

    if not bubble_name and not bubble_id:
        return "Which bubble do you want to see? Say the bubble name like 'Universe A'."

    canvas_repo = CanvasRepository()
    all_nodes = canvas_repo.list_nodes(limit=100)

    # Filter by bubble
    bubble_nodes = []
    for node in all_nodes:
        metadata = node.metadata or {}
        if bubble_id and metadata.get("bubble_id") == bubble_id:
            bubble_nodes.append(node)
        elif bubble_name and bubble_name.lower() in (metadata.get("bubble_name", "") or "").lower():
            bubble_nodes.append(node)

    if not bubble_nodes:
        return f"No items found in {bubble_name or f'bubble {bubble_id}'}."

    result_parts = [f"{bubble_name or f'Bubble {bubble_id}'} has {len(bubble_nodes)} item{'s' if len(bubble_nodes) > 1 else ''}:"]
    for i, node in enumerate(bubble_nodes, 1):
        result_parts.append(f"{i}. {node.title} ({node.node_type})")

    return " ".join(result_parts)


def edit_canvas_node(params: Dict[str, Any]) -> str:
    """
    Edit an existing node on the canvas.

    Called when user says things like:
    - "Change the title of that note"
    - "Update the text to say..."
    - "Rewrite the first note"

    Args (via params):
        node_title: Title of node to edit (searches for partial match)
        node_id: Direct node ID (optional)
        new_title: New title for the node (optional)
        new_text: New text content (optional)
        append_text: Text to append to existing content (optional)

    Returns:
        Confirmation message
    """
    node_title = params.get("node_title", "").strip()
    node_id = params.get("node_id")
    new_title = params.get("new_title", "").strip()
    new_text = params.get("new_text", "").strip()
    append_text = params.get("append_text", "").strip()

    if not node_title and not node_id:
        return "Which node should I edit? Give me the title or say which one."

    canvas_repo = CanvasRepository()

    # Find the node
    node = None
    if node_id:
        node = canvas_repo.get_node(node_id)
    elif node_title:
        # Search by title
        all_nodes = canvas_repo.list_nodes(limit=100)
        for n in all_nodes:
            if node_title.lower() in n.title.lower():
                node = n
                break

    if not node:
        return f"I couldn't find a node called '{node_title}'."

    # Apply updates
    changes = []
    if new_title:
        node.title = new_title
        changes.append(f"title to '{new_title}'")

    if new_text:
        node.content = new_text
        changes.append("text content")
    elif append_text:
        node.content = (node.content or "") + "\n\n" + append_text
        changes.append("appended text")

    if not changes:
        return "What would you like to change? The title or the text?"

    # Save to database
    canvas_repo.update_node(node)

    # Broadcast to Electron
    _broadcast_to_electron({
        "type": "tool_update_node",
        "node_id": node.id,
        "updates": {
            "title": node.title,
            "content": node.content
        }
    })

    return f"Updated node '{node.title}': changed {', '.join(changes)}."


def delete_bubble_node(params: Dict[str, Any]) -> str:
    """
    Delete a node from a bubble's canvas.

    Called when user says things like:
    - "Delete that note"
    - "Remove the first item"
    - "Get rid of the image"

    Args (via params):
        node_title: Title of node to delete
        node_id: Direct node ID (optional)
        confirm: Must be True to actually delete (safety)

    Returns:
        Confirmation message or request for confirmation
    """
    node_title = params.get("node_title", "").strip()
    node_id = params.get("node_id")
    confirm = params.get("confirm", False)

    if not node_title and not node_id:
        return "Which node should I delete? Give me the title."

    canvas_repo = CanvasRepository()

    # Find the node
    node = None
    if node_id:
        node = canvas_repo.get_node(node_id)
    elif node_title:
        all_nodes = canvas_repo.list_nodes(limit=100)
        for n in all_nodes:
            if node_title.lower() in n.title.lower():
                node = n
                break

    if not node:
        return f"I couldn't find a node called '{node_title}'."

    # Safety check
    if not confirm:
        return f"Are you sure you want to delete '{node.title}'? Say 'yes, delete it' to confirm."

    # Delete from database
    canvas_repo.delete_node(node.id)

    # Broadcast to Electron
    _broadcast_to_electron({
        "type": "tool_delete_node",
        "node_id": node.id
    })

    return f"Deleted '{node.title}' from the canvas."


# ==============================================================================
# TOOL REGISTRY
# ==============================================================================

# All tools that can be registered with ElevenLabs
WORKSPACE_TOOLS = {
    # Ideas
    "capture_idea": capture_idea,
    # list_ideas REMOVED - use idea_tools.list_ideas (notes inside bubble) 
    # or bubble_tools.list_bubbles (spaces in multiverse)
    "get_idea": get_idea,
    "score_idea": score_idea,
    # Projects
    "create_project": create_project,
    "list_projects": list_projects,
    "promote_idea": promote_idea,
    "update_project": update_project,
    # Canvas
    "add_to_canvas": add_to_canvas,
    "connect_nodes": connect_nodes,
    "list_canvas": list_canvas,
    # Bubbles (Electron Multiverse)
    "add_to_bubble": add_to_bubble,
    "add_image_to_bubble": add_image_to_bubble,
    "list_bubble_nodes": list_bubble_nodes,
    "edit_canvas_node": edit_canvas_node,
    "delete_bubble_node": delete_bubble_node,
}


def register_workspace_tools(tools_manager) -> None:
    """
    Register all workspace tools with the ClientToolsManager (with observer logging).

    Args:
        tools_manager: ClientToolsManager instance
    """
    print("Registering workspace tools with observer...")
    for tool_name, tool_func in WORKSPACE_TOOLS.items():
        tools_manager.register_with_observer(tool_name, tool_func)
        print(f"  - {tool_name}")


__all__ = [
    "capture_idea",
    "list_ideas",
    "get_idea",
    "score_idea",
    "create_project",
    "list_projects",
    "promote_idea",
    "update_project",
    "add_to_canvas",
    "connect_nodes",
    "list_canvas",
    "add_to_bubble",
    "add_image_to_bubble",
    "list_bubble_nodes",
    "edit_canvas_node",
    "delete_bubble_node",
    "WORKSPACE_TOOLS",
    "register_workspace_tools",
    "set_electron_sender",
]
