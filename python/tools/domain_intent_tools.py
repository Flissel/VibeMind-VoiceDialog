"""
Domain-Specific Intent Tools for Rachel (ElevenLabs Voice Agent)

5 separate tools that route intents to domain-specific streams:
- send_ideas_intent: Idea/note management within bubbles
- send_bubbles_intent: Space/bubble creation and navigation
- send_desktop_intent: Desktop automation, app control
- send_coding_intent: Code generation, project creation
- send_shuttles_intent: Requirements pipeline, specifications

Each tool calls the IntentOrchestrator directly with a domain_hint,
which enables optimized routing to the appropriate handler.
"""

import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Singleton orchestrator
_orchestrator = None


def _record_message(speaker: str, text: str) -> None:
    """Record message for conversation history."""
    try:
        from tools.conversation_tools import record_message
        record_message(speaker, text)
    except Exception as e:
        logger.debug(f"Could not record message: {e}")


def _get_orchestrator():
    """Get or create orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        from swarm.orchestrator import get_orchestrator
        _orchestrator = get_orchestrator()
        logger.info("IntentOrchestrator initialized for domain tools")
    return _orchestrator


def _run_async(coro):
    """Run async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(coro))
                return future.result(timeout=90)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _process_domain_intent(command: str, domain: str) -> str:
    """
    Process a domain-specific intent through the orchestrator.

    Args:
        command: User's voice command
        domain: Target domain (ideas, bubbles, desktop, coding, shuttles)

    Returns:
        Response text for TTS
    """
    try:
        _record_message("user", command)

        orchestrator = _get_orchestrator()
        result = await orchestrator.process_intent(command, domain_hint=domain)

        logger.info(f"[{domain.upper()}] Result: {result.response_hint[:100]}...")

        if result.error:
            error_response = f"Fehler: {result.error}"
            _record_message("agent", error_response)
            return error_response

        _record_message("agent", result.response_hint)
        return result.response_hint

    except Exception as e:
        logger.error(f"[{domain.upper()}] Error: {e}")
        import traceback
        traceback.print_exc()
        return f"Fehler bei {domain}: {str(e)}"


# =============================================================================
# IDEAS DOMAIN - Idea/note management
# =============================================================================

def send_ideas_intent(command: str) -> str:
    """
    Process idea/note management commands.

    Examples:
    - "Erstelle eine neue Idee API Design"
    - "Zeig mir alle Ideen"
    - "Verbinde API mit Database"
    - "Formatiere in Aktionsliste"
    - "Finde tiefere Verbindungen"

    Args:
        command: User's voice command about ideas/notes

    Returns:
        Response text for TTS
    """
    return _run_async(_process_domain_intent(command, "ideas"))


def send_ideas_intent_from_dict(params: Dict[str, Any]) -> str:
    """Dict wrapper for ElevenLabs ClientTools."""
    command = params.get("command") or params.get("text", "")
    if not command:
        return "Was möchtest du mit deinen Ideen machen?"
    return send_ideas_intent(command)


IDEAS_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "send_ideas_intent",
        "description": (
            "Handle idea and note management. Use for: creating ideas, "
            "listing ideas, connecting ideas, formatting content, "
            "summarizing, exploring connections. "
            "Keywords: Idee, Note, Notiz, verbinde, formatiere, zusammenfassung"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The idea-related command"
                }
            },
            "required": ["command"]
        }
    }
}


# =============================================================================
# BUBBLES DOMAIN - Space/bubble navigation
# =============================================================================

def send_bubbles_intent(command: str) -> str:
    """
    Process bubble/space navigation commands.

    Examples:
    - "Erstelle einen neuen Space Marketing"
    - "Geh in den Marketing Space"
    - "Zurück zur Übersicht"
    - "Zeig mir alle Bubbles"
    - "Lösche alle außer Debug"

    Args:
        command: User's voice command about spaces/bubbles

    Returns:
        Response text for TTS
    """
    return _run_async(_process_domain_intent(command, "bubbles"))


def send_bubbles_intent_from_dict(params: Dict[str, Any]) -> str:
    """Dict wrapper for ElevenLabs ClientTools."""
    command = params.get("command") or params.get("text", "")
    if not command:
        return "Was möchtest du mit deinen Spaces machen?"
    return send_bubbles_intent(command)


BUBBLES_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "send_bubbles_intent",
        "description": (
            "Handle space/bubble navigation. Use for: creating spaces, "
            "entering bubbles, exiting spaces, listing bubbles, "
            "deleting spaces. "
            "Keywords: Bubble, Space, Bereich, gehe, zurück, lösche"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bubble/space command"
                }
            },
            "required": ["command"]
        }
    }
}


# =============================================================================
# DESKTOP DOMAIN - Desktop automation
# =============================================================================

def send_desktop_intent(command: str) -> str:
    """
    Process desktop automation commands.

    Examples:
    - "Öffne Chrome"
    - "Klick auf den OK Button"
    - "Schreibe Hello World"
    - "Mach einen Screenshot"
    - "Schließe das Fenster"

    Args:
        command: User's voice command for desktop automation

    Returns:
        Response text for TTS
    """
    return _run_async(_process_domain_intent(command, "desktop"))


def send_desktop_intent_from_dict(params: Dict[str, Any]) -> str:
    """Dict wrapper for ElevenLabs ClientTools."""
    command = params.get("command") or params.get("text", "")
    if not command:
        return "Was soll ich auf dem Desktop machen?"
    return send_desktop_intent(command)


DESKTOP_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "send_desktop_intent",
        "description": (
            "Handle desktop automation. Use for: opening apps, "
            "clicking elements, typing text, taking screenshots, "
            "window management. "
            "Keywords: öffne, klick, schreibe, screenshot, Chrome, Terminal"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The desktop automation command"
                }
            },
            "required": ["command"]
        }
    }
}


# =============================================================================
# CODING DOMAIN - Code generation
# =============================================================================

def send_coding_intent(command: str) -> str:
    """
    Process code generation commands.

    Examples:
    - "Erstelle eine App für Notizen"
    - "Generiere eine API Funktion"
    - "Wie ist der Code-Status?"
    - "Implementiere Login"
    - "Erstelle eine Datenbank-Klasse"

    Args:
        command: User's voice command for code generation

    Returns:
        Response text for TTS
    """
    return _run_async(_process_domain_intent(command, "coding"))


def send_coding_intent_from_dict(params: Dict[str, Any]) -> str:
    """Dict wrapper for ElevenLabs ClientTools."""
    command = params.get("command") or params.get("text", "")
    if not command:
        return "Was soll ich programmieren?"
    return send_coding_intent(command)


CODING_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "send_coding_intent",
        "description": (
            "Handle code generation and development. Use for: creating apps, "
            "generating code, implementing features, checking status. "
            "Keywords: code, App, Funktion, implementiere, generiere, programmiere"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The coding/generation command"
                }
            },
            "required": ["command"]
        }
    }
}


# =============================================================================
# SHUTTLES DOMAIN - Requirements pipeline
# =============================================================================

def send_shuttles_intent(command: str) -> str:
    """
    Process shuttle/requirements pipeline commands.

    Examples:
    - "Starte einen neuen Shuttle"
    - "Zeig mir die Anforderungen"
    - "Validiere die Spezifikation"
    - "Nächste Stufe"
    - "Shuttle Status"

    Args:
        command: User's voice command for shuttle pipeline

    Returns:
        Response text for TTS
    """
    return _run_async(_process_domain_intent(command, "shuttles"))


def send_shuttles_intent_from_dict(params: Dict[str, Any]) -> str:
    """Dict wrapper for ElevenLabs ClientTools."""
    command = params.get("command") or params.get("text", "")
    if not command:
        return "Was möchtest du mit dem Shuttle machen?"
    return send_shuttles_intent(command)


SHUTTLES_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "send_shuttles_intent",
        "description": (
            "Handle requirements and specification pipeline. Use for: "
            "creating shuttles, managing requirements, validating specs, "
            "advancing stages. "
            "Keywords: Shuttle, Anforderung, Spezifikation, Pipeline, Stufe"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shuttle/requirements command"
                }
            },
            "required": ["command"]
        }
    }
}


# =============================================================================
# EXPORTS
# =============================================================================

# All tool definitions for registration
ALL_DOMAIN_TOOLS = {
    "ideas": {
        "function": send_ideas_intent_from_dict,
        "definition": IDEAS_TOOL_DEFINITION,
    },
    "bubbles": {
        "function": send_bubbles_intent_from_dict,
        "definition": BUBBLES_TOOL_DEFINITION,
    },
    "desktop": {
        "function": send_desktop_intent_from_dict,
        "definition": DESKTOP_TOOL_DEFINITION,
    },
    "coding": {
        "function": send_coding_intent_from_dict,
        "definition": CODING_TOOL_DEFINITION,
    },
    "shuttles": {
        "function": send_shuttles_intent_from_dict,
        "definition": SHUTTLES_TOOL_DEFINITION,
    },
}


def get_all_tool_definitions() -> list:
    """Get all domain tool definitions for ElevenLabs registration."""
    return [tool["definition"] for tool in ALL_DOMAIN_TOOLS.values()]


def get_all_tool_functions() -> Dict[str, callable]:
    """Get all domain tool functions mapped by name."""
    return {
        "send_ideas_intent": send_ideas_intent_from_dict,
        "send_bubbles_intent": send_bubbles_intent_from_dict,
        "send_desktop_intent": send_desktop_intent_from_dict,
        "send_coding_intent": send_coding_intent_from_dict,
        "send_shuttles_intent": send_shuttles_intent_from_dict,
    }


__all__ = [
    # Ideas
    "send_ideas_intent",
    "send_ideas_intent_from_dict",
    "IDEAS_TOOL_DEFINITION",
    # Bubbles
    "send_bubbles_intent",
    "send_bubbles_intent_from_dict",
    "BUBBLES_TOOL_DEFINITION",
    # Desktop
    "send_desktop_intent",
    "send_desktop_intent_from_dict",
    "DESKTOP_TOOL_DEFINITION",
    # Coding
    "send_coding_intent",
    "send_coding_intent_from_dict",
    "CODING_TOOL_DEFINITION",
    # Shuttles
    "send_shuttles_intent",
    "send_shuttles_intent_from_dict",
    "SHUTTLES_TOOL_DEFINITION",
    # Helpers
    "ALL_DOMAIN_TOOLS",
    "get_all_tool_definitions",
    "get_all_tool_functions",
]
