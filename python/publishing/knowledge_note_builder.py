"""
Builds Rowboat-compatible markdown notes from VibeMind data.

Notes follow the Rowboat knowledge graph template structure
(Projects, Topics) so the Graph Builder can auto-index them.
"""

import logging
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


def build_project_note(
    title: str,
    project_type: str = "initiative",
    status: str = "active",
    summary: str = "",
    started: str = "",
    last_activity: str = "",
    key_facts: Optional[List[str]] = None,
    open_items: Optional[List[str]] = None,
    related_topics: Optional[List[str]] = None,
    source_space: str = "",
) -> str:
    """Build a Project knowledge note following Rowboat's template.

    Args:
        title: Project title
        project_type: Type (initiative, product, research, etc.)
        status: Current status (active, completed, paused, etc.)
        summary: Brief description
        started: Start date (YYYY-MM-DD)
        last_activity: Last activity date (YYYY-MM-DD)
        key_facts: List of notable facts/metrics
        open_items: List of open tasks/questions
        related_topics: List of related topic titles for cross-linking
        source_space: VibeMind space that generated this (ideas, swe_design, etc.)
    """
    logger.debug("build_project_note: title=%s status=%s", title, status)
    lines = [f"# {title}", ""]

    # Info section
    lines.append("## Info")
    lines.append(f"**Type:** {project_type}")
    lines.append(f"**Status:** {status}")
    if source_space:
        lines.append(f"**Source:** VibeMind {source_space}")
    if started:
        lines.append(f"**Started:** {started}")
    if last_activity:
        lines.append(f"**Last activity:** {last_activity}")
    lines.append("")

    # Summary
    if summary:
        lines.append("## Summary")
        lines.append(summary)
        lines.append("")

    # Related topics
    if related_topics:
        lines.append("## Related")
        for topic in related_topics:
            lines.append(f"- [[Topics/{topic}]]")
        lines.append("")

    # Key facts
    if key_facts:
        lines.append("## Key facts")
        for fact in key_facts:
            lines.append(f"- {fact}")
        lines.append("")

    # Open items
    if open_items:
        lines.append("## Open items")
        for item in open_items:
            lines.append(f"- [ ] {item}")
        lines.append("")
    else:
        lines.append("## Open items")
        lines.append("(none)")
        lines.append("")

    # Footer
    lines.append(f"---")
    lines.append(f"*Auto-published by VibeMind on {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")

    return "\n".join(lines)


def build_topic_note(
    title: str,
    description: str = "",
    related_projects: Optional[List[str]] = None,
) -> str:
    """Build a Topic knowledge note."""
    logger.debug("build_topic_note: title=%s", title)
    lines = [f"# {title}", ""]

    if description:
        lines.append("## Description")
        lines.append(description)
        lines.append("")

    if related_projects:
        lines.append("## Related projects")
        for proj in related_projects:
            lines.append(f"- [[Projects/{proj}]]")
        lines.append("")

    lines.append(f"---")
    lines.append(f"*Auto-published by VibeMind on {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")

    return "\n".join(lines)
