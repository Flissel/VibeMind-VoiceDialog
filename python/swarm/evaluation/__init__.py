"""
VibeMind Intent Evaluation Framework

Provides tools for:
- Synthetic conversation generation for testing
- Batch evaluation of intent classification
- Real-time evaluation with user feedback
- Accuracy reporting and metrics
"""

from .intent_taxonomy import IntentCategory, INTENT_TAXONOMY, get_category

__all__ = [
    "IntentCategory",
    "INTENT_TAXONOMY",
    "get_category",
]
