"""
VibeMind Conversation Tools

Tools for capturing and transferring conversation content to the canvas.
Allows the AI to save discussion summaries, key points, and full transcripts
as structured nodes in bubbles.

Tool Categories:
- Transcript capture: save_conversation, save_summary
- Content extraction: extract_key_points, create_idea_from_discussion

All messages are automatically persisted to the database for supermemory.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data import CanvasRepository, IdeasRepository, ConversationRepository

# Import Electron sender from workspace_tools
from tools.workspace_tools import _broadcast_to_electron


# =============================================================================
# CONVERSATION STORAGE
# =============================================================================

# In-memory conversation buffer (for quick access to current session)
_conversation_buffer: List[Dict[str, str]] = []
_conversation_started: Optional[datetime] = None
_current_session_id: Optional[str] = None

# Database repository for persistence
_conversation_repo: Optional[ConversationRepository] = None


def _get_repo() -> ConversationRepository:
    """Get or create the conversation repository."""
    global _conversation_repo
    if _conversation_repo is None:
        _conversation_repo = ConversationRepository()
    return _conversation_repo


def start_session(agent_id: Optional[str] = None) -> str:
    """
    Start a new conversation session.
    Called when voice dialog begins.

    Args:
        agent_id: Optional agent ID for tracking

    Returns:
        Session ID
    """
    global _conversation_buffer, _conversation_started, _current_session_id

    # Clear in-memory buffer
    _conversation_buffer = []
    _conversation_started = datetime.now()

    # Create session in database
    repo = _get_repo()
    session = repo.create_session(agent_id=agent_id)
    _current_session_id = session.id

    logger.info(f"Started conversation session: {_current_session_id}")
    return _current_session_id


def end_session(summary: Optional[str] = None) -> None:
    """
    End the current conversation session.
    Called when voice dialog ends.

    Args:
        summary: Optional LLM-generated summary of the conversation
    """
    global _current_session_id

    if _current_session_id:
        repo = _get_repo()
        repo.end_session(_current_session_id, summary=summary)
        logger.info(f"Ended conversation session: {_current_session_id}")
        _current_session_id = None


def record_message(speaker: str, text: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Record a message to the conversation buffer AND persist to database.
    Called by voice dialog handlers.

    Args:
        speaker: "user" or "agent"
        text: The spoken text
        metadata: Optional additional metadata
    """
    global _conversation_started, _current_session_id

    # Auto-start session if not started
    if not _current_session_id:
        start_session()

    if not _conversation_started:
        _conversation_started = datetime.now()

    timestamp = datetime.now()

    # Add to in-memory buffer for quick access
    _conversation_buffer.append({
        "speaker": speaker,
        "text": text,
        "timestamp": timestamp.isoformat()
    })

    # Persist to database (supermemory)
    repo = _get_repo()
    msg = repo.add_message(
        session_id=_current_session_id,
        speaker=speaker,
        text=text,
        metadata=metadata or {}
    )
    logger.debug(f"Persisted message {msg.id}: [{speaker}] {text[:50]}...")


def clear_conversation():
    """Clear the in-memory conversation buffer and end current session."""
    global _conversation_buffer, _conversation_started, _current_session_id

    # End current session if active
    if _current_session_id:
        end_session()

    _conversation_buffer = []
    _conversation_started = None
    _current_session_id = None


def get_current_session_id() -> Optional[str]:
    """Get the current session ID."""
    return _current_session_id


def get_session_history(session_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get conversation history from the database.

    Args:
        session_id: Session to fetch (uses current if not provided)
        limit: Maximum messages to return

    Returns:
        List of message dictionaries
    """
    repo = _get_repo()
    sid = session_id or _current_session_id

    if not sid:
        return []

    messages = repo.get_session_messages(sid, limit=limit)
    return [msg.to_dict() for msg in messages]


def search_conversation_history(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Search across all conversation history (supermemory).

    Args:
        query: Text to search for
        limit: Maximum results

    Returns:
        List of matching messages with context
    """
    repo = _get_repo()
    messages = repo.search_messages(query, limit=limit)
    return [msg.to_dict() for msg in messages]


def get_conversation_transcript() -> str:
    """Get the full conversation as formatted text."""
    lines = []
    for msg in _conversation_buffer:
        speaker = "You" if msg["speaker"] == "user" else "Assistant"
        lines.append(f"{speaker}: {msg['text']}")
    return "\n\n".join(lines)


def get_conversation_summary() -> str:
    """Get a brief summary of the conversation (last few exchanges)."""
    if not _conversation_buffer:
        return "No conversation yet."

    # Get last 6 messages for summary
    recent = _conversation_buffer[-6:]
    lines = []
    for msg in recent:
        speaker = "You" if msg["speaker"] == "user" else "Assistant"
        # Truncate long messages
        text = msg["text"][:200] + "..." if len(msg["text"]) > 200 else msg["text"]
        lines.append(f"{speaker}: {text}")

    return "\n".join(lines)


# =============================================================================
# TOOL FUNCTIONS
# =============================================================================

def save_conversation(params: Dict[str, Any]) -> str:
    """
    Save the current conversation to a bubble's canvas.

    Called when user says things like:
    - "Save this conversation"
    - "Add our discussion to my canvas"
    - "Keep this conversation in Universe A"

    Args (via params):
        bubble_name: Name of bubble to save to (e.g. "Research Hub")
        bubble_id: ID of bubble (optional, uses current if not provided)
        title: Custom title for the conversation node (optional)
        save_full: If true, save full transcript; otherwise save summary (default: false)

    Returns:
        Confirmation message
    """
    bubble_name = params.get("bubble_name", "").strip()
    bubble_id = params.get("bubble_id")
    title = params.get("title", "").strip()
    save_full = params.get("save_full", False)

    if not _conversation_buffer:
        return "There's no conversation to save yet. Let's chat first!"

    if not bubble_name and not bubble_id:
        return "Which bubble should I save this to? Say the bubble name like 'Research Hub' or 'Universe A'."

    # Prepare content
    if save_full:
        content = get_conversation_transcript()
        node_title = title or f"Conversation - {_conversation_started.strftime('%Y-%m-%d %H:%M') if _conversation_started else 'Today'}"
    else:
        content = get_conversation_summary()
        node_title = title or f"Discussion Summary - {datetime.now().strftime('%H:%M')}"

    # Save to database
    canvas_repo = CanvasRepository()
    metadata = {
        "bubble_id": bubble_id,
        "bubble_name": bubble_name,
        "content_extra": {
            "conversation_type": "full" if save_full else "summary",
            "message_count": len(_conversation_buffer),
            "started": _conversation_started.isoformat() if _conversation_started else None
        }
    }

    node = canvas_repo.create_node(
        node_type="note",
        title=node_title,
        content=content,
        x=100 + __import__("random").random() * 300,
        y=100 + __import__("random").random() * 200,
        metadata=metadata
    )

    # Broadcast to Electron
    _broadcast_to_electron({
        "type": "tool_add_node",
        "bubble_name": bubble_name,
        "bubble_id": bubble_id,
        "node": {
            "type": "note",
            "position": {"x": node.x, "y": node.y},
            "content": {
                "title": node_title,
                "text": content
            }
        }
    })

    bubble_label = bubble_name or f"bubble {bubble_id}"
    return f"Saved {'full transcript' if save_full else 'summary'} to {bubble_label}."


def save_summary(params: Dict[str, Any]) -> str:
    """
    Save a conversation summary to canvas.

    Shorthand for save_conversation with save_full=False.

    Args (via params):
        bubble_name: Name of bubble
        title: Custom title (optional)

    Returns:
        Confirmation message
    """
    params["save_full"] = False
    return save_conversation(params)


def extract_key_points(params: Dict[str, Any]) -> str:
    """
    Extract and save key points from the conversation.

    Called when user says things like:
    - "What were the main points we discussed?"
    - "Summarize the key takeaways"
    - "Extract the important points"

    Args (via params):
        bubble_name: Name of bubble to save to (optional - just returns points if not provided)

    Returns:
        List of key points, optionally saved to canvas
    """
    if not _conversation_buffer:
        return "We haven't discussed anything yet."

    # Extract key points by looking for user statements
    key_points = []
    for msg in _conversation_buffer:
        if msg["speaker"] == "user":
            text = msg["text"].strip()
            # Filter out short messages and questions
            if len(text) > 20 and not text.endswith("?"):
                # Truncate if too long
                point = text[:150] + "..." if len(text) > 150 else text
                key_points.append(point)

    if not key_points:
        return "I didn't find any clear key points in our discussion."

    # Limit to top 5
    key_points = key_points[-5:]

    bubble_name = params.get("bubble_name", "").strip()

    if bubble_name:
        # Save as a structured note
        content = "Key Points:\n" + "\n".join(f"• {p}" for p in key_points)

        canvas_repo = CanvasRepository()
        node = canvas_repo.create_node(
            node_type="note",
            title="Key Points",
            content=content,
            x=100 + __import__("random").random() * 300,
            y=100 + __import__("random").random() * 200,
            metadata={
                "bubble_name": bubble_name,
                "content_extra": {"point_count": len(key_points)}
            }
        )

        _broadcast_to_electron({
            "type": "tool_add_node",
            "bubble_name": bubble_name,
            "node": {
                "type": "note",
                "position": {"x": node.x, "y": node.y},
                "content": {"title": "Key Points", "text": content}
            }
        })

        return f"Extracted {len(key_points)} key points and saved to {bubble_name}."

    # Just return the points
    points_text = ", ".join(f"{i+1}. {p[:50]}..." for i, p in enumerate(key_points))
    return f"Key points from our discussion: {points_text}"


def create_idea_from_discussion(params: Dict[str, Any]) -> str:
    """
    Create a new idea from the current discussion.

    Called when user says things like:
    - "This is a good idea, save it"
    - "Create an idea from what we discussed"
    - "That's worth capturing as an idea"

    Args (via params):
        title: Title for the idea (required)
        description: Description override (optional - uses conversation if not provided)

    Returns:
        Confirmation with idea details
    """
    title = params.get("title", "").strip()

    if not title:
        return "What should I call this idea? Give me a title."

    # Use provided description or extract from conversation
    description = params.get("description", "").strip()
    if not description and _conversation_buffer:
        # Use the last few user messages as description
        user_messages = [m["text"] for m in _conversation_buffer if m["speaker"] == "user"]
        description = " ".join(user_messages[-3:])[:500]

    # Create the idea
    ideas_repo = IdeasRepository()
    idea = ideas_repo.create(
        title=title,
        description=description,
        source="conversation",
        tags=["from-voice"]
    )

    return f"Created idea '{idea.title}'. You can find it in your ideas list or promote it to a project later."


def add_to_current_bubble(params: Dict[str, Any]) -> str:
    """
    Add content to the currently active bubble.

    Called when user says things like:
    - "Add this to the canvas"
    - "Put that here"
    - "Save this note"

    Args (via params):
        content_type: "note", "summary", or "transcript" (default: "note")
        text: Custom text to add (for note type)

    Returns:
        Confirmation message
    """
    content_type = params.get("content_type", "note")
    text = params.get("text", "").strip()

    if content_type == "summary":
        if not _conversation_buffer:
            return "No conversation to summarize."
        text = get_conversation_summary()
        title = "Summary"
    elif content_type == "transcript":
        if not _conversation_buffer:
            return "No conversation to save."
        text = get_conversation_transcript()
        title = "Transcript"
    else:
        if not text:
            return "What should I add to the canvas?"
        title = "Note"

    # Save to database (without specific bubble - Electron will use current)
    canvas_repo = CanvasRepository()
    node = canvas_repo.create_node(
        node_type="note",
        title=title,
        content=text,
        x=100 + __import__("random").random() * 300,
        y=100 + __import__("random").random() * 200,
        metadata={"source": "conversation"}
    )

    # Broadcast to Electron (it will add to current bubble)
    _broadcast_to_electron({
        "type": "tool_add_to_current_bubble",
        "node": {
            "type": "note",
            "position": {"x": node.x, "y": node.y},
            "content": {"title": title, "text": text}
        }
    })

    return f"Added {content_type} to the canvas."


# =============================================================================
# TOOL REGISTRY
# =============================================================================

CONVERSATION_TOOLS = {
    "save_conversation": save_conversation,
    "save_summary": save_summary,
    "extract_key_points": extract_key_points,
    "create_idea_from_discussion": create_idea_from_discussion,
    "add_to_current_bubble": add_to_current_bubble,
}


def register_conversation_tools(tools_manager) -> None:
    """
    Register conversation tools with the ClientToolsManager (with observer logging).

    Args:
        tools_manager: ClientToolsManager instance
    """
    print("Registering conversation tools with observer...")
    for tool_name, tool_func in CONVERSATION_TOOLS.items():
        tools_manager.register_with_observer(tool_name, tool_func)
        print(f"  - {tool_name}")


__all__ = [
    # Session management
    "start_session",
    "end_session",
    "get_current_session_id",
    # Message recording
    "record_message",
    "clear_conversation",
    # Transcript access
    "get_conversation_transcript",
    "get_conversation_summary",
    # History (supermemory)
    "get_session_history",
    "search_conversation_history",
    # Tool functions
    "save_conversation",
    "save_summary",
    "extract_key_points",
    "create_idea_from_discussion",
    "add_to_current_bubble",
    # Registry
    "CONVERSATION_TOOLS",
    "register_conversation_tools",
]
