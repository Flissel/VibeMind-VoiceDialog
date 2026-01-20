"""
Adapted Bubble Tools for AutoGen Swarm

Typed wrappers around the original Dict-based bubble tools.
These can be used directly as FunctionTool in AssistantAgent.
"""

from typing import Optional
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def list_bubbles() -> str:
    """
    List all spaces/bubbles in the multiverse.

    Returns:
        Formatted list of bubbles with scores
    """
    from tools.bubble_tools import list_bubbles as _list_bubbles
    return _list_bubbles({})


def create_bubble(title: str = None, description: str = "") -> str:
    """
    Create a new bubble/space in the multiverse.

    Args:
        title: Name for the new space (required)
        description: Optional description

    Returns:
        Confirmation message
    """
    if not title:
        return "Fehler: Kein Space-Name angegeben. Bitte sag mir wie der neue Space heissen soll."
    from tools.bubble_tools import create_bubble as _create_bubble
    return _create_bubble({"title": title, "description": description})


def enter_bubble(bubble_name: str = None) -> str:
    """
    Enter a bubble/space to work on ideas inside it.

    Args:
        bubble_name: Name of the bubble to enter

    Returns:
        Confirmation message
    """
    if not bubble_name:
        return "Fehler: Kein Space-Name angegeben. Bitte sag mir welchen Space du betreten moechtest."
    from tools.bubble_tools import enter_bubble as _enter_bubble
    return _enter_bubble({"bubble_name": bubble_name})


def exit_bubble() -> str:
    """
    Exit current bubble and return to multiverse view.

    Returns:
        Confirmation message
    """
    from tools.bubble_tools import exit_bubble as _exit_bubble
    return _exit_bubble({})


def delete_bubble(bubble_name: str = None) -> str:
    """
    Delete a bubble/space and all its content.

    Args:
        bubble_name: Name of bubble to delete

    Returns:
        Confirmation message
    """
    if not bubble_name:
        return "Fehler: Kein Space-Name angegeben. Bitte sag mir welchen Space du loeschen moechtest."
    from tools.bubble_tools import delete_bubble as _delete_bubble
    return _delete_bubble({"bubble_name": bubble_name})


def get_bubble_stats(bubble_name: str = "") -> str:
    """
    Get statistics about a bubble (note count, connections, score).

    Args:
        bubble_name: Name of bubble to check (optional, uses current if empty)

    Returns:
        Statistics string
    """
    from tools.bubble_tools import get_bubble_stats as _get_bubble_stats
    return _get_bubble_stats({"bubble_name": bubble_name})


def score_bubble(bubble_name: str = "") -> str:
    """
    Calculate and update bubble score based on content richness.

    Args:
        bubble_name: Name of bubble to score (optional, uses current if empty)

    Returns:
        Score breakdown
    """
    from tools.bubble_tools import score_bubble as _score_bubble
    return _score_bubble({"bubble_name": bubble_name})


def evaluate_bubble_evolution(bubble_name: str = "") -> str:
    """
    Evaluate how evolved/complete a bubble's ideas are using AI analysis.

    Args:
        bubble_name: Name of bubble to evaluate (optional, uses current if empty)

    Returns:
        AI evaluation with scores and recommendations
    """
    from tools.bubble_tools import evaluate_bubble_evolution as _evaluate
    return _evaluate({"bubble_name": bubble_name})


def promote_bubble(bubble_name: str = "") -> str:
    """
    Promote a bubble/idea to a project.

    Args:
        bubble_name: Name of bubble to promote (optional, uses current if empty)

    Returns:
        Confirmation message
    """
    from tools.bubble_tools import promote_bubble as _promote_bubble
    return _promote_bubble({"bubble_name": bubble_name})


def update_bubble(bubble_name: str = "", new_title: str = "", new_description: str = "") -> str:
    """
    Update a bubble's title or description.

    Voice triggers: "Benenne den Space um", "Aendere den Namen zu X",
                   "Update den Bubble-Namen"

    Args:
        bubble_name: Current name of the bubble (optional - uses current if empty)
        new_title: New title for the bubble
        new_description: New description for the bubble

    Returns:
        Confirmation message
    """
    if not new_title and not new_description:
        return "Fehler: Bitte sag mir den neuen Namen oder die neue Beschreibung."
    from tools.bubble_tools import update_bubble as _update_bubble
    return _update_bubble({
        "bubble_name": bubble_name,
        "new_title": new_title,
        "new_description": new_description
    })


# Collect all tools for export
BUBBLE_TOOLS = [
    list_bubbles,
    create_bubble,
    enter_bubble,
    exit_bubble,
    delete_bubble,
    get_bubble_stats,
    score_bubble,
    evaluate_bubble_evolution,
    promote_bubble,
    update_bubble,
]


__all__ = [
    "list_bubbles",
    "create_bubble",
    "enter_bubble",
    "exit_bubble",
    "delete_bubble",
    "get_bubble_stats",
    "score_bubble",
    "evaluate_bubble_evolution",
    "promote_bubble",
    "update_bubble",
    "BUBBLE_TOOLS",
]
