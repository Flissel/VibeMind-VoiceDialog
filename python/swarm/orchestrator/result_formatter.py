"""
Result Formatter - Standalone functions for formatting tool results.

Extracted from IntentOrchestrator to reduce module size.
These functions are stateless and operate on plain data.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationResult:
    """Result of intent orchestration."""
    job_id: str
    event_type: str
    stream: str
    response_hint: str
    is_conversational: bool = False
    error: Optional[str] = None


def format_result_for_voice(event_type: str, result: Any) -> str:
    """Format tool result for natural voice output."""
    if result is None:
        return "Done."

    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        # Handle common result patterns
        if "message" in result:
            return result["message"]
        if "bubbles" in result:
            bubbles = result["bubbles"]
            if not bubbles:
                return "You don't have any Spaces yet."
            count = len(bubbles)
            names = [b.get("title", b.get("name", "Untitled")) for b in bubbles[:5]]
            if count <= 5:
                return f"You have {count} Spaces: {', '.join(names)}."
            return f"You have {count} Spaces. The first ones are: {', '.join(names)}."
        if "ideas" in result:
            ideas = result["ideas"]
            if not ideas:
                return "No ideas found."
            count = len(ideas)
            return f"I found {count} ideas."
        if "id" in result:
            # Created something
            return f"Done. ID: {result['id']}"

    if isinstance(result, list):
        if not result:
            return "No results found."
        return f"I found {len(result)} entries."

    return str(result)[:200]


def format_multi_step_result(results: List[Dict[str, Any]]) -> str:
    """
    Format multi-step results for voice output.

    Combines successful results into a natural summary.

    Args:
        results: List of step results

    Returns:
        Voice-friendly summary string
    """
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    parts = []

    if successful:
        # Take most meaningful results
        for r in successful:
            result_text = r.get("result", "")
            if result_text and result_text != "Done.":
                # Truncate long results
                if len(result_text) > 80:
                    result_text = result_text[:77] + "..."
                parts.append(result_text)
            else:
                parts.append(f"{r['event_type']} erledigt")

    if failed:
        fail_count = len(failed)
        parts.append(f"{fail_count} step{'s' if fail_count > 1 else ''} failed")

    if parts:
        # Join with natural connectors
        if len(parts) == 1:
            return parts[0]
        elif len(parts) == 2:
            return f"{parts[0]}. {parts[1]}."
        else:
            return ". ".join(parts[:3]) + "."

    return "Alle Schritte ausgefuehrt."


def enrich_with_task_context(response: str, event_type: str, task_memory=None) -> str:
    """Add task memory context to response if relevant."""
    if not task_memory or not hasattr(task_memory, 'get_task_context_string'):
        return response

    task_context = task_memory.get_task_context_string()
    if task_context:
        # Only add if not already mentioned
        if "aufgabe" not in response.lower() and "task" not in response.lower():
            return f"{response} ({task_context})"
    return response


async def store_supermemory_task_completed(
    job_id: str,
    event_type: str,
    result: str,
    duration_ms: int,
    session_id: str = None,
    sm_task_memory=None,
    sm_user_profile=None
) -> None:
    """Store task completion event to Supermemory (non-blocking)."""
    if sm_task_memory and sm_task_memory.is_available:
        try:
            await sm_task_memory.store_task_completed(
                task_id=job_id,
                intent_type=event_type,
                result=result,
                duration_ms=duration_ms,
                session_id=session_id
            )
        except Exception as e:
            logger.debug(f"[Supermemory] Failed to store task completed: {e}")

    # Track intent usage for user profile learning
    if sm_user_profile and sm_user_profile.is_available:
        try:
            await sm_user_profile.track_intent_usage(event_type)
        except Exception as e:
            logger.debug(f"[Supermemory] Failed to track intent usage: {e}")


async def store_supermemory_task_failed(
    job_id: str,
    event_type: str,
    error: str,
    session_id: str = None,
    sm_task_memory=None
) -> None:
    """Store task failure event to Supermemory (non-blocking)."""
    if sm_task_memory and sm_task_memory.is_available:
        try:
            await sm_task_memory.store_task_failed(
                task_id=job_id,
                intent_type=event_type,
                error=error,
                session_id=session_id
            )
        except Exception as e:
            logger.debug(f"[Supermemory] Failed to store task failed: {e}")
