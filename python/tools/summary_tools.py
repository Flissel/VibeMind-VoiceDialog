"""
Summary Tools - Voice-callable summarization functions

MIGRATED TO: spaces/ideas/tools/summary_tools.py
This file re-exports for backward compatibility.
"""

import logging

logger = logging.getLogger(__name__)

# Re-export everything from new location
from spaces.ideas.tools.summary_tools import (
    # Client tools
    summarize_idea,
    list_summaries,
    get_summary,
    generate_white_paper,
    generate_project_structure,
    generate_feature_docs,
    submit_to_req_orchestrator,
    get_requirement_clarifications,
    sync_shuttle_from_orchestrator,
    create_stage_shuttles,
    # Helper functions
    _fetch_orchestrator_project_state,
    # Registry
    SUMMARY_TOOLS,
    register_summary_tools,
)

__all__ = [
    "summarize_idea",
    "list_summaries",
    "get_summary",
    "generate_white_paper",
    "generate_project_structure",
    "generate_feature_docs",
    "submit_to_req_orchestrator",
    "get_requirement_clarifications",
    "sync_shuttle_from_orchestrator",
    "create_stage_shuttles",
    "_fetch_orchestrator_project_state",
    "SUMMARY_TOOLS",
    "register_summary_tools",
]
