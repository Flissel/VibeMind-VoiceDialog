"""
Bubble/Idea Management Tools

Top-level tools for managing bubbles (Ideas) in the multiverse.
Bubbles are the top-level containers that hold canvas content (notes, thoughts).
Bubbles can be scored based on how many notes they contain.

Architecture:
- Bubbles = Idea objects (IdeasRepository) - scored, promotable
- Canvas content = CanvasNode objects (CanvasRepository) - linked via linked_idea_id
- Each bubble can have its own ElevenLabs agent for voice interaction
"""

import sys
import os
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

# ElevenLabs configuration
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
RACHEL_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice

# Agent switch signaling (checked by voice_dialog_main)
_pending_agent_switch: Optional[Dict[str, Any]] = None

# Current bubble DB ID (UUID string) for tool functions
# This is separate from electron_backend._current_bubble_id (which is local int)
_current_bubble_db_id: Optional[str] = None


def get_current_bubble_db_id() -> Optional[str]:
    """
    Get the current bubble's database UUID.
    
    This is used by other tool modules (like idea_tools.py) to know
    which bubble we're currently inside for creating linked notes.
    
    Returns:
        str: Database UUID of current bubble, or None if in multiverse view
    """
    return _current_bubble_db_id

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data import IdeasRepository, CanvasRepository
from data.repository import promote_idea_to_project

# Import Electron broadcast function from workspace_tools
from tools.workspace_tools import _broadcast_to_electron

# Repository instances
_ideas_repo: Optional[IdeasRepository] = None
_canvas_repo: Optional[CanvasRepository] = None


def _get_ideas_repo() -> IdeasRepository:
    """Get or create the ideas repository."""
    global _ideas_repo
    if _ideas_repo is None:
        _ideas_repo = IdeasRepository()
    return _ideas_repo


def _get_canvas_repo() -> CanvasRepository:
    """Get or create the canvas repository."""
    global _canvas_repo
    if _canvas_repo is None:
        _canvas_repo = CanvasRepository()
    return _canvas_repo


def _get_current_bubble_id() -> Optional[str]:
    """Get the current bubble ID from electron backend state."""
    try:
        import electron_backend
        bubble_id = electron_backend._current_bubble_id
        return str(bubble_id) if bubble_id else None
    except (ImportError, AttributeError):
        return None


def _create_elevenlabs_agent(bubble_title: str, bubble_id: str) -> Optional[str]:
    """
    Create an ElevenLabs agent for a bubble.

    Args:
        bubble_title: Title of the bubble (used in agent name and prompt)
        bubble_id: ID of the bubble

    Returns:
        str: Agent ID if successful, None otherwise
    """
    if not ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY not set, skipping agent creation")
        return None

    url = "https://api.elevenlabs.io/v1/convai/agents/create"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }

    # System prompt for bubble-specific agent
    system_prompt = f"""You are Rachel, a helpful assistant inside the "{bubble_title}" space.

Your role is to help the user develop ideas and notes within this specific space.
You have tools to create, list, find, update, and connect ideas.

When the user wants to leave this space and return to the multiverse, use the exit_bubble tool."""

    payload = {
        "name": f"Rachel - {bubble_title}",
        "conversation_config": {
            "tts": {
                "voice_id": RACHEL_VOICE_ID,
                "model_id": "eleven_flash_v2"
            },
            "agent": {
                "prompt": {
                    "prompt": system_prompt
                },
                "first_message": f"Welcome to {bubble_title}! What would you like to work on?"
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            agent_id = response.json().get("agent_id")
            logger.info(f"Created ElevenLabs agent '{bubble_title}': {agent_id}")
            return agent_id
        else:
            logger.error(f"Failed to create agent: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error creating ElevenLabs agent: {e}")
        return None


def _signal_agent_switch(agent_id: str, bubble_id: Optional[str], bubble_title: str):
    """
    Signal to voice_dialog_main that an agent switch is needed.

    Args:
        agent_id: Target ElevenLabs agent ID
        bubble_id: Target bubble ID (None for multiverse)
        bubble_title: Human-readable name of the target
    """
    global _pending_agent_switch
    _pending_agent_switch = {
        "agent_id": agent_id,
        "bubble_id": bubble_id,
        "bubble_title": bubble_title
    }

    # Also broadcast to Electron for UI update
    _broadcast_to_electron({
        "type": "agent_switching",
        "target_agent_id": agent_id,
        "bubble_id": bubble_id,
        "bubble_title": bubble_title
    })

    logger.info(f"Signaled agent switch to '{bubble_title}' (agent: {agent_id})")


def get_pending_agent_switch() -> Optional[Dict[str, Any]]:
    """
    Check if an agent switch is pending.

    Called by voice_dialog_main to detect when to switch agents.

    Returns:
        dict: Switch info if pending, None otherwise. Clears pending state.
    """
    global _pending_agent_switch
    result = _pending_agent_switch
    _pending_agent_switch = None
    return result


# =============================================================================
# BUBBLE TOOLS
# =============================================================================

def list_bubbles(params: Dict[str, Any]) -> str:
    """
    List all BUBBLES in the Ideas Space (top-level containers).

    NOT to be confused with list_ideas which shows notes INSIDE a bubble.
    This tool shows the BUBBLES available to enter.

    Voice triggers: "What bubbles do I have?", "Show my bubbles",
                   "List all bubbles", "Welche Bubbles habe ich?"

    Returns:
        str: Formatted list of bubbles with scores
    """
    logger.info("=" * 50)
    logger.info(">>> list_bubbles() CALLED <<<")
    logger.info(f"    Tool purpose: Show BUBBLES in Ideas Space (NOT notes inside)")
    logger.info("=" * 50)

    repo = _get_ideas_repo()
    ideas = repo.list(limit=20, order_by="score DESC")

    logger.info(f"    Total bubbles found: {len(ideas)}")
    for idea in ideas[:5]:
        logger.info(f"      - {idea.title} (score: {idea.score:.0f}, id: {idea.id[:8]}...)")

    if not ideas:
        logger.info("    Result: No bubbles exist yet")
        return "Du hast noch keine Bubbles. Moechtest du eine erstellen? Sag 'Erstelle eine Bubble fuer...'."

    # Store mapping for index-based voice referencing
    from tools.index_mapping import set_bubble_mapping
    set_bubble_mapping(ideas[:10])

    # Format with numbers for voice reference (1. Title, 2. Title...)
    titles = []
    indexed_bubbles = []
    for i, idea in enumerate(ideas[:10], 1):
        score_str = f" (score: {idea.score:.0f})" if idea.score > 0 else ""
        titles.append(f"{i}. {idea.title}{score_str}")
        indexed_bubbles.append({
            "index": i,
            "id": idea.id,
            "title": idea.title,
            "score": idea.score
        })

    # Broadcast indexed list to Electron UI so numbers are visible
    _broadcast_to_electron({
        "type": "bubbles_listed",
        "bubbles": indexed_bubbles,
        "total": len(ideas)
    })

    return f"Du hast {len(ideas)} Bubbles: {', '.join(titles)}. Betrete eine mit 'Geh in [Name]' oder 'Geh in [Nummer]'."


def find_bubble(params: Dict[str, Any]) -> str:
    """
    Search for a bubble by name (fuzzy) and automatically enter it.

    This is a MULTI-STEP tool:
    1. Search using fuzzy matching (handles speech recognition artifacts)
    2. If found, automatically enter the bubble
    3. Return combined result

    Voice triggers: "Such nach Bubble Marketing", "Finde Bubble Swarm Team",
                   "Wo ist die Bubble Finanzen?"

    Args (via params):
        query: Search term for bubble name (fuzzy matched)
        auto_enter: Whether to auto-enter if found (default: True)

    Returns:
        str: Search result with navigation status
    """
    global _current_bubble_db_id

    query = params.get("query", "").strip()
    auto_enter = params.get("auto_enter", True)

    logger.info("=" * 50)
    logger.info(">>> find_bubble() CALLED <<<")
    logger.info(f"    Query: '{query}', auto_enter: {auto_enter}")
    logger.info("=" * 50)

    # Phase 8A Fix: If query is empty or generic (list-like), delegate to list_bubbles
    # This handles cases like "Welche Bubbles gibt es?" being routed to find instead of list
    generic_queries = ["bubbles", "bubble", "alle", "all", "gibt es", "habe ich", ""]
    if not query or query.lower() in generic_queries:
        logger.info(f"Generic query '{query}' detected - delegating to list_bubbles()")
        return list_bubbles(params)

    if not query:
        return "Nach welcher Bubble soll ich suchen?"

    repo = _get_ideas_repo()

    # 1. Try exact match first
    bubble = repo.get_by_title(query)
    match_type = "exact"

    # 2. Fuzzy match fallback
    if not bubble:
        bubble = repo.get_by_title_fuzzy(query)
        match_type = "fuzzy"
        if bubble:
            logger.info(f"Fuzzy matched '{query}' to '{bubble.title}'")

    # 3. Semantic search fallback (Phase 9)
    if not bubble:
        try:
            semantic_matches = repo.search_semantic(query, top_k=3, min_score=0.4)
            if semantic_matches:
                bubble = semantic_matches[0]
                match_type = "semantic"
                logger.info(f"Semantic matched '{query}' to '{bubble.title}'")
        except Exception as e:
            logger.debug(f"Semantic search failed: {e}")

    # 4. Not found - list alternatives
    if not bubble:
        all_bubbles = repo.list(limit=20)
        if not all_bubbles:
            return f"Keine Bubble mit '{query}' gefunden. Du hast noch keine Bubbles."

        # Simple substring search as last resort
        candidates = [b for b in all_bubbles if query.lower() in b.title.lower()]
        if candidates:
            names = ", ".join([c.title for c in candidates[:3]])
            return f"Keine exakte Uebereinstimmung fuer '{query}'. Meintest du: {names}?"

        # No match at all
        all_names = ", ".join([b.title for b in all_bubbles[:5]])
        return f"Keine Bubble mit '{query}' gefunden. Deine Bubbles: {all_names}"

    # Found! Now auto-enter if enabled
    if auto_enter:
        # Check idempotency: already in this bubble?
        if _current_bubble_db_id == bubble.id:
            return f"Du bist bereits in der Bubble '{bubble.title}'."

        # Enter the bubble (reuse logic from enter_bubble)
        _current_bubble_db_id = bubble.id
        logger.info(f"Set _current_bubble_db_id = '{bubble.id}' for bubble '{bubble.title}'")

        # Update electron_backend
        try:
            import electron_backend
            local_bubble_id = electron_backend.get_bubble_by_db_id(bubble.id)
            backend = electron_backend.get_backend()

            if backend and local_bubble_id:
                electron_backend._current_bubble_id = local_bubble_id
                backend.current_bubble_id = local_bubble_id
                backend.enter_bubble(local_bubble_id)
            else:
                # Broadcast entered_bubble event for UI
                canvas_repo = _get_canvas_repo()
                all_nodes = canvas_repo.list_nodes(limit=1000)
                nodes = []
                for db_node in all_nodes:
                    if db_node.linked_idea_id == bubble.id:
                        nodes.append({
                            "id": db_node.id,
                            "type": db_node.node_type or "note",
                            "position": {"x": db_node.x or 100, "y": db_node.y or 100},
                            "content": {"title": db_node.title or "", "text": db_node.content or ""}
                        })

                _broadcast_to_electron({
                    "type": "entered_bubble",
                    "bubble_id": bubble.id,
                    "bubble_title": bubble.title,
                    "content": nodes,
                    "edges": []
                })
        except (ImportError, AttributeError) as e:
            logger.warning(f"Could not sync with electron_backend: {e}")

        match_info = ""
        if match_type == "fuzzy":
            match_info = " (fuzzy match)"
        elif match_type == "semantic":
            match_info = " (semantic match)"
        return f"Ich habe '{bubble.title}' gefunden{match_info} und bin reingewechselt. Was moechtest du hier tun?"

    # Just report found, don't enter
    return f"Gefunden: '{bubble.title}' mit Score {bubble.score:.0f}. Sag 'Geh rein' zum Betreten."


def create_bubble(params: Dict[str, Any]) -> str:
    """
    Create a new bubble/idea space with its own ElevenLabs agent.

    Voice triggers: "Create a new space for cooking", "Make a bubble for project ideas"

    Args (via params):
        title: Name for the new space (required)
        description: Optional description
        skip_agent_creation: If True, skip ElevenLabs agent creation (for simulation)
                            Phase 7 Fix: Agent creation takes 15s which spikes latency

    Returns:
        str: Confirmation message
    """
    title = params.get("title", "").strip()
    description = params.get("description", "").strip()
    skip_agent_creation = params.get("skip_agent_creation", False)

    if not title:
        return "What should I call this new space?"

    repo = _get_ideas_repo()

    # Check for duplicate
    existing = repo.get_by_title(title)
    if existing:
        return f"A space called '{title}' already exists"

    idea = repo.create(
        title=title,
        description=description,
        source="voice"
    )

    # Create ElevenLabs agent for this bubble (optional)
    # Phase 7: Skip during simulation to avoid 15s latency spike
    agent_id = None
    if not skip_agent_creation:
        agent_id = _create_elevenlabs_agent(title, idea.id)

    if agent_id:
        idea.agent_id = agent_id
        repo.update(idea)
        logger.info(f"Created bubble '{title}' with agent {agent_id}")
    else:
        logger.info(f"Created bubble '{title}' without agent (skipped or API error)")

    # Broadcast to Electron
    _broadcast_to_electron({
        "type": "bubble_created",
        "bubble": {
            "id": idea.id,
            "title": idea.title,
            "score": idea.score,
            "description": idea.description,
            "agent_id": idea.agent_id
        }
    })

    # Trigger PostgreSQL synchronization
    try:
        import asyncio
        from swarm.tools.data_event_handler import on_bubble_created
        bubble_data = {
            "id": str(idea.id),
            "title": idea.title,
            "description": idea.description,
            "color": None,  # Will be set by UI
            "position": {"x": 0, "y": 0, "z": 0},  # Default position
            "radius": 0.7,
            "space_type": "ideas"
        }
        asyncio.create_task(on_bubble_created(bubble_data))
    except Exception as e:
        logger.warning(f"Failed to trigger PostgreSQL sync for bubble creation: {e}")

    return f"Created new space '{title}'"


def update_bubble(params: Dict[str, Any]) -> str:
    """
    Update a bubble's title or description.

    Voice triggers: "Rename this space to X", "Update bubble name",
                   "Change the title to X"

    Args (via params):
        bubble_name: Current name of the bubble to update (optional - uses current if not specified)
        new_title: New title for the bubble (optional)
        new_description: New description for the bubble (optional)

    Returns:
        str: Confirmation message
    """
    bubble_name = params.get("bubble_name", "").strip()
    new_title = params.get("new_title", params.get("title", "")).strip()
    new_description = params.get("new_description", params.get("description", "")).strip()

    if not new_title and not new_description:
        return "Was soll ich aendern? Bitte sag mir den neuen Namen oder die neue Beschreibung."

    repo = _get_ideas_repo()

    # Find the bubble to update
    bubble = None
    if bubble_name:
        bubble = repo.get_by_title(bubble_name)
    else:
        # Use current bubble if inside one
        current_id = _get_current_bubble_id()
        if current_id:
            bubble = repo.get_by_id(current_id)

    if not bubble:
        if bubble_name:
            return f"Ich konnte den Space '{bubble_name}' nicht finden."
        else:
            return "Du bist nicht in einem Space. Bitte sag mir welchen Space ich updaten soll."

    old_title = bubble.title

    # Update the bubble
    if new_title:
        # Check for duplicate title
        existing = repo.get_by_title(new_title)
        if existing and existing.id != bubble.id:
            return f"Ein Space mit dem Namen '{new_title}' existiert bereits."
        bubble.title = new_title

    if new_description:
        bubble.description = new_description

    repo.update(bubble)

    # Broadcast to Electron
    _broadcast_to_electron({
        "type": "bubble_updated",
        "bubble": {
            "id": bubble.id,
            "title": bubble.title,
            "description": bubble.description,
            "old_title": old_title
        }
    })

    # Trigger PostgreSQL synchronization
    try:
        import asyncio
        from swarm.tools.data_event_handler import on_bubble_updated
        bubble_data = {
            "id": str(bubble.id),
            "title": bubble.title,
            "description": bubble.description,
        }
        asyncio.create_task(on_bubble_updated(bubble_data))
    except Exception as e:
        logger.warning(f"Failed to trigger PostgreSQL sync for bubble update: {e}")

    if new_title:
        return f"Space umbenannt von '{old_title}' zu '{new_title}'"
    else:
        return f"Beschreibung von Space '{bubble.title}' aktualisiert"


def get_bubble_stats(params: Dict[str, Any]) -> str:
    """
    Get statistics about a bubble based on its content.

    Voice triggers: "How developed is this idea?", "What's in this space?", "Show me stats"

    Args (via params):
        bubble_name: Name of bubble to check (optional - uses current if not specified)

    Returns:
        str: Statistics including note count, connections, and score
    """
    bubble_name = params.get("bubble_name", "").strip()

    ideas_repo = _get_ideas_repo()
    canvas_repo = _get_canvas_repo()

    # Get bubble by name or use current
    if bubble_name:
        idea = ideas_repo.get_by_title(bubble_name)
        if not idea:
            return f"Couldn't find a space called '{bubble_name}'"
    else:
        bubble_id = _get_current_bubble_id()
        if not bubble_id:
            return "You're in the multiverse view. Specify a space name or enter one first."
        idea = ideas_repo.get(bubble_id)
        if not idea:
            return "Current space not found in database"

    # Count notes inside this bubble (linked via linked_idea_id)
    all_nodes = canvas_repo.list_nodes(limit=1000)
    notes = [n for n in all_nodes if n.linked_idea_id == idea.id]

    # Count edges between notes
    edges = canvas_repo.list_edges(limit=1000)
    note_ids = {n.id for n in notes}
    connections = [e for e in edges
                   if e.from_node_id in note_ids or e.to_node_id in note_ids]

    # Status description
    status_desc = {
        "raw": "just started",
        "scored": "being developed",
        "promoted": "now a project",
        "archived": "archived"
    }.get(idea.status, idea.status)

    return (f"'{idea.title}' has {len(notes)} notes and {len(connections)} connections. "
            f"Score: {idea.score:.0f}/100. Status: {status_desc}")


def score_bubble(params: Dict[str, Any]) -> str:
    """
    Calculate and update bubble score based on content richness.

    Voice triggers: "Evaluate this idea", "Score this space", "How good is this idea?"

    The scoring algorithm:
    - Impact (35%): Based on number of notes (more content = higher impact)
    - Feasibility (25%): Based on connections (more linked = more feasible)
    - Novelty (20%): Default value, can be manually adjusted
    - Urgency (20%): Default value, can be manually adjusted

    Args (via params):
        bubble_name: Name of bubble to score (optional - uses current if not specified)

    Returns:
        str: Score breakdown
    """
    bubble_name = params.get("bubble_name", "").strip()

    ideas_repo = _get_ideas_repo()
    canvas_repo = _get_canvas_repo()

    # Get bubble by name or use current
    if bubble_name:
        idea = ideas_repo.get_by_title(bubble_name)
        if not idea:
            return f"Couldn't find '{bubble_name}'"
    else:
        bubble_id = _get_current_bubble_id()
        if not bubble_id:
            return "Specify a space name or enter one first."
        idea = ideas_repo.get(bubble_id)
        if not idea:
            return "Current space not found"

    # Count content
    all_nodes = canvas_repo.list_nodes(limit=1000)
    notes = [n for n in all_nodes if n.linked_idea_id == idea.id]
    note_count = len(notes)

    edges = canvas_repo.list_edges(limit=1000)
    note_ids = {n.id for n in notes}
    connections = [e for e in edges
                   if e.from_node_id in note_ids or e.to_node_id in note_ids]
    connection_count = len(connections)

    # Calculate score dimensions based on content
    # Impact: More notes = higher impact (cap at 10)
    idea.impact = min(10.0, note_count * 1.5)

    # Feasibility: More connections = more feasible (cap at 10)
    idea.feasibility = min(10.0, connection_count * 2.0)

    # Novelty: Keep existing or default to 5
    if idea.novelty == 0:
        idea.novelty = 5.0

    # Urgency: Keep existing or default to 3
    if idea.urgency == 0:
        idea.urgency = 3.0

    # Calculate composite score
    idea.score = idea.calculate_score()

    # Update in database
    ideas_repo.update(idea)

    # Broadcast update
    _broadcast_to_electron({
        "type": "bubble_scored",
        "bubble_id": idea.id,
        "score": idea.score,
        "details": {
            "notes": note_count,
            "connections": connection_count,
            "impact": idea.impact,
            "feasibility": idea.feasibility,
            "novelty": idea.novelty,
            "urgency": idea.urgency
        }
    })

    # Trigger PostgreSQL synchronization
    try:
        import asyncio
        from swarm.tools.data_event_handler import on_bubble_updated
        bubble_data = {
            "id": str(idea.id),
            "title": idea.title,
            "description": idea.description,
            "color": None,
            "position": {"x": 0, "y": 0, "z": 0},
            "radius": 0.7,
            "space_type": "ideas"
        }
        asyncio.create_task(on_bubble_updated(bubble_data))
    except Exception as e:
        logger.warning(f"Failed to trigger PostgreSQL sync for bubble scoring: {e}")

    logger.info(f"Scored bubble '{idea.title}': {idea.score:.0f}/100")

    return (f"'{idea.title}' scored {idea.score:.0f} out of 100. "
            f"Based on {note_count} notes and {connection_count} connections. "
            f"Impact: {idea.impact:.0f}, Feasibility: {idea.feasibility:.0f}")


def promote_bubble(params: Dict[str, Any]) -> str:
    """
    Promote a bubble/idea to a project.

    Voice triggers: "Turn this into a project", "Promote this idea", "Make this a project"

    Args (via params):
        bubble_name: Name of bubble to promote (optional - uses current if not specified)

    Returns:
        str: Confirmation message
    """
    bubble_name = params.get("bubble_name", "").strip()

    ideas_repo = _get_ideas_repo()

    # Get bubble by name or use current
    if bubble_name:
        idea = ideas_repo.get_by_title(bubble_name)
        if not idea:
            return f"Couldn't find '{bubble_name}'"
    else:
        bubble_id = _get_current_bubble_id()
        if not bubble_id:
            return "Specify a space name or enter one first."
        idea = ideas_repo.get(bubble_id)
        if not idea:
            return "Current space not found"

    # Check if already promoted
    if idea.status == "promoted":
        return f"'{idea.title}' is already a project"

    # Score first if not scored
    if idea.score == 0:
        # Quick score
        canvas_repo = _get_canvas_repo()
        all_nodes = canvas_repo.list_nodes(limit=1000)
        notes = [n for n in all_nodes if n.linked_idea_id == idea.id]
        idea.impact = min(10.0, len(notes) * 1.5)
        idea.feasibility = 5.0
        idea.novelty = 5.0
        idea.urgency = 5.0
        idea.score = idea.calculate_score()
        ideas_repo.update(idea)

    # Promote to project
    project = promote_idea_to_project(idea.id)

    if project:
        # Broadcast
        _broadcast_to_electron({
            "type": "bubble_promoted",
            "bubble_id": idea.id,
            "project_id": project.id,
            "project_name": project.name
        })

        logger.info(f"Promoted bubble '{idea.title}' to project '{project.name}'")
        return f"'{idea.title}' is now a project! Ready to take action."

    return "Failed to promote to project"


def delete_bubble(params: Dict[str, Any]) -> str:
    """
    Delete a bubble/idea space with CASCADE deletion of all content.
    Supports deleting multiple bubbles when a list of names is provided.

    Voice triggers: "Delete this space", "Remove the cooking bubble"

    CASCADE DELETE order (handled atomically in database):
    1. Delete all edges connected to nodes in this bubble
    2. Delete all canvas nodes linked to this bubble
    3. Delete the bubble/idea itself

    Args (via params):
        bubble_name: Name of bubble to delete (required) - can be string or list of strings

    Returns:
        str: Confirmation message
    """
    raw_bubble_name = params.get("bubble_name", "")

    logger.info(f"delete_bubble called with params: {params}")

    # Handle list input (RAG classifier may pass multiple names)
    if isinstance(raw_bubble_name, list):
        return _delete_multiple_bubbles(raw_bubble_name)

    # Handle single string input
    bubble_name = raw_bubble_name.strip() if isinstance(raw_bubble_name, str) else str(raw_bubble_name)

    if not bubble_name:
        return "Which space should I delete? Please specify the name."

    ideas_repo = _get_ideas_repo()

    idea = ideas_repo.get_by_title(bubble_name)
    if not idea:
        logger.warning(f"Bubble not found by title: '{bubble_name}'")
        return f"Couldn't find a space called '{bubble_name}'"

    title = idea.title
    idea_id = idea.id

    logger.info(f"Found bubble to delete: '{title}' (id: {idea_id})")

    # Use CASCADE DELETE which handles FK constraints atomically
    try:
        stats = ideas_repo.delete_cascade(idea_id)
        deleted_nodes = stats.get("nodes_deleted", 0)
        deleted_edges = stats.get("edges_deleted", 0)

        if not stats.get("idea_deleted", False):
            logger.error(f"Failed to delete idea {idea_id} - idea_deleted is False")
            return f"Error deleting space '{title}'"

    except Exception as e:
        logger.error(f"Cascade delete failed for bubble {idea_id}: {e}")
        return f"Error deleting space '{title}': {str(e)}"

    # Broadcast to UI - include title for fallback matching
    _broadcast_to_electron({
        "type": "bubble_deleted",
        "bubble_id": idea_id,
        "title": title,
        "deleted_nodes": deleted_nodes,
        "deleted_edges": deleted_edges
    })

    logger.info(f"Cascade deleted bubble '{title}': {deleted_nodes} nodes, {deleted_edges} edges")
    return f"Deleted space '{title}' with {deleted_nodes} notes and {deleted_edges} connections"


def _delete_multiple_bubbles(bubble_names: list) -> str:
    """
    Helper to delete multiple bubbles by name.

    Args:
        bubble_names: List of bubble names to delete

    Returns:
        str: Summary of deletion results
    """
    if not bubble_names:
        return "No bubble names provided to delete."

    ideas_repo = _get_ideas_repo()
    deleted = []
    not_found = []
    errors = []
    total_nodes = 0
    total_edges = 0

    for name in bubble_names:
        # Clean up the name
        if isinstance(name, str):
            name = name.strip()
        else:
            name = str(name).strip()

        if not name:
            continue

        idea = ideas_repo.get_by_title(name)
        if not idea:
            not_found.append(name)
            continue

        try:
            stats = ideas_repo.delete_cascade(idea.id)
            if stats.get("idea_deleted", False):
                deleted.append(idea.title)
                total_nodes += stats.get("nodes_deleted", 0)
                total_edges += stats.get("edges_deleted", 0)

                # Broadcast each deletion to UI
                _broadcast_to_electron({
                    "type": "bubble_deleted",
                    "bubble_id": idea.id,
                    "title": idea.title,
                    "deleted_nodes": stats.get("nodes_deleted", 0),
                    "deleted_edges": stats.get("edges_deleted", 0)
                })
            else:
                errors.append(name)
        except Exception as e:
            logger.error(f"Failed to delete bubble '{name}': {e}")
            errors.append(name)

    # Build response message
    parts = []
    if deleted:
        parts.append(f"Deleted {len(deleted)} spaces: {', '.join(deleted[:5])}" +
                    (f" and {len(deleted) - 5} more" if len(deleted) > 5 else ""))
        parts.append(f"Removed {total_nodes} notes and {total_edges} connections total")
    if not_found:
        parts.append(f"Not found: {', '.join(not_found[:3])}" +
                    (f" and {len(not_found) - 3} more" if len(not_found) > 3 else ""))
    if errors:
        parts.append(f"Errors deleting: {', '.join(errors[:3])}")

    if not parts:
        return "No bubbles were deleted."

    logger.info(f"Bulk delete: {len(deleted)} deleted, {len(not_found)} not found, {len(errors)} errors")
    return ". ".join(parts)


def delete_all_bubbles_except(params: Dict[str, Any] = None) -> str:
    """
    Delete all bubbles/spaces EXCEPT the specified ones.

    Voice triggers:
    - "Lösche alle Bubbles außer Langzeitspeicher"
    - "Delete all spaces except VibeMind"
    - "Lösche alles bis auf X und Y"

    Args (via params):
        exceptions: Bubble names to keep (string or list of strings)
                   Can be comma-separated string: "VibeMind, Langzeitspeicher"
                   Or a list: ["VibeMind", "Langzeitspeicher"]

    Returns:
        str: Summary of what was deleted and what was kept
    """
    params = params or {}
    exceptions_raw = params.get("exceptions", params.get("keep", params.get("bubble_name", "")))

    logger.info(f"delete_all_bubbles_except called with params: {params}")

    # Normalize exceptions to a list of lowercase names
    exceptions = []
    if isinstance(exceptions_raw, list):
        for e in exceptions_raw:
            if isinstance(e, str):
                # Handle comma-separated within list items
                for part in e.split(","):
                    cleaned = part.strip().lower()
                    if cleaned:
                        exceptions.append(cleaned)
            else:
                exceptions.append(str(e).strip().lower())
    elif isinstance(exceptions_raw, str):
        # Handle comma-separated string
        for part in exceptions_raw.split(","):
            cleaned = part.strip().lower()
            if cleaned:
                exceptions.append(cleaned)

    if not exceptions:
        return "Welche Spaces sollen behalten werden? Bitte sag z.B. 'Lösche alle außer VibeMind'."

    logger.info(f"Keeping bubbles (lowercase): {exceptions}")

    # Get all bubbles
    ideas_repo = _get_ideas_repo()
    all_ideas = ideas_repo.list(limit=1000)

    if not all_ideas:
        return "Es gibt keine Bubbles zum Löschen."

    deleted = []
    skipped = []
    errors = []
    total_nodes = 0
    total_edges = 0

    for idea in all_ideas:
        title_lower = idea.title.lower()

        # Check if this bubble should be kept
        should_keep = False
        for exc in exceptions:
            if exc in title_lower or title_lower in exc:
                should_keep = True
                break

        if should_keep:
            skipped.append(idea.title)
            logger.info(f"Keeping bubble: {idea.title}")
            continue

        # Delete this bubble
        try:
            stats = ideas_repo.delete_cascade(idea.id)
            if stats.get("idea_deleted", False):
                deleted.append(idea.title)
                total_nodes += stats.get("nodes_deleted", 0)
                total_edges += stats.get("edges_deleted", 0)

                # Broadcast deletion to UI
                _broadcast_to_electron({
                    "type": "bubble_deleted",
                    "bubble_id": idea.id,
                    "title": idea.title,
                    "deleted_nodes": stats.get("nodes_deleted", 0),
                    "deleted_edges": stats.get("edges_deleted", 0)
                })
                logger.info(f"Deleted bubble: {idea.title}")
            else:
                errors.append(idea.title)
        except Exception as e:
            logger.error(f"Failed to delete bubble '{idea.title}': {e}")
            errors.append(idea.title)

    # Build response message
    parts = []
    if deleted:
        if len(deleted) <= 5:
            parts.append(f"{len(deleted)} Spaces gelöscht: {', '.join(deleted)}")
        else:
            parts.append(f"{len(deleted)} Spaces gelöscht: {', '.join(deleted[:5])} und {len(deleted) - 5} weitere")
        parts.append(f"Insgesamt {total_nodes} Notizen und {total_edges} Verbindungen entfernt")

    if skipped:
        parts.append(f"Behalten: {', '.join(skipped)}")

    if errors:
        parts.append(f"Fehler bei: {', '.join(errors[:3])}")

    if not deleted and not errors:
        return f"Keine Spaces gelöscht. Alle {len(skipped)} Spaces wurden behalten: {', '.join(skipped)}"

    logger.info(f"Delete all except: {len(deleted)} deleted, {len(skipped)} kept, {len(errors)} errors")
    return ". ".join(parts)


def enter_bubble(params: Dict[str, Any]) -> str:
    """
    Enter a bubble and switch to its dedicated agent.

    Voice triggers: "Enter cooking space", "Go into my project ideas", "Open the recipes bubble",
                   "Geh in 2" (index-based)

    Args (via params):
        bubble_name: Name or index of the bubble to enter (required)

    Returns:
        str: Confirmation message (triggers agent switch in Python)
    """
    global _current_bubble_db_id
    from tools.index_mapping import resolve_bubble_index, get_index_mapping

    bubble_name = params.get("bubble_name", "").strip()

    if not bubble_name:
        return "Which space would you like to enter?"

    repo = _get_ideas_repo()
    idea = None

    # 0. Try index-based resolution first (e.g., "2" -> second bubble)
    if bubble_name.isdigit():
        bubble_id = resolve_bubble_index(bubble_name)
        if bubble_id:
            idea = repo.get(bubble_id)
            if idea:
                logger.info(f"Resolved bubble index {bubble_name} -> '{idea.title}'")
        if not idea:
            mapping = get_index_mapping()
            max_idx = len(mapping.bubbles) if mapping.bubbles else 0
            if max_idx > 0:
                return f"Keine Bubble mit Index {bubble_name}. Verfuegbar: 1-{max_idx}. Nutze 'Zeig mir meine Spaces' fuer die Liste."
            # Fall through to try numeric as title

    # 1. Try exact match first
    if not idea:
        idea = repo.get_by_title(bubble_name)

    # 2. Fuzzy match fallback (handles speech recognition accent artifacts)
    if not idea:
        idea = repo.get_by_title_fuzzy(bubble_name)
        if idea:
            logger.info(f"Fuzzy matched '{bubble_name}' to '{idea.title}'")

    if not idea:
        return f"I couldn't find a space called '{bubble_name}'. Use 'create bubble {bubble_name}' to create one."

    # 3. Idempotency check: if already in this bubble, just confirm
    if _current_bubble_db_id == idea.id:
        logger.info(f"Already in bubble '{idea.title}' (id: {idea.id}) - idempotent return")
        return f"You are already in {idea.title}. What would you like to work on?"

    # CRITICAL: Set the DB UUID for tool functions (like create_idea)
    _current_bubble_db_id = idea.id
    logger.info(f"Set _current_bubble_db_id = '{idea.id}' for bubble '{idea.title}'")

    # Get the Rachel/Multiverse agent - optional, only needed for voice switching
    multiverse_agent_id = os.getenv("AGENT_MULTIVERSE") or os.getenv("AGENT_RACHEL")

    # Helper function to load nodes for this bubble from DB
    def load_bubble_nodes(bubble_db_id: str) -> tuple:
        """Load nodes and edges for a bubble from the database."""
        nodes = []
        edges = []
        try:
            canvas_repo = _get_canvas_repo()
            all_nodes = canvas_repo.list_nodes(limit=1000)
            
            for db_node in all_nodes:
                if db_node.linked_idea_id == bubble_db_id:
                    node = {
                        "id": db_node.id,  # Use DB UUID as ID
                        "type": db_node.node_type or "note",
                        "position": {"x": db_node.x or 100, "y": db_node.y or 100},
                        "content": {
                            "title": db_node.title or "",
                            "text": db_node.content or "",
                        },
                        "connections": []
                    }
                    nodes.append(node)
            
            # Load edges
            all_edges = canvas_repo.list_edges(limit=1000)
            node_ids = {n["id"] for n in nodes}
            for db_edge in all_edges:
                if db_edge.from_node_id in node_ids or db_edge.to_node_id in node_ids:
                    edges.append({
                        "from_node_id": db_edge.from_node_id,
                        "to_node_id": db_edge.to_node_id
                    })
                    
            logger.info(f"Loaded {len(nodes)} nodes and {len(edges)} edges for bubble {bubble_db_id}")
        except Exception as e:
            logger.warning(f"Failed to load nodes for bubble: {e}")
        
        return nodes, edges

    # Update current bubble in electron_backend and trigger canvas switch
    try:
        import electron_backend
        
        # Get the local bubble ID from the mapping
        local_bubble_id = electron_backend.get_bubble_by_db_id(idea.id)
        backend = electron_backend.get_backend()
        
        if backend and local_bubble_id:
            # Set current bubble (uses local ID)
            electron_backend._current_bubble_id = local_bubble_id
            backend.current_bubble_id = local_bubble_id
            
            # Call enter_bubble to trigger canvas loading
            backend.enter_bubble(local_bubble_id)
            logger.info(f"Called electron_backend.enter_bubble({local_bubble_id}) for '{idea.title}'")
        else:
            # Bubble not in memory yet - add it
            if backend:
                bubble = backend.add_bubble(
                    title=idea.title,
                    position={"x": 0, "y": 0, "z": 0},
                    color=0x4488ff,
                    radius=0.7
                )
                # Update mapping
                electron_backend._bubble_id_map[idea.id] = bubble.id
                backend.bubble_id_map[idea.id] = bubble.id
                
                electron_backend._current_bubble_id = bubble.id
                backend.enter_bubble(bubble.id)
                logger.info(f"Created and entered bubble '{idea.title}' (local id: {bubble.id})")
            else:
                # Fallback: load nodes ourselves and broadcast entered_bubble with content
                nodes, edges = load_bubble_nodes(idea.id)
                _broadcast_to_electron({
                    "type": "entered_bubble",  # Use entered_bubble with content
                    "bubble_id": idea.id,
                    "bubble_title": idea.title,
                    "content": nodes,
                    "edges": edges
                })
                logger.warning("No backend instance - sent entered_bubble with loaded nodes")
                
    except (ImportError, AttributeError) as e:
        logger.warning(f"Could not sync with electron_backend: {e}")
        # Fallback: load nodes ourselves and broadcast entered_bubble with content
        nodes, edges = load_bubble_nodes(idea.id)
        _broadcast_to_electron({
            "type": "entered_bubble",  # Use entered_bubble with content
            "bubble_id": idea.id,
            "bubble_title": idea.title,
            "content": nodes,
            "edges": edges
        })
        logger.info(f"Fallback: sent entered_bubble with {len(nodes)} nodes")
    
    logger.info(f"Entered bubble '{idea.title}' (db id: {idea.id})")

    return f"You are now in {idea.title}. What would you like to work on?"


def exit_bubble(params: Dict[str, Any]) -> str:
    """
    Exit current bubble and return to the multiverse agent.

    Voice triggers: "Go back", "Exit this space", "Return to multiverse", "Leave"

    Returns:
        str: Confirmation message (triggers agent switch in Python)
    """
    global _current_bubble_db_id
    
    # Get multiverse agent ID from config
    multiverse_agent_id = os.getenv("AGENT_MULTIVERSE")

    if not multiverse_agent_id:
        return "Cannot find multiverse agent configuration. Please set AGENT_MULTIVERSE in .env"

    # CRITICAL: Clear the DB UUID
    _current_bubble_db_id = None
    logger.info("Cleared _current_bubble_db_id (exiting bubble)")

    # Clear current bubble in electron_backend
    try:
        import electron_backend
        electron_backend._current_bubble_id = None
    except (ImportError, AttributeError):
        pass

    # BUG 2 FIX: Broadcast exited_bubble event to Electron UI
    _broadcast_to_electron({
        "type": "exited_bubble"
    })
    logger.info("Broadcast exited_bubble to Electron")

    # Signal agent switch back to multiverse
    _signal_agent_switch(multiverse_agent_id, None, "Multiverse")

    return "Returning to multiverse view..."


# =============================================================================
# AGENT TRANSFER TOOLS
# =============================================================================

def transfer_to_alice(params: Dict[str, Any]) -> str:
    """
    Transfer conversation to Alice, the coordinator.
    
    Alice can delegate to Adam (desktop tasks) or Antoni (coding/writing).
    
    Args (via params):
        reason: Why transferring (optional)
    
    Returns:
        str: Confirmation that transfer is initiated
    """
    alice_agent_id = os.getenv("AGENT_ALICE")
    
    if not alice_agent_id:
        return "Cannot find Alice agent configuration. Please set AGENT_ALICE in .env"
    
    reason = params.get("reason", "User request")
    
    # Signal the switch
    _signal_agent_switch(alice_agent_id, None, "Alice")
    
    logger.info(f"Transfer to Alice initiated. Reason: {reason}")
    return "Transferring to Alice..."


def transfer_to_adam(params: Dict[str, Any]) -> str:
    """
    Transfer conversation to Adam for desktop operations.
    
    Adam handles file management, system tasks, and desktop operations.
    
    Args (via params):
        reason: Why transferring (optional)
    
    Returns:
        str: Confirmation that transfer is initiated
    """
    adam_agent_id = os.getenv("AGENT_ADAM")
    
    if not adam_agent_id:
        return "Cannot find Adam agent configuration. Please set AGENT_ADAM in .env"
    
    reason = params.get("reason", "Desktop task")
    
    # Signal the switch
    _signal_agent_switch(adam_agent_id, None, "Adam")
    
    logger.info(f"Transfer to Adam initiated. Reason: {reason}")
    return "Transferring to Adam..."


def transfer_to_antoni(params: Dict[str, Any]) -> str:
    """
    Transfer conversation to Antoni for coding/writing tasks.
    
    Antoni handles programming, code writing, and text composition.
    
    Args (via params):
        reason: Why transferring (optional)
    
    Returns:
        str: Confirmation that transfer is initiated
    """
    antoni_agent_id = os.getenv("AGENT_ANTONI")
    
    if not antoni_agent_id:
        return "Cannot find Antoni agent configuration. Please set AGENT_ANTONI in .env"
    
    reason = params.get("reason", "Coding task")
    
    # Signal the switch
    _signal_agent_switch(antoni_agent_id, None, "Antoni")
    
    logger.info(f"Transfer to Antoni initiated. Reason: {reason}")
    return "Transferring to Antoni..."


def transfer_to_rachel(params: Dict[str, Any]) -> str:
    """
    Transfer conversation to Rachel for creative/multiverse tasks.
    
    Rachel handles brainstorming, idea exploration, and multiverse navigation.
    
    Args (via params):
        reason: Why transferring (optional)
    
    Returns:
        str: Confirmation that transfer is initiated
    """
    rachel_agent_id = os.getenv("AGENT_RACHEL") or os.getenv("AGENT_CONVERSATIONAL_MEMORY")
    
    if not rachel_agent_id:
        return "Cannot find Rachel agent configuration. Please set AGENT_RACHEL in .env"
    
    reason = params.get("reason", "Creative task")
    
    # Signal the switch
    _signal_agent_switch(rachel_agent_id, None, "Rachel")
    
    logger.info(f"Transfer to Rachel initiated. Reason: {reason}")
    return "Transferring to Rachel..."


def transfer_to_multiverse(params: Dict[str, Any]) -> str:
    """
    Transfer conversation to Multiverse Navigator.

    Multiverse handles navigation between bubbles/spaces and exploration.

    Args (via params):
        reason: Why transferring (optional)

    Returns:
        str: Confirmation that transfer is initiated
    """
    multiverse_agent_id = os.getenv("AGENT_MULTIVERSE")

    if not multiverse_agent_id:
        return "Cannot find Multiverse agent configuration. Please set AGENT_MULTIVERSE in .env"

    reason = params.get("reason", "Space navigation")

    # Clear current bubble since we're going to multiverse view
    try:
        import electron_backend
        electron_backend._current_bubble_id = None
    except (ImportError, AttributeError):
        pass

    # Signal the switch
    _signal_agent_switch(multiverse_agent_id, None, "Multiverse")

    logger.info(f"Transfer to Multiverse initiated. Reason: {reason}")
    return "Transferring to Multiverse..."


def generate_bubble_embeddings(params: Dict[str, Any]) -> str:
    """
    Generate embeddings for all bubbles in the database.

    This function generates embeddings for all bubbles that don't have embeddings yet,
    or whose content has changed (detected by hash mismatch).

    Voice triggers: "Generiere Embeddings", "Erstelle Vektoren", "Bubbles indizieren"

    Args (via params):
        None

    Returns:
        str: Summary of embedding generation process
    """
    from data.repository import IdeasRepository

    repo = _get_ideas_repo()
    result = repo.generate_embeddings_for_all_bubbles()

    if not result.get("success"):
        return f"Fehler bei der Embedding-Generierung: {result.get('error', 'Unbekannter Fehler')}"

    total = result.get("total", 0)
    generated = result.get("generated", 0)
    skipped = result.get("skipped", 0)
    errors = result.get("errors", 0)

    message = f"Embeddings generiert für {total} Bubbles: {generated} neu, {skipped} übersprungen"
    if errors > 0:
        message += f", {errors} Fehler"

    logger.info(f"[generate_bubble_embeddings] {message}")
    return message


# =============================================================================
# AI EVOLUTION SCORING
# =============================================================================

# OpenRouter client for AI-based evaluation
_openrouter_client = None

def _get_openrouter_client():
    """Get or create OpenRouter client (OpenAI-compatible endpoint)."""
    global _openrouter_client
    if _openrouter_client is None:
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENROUTER_API_KEY")
            if api_key:
                _openrouter_client = OpenAI(
                    api_key=api_key,
                    base_url="https://openrouter.ai/api/v1"
                )
                logger.info("OpenRouter client initialized for bubble evaluation")
        except ImportError:
            logger.warning("OpenAI package not installed, AI evaluation unavailable")
    return _openrouter_client


def _get_bubble_content(idea_id: str) -> tuple:
    """
    Get all content from a bubble for evaluation.

    Returns:
        tuple: (title, combined_content, node_count)
    """
    ideas_repo = _get_ideas_repo()
    canvas_repo = _get_canvas_repo()

    idea = ideas_repo.get(idea_id)
    if not idea:
        return None, None, 0

    # Get all nodes linked to this idea
    all_nodes = canvas_repo.list_nodes(limit=1000)
    idea_nodes = [n for n in all_nodes if n.linked_idea_id == idea_id]

    # Combine all content
    content_parts = []
    for node in idea_nodes:
        if node.title:
            content_parts.append(f"## {node.title}")
        if node.content:
            content_parts.append(node.content)
        content_parts.append("")

    combined_content = "\n".join(content_parts)

    return idea.title, combined_content, len(idea_nodes)


def evaluate_bubble_evolution(params: Dict[str, Any]) -> str:
    """
    Evaluate how evolved/complete a bubble's ideas are using AI analysis.

    Voice triggers: "Evaluate this bubble", "How complete is this idea?",
                   "Score the evolution of this space"

    Evaluates on 4 dimensions:
    - Completeness (0-10): Clear goals, requirements, scope
    - Structure (0-10): Organized logically, well-connected
    - Actionability (0-10): Can be turned into concrete tasks
    - Depth (0-10): Detailed descriptions, thorough exploration

    Args (via params):
        bubble_name: Name of bubble to evaluate (optional - uses current)

    Returns:
        str: Score breakdown with recommendations
    """
    bubble_name = params.get("bubble_name", "").strip()

    logger.info(f"evaluate_bubble_evolution called: bubble_name='{bubble_name}'")

    # Check OpenRouter availability
    client = _get_openrouter_client()
    if not client:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return "Please set OPENROUTER_API_KEY in your .env file to enable AI evaluation."
        return "OpenAI package required. Install with: pip install openai"

    ideas_repo = _get_ideas_repo()

    # Get bubble by name or use current
    if bubble_name:
        idea = ideas_repo.get_by_title(bubble_name)
        if not idea:
            return f"Couldn't find '{bubble_name}'"
    else:
        bubble_id = _get_current_bubble_id()
        if not bubble_id:
            return "Specify a space name or enter one first."
        idea = ideas_repo.get(bubble_id)
        if not idea:
            return "Current space not found"

    # Get content
    title, content, node_count = _get_bubble_content(idea.id)

    if not content or node_count == 0:
        return f"'{title}' has no content to evaluate yet. Add some notes first!"

    # Call OpenRouter for AI evaluation
    model = os.getenv("OPENROUTER_EVAL_MODEL", "openai/gpt-4o-mini")

    system_prompt = """You are an idea evolution evaluator. Analyze the content and score it on 4 dimensions (0-10 each):

1. COMPLETENESS: Does it have clear goals, requirements, and defined scope?
2. STRUCTURE: Is the content organized logically? Are ideas well-connected?
3. ACTIONABILITY: Can this be turned into concrete tasks and deliverables?
4. DEPTH: How detailed and thoroughly explored are the descriptions?

Respond in this exact JSON format:
{
    "completeness": <0-10>,
    "structure": <0-10>,
    "actionability": <0-10>,
    "depth": <0-10>,
    "overall_score": <0-100>,
    "summary": "<1-2 sentence summary>",
    "recommendations": ["<recommendation 1>", "<recommendation 2>", "<recommendation 3>"]
}"""

    user_prompt = f"""Evaluate this idea/project bubble:

Title: {title}

Content ({node_count} notes):
{content[:4000]}  # Limit to avoid token limits

Provide your evaluation as JSON."""

    import json  # Import before try block so except json.JSONDecodeError works

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )

        result_text = response.choices[0].message.content.strip()

        # Parse JSON response
        # Handle markdown code blocks
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        result = json.loads(result_text)

        # Extract scores
        completeness = result.get("completeness", 5)
        structure = result.get("structure", 5)
        actionability = result.get("actionability", 5)
        depth = result.get("depth", 5)
        overall_score = result.get("overall_score", (completeness + structure + actionability + depth) * 2.5)
        summary = result.get("summary", "")
        recommendations = result.get("recommendations", [])

        # Update idea with new scores
        # Map AI dimensions to Idea model fields:
        # - completeness stored in metadata (no direct field)
        # - structure → feasibility
        # - actionability → impact
        # - depth → novelty
        idea.feasibility = structure
        idea.impact = actionability
        idea.novelty = depth
        idea.urgency = max(idea.urgency, completeness)  # Use completeness for urgency
        idea.score = overall_score
        idea.status = "scored"

        # Store completeness in metadata for reference
        idea.metadata["ai_eval"] = {
            "completeness": completeness,
            "structure": structure,
            "actionability": actionability,
            "depth": depth,
            "summary": summary,
            "recommendations": recommendations
        }
        ideas_repo.update(idea)

        # Broadcast update
        _broadcast_to_electron({
            "type": "bubble_evolution_scored",
            "bubble_id": idea.id,
            "score": overall_score,
            "details": {
                "completeness": completeness,
                "structure": structure,
                "actionability": actionability,
                "depth": depth,
                "summary": summary,
                "recommendations": recommendations,
                "node_count": node_count
            }
        })

        logger.info(f"AI evaluated bubble '{idea.title}': {overall_score}/100")

        # Format response
        rec_text = "\n".join(f"  • {r}" for r in recommendations[:3])

        return (f"'{title}' scored {overall_score:.0f}/100\n\n"
                f"Completeness: {completeness}/10\n"
                f"Structure: {structure}/10\n"
                f"Actionability: {actionability}/10\n"
                f"Depth: {depth}/10\n\n"
                f"{summary}\n\n"
                f"To improve:\n{rec_text}")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        return "AI evaluation failed - couldn't parse response. Try again."
    except Exception as e:
        logger.error(f"OpenRouter evaluation error: {e}")
        return f"AI evaluation failed: {str(e)}"


# =============================================================================
# TOOL REGISTRY
# =============================================================================

BUBBLE_TOOLS = {
    "list_bubbles": list_bubbles,
    "find_bubble": find_bubble,  # Multi-step: search + auto-enter
    "create_bubble": create_bubble,
    "get_bubble_stats": get_bubble_stats,
    "score_bubble": score_bubble,
    "evaluate_bubble_evolution": evaluate_bubble_evolution,  # AI-based scoring
    "promote_bubble": promote_bubble,
    "delete_bubble": delete_bubble,
    "delete_all_bubbles_except": delete_all_bubbles_except,  # Bulk delete with exceptions
    "enter_bubble": enter_bubble,
    "exit_bubble": exit_bubble,
    # Agent transfer tools
    "transfer_to_alice": transfer_to_alice,
    "transfer_to_adam": transfer_to_adam,
    "transfer_to_antoni": transfer_to_antoni,
    "transfer_to_rachel": transfer_to_rachel,
    "transfer_to_multiverse": transfer_to_multiverse,
    # Embedding generation tool
    "generate_bubble_embeddings": generate_bubble_embeddings,
}


def register_bubble_tools(tools_manager) -> None:
    """Register all bubble tools with the tools manager (with observer logging)."""
    print("Registering bubble tools with observer...")
    for tool_name, tool_func in BUBBLE_TOOLS.items():
        tools_manager.register_with_observer(tool_name, tool_func)
        print(f"  - {tool_name}")


__all__ = [
    "list_bubbles",
    "find_bubble",
    "create_bubble",
    "update_bubble",
    "get_bubble_stats",
    "score_bubble",
    "evaluate_bubble_evolution",
    "promote_bubble",
    "delete_bubble",
    "delete_all_bubbles_except",
    "enter_bubble",
    "exit_bubble",
    "transfer_to_alice",
    "transfer_to_adam",
    "transfer_to_antoni",
    "transfer_to_rachel",
    "transfer_to_multiverse",
    "generate_bubble_embeddings",
    "get_pending_agent_switch",
    "get_current_bubble_db_id",
    "BUBBLE_TOOLS",
    "register_bubble_tools",
]
