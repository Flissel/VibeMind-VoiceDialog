"""
Adapted Idea Tools for AutoGen Swarm

MIGRATED TO: spaces/ideas/adapted/idea_tools.py
This file re-exports for backward compatibility.
"""

# Re-export everything from new location
from spaces.ideas.adapted.idea_tools import (
    list_ideas,
    count_ideas,
    create_idea,
    add_image,
    find_idea,
    update_idea,
    delete_idea,
    move_idea,
    connect_ideas,
    disconnect_ideas,
    connect_ideas_multi,
    link_idea_to_root,
    classify_idea,
    get_current_space,
    auto_link_ideas,
    format_idea_as_table,
    summarize_idea,
    generate_white_paper,
    expand_ideas,
    analyze_and_suggest_links,
    explain_idea,
    IDEA_TOOLS,
)

__all__ = [
    "list_ideas",
    "count_ideas",
    "create_idea",
    "add_image",
    "find_idea",
    "update_idea",
    "delete_idea",
    "move_idea",
    "connect_ideas",
    "disconnect_ideas",
    "connect_ideas_multi",
    "link_idea_to_root",
    "classify_idea",
    "get_current_space",
    "auto_link_ideas",
    "format_idea_as_table",
    "summarize_idea",
    "generate_white_paper",
    "expand_ideas",
    "analyze_and_suggest_links",
    "explain_idea",
    "IDEA_TOOLS",
]
