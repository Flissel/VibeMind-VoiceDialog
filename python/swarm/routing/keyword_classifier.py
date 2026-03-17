"""
Deterministic keyword-based intent classifier.

Zero-cost fallback when LLM classifier is unavailable (no API credits, offline, etc.).
Maps German/English phrases to event_types using regex patterns extracted from
the CLASSIFIER_PROMPT_TEMPLATE in intent_classifier.py.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Pattern: (compiled_regex, event_type, param_extractor_or_None)
_RULES: List[Tuple[re.Pattern, str, Optional[str]]] = []


def _build_rules():
    """Build classification rules once. Order matters — first match wins."""
    global _RULES
    if _RULES:
        return

    def r(pattern: str, event_type: str, param_key: Optional[str] = None):
        _RULES.append((re.compile(pattern, re.IGNORECASE), event_type, param_key))

    # ── Bubble Events ──
    r(r"(?:zeig|list|alle)\w*\s*(?:meine\s+)?(?:bubbles?|spaces?|bereiche?)", "bubble.list")
    r(r"(?:erstell|mach|neu)\w*\s+(?:eine?\s+)?bubble\s+(.+)", "bubble.create", "title")
    r(r"(?:geh|wechsel|navigier)\w*\s+(?:in|zu|nach)\s+(.+)", "bubble.enter", "bubble_name")
    r(r"^(?:zurueck|back|exit|raus)$", "bubble.exit")

    # ── Idea Events ──
    r(r"(?:zeig|list|alle)\w*\s*(?:die\s+)?(?:ideen?|notizen?|notes?)", "idea.list")
    r(r"(?:notier|merk|schreib|erstell)\w*[:\s]+(.+)", "idea.create", "title")
    r(r"(?:verlink|verbind|connect)\w*\s+(?:die\s+)?(?:ideen?|notizen?)", "idea.auto_link")
    r(r"(?:formatier|struktur)\w*.*(?:als|in)\s+(\w+)", "idea.format", "format_type")
    r(r"(?:was\s+hab\s+ich|meine)\s+(?:notiert|aufgeschrieben|ideen)", "idea.list")

    # ── Code Events ──
    r(r"(?:erstell|bau|generier|mach)\w*\s+(?:eine?\s+)?(?:app|anwendung|programm|software)\s+(?:fuer|for)\s+(.+)", "code.generate", "description")
    r(r"(?:code|projekt|generation)\w*[\s-]*status", "code.status")
    r(r"(?:code|projekt)\s+(?:abbrech|cancel|stopp)", "code.cancel")

    # ── Desktop Events ──
    r(r"(?:oeffne|start|open)\s+(.+)", "desktop.open_app", "app_name")
    r(r"(?:screenshot|bildschirmfoto|bildschirm\s*aufnahme)", "desktop.screenshot")
    r(r"(?:klick|click)\w*\s+(?:auf\s+)?(.+)", "desktop.click", "element")
    r(r"(?:schliess|close)\w*\s+(.+)", "desktop.close_app", "app_name")

    # ── Schedule Events ──
    r(r"(?:setz|erstell|plan|mach)\w*\s+(?:einen?\s+)?(?:termin|erinnerung|timer|wecker)", "schedule.create")
    r(r"(?:erinner)\w*\s+(?:mich\s+)?(?:an\s+)?(.+)", "schedule.create", "title")
    r(r"(?:zeig|list)\w*\s*(?:meine\s+)?(?:termine?|erinnerungen?|schedule)", "schedule.list")

    # ── N8n Events ──
    r(r"(?:erstell|bau|generier)\w*\s+(?:einen?\s+)?workflow\s+(?:fuer|for)\s+(.+)", "n8n.generate", "description")
    r(r"(?:zeig|list)\w*\s*(?:alle\s+)?workflows?", "n8n.list")
    r(r"n8n\s*status", "n8n.status")

    # ── Research Events ──
    r(r"(?:recherchier|such|forsch|research)\w*\s+(?:nach\s+|ueber\s+|zu\s+)?(.+)", "research.search", "query")

    # ── Roarboot Events ──
    r(r"(?:roarboot|rowboat)\s+(.+)", "roarboot.query", "query")

    # ── Conversation Events ──
    r(r"^(?:hallo|hi|hey|guten\s+(?:morgen|tag|abend)|servus)\b", "conversation.greeting")
    r(r"^(?:danke|tschuess|bye|auf\s+wiedersehen)\b", "conversation.farewell")
    r(r"(?:hilfe|help|was\s+kannst\s+du)", "conversation.help")

    logger.info(f"KeywordClassifier: {len(_RULES)} rules loaded")


def classify_by_keywords(user_input: str) -> Optional[Dict[str, Any]]:
    """
    Classify user input using deterministic keyword rules.

    Returns:
        Dict with event_type + parameters, or None if no match.
    """
    _build_rules()
    text = user_input.strip()

    for pattern, event_type, param_key in _RULES:
        match = pattern.search(text)
        if match:
            result = {
                "event_type": event_type,
                "parameters": {},
                "response_hint": "",
                "classifier": "keyword",
            }
            # Extract parameter from capture group
            if param_key and match.lastindex and match.lastindex >= 1:
                result["parameters"][param_key] = match.group(1).strip()

            logger.debug(f"KeywordClassifier: '{text}' -> {event_type}")
            return result

    return None
