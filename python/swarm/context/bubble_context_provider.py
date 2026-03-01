"""
BubbleContextProvider - Provides current bubble context for classifiers.

This module provides synchronous access to the current bubble state,
including the bubble name and list of ideas within it.

This context is used by the RAG intent classifier to make better
classification decisions based on the current user context.
"""

import logging
import sys
from typing import Dict, Any, Optional, List
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


class BubbleContextProvider:
    """
    Provides synchronous access to current bubble state.

    This class queries the current bubble and its ideas to provide
    context for intent classification. The context helps the classifier
    make better decisions (e.g., knowing what ideas exist when user
    says "verlinke die Ideen").
    """

    def get_current_context(self) -> Dict[str, Any]:
        """
        Get current bubble context.

        Returns:
            Dict with:
            - bubble_id: Current bubble ID (or None if multiverse)
            - bubble_name: Bubble title
            - idea_titles: List of idea titles in bubble (max 10)
            - idea_count: Total number of ideas
        """
        try:
            # Import here to avoid circular imports
            from spaces.ideas.tools.idea_tools import _get_current_bubble_id, _get_bubble_info

            bubble_id = _get_current_bubble_id()

            if not bubble_id:
                return {
                    "bubble_id": None,
                    "bubble_name": "Multiverse-Ansicht",
                    "idea_titles": [],
                    "idea_count": 0,
                }

            # Get bubble info - try electron backend first, then database
            bubble_info = _get_bubble_info(bubble_id) or {}
            bubble_name = bubble_info.get("title")

            # Fallback to database lookup if electron backend doesn't have the title
            if not bubble_name:
                try:
                    from data import IdeasRepository
                    idea_repo = IdeasRepository()
                    idea = idea_repo.get(bubble_id)
                    if idea:
                        bubble_name = idea.title
                except Exception as db_err:
                    logger.debug(f"[BubbleContextProvider] DB lookup failed: {db_err}")

            # Final fallback to ID if nothing found
            if not bubble_name:
                bubble_name = f"Space {bubble_id[:8]}..."

            # Get ideas in bubble
            from data import CanvasRepository
            repo = CanvasRepository()
            all_nodes = repo.list_nodes(limit=1000)
            nodes = [n for n in all_nodes if n.linked_idea_id == bubble_id]
            idea_titles = [n.title for n in nodes if n.title][:10]  # Limit to 10

            context = {
                "bubble_id": bubble_id,
                "bubble_name": bubble_name,
                "idea_titles": idea_titles,
                "idea_count": len(nodes),
            }

            logger.debug(f"[BubbleContextProvider] Context: {bubble_name}, {len(nodes)} ideas")
            return context

        except Exception as e:
            logger.warning(f"[BubbleContextProvider] Failed to get context: {e}")
            return {
                "bubble_id": None,
                "bubble_name": "Unbekannt",
                "idea_titles": [],
                "idea_count": 0,
            }

    def get_all_bubbles_summary(self) -> list:
        """
        Get summary of all top-level bubbles (spaces) for LLM context.

        Returns:
            List of dicts with title, id, idea_count for each bubble.
        """
        try:
            from data import IdeasRepository, CanvasRepository
            repo = IdeasRepository()
            # Top-level ideas = bubbles (parent_id IS NULL)
            rows = repo.db.fetch_all(
                "SELECT * FROM ideas WHERE parent_id IS NULL ORDER BY created_at DESC LIMIT 20"
            )
            from data.models import Idea
            bubbles = [Idea.from_dict(dict(r)) for r in rows]

            # Count ideas per bubble
            canvas_repo = CanvasRepository()
            all_nodes = canvas_repo.list_nodes(limit=2000)

            result = []
            for b in bubbles:
                idea_count = sum(1 for n in all_nodes if n.linked_idea_id == b.id)
                idea_titles = [n.title for n in all_nodes if n.linked_idea_id == b.id and n.title][:5]
                result.append({
                    "title": b.title,
                    "id": b.id,
                    "idea_count": idea_count,
                    "idea_titles": idea_titles,
                })
            return result
        except Exception as e:
            logger.warning(f"[BubbleContextProvider] get_all_bubbles_summary failed: {e}")
            return []

    def format_for_prompt(self) -> str:
        """
        Get formatted context string for LLM prompt.

        Returns:
            Formatted string describing current context
        """
        ctx = self.get_current_context()

        if not ctx.get("bubble_id"):
            return "Aktueller Kontext: Multiverse-Ansicht (kein Space betreten)"

        ideas_str = ", ".join(ctx.get("idea_titles", []))[:200] or "keine"
        return (
            f"Aktueller Kontext:\n"
            f"- Space: {ctx.get('bubble_name')}\n"
            f"- Anzahl Ideen: {ctx.get('idea_count')}\n"
            f"- Ideen: {ideas_str}"
        )


# =============================================================================
# SINGLETON
# =============================================================================

_provider: Optional[BubbleContextProvider] = None


def get_bubble_context_provider() -> BubbleContextProvider:
    """Get or create the singleton BubbleContextProvider."""
    global _provider
    if _provider is None:
        _provider = BubbleContextProvider()
    return _provider


__all__ = ["BubbleContextProvider", "get_bubble_context_provider"]
