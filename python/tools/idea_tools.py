"""
Note/Canvas Content Management Tools

MIGRATED TO: spaces/ideas/tools/idea_tools.py
This file re-exports for backward compatibility.
"""

import logging

logger = logging.getLogger(__name__)

# Re-export everything from new location
from spaces.ideas.tools.idea_tools import (
    # Core idea tools
    list_ideas,
    count_ideas,
    create_idea,
    add_image,
    find_idea,
    update_idea,
    classify_idea,
    delete_idea,
    get_current_space,
    # Connection tools
    connect_ideas,
    disconnect_ideas,
    connect_ideas_multi,
    link_idea_to_root,
    # AI-powered tools
    expand_ideas,
    auto_link_ideas,
    analyze_and_suggest_links,
    explain_idea,
    # Movement
    move_idea,
    # Formatting
    format_idea_as_table,
    # Registry
    IDEA_TOOLS,
    register_idea_tools,
    # Helpers
    _fuzzy_find_idea,
    _get_available_idea_names,
    calculate_spiral_position,
)

__all__ = [
    "list_ideas",
    "count_ideas",
    "create_idea",
    "add_image",
    "find_idea",
    "update_idea",
    "classify_idea",
    "connect_ideas",
    "disconnect_ideas",
    "connect_ideas_multi",
    "link_idea_to_root",
    "delete_idea",
    "get_current_space",
    "expand_ideas",
    "move_idea",
    "auto_link_ideas",
    "analyze_and_suggest_links",
    "explain_idea",
    "format_idea_as_table",
    "IDEA_TOOLS",
    "register_idea_tools",
    "_fuzzy_find_idea",
    "_get_available_idea_names",
    "calculate_spiral_position",
]
