"""
Question Answer Tools for Rachel.

Allows Rachel to submit user's answers back to waiting backend agents.

Flow:
    Backend Agent asks question → QuestionQueue → Rachel sees in context
    Rachel asks user → User answers → Rachel calls answer_question()
    Answer published to events:answers → Backend receives and continues
"""

import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def answer_question_async(
    job_id: str,
    answer: str,
    selected_option: Optional[str] = None
) -> str:
    """
    Submit user's answer to a pending question.

    Args:
        job_id: The job ID that asked the question
        answer: User's answer text
        selected_option: If options were provided, which was selected

    Returns:
        Confirmation message
    """
    try:
        from swarm.event_bus import get_event_bus, SwarmEvent

        bus = get_event_bus()

        event = SwarmEvent(
            stream="events:answers",  # Backend listens here
            event_type="question.answered",
            payload={
                "answer": answer,
                "selected_option": selected_option,
            },
            job_id=job_id
        )

        await bus.publish(event)
        logger.info(f"[AnswerTool] Submitted answer for job={job_id}: {answer[:50]}...")

        return f"Antwort übermittelt: {answer}"

    except Exception as e:
        logger.error(f"[AnswerTool] Error submitting answer: {e}")
        return f"Fehler beim Übermitteln der Antwort: {e}"


def answer_question(params: Dict[str, Any]) -> str:
    """
    Synchronous wrapper for ElevenLabs ClientTools.

    Args:
        params: Dict with job_id, answer, optional selected_option

    Returns:
        Confirmation message
    """
    job_id = params.get("job_id", "")
    answer = params.get("answer", "")
    selected_option = params.get("selected_option")

    if not job_id:
        return "Fehler: Keine Job-ID angegeben."

    if not answer:
        return "Fehler: Keine Antwort angegeben."

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(
                        answer_question_async(job_id, answer, selected_option)
                    )
                )
                return future.result(timeout=30)
        return loop.run_until_complete(
            answer_question_async(job_id, answer, selected_option)
        )
    except RuntimeError:
        return asyncio.run(
            answer_question_async(job_id, answer, selected_option)
        )


# ElevenLabs Tool Definition
ANSWER_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "answer_question",
        "description": (
            "Submit the user's answer to a pending system question. "
            "Use when the system asked a clarification question and the user responded."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "Job ID from the question (shown in [job=xxx])"
                },
                "answer": {
                    "type": "string",
                    "description": "The user's answer to the question"
                },
                "selected_option": {
                    "type": "string",
                    "description": "If options were provided, which one was selected"
                }
            },
            "required": ["job_id", "answer"]
        }
    }
}


__all__ = [
    "answer_question",
    "answer_question_async",
    "ANSWER_TOOL_DEFINITION",
]
