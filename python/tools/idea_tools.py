"""
Note/Canvas Content Management Tools for Conversational Memory Agent

Tools for managing notes/content INSIDE a bubble/space.
These are the CanvasNodes that live inside Ideas/Bubbles.

Architecture:
- Bubbles = Ideas (managed by bubble_tools.py)
- Notes inside bubbles = CanvasNodes (managed by THIS file)
- CanvasNodes link to their parent Idea via linked_idea_id

Tool Categories:
- list_ideas: List all notes in current bubble
- create_idea: Create a new note/canvas item
- find_idea: Search for notes
- update_idea: Update an existing note
- connect_ideas: Link two notes together
- delete_idea: Remove a note
- get_current_space: Get info about current location
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data import CanvasRepository

# Import Electron broadcast function from workspace_tools
from tools.workspace_tools import _broadcast_to_electron

# Import the current bubble DB ID getter from bubble_tools
from tools.bubble_tools import get_current_bubble_db_id

# Repository instance
_canvas_repo: Optional[CanvasRepository] = None


def _get_canvas_repo() -> CanvasRepository:
    """Get or create the canvas repository."""
    global _canvas_repo
    if _canvas_repo is None:
        _canvas_repo = CanvasRepository()
    return _canvas_repo


def _get_current_bubble_id() -> Optional[str]:
    """Get the current bubble ID (database UUID) from bubble_tools state.

    Returns the Idea ID (string UUID) that corresponds to the current bubble.
    This is the DB UUID, not the local Electron int ID.
    """
    # Use the bubble_tools module-level state which is set by enter_bubble()
    return get_current_bubble_db_id()


def _get_bubble_info(bubble_id: int) -> Optional[Dict[str, Any]]:
    """Get bubble info from electron backend state."""
    try:
        import electron_backend
        bubbles = electron_backend._bubbles
        if bubbles and bubble_id in bubbles:
            bubble = bubbles[bubble_id]
            return {"id": bubble.id, "title": bubble.title}
        return None
    except (ImportError, AttributeError):
        return None


# =============================================================================
# IDEA TOOLS
# =============================================================================

def list_ideas(params: Dict[str, Any]) -> str:
    """
    List all NOTES (canvas items) inside the current space/bubble.
    
    NOT to be confused with list_bubbles which shows spaces in the multiverse.
    This tool shows the CONTENT inside the current space you are in.

    Voice triggers: "What notes do I have here?", "Show my ideas in this space", 
                   "List notes", "What's in this bubble?"
    
    IMPORTANT: User must be inside a space first. If in multiverse view,
    this returns "Enter a space first".

    Returns:
        str: Formatted list of notes/canvas items in current bubble
    """
    bubble_id = _get_current_bubble_id()
    
    logger.info("=" * 50)
    logger.info(">>> list_ideas() CALLED <<<")
    logger.info(f"    bubble_id = {bubble_id}")
    logger.info(f"    Tool purpose: Show NOTES inside current bubble (NOT spaces)")
    logger.info("=" * 50)

    if bubble_id is None:
        logger.info("    Result: User is in multiverse view, no bubble entered")
        return "You're in the multiverse view. Enter a space first to see its notes. Use 'list bubbles' to see available spaces."

    repo = _get_canvas_repo()

    # Get all nodes and filter by linked_idea_id
    all_nodes = repo.list_nodes(limit=1000)
    nodes = [n for n in all_nodes if n.linked_idea_id == bubble_id]
    
    logger.info(f"    Total nodes in DB: {len(all_nodes)}")
    logger.info(f"    Nodes linked to bubble {bubble_id}: {len(nodes)}")
    for n in nodes[:5]:
        logger.info(f"      - {n.title or 'Untitled'} (id: {n.id[:8]}...)")

    if not nodes:
        return "This space is empty. Would you like me to add a note? Say 'Add a note about...'."

    # Get titles or first 30 chars of content
    titles = []
    for n in nodes[:10]:
        title = n.title or (n.content[:30] if n.content else "Untitled")
        titles.append(title)

    return f"In this space you have {len(nodes)} notes: {', '.join(titles)}"


def create_idea(params: Dict[str, Any]) -> str:
    """
    Create a new note in the current bubble/space.

    Voice triggers: "Add an idea about cooking", "Create a note for Python tips"

    Args (via params):
        title: Short title for the note (required)
        content: Full content/description (optional)
        type: Type of node - "idea", "note", "link", "image" (optional, default: "note")

    Returns:
        str: Confirmation message
    """
    title = params.get("title", "").strip()
    content = params.get("content", "").strip()
    node_type = params.get("type", "note")

    if not title:
        return "What should I call this note?"

    bubble_id = _get_current_bubble_id()

    if bubble_id is None:
        return "Enter a space first before adding notes."

    repo = _get_canvas_repo()

    # Count existing nodes for positioning
    all_nodes = repo.list_nodes(limit=1000)
    bubble_nodes = [n for n in all_nodes if n.linked_idea_id == bubble_id]
    count = len(bubble_nodes)

    # Create node in database with linked_idea_id pointing to parent bubble
    node = repo.create_node(
        node_type=node_type,
        title=title,
        content=content or title,
        x=100 + (count * 50) % 400,
        y=100 + (count * 30) % 300,
        linked_idea_id=bubble_id  # Link to parent Idea/Bubble
    )

    # Broadcast to Electron UI
    _broadcast_to_electron({
        "type": "node_added",
        "bubble_id": bubble_id,
        "node": {
            "id": node.id,
            "type": node.node_type,
            "position": {"x": node.x, "y": node.y},
            "content": {"title": node.title, "text": node.content},
            "connections": []
        }
    })

    logger.info(f"Created note '{title}' in bubble {bubble_id}")
    return f"Added '{title}'"


def add_image(params: Dict[str, Any]) -> str:
    """
    Add an image to the current bubble/space.

    Voice triggers: "Add an image", "Save this picture", "Add image from URL"

    Args (via params):
        url: URL of the image (required)
        title: Caption/title for the image (optional)

    Returns:
        str: Confirmation message
    """
    url = params.get("url", "").strip()
    title = params.get("title", "").strip() or "Image"

    if not url:
        return "What's the image URL?"

    # Validate URL has image extension or is a valid URL
    if not url.startswith(("http://", "https://", "data:")):
        return "Please provide a valid image URL starting with http:// or https://"

    bubble_id = _get_current_bubble_id()

    if bubble_id is None:
        return "Enter a space first before adding images."

    repo = _get_canvas_repo()

    # Count existing nodes for positioning
    all_nodes = repo.list_nodes(limit=1000)
    bubble_nodes = [n for n in all_nodes if n.linked_idea_id == bubble_id]
    count = len(bubble_nodes)

    # Create image node in database
    node = repo.create_node(
        node_type="image",
        title=title,
        content=url,  # Store URL in content field
        x=100 + (count * 50) % 400,
        y=100 + (count * 30) % 300,
        linked_idea_id=bubble_id,
        metadata={"url": url, "caption": title}  # Also store in metadata
    )

    # Broadcast to Electron UI
    _broadcast_to_electron({
        "type": "node_added",
        "bubble_id": bubble_id,
        "node": {
            "id": node.id,
            "type": "image",
            "position": {"x": node.x, "y": node.y},
            "content": {"url": url, "caption": title},
            "connections": []
        }
    })

    logger.info(f"Added image '{title}' ({url[:50]}...) in bubble {bubble_id}")
    return f"Added image '{title}'"


def find_idea(params: Dict[str, Any]) -> str:
    """
    Search for notes matching a query.

    Voice triggers: "Find my notes about Python", "Search for cooking ideas"

    Args (via params):
        query: Search text (required)

    Returns:
        str: Matching notes or "no matches"
    """
    query = params.get("query", "").strip().lower()

    if not query:
        return "What would you like me to search for?"

    bubble_id = _get_current_bubble_id()
    repo = _get_canvas_repo()

    # Get all nodes
    all_nodes = repo.list_nodes(limit=1000)

    # Filter by bubble if inside one, otherwise search all
    if bubble_id:
        nodes = [n for n in all_nodes if n.linked_idea_id == bubble_id]
    else:
        nodes = all_nodes

    # Filter by query
    matches = [
        n for n in nodes
        if query in (n.title or "").lower() or query in (n.content or "").lower()
    ]

    if not matches:
        return f"No notes found matching '{query}'"

    titles = []
    for m in matches[:5]:
        title = m.title or (m.content[:30] if m.content else "Untitled")
        titles.append(title)

    return f"Found {len(matches)} notes: {', '.join(titles)}"


def update_idea(params: Dict[str, Any]) -> str:
    """
    Update an existing idea.

    Voice triggers: "Update the cooking idea", "Change my Python note"

    Args (via params):
        idea_name: Name/title of the idea to update (required)
        new_content: New content (optional)
        new_title: New title (optional)

    Returns:
        str: Confirmation message
    """
    idea_name = params.get("idea_name", "").strip().lower()
    new_content = params.get("new_content", "").strip()
    new_title = params.get("new_title", "").strip()

    if not idea_name:
        return "Which idea should I update?"

    if not new_content and not new_title:
        return "What should I change it to?"

    bubble_id = _get_current_bubble_id()
    repo = _get_canvas_repo()

    # Get nodes
    all_nodes = repo.list_nodes(limit=1000)
    if bubble_id:
        nodes = [n for n in all_nodes if n.linked_idea_id == bubble_id]
    else:
        nodes = all_nodes

    # Find matching node
    match = None
    for n in nodes:
        if idea_name in (n.title or "").lower():
            match = n
            break

    if not match:
        return f"Couldn't find an idea called '{idea_name}'"

    # Update
    if new_title:
        match.title = new_title
    if new_content:
        match.content = new_content

    repo.update_node(match)

    # Broadcast update
    _broadcast_to_electron({
        "type": "node_updated",
        "node_id": match.id,
        "updates": {
            "title": match.title,
            "content": {
                "title": match.title,
                "text": match.content
            }
        }
    })

    logger.info(f"Updated idea '{match.title}'")
    return f"Updated '{match.title}'"


def connect_ideas(params: Dict[str, Any]) -> str:
    """
    Connect two ideas with an edge.

    Voice triggers: "Link cooking to recipes", "Connect Python to coding"

    Args (via params):
        idea1: First idea name (required)
        idea2: Second idea name (required)

    Returns:
        str: Confirmation message
    """
    idea1 = params.get("idea1", "").strip().lower()
    idea2 = params.get("idea2", "").strip().lower()

    if not idea1 or not idea2:
        return "Which two ideas should I connect?"

    bubble_id = _get_current_bubble_id()
    repo = _get_canvas_repo()

    # Get nodes
    all_nodes = repo.list_nodes(limit=1000)
    if bubble_id:
        nodes = [n for n in all_nodes if n.linked_idea_id == bubble_id]
    else:
        nodes = all_nodes

    # Find both nodes
    node1 = node2 = None
    for n in nodes:
        title_lower = (n.title or "").lower()
        if idea1 in title_lower:
            node1 = n
        if idea2 in title_lower:
            node2 = n

    if not node1:
        return f"Couldn't find '{idea1}'"
    if not node2:
        return f"Couldn't find '{idea2}'"

    # Create edge
    edge = repo.create_edge(node1.id, node2.id, "related")

    # Broadcast
    _broadcast_to_electron({
        "type": "edge_added",
        "edge": {
            "from_node_id": node1.id,
            "to_node_id": node2.id,
            "label": "related"
        }
    })

    logger.info(f"Connected '{node1.title}' to '{node2.title}'")
    return f"Connected '{node1.title}' to '{node2.title}'"


def delete_idea(params: Dict[str, Any]) -> str:
    """
    Delete an idea.

    Voice triggers: "Remove the old note", "Delete cooking idea"

    Args (via params):
        idea_name: Name of idea to delete (required)

    Returns:
        str: Confirmation message
    """
    idea_name = params.get("idea_name", "").strip().lower()

    if not idea_name:
        return "Which idea should I delete?"

    bubble_id = _get_current_bubble_id()
    repo = _get_canvas_repo()

    # Get nodes
    all_nodes = repo.list_nodes(limit=1000)
    if bubble_id:
        nodes = [n for n in all_nodes if n.linked_idea_id == bubble_id]
    else:
        nodes = all_nodes

    # Find matching node
    match = None
    for n in nodes:
        if idea_name in (n.title or "").lower():
            match = n
            break

    if not match:
        return f"Couldn't find an idea called '{idea_name}'"

    title = match.title
    node_id = match.id
    repo.delete_node(node_id)

    # Broadcast
    _broadcast_to_electron({
        "type": "node_deleted",
        "node_id": node_id
    })

    logger.info(f"Deleted idea '{title}'")
    return f"Deleted '{title}'"


def get_current_space(params: Dict[str, Any]) -> str:
    """
    Get information about current location.

    Voice triggers: "Where am I?", "What space is this?"

    Returns:
        str: Current location description
    """
    bubble_id = _get_current_bubble_id()

    if bubble_id is None:
        return "You're in the multiverse view, looking at all your spaces"

    bubble_info = _get_bubble_info(bubble_id)
    if bubble_info:
        return f"You're inside {bubble_info.get('title', 'a space')}"

    return f"You're in space {bubble_id}"


# =============================================================================
# TOOL REGISTRY
# =============================================================================

IDEA_TOOLS = {
    "list_ideas": list_ideas,
    "create_idea": create_idea,
    "add_image": add_image,
    "find_idea": find_idea,
    "update_idea": update_idea,
    "connect_ideas": connect_ideas,
    "delete_idea": delete_idea,
    "get_current_space": get_current_space,
}


def register_idea_tools(tools_manager) -> None:
    """Register all idea tools with the tools manager (with observer logging)."""
    print("Registering idea tools with observer...")
    for tool_name, tool_func in IDEA_TOOLS.items():
        try:
            tools_manager.register_with_observer(tool_name, tool_func)
            print(f"  - {tool_name}")
        except ValueError:
            # Tool already registered by workspace_tools - skip
            print(f"  - {tool_name} (skipped - already registered)")


__all__ = [
    "list_ideas",
    "create_idea",
    "add_image",
    "find_idea",
    "update_idea",
    "connect_ideas",
    "delete_idea",
    "get_current_space",
    "IDEA_TOOLS",
    "register_idea_tools",
]
