"""
Domain Router - Fast domain detection for intent routing.

Routes user intents to the correct domain stream based on keyword matching.
No LLM calls needed - uses pattern matching for speed.

Domains:
- ideas: Note/idea management within bubbles
- bubbles: Space/bubble creation and navigation
- desktop: Desktop automation, app control
- coding: Code generation, project creation
- shuttles: Requirements pipeline, specifications
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class Domain(Enum):
    """Available domains for intent routing."""
    IDEAS = "ideas"
    BUBBLES = "bubbles"
    DESKTOP = "desktop"
    CODING = "coding"
    SHUTTLES = "shuttles"
    UNKNOWN = "unknown"


@dataclass
class DomainMatch:
    """Result of domain detection."""
    domain: Domain
    confidence: float
    matched_keywords: List[str]
    stream: str

    @property
    def intent_stream(self) -> str:
        """Get the intent stream for this domain."""
        return f"intents:{self.domain.value}"


# Domain detection patterns
# Each domain has primary keywords (high confidence) and secondary (medium confidence)
DOMAIN_PATTERNS = {
    Domain.IDEAS: {
        "primary": [
            # German
            r"\b(idee|ideen|note|notes|notiz|notizen)\b",
            r"\b(erstelle|neue?)\s+(idee|note|notiz)",
            r"\b(liste?|zeig|finde)\s+(ideen|notes|notizen)",
            r"\bverbinde\b.*\bmit\b",  # "verbinde X mit Y"
            r"\btrenne\b",  # disconnect
            r"\bauto.?link",
            r"\bverlinke\b",
            r"\bsummar",  # summarize
            r"\berweitere\b.*\bideen\b",
            r"\bexplor",  # exploration
            # English
            r"\b(idea|ideas|note|notes)\b",
            r"\b(create|new)\s+(idea|note)",
            r"\b(list|show|find)\s+(ideas|notes)",
            r"\bconnect\b.*\bto\b",
            r"\bdisconnect\b",
        ],
        "secondary": [
            r"\binhalt\b",  # content
            r"\bbeschreibung\b",  # description
            r"\bformat",  # formatting
            r"\btabelle\b",  # table
            r"\baktionsliste\b",  # action list
        ],
    },
    Domain.BUBBLES: {
        "primary": [
            # German
            r"\b(bubble|bubbles|space|spaces|bereich|bereiche)\b",
            r"\b(gehe?|navigiere?)\s+(in|zu|nach)",
            r"\bzurück\b",  # back/exit
            r"\b(erstelle|neue?)\s+(bubble|space|bereich)",
            r"\blösche\s+(alle\s+)?(bubbles?|spaces?)",
            r"\balle\s+außer\b",  # delete all except
            # English
            r"\b(enter|go\s+to|navigate)\b",
            r"\bexit\b",
            r"\b(create|new)\s+(bubble|space)",
            r"\bdelete\s+(all\s+)?(bubbles?|spaces?)",
        ],
        "secondary": [
            r"\bwo\s+bin\s+ich\b",  # where am I
            r"\bübersicht\b",  # overview
            r"\bmultiverse\b",
        ],
    },
    Domain.DESKTOP: {
        "primary": [
            # German
            r"\böffne\b",  # open
            r"\bschließe?\b",  # close
            r"\bstarte?\b",  # start
            r"\bklick",  # click
            r"\btippe?\b",  # type
            r"\bschreibe?\b.*\bin\b",  # write in
            r"\bscreenshot\b",
            r"\bfenster\b",  # window
            r"\bapp(likation)?\b",
            r"\bbrowser\b",
            r"\bchrome\b",
            r"\bedge\b",
            r"\bfirefox\b",
            r"\bterminal\b",
            r"\bvscode\b",
            r"\bexplorer\b",
            # English
            r"\bopen\b",
            r"\bclose\b",
            r"\blaunch\b",
            r"\bclick\b",
            r"\btype\b",
            r"\bwindow\b",
        ],
        "secondary": [
            r"\bbildschirm\b",  # screen
            r"\bmonitor\b",
            r"\bsystem\b",
            r"\bauflösung\b",  # resolution
        ],
    },
    Domain.CODING: {
        "primary": [
            # German
            r"\b(code|coden|coding|programmier)\b",
            r"\berstelle\s+(eine?\s+)?(app|anwendung|programm|projekt)\b",
            r"\bgeneriere\s+code\b",
            r"\bimplementiere\b",
            r"\bfunktion\b",
            r"\bklasse\b",
            r"\bapi\b",
            r"\bbackend\b",
            r"\bfrontend\b",
            r"\bdatenbank\b",
            # English
            r"\b(generate|create)\s+code\b",
            r"\bimplement\b",
            r"\bfunction\b",
            r"\bclass\b",
            r"\bdatabase\b",
        ],
        "secondary": [
            r"\btest\b",
            r"\bdebug\b",
            r"\brefactor\b",
            r"\bbuild\b",
            r"\bdeploy\b",
        ],
    },
    Domain.SHUTTLES: {
        "primary": [
            # German
            r"\bshuttle\b",
            r"\banforderung(en)?\b",  # requirements
            r"\bspezifikation(en)?\b",  # specifications
            r"\bpipeline\b",
            r"\bworkflow\b",
            r"\bstufe\b",  # stage
            # English
            r"\brequirement\b",
            r"\bspecification\b",
            r"\bstage\b",
        ],
        "secondary": [
            r"\bvalidier\b",  # validate
            r"\bprüf\b",  # check
            r"\bfortschritt\b",  # progress
        ],
    },
}


class DomainRouter:
    """
    Routes user intents to the correct domain stream.

    Uses fast keyword matching instead of LLM calls.
    Falls back to UNKNOWN domain if no clear match.
    """

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for speed."""
        self._compiled = {}
        for domain, patterns in DOMAIN_PATTERNS.items():
            self._compiled[domain] = {
                "primary": [re.compile(p, re.IGNORECASE) for p in patterns["primary"]],
                "secondary": [re.compile(p, re.IGNORECASE) for p in patterns["secondary"]],
            }

    def detect_domain(self, text: str) -> DomainMatch:
        """
        Detect which domain an intent belongs to.

        Args:
            text: User input text

        Returns:
            DomainMatch with domain, confidence, and matched keywords
        """
        scores: dict[Domain, Tuple[float, List[str]]] = {}

        for domain, patterns in self._compiled.items():
            score = 0.0
            matched = []

            # Primary patterns = high weight
            for pattern in patterns["primary"]:
                if match := pattern.search(text):
                    score += 0.4
                    matched.append(match.group())

            # Secondary patterns = lower weight
            for pattern in patterns["secondary"]:
                if match := pattern.search(text):
                    score += 0.15
                    matched.append(match.group())

            if score > 0:
                scores[domain] = (min(score, 1.0), matched)

        if not scores:
            return DomainMatch(
                domain=Domain.UNKNOWN,
                confidence=0.0,
                matched_keywords=[],
                stream="intents:unknown"
            )

        # Get best match
        best_domain = max(scores.keys(), key=lambda d: scores[d][0])
        confidence, matched = scores[best_domain]

        logger.debug(f"[DomainRouter] '{text[:50]}...' → {best_domain.value} ({confidence:.0%})")

        return DomainMatch(
            domain=best_domain,
            confidence=confidence,
            matched_keywords=matched,
            stream=f"intents:{best_domain.value}"
        )

    def get_stream_for_domain(self, domain: Domain) -> str:
        """Get the intent stream name for a domain."""
        return f"intents:{domain.value}"

    def get_all_streams(self) -> List[str]:
        """Get all domain intent stream names."""
        return [f"intents:{d.value}" for d in Domain if d != Domain.UNKNOWN]


# Singleton instance
_domain_router: Optional[DomainRouter] = None


def get_domain_router() -> DomainRouter:
    """Get or create DomainRouter singleton."""
    global _domain_router
    if _domain_router is None:
        _domain_router = DomainRouter()
    return _domain_router


__all__ = [
    "Domain",
    "DomainMatch",
    "DomainRouter",
    "get_domain_router",
]
