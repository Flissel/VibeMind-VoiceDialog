"""
Index Mapping for Voice-Based Referencing

Stores {1: "uuid_abc", 2: "uuid_def"} mappings that persist between tool calls,
enabling users to reference items by number:
- "connect 3 and 4" -> connects ideas at indices 3 and 4
- "link 2 to 3, 4, 5" -> links idea 2 to ideas 3, 4, 5
- "geh in 2" -> enters bubble at index 2

The mapping is updated whenever list_ideas() or list_bubbles() is called.
"""
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class IndexMapping:
    """Stores current index-to-ID mappings for voice referencing."""

    # ID mappings: {1: "uuid", 2: "uuid", ...}
    ideas: Dict[int, str] = field(default_factory=dict)
    bubbles: Dict[int, str] = field(default_factory=dict)

    # Title mappings for display: {1: "API Design", 2: "Database"}
    idea_titles: Dict[int, str] = field(default_factory=dict)
    bubble_titles: Dict[int, str] = field(default_factory=dict)

    # Track which bubble the idea mapping is for
    current_bubble_id: Optional[str] = None


# Singleton instance
_mapping: Optional[IndexMapping] = None


def get_index_mapping() -> IndexMapping:
    """Get or create the IndexMapping singleton."""
    global _mapping
    if _mapping is None:
        _mapping = IndexMapping()
    return _mapping


def clear_index_mapping():
    """Clear all mappings (useful for testing)."""
    global _mapping
    _mapping = IndexMapping()


def set_idea_mapping(nodes: List[Any], bubble_id: Optional[str] = None):
    """
    Update idea mapping from list_ideas() result.

    Args:
        nodes: List of CanvasNode objects from list_ideas()
        bubble_id: Current bubble ID (for context tracking)
    """
    m = get_index_mapping()
    m.current_bubble_id = bubble_id
    m.ideas = {}
    m.idea_titles = {}

    for i, n in enumerate(nodes[:10], 1):
        m.ideas[i] = n.id
        title = n.title or (n.content[:30] if n.content else "Untitled")
        m.idea_titles[i] = title

    logger.debug(f"[IndexMapping] Set idea mapping: {len(m.ideas)} items for bubble {bubble_id}")


def set_bubble_mapping(bubbles: List[Any]):
    """
    Update bubble mapping from list_bubbles() result.

    Args:
        bubbles: List of Idea objects (bubbles) from list_bubbles()
    """
    m = get_index_mapping()
    m.bubbles = {}
    m.bubble_titles = {}

    for i, b in enumerate(bubbles[:10], 1):
        m.bubbles[i] = b.id
        m.bubble_titles[i] = b.title or "Untitled"

    logger.debug(f"[IndexMapping] Set bubble mapping: {len(m.bubbles)} items")


def resolve_idea_index(ref: str) -> Optional[str]:
    """
    Resolve a numeric reference to an idea ID.

    Args:
        ref: String like "3" or "3."

    Returns:
        The idea ID if found, None otherwise
    """
    ref_clean = ref.strip().rstrip('.')
    if ref_clean.isdigit():
        idx = int(ref_clean)
        idea_id = get_index_mapping().ideas.get(idx)
        if idea_id:
            logger.debug(f"[IndexMapping] Resolved idea index {idx} -> {idea_id[:8]}...")
        return idea_id
    return None


def resolve_bubble_index(ref: str) -> Optional[str]:
    """
    Resolve a numeric reference to a bubble ID.

    Args:
        ref: String like "2" or "2."

    Returns:
        The bubble ID if found, None otherwise
    """
    ref_clean = ref.strip().rstrip('.')
    if ref_clean.isdigit():
        idx = int(ref_clean)
        bubble_id = get_index_mapping().bubbles.get(idx)
        if bubble_id:
            logger.debug(f"[IndexMapping] Resolved bubble index {idx} -> {bubble_id[:8]}...")
        return bubble_id
    return None


def get_idea_title(index: int) -> Optional[str]:
    """Get the title of an idea by its index."""
    return get_index_mapping().idea_titles.get(index)


def get_bubble_title(index: int) -> Optional[str]:
    """Get the title of a bubble by its index."""
    return get_index_mapping().bubble_titles.get(index)


def get_available_idea_indices() -> List[int]:
    """Get list of available idea indices (1, 2, 3, ...)."""
    return sorted(get_index_mapping().ideas.keys())


def get_available_bubble_indices() -> List[int]:
    """Get list of available bubble indices (1, 2, 3, ...)."""
    return sorted(get_index_mapping().bubbles.keys())


def format_available_ideas() -> str:
    """Format available ideas for voice output."""
    m = get_index_mapping()
    if not m.idea_titles:
        return "No ideas available."
    items = [f"{i}. {title}" for i, title in sorted(m.idea_titles.items())]
    return ", ".join(items)


def format_available_bubbles() -> str:
    """Format available bubbles for voice output."""
    m = get_index_mapping()
    if not m.bubble_titles:
        return "No Spaces available."
    items = [f"{i}. {title}" for i, title in sorted(m.bubble_titles.items())]
    return ", ".join(items)
