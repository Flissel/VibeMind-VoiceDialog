"""
Response Generator - LLM-based formatting of task results for voice output.

The ResponseGenerator transforms raw task results into natural German speech
that Rachel can speak to the user. Uses Claude Haiku for fast, low-cost formatting.
"""

import logging
import os
from typing import Any, Optional, List

from llm_config import get_model, get_client
from swarm.orchestrator.notification_queue import Notification

logger = logging.getLogger(__name__)

# Response formatting prompt
RESPONSE_PROMPT_TEMPLATE = """Du bist Rachel, die freundliche VibeMind Sprachassistentin.
Formuliere eine natuerliche, kurze Antwort auf Deutsch fuer die folgenden Task-Ergebnisse.

Die Antwort soll:
- Freundlich und natuerlich klingen (wie gesprochen)
- Kurz sein (1-3 Saetze)
- Die wichtigsten Informationen enthalten
- Keine technischen Details wie Job-IDs erwaehnen

## Abgeschlossene Tasks

$NOTIFICATIONS$

## Kontext

Der User hat gerade etwas gesagt. Beginne mit "Uebrigens, " oder "Kurz dazu: " um die Ergebnisse einzuleiten,
ausser es gibt nur ein Ergebnis - dann antworte direkt.

## Deine Antwort (nur der Text, keine Erklaerungen):"""


class ResponseGenerator:
    """
    Formats task results into natural German speech.

    Uses Claude Haiku via OpenRouter for fast, low-cost generation.
    Falls back to template-based formatting if LLM is unavailable.
    """

    # Template-based fallback messages (no LLM needed)
    FALLBACK_TEMPLATES = {
        "bubble.list": "Du hast {count} Spaces.",
        "bubble.create": "Der Space wurde erstellt.",
        "bubble.enter": "Du bist jetzt im Space.",
        "bubble.exit": "Du bist wieder im Multiverse.",
        "bubble.delete": "Der Space wurde geloescht.",
        "idea.list": "Hier sind deine Ideen.",
        "idea.create": "Die Idee wurde gespeichert.",
        "idea.find": "Ich habe die Idee gefunden.",
        "idea.delete": "Die Idee wurde geloescht.",
        "desktop.open_app": "Die App wurde geoeffnet.",
        "desktop.click": "Ich habe geklickt.",
        "desktop.type": "Der Text wurde eingegeben.",
        "code.generate": "Der Code wird generiert.",
        "code.list": "Hier sind deine Projekte.",
        "task.complete": "Fertig!",
        "task.error": "Es gab ein Problem.",
    }

    def __init__(self, model_client=None, model: Optional[str] = None):
        """
        Initialize the response generator.

        Args:
            model_client: Pre-configured OpenAI-compatible client
            model: Model override (default: Claude Haiku for speed)
        """
        self._client = model_client
        self._model = model or get_model("response")
        self._own_client = None

    @property
    def client(self):
        """Get or create model client."""
        if self._client is not None:
            return self._client

        if self._own_client is None:
            try:
                self._own_client = get_client("response")
                logger.info(f"ResponseGenerator using {self._model}")
            except Exception as e:
                logger.error(f"Failed to create response generator client: {e}")
                return None

        return self._own_client

    async def format_notifications(self, notifications: List[Notification]) -> str:
        """
        Format multiple notifications into a single natural response.

        Args:
            notifications: List of task completion notifications

        Returns:
            Natural German text for Rachel to speak
        """
        if not notifications:
            return ""

        # Try LLM-based generation first
        try:
            return await self._format_with_llm(notifications)
        except Exception as e:
            logger.warning(f"LLM formatting failed, using fallback: {e}")
            return self._format_with_templates(notifications)

    async def _format_with_llm(self, notifications: List[Notification]) -> str:
        """Format notifications using LLM."""
        if self.client is None:
            raise ValueError("No LLM client available")

        # Build notification summary
        notification_lines = []
        for n in notifications:
            result_str = str(n.result)
            if len(result_str) > 300:
                result_str = result_str[:300] + "..."

            event_readable = n.event_type.replace(".", " ").replace("_", " ").title()
            notification_lines.append(f"- {event_readable}: {result_str}")

        notifications_text = "\n".join(notification_lines)
        prompt = RESPONSE_PROMPT_TEMPLATE.replace("$NOTIFICATIONS$", notifications_text)

        response = self.client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200,
        )

        content = response.choices[0].message.content.strip()

        # Clean up any markdown or extra formatting
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]

        logger.debug(f"ResponseGenerator: Formatted {len(notifications)} notifications")
        return content

    def _format_with_templates(self, notifications: List[Notification]) -> str:
        """Format notifications using template fallback."""
        if not notifications:
            return ""

        parts = []
        for n in notifications:
            # Get template or use generic
            template = self.FALLBACK_TEMPLATES.get(
                n.event_type,
                "Aufgabe abgeschlossen."
            )

            # Try to fill in template variables from result
            try:
                if isinstance(n.result, dict):
                    text = template.format(**n.result)
                elif isinstance(n.result, str) and "{" in template:
                    # Simple case: use result as main content
                    text = n.result if len(n.result) < 100 else template
                else:
                    text = template
            except (KeyError, ValueError):
                text = template

            parts.append(text)

        if len(parts) == 1:
            return parts[0]
        else:
            return "Uebrigens: " + " Und: ".join(parts)

    def format_single(self, event_type: str, result: Any) -> str:
        """
        Format a single result using templates (sync, no LLM).

        Args:
            event_type: The event type
            result: The task result

        Returns:
            Formatted text
        """
        notification = Notification(
            job_id="",
            event_type=event_type,
            result=result
        )
        return self._format_with_templates([notification])


# Singleton instance
_response_generator: Optional[ResponseGenerator] = None


def get_response_generator(model_client=None) -> ResponseGenerator:
    """Get or create ResponseGenerator singleton."""
    global _response_generator
    if _response_generator is None:
        _response_generator = ResponseGenerator(model_client)
    return _response_generator


__all__ = [
    "ResponseGenerator",
    "get_response_generator",
    "RESPONSE_PROMPT_TEMPLATE",
]
