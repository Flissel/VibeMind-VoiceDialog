"""
Exploration Tools - Voice-callable tools for AI-Scientist-style idea exploration.

MIGRATED TO: spaces/ideas/tools/exploration_tools.py
This file re-exports for backward compatibility.
"""

# Re-export everything from new location
from spaces.ideas.tools.exploration_tools import (
    # Core exploration functions
    start_exploration,
    stop_exploration,
    get_exploration_status,
    accept_connection,
    reject_connection,
    explore_deeper,
    visualize_exploration,
    respond_to_exploration_question,
    set_exploration_direction,
    # Paper/Research functions
    parse_bubble_content_for_paper,
    generate_requirements_from_sections,
    optimize_paper_coherence,
    generate_complete_research_paper,
    explore_bubble_complete,
    conduct_autogen_research,
    # Registry
    get_exploration_tools,
    EXPLORATION_TOOLS,
)

__all__ = [
    "start_exploration",
    "stop_exploration",
    "get_exploration_status",
    "accept_connection",
    "reject_connection",
    "explore_deeper",
    "visualize_exploration",
    "respond_to_exploration_question",
    "set_exploration_direction",
    "parse_bubble_content_for_paper",
    "generate_requirements_from_sections",
    "optimize_paper_coherence",
    "generate_complete_research_paper",
    "explore_bubble_complete",
    "conduct_autogen_research",
    "get_exploration_tools",
    "EXPLORATION_TOOLS",
]
