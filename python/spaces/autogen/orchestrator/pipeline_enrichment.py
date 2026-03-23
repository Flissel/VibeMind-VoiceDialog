"""
Pipeline Enrichment — Multi-turn voice/chat dialog to enrich the task description
before starting the HybridPipeline.

Rachel asks clarifying questions to build a complete spec:
1. What does the team do? (already from user)
2. What data sources? (CRM, API, CSV, DB?)
3. What output format? (Report, Email, Dashboard?)
4. Any specific tools/MCP servers?
5. Confirmation before pipeline start

Works with both Voice (Rachel) and Chat (ClawPort).
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default MCP servers always available
DEFAULT_MCP_SERVERS = [
    {"name": "context7", "description": "Library documentation lookup (AutoGen, FastAPI, etc.)"},
    {"name": "web_fetch", "description": "Fetch and read web pages"},
    {"name": "filesystem", "description": "Read/write local files"},
]

# Questions Rachel asks (in order)
ENRICHMENT_QUESTIONS = [
    {
        "id": "data_sources",
        "question": "Was fuer Datenquellen soll das Team nutzen? Z.B. API, Datenbank, CSV, Web-Scraping?",
        "question_en": "What data sources? API, database, CSV, web scraping?",
        "extract_key": "data_sources",
        "skip_if": ["datenquelle", "datenbank", "api", "csv", "scrape", "web"],
    },
    {
        "id": "output_format",
        "question": "Was soll der Output sein? Report, Email, Dashboard, JSON-API?",
        "question_en": "What output? Report, email, dashboard, JSON API?",
        "extract_key": "output_format",
        "skip_if": ["report", "email", "dashboard", "json", "pdf", "bericht"],
    },
    {
        "id": "mcp_servers",
        "question": "Sollen spezielle Tools aktiviert werden? Wir haben: brave-search (Web-Suche), postgres (Datenbank), context7 (Doku-Lookup). Oder soll ich automatisch auswaehlen?",
        "question_en": "Any specific MCP tools? brave-search, postgres, context7? Or auto-select?",
        "extract_key": "mcp_hint",
        "skip_if": ["brave", "postgres", "mcp", "tool", "server"],
    },
]


def needs_enrichment(task_description: str) -> bool:
    """Check if the task description is detailed enough or needs clarification."""
    words = task_description.split()

    # Short descriptions (< 8 words) always need enrichment
    if len(words) < 8:
        return True

    # If user already mentioned specific details, skip enrichment
    detail_indicators = [
        "agent", "datenbank", "api", "report", "email", "csv",
        "postgres", "brave", "mcp", "tool", "dashboard",
        "pdf", "json", "webhook", "scrape", "fetch",
    ]
    detail_count = sum(1 for w in task_description.lower().split()
                       if any(d in w for d in detail_indicators))

    # If 3+ detail words found, user knows what they want
    return detail_count < 3


def get_next_question(task_description: str, answered: Dict[str, str]) -> Optional[Dict]:
    """Get the next unanswered question, skipping if already covered."""
    text_lower = task_description.lower()

    for q in ENRICHMENT_QUESTIONS:
        if q["id"] in answered:
            continue

        # Skip if task description already contains relevant keywords
        if any(kw in text_lower for kw in q["skip_if"]):
            continue

        return q

    return None  # All questions answered or skipped


def build_enriched_description(
    original_task: str,
    answers: Dict[str, str],
) -> str:
    """Combine original task + answers into a rich task description."""
    parts = [original_task]

    if answers.get("data_sources"):
        parts.append(f"Datenquellen: {answers['data_sources']}")

    if answers.get("output_format"):
        parts.append(f"Output: {answers['output_format']}")

    if answers.get("mcp_hint"):
        parts.append(f"Tools: {answers['mcp_hint']}")

    return ". ".join(parts)


def build_confirmation_message(
    original_task: str,
    answers: Dict[str, str],
) -> str:
    """Build a human-readable confirmation before pipeline start."""
    lines = [f"Ich starte die Pipeline mit:"]
    lines.append(f"  Aufgabe: {original_task}")

    if answers.get("data_sources"):
        lines.append(f"  Datenquellen: {answers['data_sources']}")
    if answers.get("output_format"):
        lines.append(f"  Output: {answers['output_format']}")
    if answers.get("mcp_hint"):
        lines.append(f"  Tools: {answers['mcp_hint']}")
    else:
        lines.append(f"  Tools: context7, web_fetch, filesystem (Standard)")

    lines.append("Soll ich loslegen?")
    return "\n".join(lines)


class PipelineEnrichment:
    """Manages the multi-turn enrichment conversation."""

    def __init__(self):
        self._active_sessions: Dict[str, Dict] = {}

    def start_session(self, session_id: str, task_description: str) -> Dict[str, Any]:
        """Start enrichment for a new pipeline request.

        Returns either:
        - {"action": "ask", "question": "..."} — need more info
        - {"action": "ready", "enriched_task": "..."} — ready to start
        """
        if not needs_enrichment(task_description):
            return {
                "action": "ready",
                "enriched_task": task_description,
                "confirmation": build_confirmation_message(task_description, {}),
            }

        session = {
            "task": task_description,
            "answers": {},
            "state": "asking",
        }
        self._active_sessions[session_id] = session

        next_q = get_next_question(task_description, {})
        if next_q:
            return {"action": "ask", "question": next_q["question"], "question_id": next_q["id"]}
        else:
            return {
                "action": "ready",
                "enriched_task": task_description,
                "confirmation": build_confirmation_message(task_description, {}),
            }

    def answer(self, session_id: str, answer_text: str) -> Dict[str, Any]:
        """Process user's answer and return next question or ready state."""
        session = self._active_sessions.get(session_id)
        if not session:
            return {"action": "error", "message": "No active enrichment session"}

        # Find which question we're answering
        next_q = get_next_question(session["task"], session["answers"])
        if next_q:
            session["answers"][next_q["extract_key"]] = answer_text

        # Check if more questions needed
        next_q = get_next_question(session["task"], session["answers"])
        if next_q:
            return {"action": "ask", "question": next_q["question"], "question_id": next_q["id"]}

        # All questions answered — build enriched task
        enriched = build_enriched_description(session["task"], session["answers"])
        confirmation = build_confirmation_message(session["task"], session["answers"])

        session["state"] = "confirming"
        session["enriched_task"] = enriched

        return {
            "action": "confirm",
            "enriched_task": enriched,
            "confirmation": confirmation,
        }

    def confirm(self, session_id: str, confirmed: bool = True) -> Dict[str, Any]:
        """User confirmed — return enriched task or cancel."""
        session = self._active_sessions.pop(session_id, None)
        if not session:
            return {"action": "error", "message": "No active session"}

        if confirmed:
            return {"action": "ready", "enriched_task": session.get("enriched_task", session["task"])}
        else:
            return {"action": "cancelled"}

    def cancel(self, session_id: str):
        """Cancel enrichment session."""
        self._active_sessions.pop(session_id, None)


# Singleton
_enrichment = PipelineEnrichment()


def get_pipeline_enrichment() -> PipelineEnrichment:
    return _enrichment
