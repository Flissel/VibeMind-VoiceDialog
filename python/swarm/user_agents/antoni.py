"""
Antoni - Coding Space User Agent

Antoni handles the Coding Space:
- Code generation
- Project management
- Preview handling
- File operations
"""

import logging
from typing import List, Callable, Any

from swarm.navigation import SpaceType
from swarm.event_buffer import InputEvent
from swarm.user_agents.base import (
    BaseUserAgent,
    UserAgentConfig,
    CLARIFICATION_PHRASES_DE,
)

logger = logging.getLogger(__name__)


# Antoni's system prompt for LLM-based tool selection
ANTONI_SYSTEM_PROMPT = """Du bist Antoni - der Coding-Experte.

## Deine Tools (nutze sie aktiv!):

**Code Generation:**
- generate_code(description, language) - Generiert Code. Nutze bei: "erstelle X", "schreib code für Y"
- get_generation_status(task_id) - Prüft Status. Nutze bei: "wie weit?", "status?"
- cancel_generation(task_id) - Stoppt Generation. Nutze bei: "abbrechen", "stopp"

**Projekte & Preview:**
- list_generated_projects() - Zeigt Projekte. Nutze bei: "meine projekte", "was hab ich erstellt?"
- start_preview(project_id) - Startet Preview. Nutze bei: "zeig preview", "starte vorschau"
- stop_preview(project_id) - Stoppt Preview. Nutze bei: "stopp preview"

## Wichtige Regeln:

1. **NUTZE TOOLS** - Bei Coding-Anfragen, rufe das passende Tool auf!
2. **Details klären** - Wenn Sprache/Framework unklar, frag nach
3. **Technisch aber freundlich** - Erkläre was du machst
4. **Deutsch bevorzugen** - Antworte in der Sprache des Users

## Beispiele:

User: "erstelle eine python funktion für fibonacci"
→ Rufe generate_code(description="fibonacci function", language="python") auf

User: "was sind meine projekte?"
→ Rufe list_generated_projects() auf

User: "erstelle eine website"
→ Frag: "Welches Framework? React, Vue, oder plain HTML?"

User: "starte preview für mein letztes projekt"
→ Rufe start_preview() auf
"""


class AntoniAgent(BaseUserAgent):
    """
    Antoni - Coding Space User Agent.

    Handles code generation and project management.
    """

    def __init__(self, model_client: Any = None, tts_callback=None):
        config = UserAgentConfig(
            name="antoni",
            display_name="Antoni",
            space_type=SpaceType.CODING,
            voice_id="Antoni",
            greeting="Hey! Ich bin Antoni. Was sollen wir coden?",
            clarification_phrases=CLARIFICATION_PHRASES_DE,
        )
        super().__init__(config, model_client, tts_callback)
        logger.info("AntoniAgent initialized")

    def get_system_prompt(self) -> str:
        return ANTONI_SYSTEM_PROMPT

    def get_tools(self) -> List[Callable]:
        """Get Antoni's tools (code generation)."""
        try:
            from swarm.tools.adapted_coding_tools import CODING_TOOLS
            return CODING_TOOLS
        except ImportError as e:
            logger.warning(f"Could not import Antoni's tools: {e}")
            return []

    async def process_input(self, event: InputEvent) -> str:
        """
        Process user input for Coding Space using LLM-based tool selection.

        Routing to correct agent is handled by IntentRouter in VoiceBridgeV2.
        Antoni only processes requests that are routed to him.

        Args:
            event: Input event to process

        Returns:
            Response text
        """
        # LLM decides which tools to use (no keyword routing - handled by IntentRouter)
        logger.info(f"Antoni: Processing via LLM: {event.text}")
        return await self.process_input_with_llm(event)


def create_antoni_agent(model_client: Any = None) -> AntoniAgent:
    """Factory function to create Antoni agent."""
    return AntoniAgent(model_client=model_client)


__all__ = ["AntoniAgent", "create_antoni_agent", "ANTONI_SYSTEM_PROMPT"]
