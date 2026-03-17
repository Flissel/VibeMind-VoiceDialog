"""
Roarboot Tools - Voice-controllable tools for Rowboat integration

Each tool wraps a RoarbootClient method and returns a
VibeMind-standard result dict with broadcast to Electron.
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _broadcast_to_electron(message: Dict[str, Any]):
    """Broadcast message to Electron UI."""
    try:
        print(json.dumps(message), flush=True)
    except Exception as e:
        logger.error(f"Broadcast error: {e}")


def _broadcast_conversation_update(client, context: str):
    """Broadcast conversation URL to Electron for iframe sync."""
    conversations = client.list_conversations()
    conversation_id = conversations.get(context)
    if conversation_id and client.project_id:
        _broadcast_to_electron({
            "type": "roarboot_conversation_update",
            "conversation_id": conversation_id,
            "project_id": client.project_id,
            "context": context,
        })


def search_knowledge(query: str) -> Dict[str, Any]:
    """
    Search the Rowboat knowledge graph.

    Args:
        query: Search query

    Returns:
        VibeMind result dict
    """
    from .roarboot_client import get_roarboot_client

    logger.info(f"roarboot.search: query='{query}'")
    client = get_roarboot_client()
    result = client.search_knowledge(query)

    _broadcast_to_electron({
        "type": "roarboot_result",
        "action": "search",
        "query": query,
        "result": result.get("response", ""),
    })
    _broadcast_conversation_update(client, "search")

    return {
        "success": result.get("success", False),
        "message": result.get("response", "No results."),
        "response_hint": result.get("response", "I couldn't find anything.")[:200],
    }


def query_knowledge(subject: str, question: str = None) -> Dict[str, Any]:
    """
    Query knowledge about a person, project, or topic.

    Args:
        subject: Subject to query about
        question: Optional specific question

    Returns:
        VibeMind result dict
    """
    from .roarboot_client import get_roarboot_client

    logger.info(f"roarboot.query: subject='{subject}', question='{question}'")
    client = get_roarboot_client()
    result = client.query_knowledge(subject, question)

    _broadcast_to_electron({
        "type": "roarboot_result",
        "action": "query",
        "subject": subject,
        "result": result.get("response", ""),
    })
    _broadcast_conversation_update(client, "query")

    return {
        "success": result.get("success", False),
        "message": result.get("response", "No information found."),
        "response_hint": result.get("response", "I don't have information on that.")[:200],
    }


def draft_email(recipient: str, topic: str, context: str = "") -> Dict[str, Any]:
    """
    Draft an email using Rowboat's knowledge context.

    Args:
        recipient: Recipient name/email
        topic: Email topic
        context: Additional context

    Returns:
        VibeMind result dict
    """
    from .roarboot_client import get_roarboot_client

    logger.info(f"roarboot.email_draft: to='{recipient}', topic='{topic}'")
    client = get_roarboot_client()
    result = client.draft_email(recipient, topic, context)

    _broadcast_to_electron({
        "type": "roarboot_result",
        "action": "email_draft",
        "recipient": recipient,
        "topic": topic,
        "result": result.get("response", ""),
    })
    _broadcast_conversation_update(client, "email")

    return {
        "success": result.get("success", False),
        "message": result.get("response", "Email draft could not be created."),
        "response_hint": f"I created an email draft to {recipient} about {topic}.",
    }


def generate_meeting_brief(meeting: str, participants: str = "") -> Dict[str, Any]:
    """
    Generate a meeting brief with relevant context.

    Args:
        meeting: Meeting description
        participants: Participant names

    Returns:
        VibeMind result dict
    """
    from .roarboot_client import get_roarboot_client

    logger.info(f"roarboot.meeting_brief: meeting='{meeting}'")
    client = get_roarboot_client()
    result = client.generate_meeting_brief(meeting, participants)

    _broadcast_to_electron({
        "type": "roarboot_result",
        "action": "meeting_brief",
        "meeting": meeting,
        "result": result.get("response", ""),
    })
    _broadcast_conversation_update(client, "meeting")

    return {
        "success": result.get("success", False),
        "message": result.get("response", "Meeting brief could not be created."),
        "response_hint": f"I prepared a meeting brief for {meeting}.",
    }


def generate_deck(topic: str, context: str = "") -> Dict[str, Any]:
    """
    Generate a presentation deck outline.

    Args:
        topic: Presentation topic
        context: Additional context

    Returns:
        VibeMind result dict
    """
    from .roarboot_client import get_roarboot_client

    logger.info(f"roarboot.deck: topic='{topic}'")
    client = get_roarboot_client()
    result = client.generate_deck(topic, context)

    _broadcast_to_electron({
        "type": "roarboot_result",
        "action": "deck",
        "topic": topic,
        "result": result.get("response", ""),
    })
    _broadcast_conversation_update(client, "deck")

    return {
        "success": result.get("success", False),
        "message": result.get("response", "Presentation could not be created."),
        "response_hint": f"I created a presentation about {topic}.",
    }


def process_voice_note(text: str) -> Dict[str, Any]:
    """
    Process a voice note and update the knowledge graph.

    Args:
        text: Voice note transcription

    Returns:
        VibeMind result dict
    """
    from .roarboot_client import get_roarboot_client

    logger.info(f"roarboot.voice_note: text='{text[:50]}...'")
    client = get_roarboot_client()
    result = client.process_voice_note(text)

    _broadcast_to_electron({
        "type": "roarboot_result",
        "action": "voice_note",
        "result": result.get("response", ""),
    })
    _broadcast_conversation_update(client, "voice_note")

    return {
        "success": result.get("success", False),
        "message": result.get("response", "Note could not be processed."),
        "response_hint": "I processed your note and updated the knowledge graph.",
    }


def get_status() -> Dict[str, Any]:
    """
    Check Rowboat connection status.

    Returns:
        VibeMind result dict
    """
    from .roarboot_client import get_roarboot_client

    logger.info("roarboot.status")
    client = get_roarboot_client()
    result = client.get_status()

    _broadcast_to_electron({
        "type": "roarboot_status",
        "status": result.get("status", "unknown"),
        "url": result.get("url", ""),
    })

    return {
        "success": result.get("success", False),
        "message": result.get("message", "Status unknown."),
        "response_hint": result.get("message", "Status unknown."),
    }


def open_webview(context: str = "default") -> Dict[str, Any]:
    """
    Signal Electron to show the Rowboat WebView.

    Opens the WebView navigated to the active conversation for the given
    context, or falls back to the base Rowboat URL if no conversation exists.

    Args:
        context: Conversation context key (e.g., "default", "search", "email")

    Returns:
        VibeMind result dict
    """
    from .roarboot_client import get_roarboot_client

    logger.info(f"roarboot.open: context={context}")
    client = get_roarboot_client()
    status = client.get_status()
    base_url = status.get("url", "http://localhost:3000")

    # Build conversation-specific URL if available
    conversations = client.list_conversations()
    conversation_id = conversations.get(context)
    if conversation_id and client.project_id:
        url = f"{base_url}/projects/{client.project_id}/conversations/{conversation_id}"
    else:
        url = base_url

    _broadcast_to_electron({
        "type": "roarboot_open_webview",
        "url": url,
        "conversation_id": conversation_id,
    })

    if status.get("success"):
        return {
            "success": True,
            "message": "Rowboat WebView opened.",
            "response_hint": "Opening Rowboat for you.",
        }
    else:
        return {
            "success": False,
            "message": f"Rowboat not reachable: {status.get('message', '')}",
            "response_hint": "Rowboat is not reachable. Is the Docker container started?",
        }


def reset_conversation(context: str = None) -> Dict[str, Any]:
    """
    Reset Rowboat conversation context.

    Args:
        context: Specific context to reset (e.g., "search", "email"),
                 or None to reset all conversations

    Returns:
        VibeMind result dict
    """
    from .roarboot_client import get_roarboot_client

    logger.info(f"roarboot.reset: context={context}")
    client = get_roarboot_client()

    active_before = len(client.list_conversations())
    client.reset_conversation(context)
    active_after = len(client.list_conversations())

    if context:
        msg = f"Roarboot conversation '{context}' reset."
    else:
        msg = f"All Roarboot conversations reset ({active_before} -> {active_after})."

    return {
        "success": True,
        "message": msg,
        "response_hint": "New conversation with Roarboot started.",
    }


__all__ = [
    "search_knowledge",
    "query_knowledge",
    "draft_email",
    "generate_meeting_brief",
    "generate_deck",
    "process_voice_note",
    "get_status",
    "open_webview",
    "reset_conversation",
]
