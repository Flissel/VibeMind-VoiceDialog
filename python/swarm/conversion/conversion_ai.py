"""
ConversionAI - Personalized AI with dynamic personality

Phase 13: Conversion AI System

Features:
- Dynamic personality that adapts to user
- Self-naming capability
- Context-rich prompt generation
- Personalized response formatting
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from swarm.analysis.user_context import UserContext
from llm_config import get_model, get_client
from swarm.analysis.intent_analysis_team import IntentHypothesis

logger = logging.getLogger(__name__)


@dataclass
class AIPersonality:
    """
    AI Personality configuration.

    Defines how the AI presents itself and interacts with users.
    """
    name: str  # Self-chosen or user-assigned name
    style: str = "casual"  # "formal" | "casual" | "technical"
    verbosity: str = "concise"  # "concise" | "detailed"
    traits: List[str] = field(default_factory=lambda: ["freundlich", "hilfsbereit"])
    language: str = "de"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "style": self.style,
            "verbosity": self.verbosity,
            "traits": self.traits,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AIPersonality':
        """Create from dictionary."""
        return cls(
            name=data.get("name", "Luna"),
            style=data.get("style", "casual"),
            verbosity=data.get("verbosity", "concise"),
            traits=data.get("traits", ["freundlich", "hilfsbereit"]),
            language=data.get("language", "de"),
        )


class ConversionAI:
    """
    Personalized AI with dynamic personality.

    Adapts responses based on:
    - User preferences and interaction history
    - Current context and task
    - Personality configuration
    """

    def __init__(self, model: Optional[str] = None):
        """
        Initialize the Conversion AI.

        Args:
            model: LLM model to use (default: from env)
        """
        self._model = model or get_model("conversion")
        self._client = None
        self._personality: Optional[AIPersonality] = None
        self._db_repo = None

    @property
    def client(self):
        """Lazy-load OpenAI-compatible client."""
        if self._client is None:
            try:
                self._client = get_client("conversion")
            except Exception as e:
                logger.error(f"Failed to create conversion client: {e}")
                raise
        return self._client

    @property
    def db_repo(self):
        """Lazy-load database repository."""
        if self._db_repo is None:
            try:
                from data.conversion_ai_repository import get_conversion_ai_repository
                self._db_repo = get_conversion_ai_repository()
            except ImportError:
                logger.debug("ConversionAI repository not available")
        return self._db_repo

    @property
    def personality(self) -> AIPersonality:
        """Get current personality (loads default if not initialized)."""
        if self._personality is None:
            self._personality = AIPersonality(name="Luna")
        return self._personality

    async def initialize(self, user_id: str = "default") -> AIPersonality:
        """
        Initialize or load personality for a user.

        Args:
            user_id: User identifier

        Returns:
            Loaded or newly created AIPersonality
        """
        logger.debug("initialize called with user_id=%s", user_id)
        # Try to load existing personality
        if self.db_repo:
            try:
                existing = await self.db_repo.get_personality(user_id)
                if existing:
                    self._personality = existing
                    logger.info(f"Loaded personality '{existing.name}' for user {user_id}")
                    return existing
            except Exception as e:
                logger.warning(f"Failed to load personality: {e}")

        # Generate new personality
        from swarm.conversion.personality_generator import get_personality_generator
        generator = get_personality_generator()

        name = await generator.generate_name()
        traits = await generator.generate_traits(user_id)

        personality = AIPersonality(
            name=name,
            traits=traits,
        )

        # Save to database
        if self.db_repo:
            try:
                await self.db_repo.save_personality(user_id, personality)
                logger.info(f"Created new personality '{name}' for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to save personality: {e}")

        self._personality = personality
        return personality

    def build_prompt(self,
                    intent: IntentHypothesis,
                    context: UserContext,
                    task_result: Optional[str] = None) -> str:
        """
        Build context-rich prompt for response generation.

        Args:
            intent: The detected intent hypothesis
            context: User context
            task_result: Optional result from tool execution

        Returns:
            Enriched prompt for LLM
        """
        logger.debug("build_prompt called with intent=%s", intent.event_type)
        p = self.personality

        # Build personality section
        personality_desc = f"Du bist {p.name}, eine {p.style}e AI."
        if p.traits:
            personality_desc += f" Du bist {', '.join(p.traits)}."

        # Build context section
        context_section = f"""
Aktuelle Situation:
- User ist in: {context.current_space or 'Multiverse'}
- Letzte Aktion: {context.get_last_result() or 'keine'}
- Aktuelles Thema: {context.current_topic or 'keins'}
- User-Stil: {context.interaction_style}
"""

        # Build intent section
        intent_section = f"""
Erkannter Intent: {intent.event_type}
Confidence: {intent.confidence:.0%}
Parameter: {intent.payload}
Reasoning: {intent.reasoning}
"""

        # Build result section (if available)
        result_section = ""
        if task_result:
            result_section = f"""
Task-Ergebnis: {task_result}
"""

        # Build instructions
        instructions = f"""
Antworte {p.verbosity} und in {self._get_language_name(p.language)}.
Sei natuerlich und verwende keine uebertriebene Foermlichkeit.
"""

        return f"""{personality_desc}

{context_section}
{intent_section}
{result_section}
{instructions}
"""

    async def format_response(self,
                             task_result: str,
                             intent: IntentHypothesis,
                             context: UserContext) -> str:
        """
        Format task result into personalized response.

        Args:
            task_result: Raw result from tool execution
            intent: The detected intent
            context: User context

        Returns:
            Formatted response suitable for voice output
        """
        logger.debug("format_response called with intent=%s", intent.event_type)
        prompt = f"""{self.build_prompt(intent, context, task_result)}

Formatiere das Ergebnis fuer eine natuerliche Sprachausgabe.
Das Ergebnis sollte:
- Kurz und praegnant sein (1-2 Saetze)
- Natuerlich klingen
- Den wichtigsten Teil der Information enthalten

Antworte NUR mit dem formatierten Text, keine Erklaerungen."""

        try:
            from llm_config import token_kwargs
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                **token_kwargs(self._model, 200),
            )

            formatted = response.choices[0].message.content.strip()

            # Remove quotes if the LLM wrapped the response
            if formatted.startswith('"') and formatted.endswith('"'):
                formatted = formatted[1:-1]

            return formatted

        except Exception as e:
            logger.warning(f"Response formatting failed: {e}")
            return task_result  # Return raw result as fallback

    async def introduce(self) -> str:
        """
        Generate a self-introduction.

        Returns:
            Introduction text for the AI
        """
        logger.debug("introduce called")
        p = self.personality

        prompt = f"""Du bist {p.name}, eine VibeMind AI-Assistentin.
Eigenschaften: {', '.join(p.traits)}
Stil: {p.style}

Stelle dich kurz (1-2 Saetze) vor. Sei freundlich aber nicht uebertrieben enthusiastisch."""

        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                **token_kwargs(self._model, 100),
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.warning(f"Introduction generation failed: {e}")
            return f"Hallo, ich bin {p.name}. Wie kann ich dir helfen?"

    def adapt_to_user(self, feedback: str, preference: str, value: Any) -> None:
        """
        Adapt personality based on user feedback.

        Args:
            feedback: Type of feedback (positive/negative)
            preference: What preference to adapt
            value: New value for the preference
        """
        logger.debug("adapt_to_user called with feedback=%s, preference=%s, value=%s", feedback, preference, value)
        if self._personality is None:
            return

        if preference == "verbosity":
            if value in ["concise", "detailed"]:
                self._personality.verbosity = value
                logger.info(f"Adapted verbosity to {value}")

        elif preference == "style":
            if value in ["formal", "casual", "technical"]:
                self._personality.style = value
                logger.info(f"Adapted style to {value}")

    def _get_language_name(self, code: str) -> str:
        """Get language name from code."""
        languages = {
            "de": "Deutsch",
            "en": "Englisch",
            "fr": "Franzoesisch",
        }
        return languages.get(code, "Deutsch")


# Singleton
_conversion_ai: Optional[ConversionAI] = None


def get_conversion_ai() -> ConversionAI:
    """Get or create ConversionAI singleton."""
    global _conversion_ai
    if _conversion_ai is None:
        _conversion_ai = ConversionAI()
    return _conversion_ai


__all__ = [
    "AIPersonality",
    "ConversionAI",
    "get_conversion_ai",
]
