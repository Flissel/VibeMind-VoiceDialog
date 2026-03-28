"""
Builds Rowboat-compatible markdown notes from VibeMind data.

Notes follow the Rowboat knowledge graph template structure
(Projects, Topics) so the Graph Builder can auto-index them.

Wizard output files use _ prefix to distinguish from idea notes:
  _requirements.md, _stakeholders.md, _constraints.md, _techstack.md, _mirofish_eval.md
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

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


# ============================================
# Wizard Output Builders (underscore-prefixed files)
# ============================================

def _footer() -> str:
    return f"---\n*Auto-published by VibeMind on {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"


def build_requirements_note(title: str, requirements: List[Dict[str, Any]]) -> str:
    """Build _requirements.md from wizard step 2 output."""
    lines = [f"# {title} — Requirements", ""]

    if not requirements:
        lines.append("*No requirements defined yet.*")
        lines.append("")
        lines.append(_footer())
        return "\n".join(lines)

    lines.append(f"**Total:** {len(requirements)} requirements")
    lines.append("")

    for req in requirements:
        req_id = req.get("id", "REQ-???")
        req_title = req.get("title", "Untitled")
        priority = req.get("priority", "medium")
        status = req.get("status", "pending")
        desc = req.get("description", "")
        criteria = req.get("acceptance_criteria", [])
        stories = req.get("user_stories", [])

        lines.append(f"### {req_id}: {req_title}")
        lines.append(f"**Priority:** {priority} | **Status:** {status}")
        lines.append("")
        if desc:
            lines.append(desc)
            lines.append("")
        if criteria:
            lines.append("**Acceptance Criteria:**")
            for ac in criteria:
                lines.append(f"- [ ] {ac}")
            lines.append("")
        if stories:
            lines.append("**User Stories:**")
            for us in stories:
                lines.append(f"- {us}")
            lines.append("")

    lines.append(_footer())
    return "\n".join(lines)


def build_stakeholders_note(title: str, stakeholders: List[Dict[str, Any]]) -> str:
    """Build _stakeholders.md from wizard step 2 output."""
    lines = [f"# {title} — Stakeholders", ""]

    if not stakeholders:
        lines.append("*No stakeholders defined yet.*")
        lines.append("")
        lines.append(_footer())
        return "\n".join(lines)

    for sh in stakeholders:
        role = sh.get("role", sh.get("name", "Unknown"))
        lines.append(f"### {role}")
        if sh.get("name") and sh.get("role"):
            lines.append(f"**Name:** {sh['name']}")
        if sh.get("responsibilities"):
            lines.append(f"**Responsibilities:** {sh['responsibilities']}")
        if sh.get("interests"):
            lines.append(f"**Interests:** {sh['interests']}")
        if sh.get("influence"):
            lines.append(f"**Influence:** {sh['influence']}")
        lines.append("")

    lines.append(_footer())
    return "\n".join(lines)


def build_constraints_note(title: str, constraints: Dict[str, Any]) -> str:
    """Build _constraints.md from wizard step 3 output."""
    lines = [f"# {title} — Constraints", ""]

    if not constraints:
        lines.append("*No constraints defined yet.*")
        lines.append("")
        lines.append(_footer())
        return "\n".join(lines)

    # Categorized constraint lists
    for category in ("technical", "regulatory", "mirofish_gaps"):
        items = constraints.get(category, [])
        if items:
            label = category.replace("_", " ").title()
            lines.append(f"## {label}")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")

    # Scalar constraints
    for key in ("budget", "timeline", "team_size"):
        val = constraints.get(key)
        if val:
            lines.append(f"**{key.replace('_', ' ').title()}:** {val}")

    lines.append("")
    lines.append(_footer())
    return "\n".join(lines)


def build_techstack_note(
    title: str, techstack: Dict[str, Any], work_division: str = ""
) -> str:
    """Build _techstack.md from wizard step 4 output."""
    lines = [f"# {title} — Tech Stack", ""]

    if not techstack and not work_division:
        lines.append("*No tech stack defined yet.*")
        lines.append("")
        lines.append(_footer())
        return "\n".join(lines)

    if work_division:
        lines.append(f"**Work Division:** {work_division}")
        lines.append("")

    # Render techstack dict — keys are categories, values are choices
    for key, val in techstack.items():
        if isinstance(val, list):
            lines.append(f"## {key.replace('_', ' ').title()}")
            for item in val:
                lines.append(f"- {item}")
            lines.append("")
        elif isinstance(val, dict):
            lines.append(f"## {key.replace('_', ' ').title()}")
            for k, v in val.items():
                lines.append(f"- **{k}:** {v}")
            lines.append("")
        else:
            lines.append(f"**{key.replace('_', ' ').title()}:** {val}")
            lines.append("")

    lines.append(_footer())
    return "\n".join(lines)


def build_mirofish_eval_note(title: str, eval_result: Dict[str, Any]) -> str:
    """Build _mirofish_eval.md from MiroFish evaluation output."""
    lines = [f"# {title} — MiroFish Evaluation", ""]

    if not eval_result:
        lines.append("*MiroFish evaluation not available.*")
        lines.append("")
        lines.append(_footer())
        return "\n".join(lines)

    total = eval_result.get("total_score", "?")
    prediction = eval_result.get("prediction", "UNKNOWN")
    lines.append(f"**Score:** {total}/100")
    lines.append(f"**Prediction:** {prediction}")
    lines.append("")

    # Per-agent breakdown
    agents = eval_result.get("per_agent_scores", {})
    if agents:
        lines.append("## Agent Scores")
        lines.append("")
        lines.append("| Agent | Score | Assessment |")
        lines.append("|-------|-------|------------|")
        for agent_name, data in agents.items():
            if isinstance(data, dict):
                score = data.get("score", "?")
                assessment = data.get("assessment", "").replace("\n", " ")[:80]
                lines.append(f"| {agent_name} | {score}/25 | {assessment} |")
            else:
                lines.append(f"| {agent_name} | {data} | — |")
        lines.append("")

    # Missing items
    missing = eval_result.get("missing_items", [])
    if missing:
        lines.append("## Missing Items")
        for item in missing:
            lines.append(f"- [ ] {item}")
        lines.append("")

    lines.append(_footer())
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
