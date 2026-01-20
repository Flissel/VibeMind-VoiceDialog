"""
Intent Router - LLM-First Routing for VibeMind

Uses Claude (via OpenRouter) to classify user intent and route to the correct agent.
Replaces fragile keyword-based routing.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Result of intent classification."""
    agent: str  # "rachel" | "adam" | "antoni"
    intent: str  # Brief description
    confidence: float  # 0.0 - 1.0
    should_switch_space: bool
    needs_clarification: bool = False
    clarification_prompt: Optional[str] = None


# System prompt for intent classification
ROUTING_SYSTEM_PROMPT = """Du bist ein Intent-Klassifikator für VibeMind Voice Assistant.
Klassifiziere die Benutzeranfrage zu einem der drei Agents:

## Agents und ihre Domains:

**Rachel (ideas)** - Ideas Space Navigator
- Bubble/Space-Verwaltung (erstellen, löschen, betreten, verlassen)
- Ideen und Notizen verwalten (erstellen, auflisten, finden, aktualisieren)
- Multiverse-Navigation
- Allgemeine Gespräche über Ideen und Organisation
- WICHTIG: Wenn User Namen wie "Rachel", "Adam", "Antoni" als Subjekte nennt (nicht Befehle), route zum aktuellen Agent

**Adam (desktop)** - Desktop Automation
- Anwendungen öffnen (Chrome, Word, VSCode, etc.)
- UI-Elemente klicken, Text tippen
- Screenshots, Scrollen
- System/Computer-Steuerung
- Browser-Automation

**Antoni (coding)** - Code Generierung
- Code-Projekte erstellen
- Funktionen, Klassen, Module generieren
- Projektstatus und Preview
- Programmieraufgaben

## Klassifikations-Regeln:

1. Fokus auf INTENT, nicht einzelne Keywords
2. "click on Rachel" = ideas (Klick auf Rachel-Bubble im UI, nicht Desktop-Automation)
3. "open chrome" = desktop (Browser-Anwendung starten)
4. "create a react app" = coding (Code-Generierung)
5. "create a new space" = ideas (Space/Bubble-Verwaltung)
6. Bei Unklarheit: bevorzuge den AKTUELLEN Agent
7. Bei wirklich unklaren Anfragen: confidence < 0.5

## Output Format (NUR JSON):
{"agent": "rachel" | "adam" | "antoni", "intent": "kurze Beschreibung", "confidence": 0.0-1.0}
"""


class IntentRouter:
    """Routes user input to the correct agent using LLM classification."""

    def __init__(self, use_fast_model: bool = True):
        """
        Initialize the IntentRouter.

        Args:
            use_fast_model: Use Haiku for faster routing (default True)
        """
        self.use_fast_model = use_fast_model
        self._client = None

        # Model selection
        if use_fast_model:
            # Use Claude 3.5 Haiku for fast routing (OpenRouter model ID)
            self.model = "anthropic/claude-3.5-haiku"
        else:
            self.model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4")

        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"

        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set - IntentRouter will not work")

    @property
    def client(self):
        """Lazy-load the OpenAI client for OpenRouter."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
                logger.info(f"IntentRouter using model: {self.model}")
            except ImportError:
                logger.error("openai package not installed")
                raise
        return self._client

    async def classify_intent(
        self,
        text: str,
        current_space: str = "ideas"
    ) -> RoutingDecision:
        """
        Classify user intent and determine target agent.

        Args:
            text: User's voice input text
            current_space: Current space name ("ideas", "desktop", "coding")

        Returns:
            RoutingDecision with agent, intent, and confidence
        """
        try:
            # Build user message with context
            user_message = f"Aktueller Space: {current_space}\nUser-Anfrage: {text}"

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": ROUTING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=100,
            )

            # Parse response
            content = response.choices[0].message.content.strip()
            logger.debug(f"IntentRouter response: {content}")

            # Extract JSON from response
            result = self._parse_response(content)

            # Map agent to space for switch decision
            agent = result.get("agent", "rachel")
            current_agent = self._space_to_agent(current_space)
            should_switch = agent != current_agent

            confidence = result.get("confidence", 0.5)

            # Handle low confidence
            if confidence < 0.5:
                return RoutingDecision(
                    agent=current_agent,  # Stay with current
                    intent=result.get("intent", "unclear"),
                    confidence=confidence,
                    should_switch_space=False,
                    needs_clarification=True,
                    clarification_prompt=f"Ich bin nicht sicher was du meinst. Kannst du das genauer beschreiben?"
                )

            return RoutingDecision(
                agent=agent,
                intent=result.get("intent", ""),
                confidence=confidence,
                should_switch_space=should_switch,
                needs_clarification=False
            )

        except Exception as e:
            logger.error(f"IntentRouter error: {e}")
            # Fallback: stay with current agent
            return RoutingDecision(
                agent=self._space_to_agent(current_space),
                intent="fallback",
                confidence=0.0,
                should_switch_space=False,
                needs_clarification=False
            )

    def _parse_response(self, content: str) -> dict:
        """Parse JSON from LLM response."""
        try:
            # Try direct parse
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[^}]+\}', content)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            # Fallback parsing
            agent = "rachel"
            if "adam" in content.lower():
                agent = "adam"
            elif "antoni" in content.lower():
                agent = "antoni"

            return {
                "agent": agent,
                "intent": "parsed from text",
                "confidence": 0.6
            }

    def _space_to_agent(self, space: str) -> str:
        """Map space name to agent name."""
        mapping = {
            "ideas": "rachel",
            "desktop": "adam",
            "coding": "antoni",
            # Also handle direct agent names
            "rachel": "rachel",
            "adam": "adam",
            "antoni": "antoni",
        }
        return mapping.get(space.lower(), "rachel")

    def _agent_to_space(self, agent: str) -> str:
        """Map agent name to space name."""
        mapping = {
            "rachel": "ideas",
            "adam": "desktop",
            "antoni": "coding",
        }
        return mapping.get(agent.lower(), "ideas")


# Singleton instance
_router: Optional[IntentRouter] = None


def get_intent_router(use_fast_model: bool = True) -> IntentRouter:
    """Get or create IntentRouter singleton."""
    global _router
    if _router is None:
        _router = IntentRouter(use_fast_model=use_fast_model)
    return _router


__all__ = [
    "IntentRouter",
    "RoutingDecision",
    "get_intent_router",
]
