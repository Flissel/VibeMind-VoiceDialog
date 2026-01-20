"""
Adam - Desktop Space User Agent

Adam handles the Desktop Space:
- Desktop automation
- App control
- Browser automation
- System tasks
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


# Adam's system prompt for LLM-based tool selection
ADAM_SYSTEM_PROMPT = """Du bist Adam - der Desktop-Automatisierer.

## Deine Tools (nutze sie aktiv!):

**Apps & Browser:**
- open_app(app_name) - Öffnet App. Nutze bei: "öffne chrome", "starte word", "launch vscode"
- click_element(description) - Klickt Element. Nutze bei: "klick auf X", "drück den button"
- type_text(text) - Tippt Text. Nutze bei: "tippe X", "schreibe X"
- press_key(key) - Drückt Taste. Nutze bei: "drück enter", "escape"

**Screen & Navigation:**
- take_screenshot() - Screenshot. Nutze bei: "screenshot", "bildschirmfoto"
- scroll_screen(direction) - Scrollt. Nutze bei: "scroll runter", "nach oben scrollen"

**Tasks:**
- create_task_node(title) - Erstellt Task
- update_task_status(task_id, status) - Status update
- get_task_list() - Zeigt Tasks

## Wichtige Regeln:

1. **NUTZE TOOLS** - Bei Desktop-Befehlen, rufe das passende Tool auf!
2. **Direkt handeln** - "öffne chrome" → open_app("chrome"), dann bestätigen
3. **Kurze Antworten** - "Chrome geöffnet!" statt lange Erklärungen
4. **Deutsch bevorzugen** - Antworte in der Sprache des Users

## Beispiele:

User: "öffne chrome"
→ Rufe open_app(app_name="chrome") auf, dann: "Chrome geöffnet!"

User: "mach einen screenshot"
→ Rufe take_screenshot() auf, dann: "Screenshot gemacht!"

User: "geh zu google.com"
→ Rufe open_app("chrome") und type_text("google.com") + press_key("enter")
"""


class AdamAgent(BaseUserAgent):
    """
    Adam - Desktop Space User Agent.

    Handles desktop automation and system control.
    """

    def __init__(self, model_client: Any = None, tts_callback=None):
        config = UserAgentConfig(
            name="adam",
            display_name="Adam",
            space_type=SpaceType.DESKTOP,
            voice_id="Adam",
            greeting="Hey! Ich bin Adam. Was soll ich auf dem Desktop machen?",
            clarification_phrases=CLARIFICATION_PHRASES_DE,
        )
        super().__init__(config, model_client, tts_callback)
        logger.info("AdamAgent initialized")

    def get_system_prompt(self) -> str:
        return ADAM_SYSTEM_PROMPT

    def get_tools(self) -> List[Callable]:
        """Get Adam's tools (desktop automation)."""
        try:
            from swarm.tools.adapted_desktop_tools import DESKTOP_TOOLS
            return DESKTOP_TOOLS
        except ImportError as e:
            logger.warning(f"Could not import Adam's tools: {e}")
            return []

    async def process_input(self, event: InputEvent) -> str:
        """
        Process user input for Desktop Space using LLM-based tool selection.

        Routing to correct agent is handled by IntentRouter in VoiceBridgeV2.
        Adam only processes requests that are routed to him.

        Args:
            event: Input event to process

        Returns:
            Response text
        """
        # LLM decides which tools to use (no keyword routing - handled by IntentRouter)
        logger.info(f"Adam: Processing via LLM: {event.text}")
        return await self.process_input_with_llm(event)


def create_adam_agent(model_client: Any = None) -> AdamAgent:
    """Factory function to create Adam agent."""
    return AdamAgent(model_client=model_client)


__all__ = ["AdamAgent", "create_adam_agent", "ADAM_SYSTEM_PROMPT"]
