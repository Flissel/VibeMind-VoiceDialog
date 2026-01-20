"""
Conversion Package - Personalized AI with dynamic personality

Phase 13: Conversion AI System

Components:
- ConversionAI: Personalized AI with user-adapted responses
- PersonalityGenerator: Self-naming and trait generation
- AIPersonality: Personality configuration dataclass
"""

from swarm.conversion.conversion_ai import (
    AIPersonality,
    ConversionAI,
    get_conversion_ai,
)
from swarm.conversion.personality_generator import (
    PersonalityGenerator,
    get_personality_generator,
)

__all__ = [
    # Personality
    "AIPersonality",
    "PersonalityGenerator",
    "get_personality_generator",
    # Conversion AI
    "ConversionAI",
    "get_conversion_ai",
]
