"""Multi-step intent detector.

Heuristic gate that identifies user inputs combining two or more actions
connected by conjunctions like "und dann", "danach", "then", etc.

Extracted from the inline check at intent_classifier.py Rule 24 (which only
logged the detection but didn't act on it). The orchestrator now consults
this helper *before* asking the Brain event-classifier: if the input looks
multi-step, it defers to the LLM, which supports full multi-step planning
(`is_multi_step: true` with a `steps` array). The Brain only handles
single-step intents — letting it fire on a multi-step request would silently
drop half of what the user asked for.
"""
from __future__ import annotations

from typing import Tuple

# Multi-step connectors — match literal substrings with surrounding spaces
# to avoid false positives on substrings (e.g. "dann" inside a word).
_MULTI_STEP_CONNECTORS: Tuple[str, ...] = (
    " und dann ",
    " und anschließend ",
    " dann ",
    " danach ",
    ", dann ",
    " sowie ",
    " then ",
    " after that ",
    " afterwards ",
    " and then ",
    " and after ",
    # Plain " and " / " und " alone only count when there are ≥3 verbs,
    # handled below via _WEAK_CONNECTORS.
)

# Weak connectors — require MORE verbs to trigger, because " und " and " and "
# frequently appear in compound subjects ("Äpfel und Birnen") rather than
# compound actions ("erstelle X und füge Y hinzu").
_WEAK_CONNECTORS: Tuple[str, ...] = (
    " und ",
    " and ",
    ", und ",
    ", and ",
)

# Action verbs in DE and EN. Keep each verb DISTINCT — no substring variants
# (e.g. do NOT include both "erstelle" and "erstell", because "erstelle" will
# double-count and falsely flag single-verb inputs as multi-step).
_ACTION_VERBS: Tuple[str, ...] = (
    # German
    "erstelle", "lege", "füge", "fuege", "lösche", "loesche",
    "zeige", "liste", "verbinde", "verlinke", "gehe",
    "öffne", "oeffne", "schließe", "schliesse", "sende", "schreibe",
    "speichere", "entferne", "bearbeite",
    # English
    "create", "add", "delete", "remove", "show", "list", "link", "connect",
    "open", "close", "send", "write", "make", "build", "search", "take",
    "save", "edit", "fetch", "run",
)


def looks_multi_step(text: str) -> bool:
    """Return True if the input looks like a multi-action plan.

    Two paths trigger a multi-step classification:

    1. **Strong connector + ≥2 distinct verbs.** Strong connectors are
       explicit sequence markers like "dann", "then", "and then", "danach".
       Two verbs separated by one of these are a multi-step plan.

    2. **Weak connector + ≥2 distinct verbs.** Weak connectors are plain
       " und " / " and " which also appear in compound subjects
       ("Äpfel und Birnen"). We require two or more *distinct* verbs to
       avoid false positives, e.g. "erstelle eine idee für APIs und
       Microservices" has one verb and stays single-step.
    """
    is_multi, _ = explain(text)
    return is_multi


def explain(text: str) -> Tuple[bool, dict]:
    """Like looks_multi_step but also returns the evidence for logging."""
    text_lower = (text or "").lower()
    if not text_lower:
        return False, {"connectors": [], "weak_connectors": [], "verbs": [], "is_multi_step": False}

    strong = [c for c in _MULTI_STEP_CONNECTORS if c in text_lower]
    weak = [c for c in _WEAK_CONNECTORS if c in text_lower]
    verbs = sorted(set(v for v in _ACTION_VERBS if v in text_lower))

    is_multi = False
    if strong and len(verbs) >= 2:
        is_multi = True
    elif weak and len(verbs) >= 2:
        is_multi = True

    return is_multi, {
        "connectors": strong,
        "weak_connectors": weak,
        "verbs": verbs,
        "is_multi_step": is_multi,
    }
