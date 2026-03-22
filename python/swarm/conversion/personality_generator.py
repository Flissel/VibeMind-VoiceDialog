"""
PersonalityGenerator - Self-naming and trait generation for AI

Phase 13: Conversion AI System

Generates unique, friendly AI names and personality traits
based on user context and preferences.
"""

import logging
import random
from typing import List, Optional

from llm_config import get_model, get_client

logger = logging.getLogger(__name__)


# Predefined name pools for fallback
FALLBACK_NAMES = [
    "Luna", "Nova", "Aria", "Zara", "Maya",
    "Stella", "Cleo", "Nora", "Ivy", "Ava",
    "Mira", "Lina", "Tara", "Vera", "Dina"
]

# Predefined trait pools
TRAIT_POOLS = {
    "positive": [
        "freundlich", "hilfsbereit", "geduldig", "aufmerksam",
        "praezise", "zuverlaessig", "kompetent", "warmherzig"
    ],
    "professional": [
        "effizient", "strukturiert", "fokussiert", "sachlich",
        "analytisch", "gruendlich", "organisiert"
    ],
    "casual": [
        "locker", "entspannt", "humorvoll", "spontan",
        "zugaenglich", "unkompliziert"
    ]
}


class PersonalityGenerator:
    """
    Generates AI personalities with unique names and traits.

    Can generate names:
    - Via LLM for creative, context-aware names
    - Via fallback pool if LLM unavailable
    """

    def __init__(self, model: Optional[str] = None):
        """
        Initialize the generator.

        Args:
            model: LLM model to use for generation
        """
        self._model = model or get_model("personality")
        self._client = None
        self._used_names: List[str] = []

    @property
    def client(self):
        """Lazy-load OpenAI-compatible client."""
        if self._client is None:
            try:
                self._client = get_client("personality")
            except Exception as e:
                logger.debug(f"LLM client not available for personality generation: {e}")
        return self._client

    async def generate_name(self, exclude: Optional[List[str]] = None) -> str:
        """
        Generate a unique, friendly AI name.

        Args:
            exclude: Names to exclude (e.g., existing agents)

        Returns:
            Generated name
        """
        # Default exclusions (existing VibeMind agents)
        default_exclude = ["Rachel", "Alice", "Adam", "Antoni"]
        all_exclude = set(default_exclude + (exclude or []) + self._used_names)

        # Try LLM generation first
        if self.client:
            try:
                name = await self._generate_name_llm(all_exclude)
                if name and name not in all_exclude:
                    self._used_names.append(name)
                    return name
            except Exception as e:
                logger.debug(f"LLM name generation failed: {e}")

        # Fallback to predefined pool
        available = [n for n in FALLBACK_NAMES if n not in all_exclude]
        if available:
            name = random.choice(available)
            self._used_names.append(name)
            return name

        # Last resort: generate random variation
        base = random.choice(FALLBACK_NAMES)
        return f"{base}-{random.randint(1, 99)}"

    async def _generate_name_llm(self, exclude: set) -> str:
        """Generate name using LLM."""
        exclude_str = ", ".join(exclude) if exclude else "keine"

        prompt = f"""Generiere einen einzigartigen, freundlichen Namen fuer eine AI-Assistentin.

Anforderungen:
- Kurz (1-2 Silben)
- Freundlich und einpraegsam
- Weiblich klingend
- NICHT aus dieser Liste: {exclude_str}

Antworte NUR mit dem Namen, nichts anderes."""

        response = self.client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,  # Higher for creativity
            max_tokens=20,
        )

        name = response.choices[0].message.content.strip()

        # Clean up response (remove quotes, punctuation)
        name = name.strip('"\'.,!?')

        # Validate: should be short and not in exclude
        if len(name) <= 10 and name not in exclude:
            return name

        return None

    async def generate_traits(self, user_id: str = "default", count: int = 3) -> List[str]:
        """
        Generate personality traits.

        Args:
            user_id: User identifier for personalization
            count: Number of traits to generate

        Returns:
            List of trait strings
        """
        # For now, use a mix from pools
        # Future: Personalize based on user history

        traits = []

        # Always include one positive trait
        traits.append(random.choice(TRAIT_POOLS["positive"]))

        # Add from other pools
        remaining = count - 1
        other_pools = ["professional", "casual"]

        for _ in range(remaining):
            pool_name = random.choice(other_pools)
            pool = TRAIT_POOLS[pool_name]
            trait = random.choice([t for t in pool if t not in traits])
            traits.append(trait)

        return traits[:count]

    async def generate_style(self, user_history: Optional[List] = None) -> str:
        """
        Generate interaction style based on user history.

        Args:
            user_history: Optional list of past interactions

        Returns:
            Style string: "formal" | "casual" | "technical"
        """
        if not user_history:
            return "casual"  # Default to casual

        # Analyze history for style indicators
        # Future: Use LLM to analyze interaction patterns

        return "casual"

    async def generate_verbosity(self, user_history: Optional[List] = None) -> str:
        """
        Generate verbosity preference based on user history.

        Args:
            user_history: Optional list of past interactions

        Returns:
            Verbosity string: "concise" | "detailed"
        """
        if not user_history:
            return "concise"  # Default to concise (good for voice)

        # Analyze if user prefers detailed explanations
        # Future: Use LLM to analyze interaction patterns

        return "concise"


# Singleton
_personality_generator: Optional[PersonalityGenerator] = None


def get_personality_generator() -> PersonalityGenerator:
    """Get or create PersonalityGenerator singleton."""
    global _personality_generator
    if _personality_generator is None:
        _personality_generator = PersonalityGenerator()
    return _personality_generator


__all__ = [
    "PersonalityGenerator",
    "get_personality_generator",
    "FALLBACK_NAMES",
    "TRAIT_POOLS",
]
