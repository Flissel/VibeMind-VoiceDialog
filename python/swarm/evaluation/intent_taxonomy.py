"""
Intent Taxonomy - Categorization of all VibeMind intent types.

Provides a structured classification of the 35+ intent types into
9 semantic categories for analysis and reporting.
"""

from enum import Enum
from typing import Dict, Optional


class IntentCategory(Enum):
    """
    Semantic categories for intent classification.

    Each category represents a distinct type of user action:
    - QUERY: Read-only operations (listing, searching, status)
    - CREATE: Creating new entities (spaces, ideas, code)
    - MODIFY: Changing existing entities
    - DELETE: Removing entities
    - NAVIGATE: Moving between spaces
    - GENERATE: AI-powered content generation
    - AUTOMATE: Desktop automation tasks
    - PREVIEW: Live preview controls
    - CONVERSATION: Conversational intents (no backend action)
    - EVALUATION: Feedback on classification accuracy
    """
    QUERY = "query"              # Nur lesen, keine Aenderungen
    CREATE = "create"            # Neue Entitaeten erstellen
    MODIFY = "modify"            # Bestehende Entitaeten aendern
    DELETE = "delete"            # Entitaeten loeschen
    NAVIGATE = "navigate"        # Zwischen Spaces wechseln
    GENERATE = "generate"        # KI-gestuetzte Generierung
    AUTOMATE = "automate"        # Desktop-Automatisierung
    PREVIEW = "preview"          # Live-Vorschau steuern
    CONVERSATION = "conversation"  # Keine Backend-Aktion
    EVALUATION = "evaluation"    # Feedback zur Klassifikation


# Complete mapping of all intent types to their categories
INTENT_TAXONOMY: Dict[str, IntentCategory] = {
    # =========================================================================
    # QUERY - Read-only operations
    # =========================================================================
    "bubble.list": IntentCategory.QUERY,
    "bubble.find": IntentCategory.QUERY,  # Search for bubble by name (fuzzy)
    "bubble.stats": IntentCategory.QUERY,
    "bubble.current": IntentCategory.QUERY,
    "idea.list": IntentCategory.QUERY,
    "idea.find": IntentCategory.QUERY,
    "code.list": IntentCategory.QUERY,
    "code.status": IntentCategory.QUERY,

    # =========================================================================
    # CREATE - Creating new entities
    # =========================================================================
    "bubble.create": IntentCategory.CREATE,
    "idea.create": IntentCategory.CREATE,
    "code.generate": IntentCategory.CREATE,

    # =========================================================================
    # MODIFY - Changing existing entities
    # =========================================================================
    "idea.update": IntentCategory.MODIFY,
    "idea.connect": IntentCategory.MODIFY,
    "idea.move": IntentCategory.MODIFY,
    "bubble.promote": IntentCategory.MODIFY,
    "bubble.score": IntentCategory.MODIFY,

    # =========================================================================
    # DELETE - Removing entities
    # =========================================================================
    "bubble.delete": IntentCategory.DELETE,
    "idea.delete": IntentCategory.DELETE,
    "code.cancel": IntentCategory.DELETE,

    # =========================================================================
    # NAVIGATE - Moving between spaces
    # =========================================================================
    "bubble.enter": IntentCategory.NAVIGATE,
    "bubble.exit": IntentCategory.NAVIGATE,
    "code.exit": IntentCategory.NAVIGATE,  # Exit from Coding/Project Space

    # =========================================================================
    # GENERATE - AI-powered content generation
    # =========================================================================
    "idea.expand": IntentCategory.GENERATE,
    "idea.add_image": IntentCategory.GENERATE,
    "idea.auto_link": IntentCategory.GENERATE,

    # =========================================================================
    # AUTOMATE - Desktop automation
    # =========================================================================
    "desktop.task": IntentCategory.AUTOMATE,
    "desktop.open_app": IntentCategory.AUTOMATE,
    "desktop.click": IntentCategory.AUTOMATE,
    "desktop.type": IntentCategory.AUTOMATE,
    "desktop.press_key": IntentCategory.AUTOMATE,
    "desktop.screenshot": IntentCategory.AUTOMATE,
    "desktop.scroll": IntentCategory.AUTOMATE,

    # =========================================================================
    # PREVIEW - Live preview controls
    # =========================================================================
    "code.preview.start": IntentCategory.PREVIEW,
    "code.preview.stop": IntentCategory.PREVIEW,

    # =========================================================================
    # CONVERSATION - No backend action needed
    # =========================================================================
    "conversation.greeting": IntentCategory.CONVERSATION,
    "conversation.help": IntentCategory.CONVERSATION,
    "conversation.unknown": IntentCategory.CONVERSATION,
    "conversation.clarify": IntentCategory.CONVERSATION,

    # =========================================================================
    # EVALUATION - Feedback on classification
    # =========================================================================
    "evaluation.correct": IntentCategory.EVALUATION,
    "evaluation.incorrect": IntentCategory.EVALUATION,
    "evaluation.clarify": IntentCategory.EVALUATION,
}


# Category descriptions in German
CATEGORY_DESCRIPTIONS: Dict[IntentCategory, str] = {
    IntentCategory.QUERY: "Abfragen - Nur lesen, keine Aenderungen",
    IntentCategory.CREATE: "Erstellen - Neue Entitaeten anlegen",
    IntentCategory.MODIFY: "Modifizieren - Bestehende Entitaeten aendern",
    IntentCategory.DELETE: "Loeschen - Entitaeten entfernen",
    IntentCategory.NAVIGATE: "Navigieren - Zwischen Spaces wechseln",
    IntentCategory.GENERATE: "Generieren - KI-gestuetzte Erweiterung",
    IntentCategory.AUTOMATE: "Automatisieren - Desktop-Steuerung",
    IntentCategory.PREVIEW: "Vorschau - Live-Vorschau steuern",
    IntentCategory.CONVERSATION: "Gespraech - Keine Backend-Aktion",
    IntentCategory.EVALUATION: "Evaluation - Feedback zur Klassifikation",
}


def get_category(intent_type: str) -> Optional[IntentCategory]:
    """
    Get the category for an intent type.

    Args:
        intent_type: The intent event type (e.g., "bubble.create")

    Returns:
        IntentCategory or None if not found
    """
    return INTENT_TAXONOMY.get(intent_type)


def get_intents_by_category(category: IntentCategory) -> list:
    """
    Get all intent types for a specific category.

    Args:
        category: The IntentCategory to filter by

    Returns:
        List of intent type strings
    """
    return [
        intent for intent, cat in INTENT_TAXONOMY.items()
        if cat == category
    ]


def get_category_stats() -> Dict[IntentCategory, int]:
    """
    Get count of intents per category.

    Returns:
        Dict mapping category to count of intents
    """
    stats = {cat: 0 for cat in IntentCategory}
    for intent, category in INTENT_TAXONOMY.items():
        stats[category] += 1
    return stats


__all__ = [
    "IntentCategory",
    "INTENT_TAXONOMY",
    "CATEGORY_DESCRIPTIONS",
    "get_category",
    "get_intents_by_category",
    "get_category_stats",
]
