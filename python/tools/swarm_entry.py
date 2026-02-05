"""
Swarm Entry Point for ElevenLabs Agent

Single tool that routes ALL voice commands through VoiceBridgeV2.
ElevenLabs Agent only needs this ONE tool.

Usage:
    ElevenLabs Agent calls process_input(command="user text")
    → VoiceBridgeV2 routes to correct User Agent (Rachel/Adam/Antoni)
    → User Agent calls appropriate tools
    → Response returned to ElevenLabs for TTS
"""

import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Singleton bridge instance
_voice_bridge = None


async def _get_bridge():
    """Get or create VoiceBridgeV2 singleton."""
    global _voice_bridge
    if _voice_bridge is None:
        from swarm.voice_bridge_v2 import create_voice_bridge_v2
        _voice_bridge = await create_voice_bridge_v2()
        logger.info("VoiceBridgeV2 initialized for swarm entry")
    return _voice_bridge


async def process_input_async(command: str) -> str:
    """
    Process user command through VibeMind Swarm.

    This is the ONLY tool ElevenLabs needs. It:
    1. Routes to correct space based on navigation state
    2. User Agent (Rachel/Adam/Antoni) handles the request
    3. Tools are called as needed
    4. Response returned for TTS

    Args:
        command: User's voice command (transcribed text)

    Returns:
        Response text for TTS output
    """
    try:
        # Record user message for conversation history
        try:
            from tools.conversation_tools import record_message
            record_message("user", command)
        except Exception as rec_err:
            logger.debug(f"Could not record user message: {rec_err}")

        bridge = await _get_bridge()
        result = await bridge.handle_voice_input(command)

        logger.info(f"Swarm result: agent={result.agent_name}, space={result.space}")

        if result.error:
            logger.warning(f"Swarm error: {result.error}")
            error_response = f"Es gab einen Fehler: {result.error}"
            # Record agent error response
            try:
                from tools.conversation_tools import record_message
                record_message("agent", error_response)
            except Exception:
                pass
            return error_response

        # Record agent response for conversation history
        try:
            from tools.conversation_tools import record_message
            record_message("agent", result.response)
        except Exception as rec_err:
            logger.debug(f"Could not record agent response: {rec_err}")

        return result.response

    except Exception as e:
        logger.error(f"Swarm entry error: {e}")
        import traceback
        traceback.print_exc()
        return f"Entschuldigung, es gab einen Fehler: {str(e)}"


def process_input(command: str) -> str:
    """
    Synchronous wrapper for ElevenLabs tools.

    Args:
        command: User's voice command

    Returns:
        Response text for TTS
    """
    try:
        # Try to get existing loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context - create a new loop in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(process_input_async(command))
                )
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(process_input_async(command))
    except RuntimeError:
        # No event loop - create one
        return asyncio.run(process_input_async(command))


def process_input_from_dict(params: Dict[str, Any]) -> str:
    """
    Dict-based wrapper for ElevenLabs ClientTools.

    Args:
        params: Dict with 'command' or 'text' key

    Returns:
        Response text for TTS
    """
    command = params.get("command") or params.get("text", "")
    if not command:
        return "Ich habe dich nicht verstanden. Was kann ich für dich tun?"
    return process_input(command)


# ElevenLabs Tool Definition
TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "process_input",
        "description": (
            "Process ANY user command through VibeMind. "
            "Use this for ALL requests - the Swarm will route to the correct agent. "
            "Examples: 'create a space', 'list my bubbles', 'open chrome', 'generate code'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The user's command or request"
                }
            },
            "required": ["command"]
        }
    }
}


__all__ = [
    "process_input",
    "process_input_async",
    "process_input_from_dict",
    "TOOL_DEFINITION",
]
