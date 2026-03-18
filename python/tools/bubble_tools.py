"""
Bubble/Idea Management Tools

MIGRATED TO: spaces/ideas/tools/bubble_tools.py
This file re-exports for backward compatibility.
"""

import logging

logger = logging.getLogger(__name__)

# Re-export everything from new location
from spaces.ideas.tools.bubble_tools import (
    # Bubble management
    list_bubbles,
    find_bubble,
    create_bubble,
    update_bubble,
    get_bubble_stats,
    score_bubble,
    evaluate_bubble_evolution,
    promote_bubble,
    delete_bubble,
    delete_all_bubbles_except,
    enter_bubble,
    exit_bubble,
    # Utilities
    generate_bubble_embeddings,
    get_pending_agent_switch,
    get_current_bubble_db_id,
    get_current_bubble,
    # Registry
    BUBBLE_TOOLS,
    register_bubble_tools,
)

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
    "generate_bubble_embeddings",
    "get_pending_agent_switch",
    "get_current_bubble_db_id",
    "get_current_bubble",
    "BUBBLE_TOOLS",
    "register_bubble_tools",
]
