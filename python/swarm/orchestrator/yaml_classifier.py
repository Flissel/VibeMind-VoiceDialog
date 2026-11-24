"""
YamlClassifier — Ideas-Space Intent Classifier driven by tool_schemas.yml.

Drop-in alternative to IntentClassifier for the Ideas-Space (bubble.* + idea.*).
Uses a compact, YAML-sourced prompt (~1.5k tokens vs. ~10k for the legacy
classifier). Activated via USE_YAML_CLASSIFIER=true env flag.

Return shape matches IntentClassifier.classify():
  {"event_type": str, "payload": dict, "response_hint": str}
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, Optional

from swarm.orchestrator.schema_loader import render_ideas_space_block

MAX_RETRIES = 3          # total attempts (first + 2 retries)
BACKOFF_BASE = 0.3       # seconds — doubles per retry

logger = logging.getLogger(__name__)


PROMPT_TEMPLATE = """Du klassifizierst Benutzer-Intents zu Event-Types im VibeMind Ideas-Space.

Verfuegbare Events:

$EVENT_BLOCK$

Regeln:
- Antworte NUR mit JSON, keine Erklaerung.
- Format: {"event_type": "<exakter Name>", "payload": {<params>}}
- payload enthaelt NUR die tatsaechlich genannten Parameter.
- Wenn unklar: {"event_type": "conversation.unknown", "payload": {}}

Benutzer-Input: "$INTENT$"

JSON:"""


GREETING = re.compile(
    r"^\s*(?:hallo|hi|hey|moin|servus|guten\s+(?:morgen|tag|abend))(?:\s+rachel)?\s*[!.,]*\s*$",
    re.IGNORECASE,
)
GREETING_HINT = "Hallo! Wie kann ich dir helfen?"
THANKS = re.compile(
    r"^\s*(?:danke(?:\s*sch(?:ö|oe)n)?|dankesch(?:ö|oe)n|vielen\s+dank|merci)(?:\s+rachel)?\s*[!.,]*\s*$",
    re.IGNORECASE,
)
THANKS_HINT = "Gern geschehen!"
# A bare yes, no or ok. The old path only runs when the Brain gave no sentence, so there is no
# question of the Brain open that it answers: it is acknowledged calmly and nothing is done.
YES = re.compile(
    r"^\s*(?:ja|jo|jap|jep|jawohl|genau|ok|okay|okey|alles\s+klar|passt)(?:\s+rachel)?\s*[!.,]*\s*$",
    re.IGNORECASE,
)
NO = re.compile(r"^\s*(?:nein|nee|n(?:ö|oe))(?:\s+rachel)?\s*[!.,]*\s*$", re.IGNORECASE)
YES_HINT = "Alles klar."
NO_HINT = "In Ordnung."
# Nothing to read: empty, blanks or only punctuation.
EMPTY = re.compile(r"^[\s\W_]*$")
EMPTY_HINT = "Ich hoere zu..."
# Marks an "unknown" that comes from a classifier out of reach (no key, no agent, no answer), not
# from the sentence: the answer says so calmly (tool_registry, conversation.unknown).
NO_CLASSIFIER = "_einordner_fehlt"


def fixed_rule(intent_text: str) -> Optional[Dict[str, Any]]:
    """What is safe to answer without a model (a call to OpenFang takes 9 to 21 s): a greeting,
    a thanks, a bare yes/no/ok ("ja", "Nein.", "okay") and an empty input."""
    if intent_text is None:
        intent_text = ""
    if not isinstance(intent_text, str):
        return None
    rules = (
        (EMPTY, "conversation.listening", {}, EMPTY_HINT),
        (GREETING, "conversation.greeting", {}, GREETING_HINT),
        (THANKS, "conversation.thanks", {}, THANKS_HINT),
        (YES, "conversation.ack", {"antwort": "ja"}, YES_HINT),
        (NO, "conversation.ack", {"antwort": "nein"}, NO_HINT),
    )
    for pattern, event_type, payload, hint in rules:
        if pattern.match(intent_text):
            return {"event_type": event_type, "payload": dict(payload), "parameters": dict(payload), "response_hint": hint}
    return None


class YamlClassifier:
    """Classifier driven by tool_schemas.yml for Ideas-Space events."""

    def __init__(self, model_client=None):
        self._own_client = None
        self._model = None
        # Reuse same provider/model as legacy IntentClassifier
        from llm_config import classifier_role, get_client, get_model, get_provider
        role = classifier_role()
        self._model = get_model(role)
        # The retries were for openrouter/free and its flaky providers; OpenFang gets one call.
        self._openfang = get_provider(role) == "openfang"
        self._retries = 1 if self._openfang else MAX_RETRIES
        try:
            self._own_client = get_client(role)
            logger.info(f"YamlClassifier using {self._model}")
        except Exception as e:
            if get_provider(role) != "openfang":
                logger.error(f"YamlClassifier init failed: {e}")
                raise
            # no OpenFang key: no call at all, "nicht verstanden" at once (never OpenRouter)
            logger.warning(f"YamlClassifier: {e}; the old path sends nothing")

        # Pre-render the event block once (schemas cached in schema_loader)
        self._event_block = render_ideas_space_block(max_examples=3)
        logger.debug(f"YamlClassifier event block: {len(self._event_block)} chars")

    @property
    def client(self):
        return self._own_client

    async def classify(self, intent_text: str) -> Dict[str, Any]:
        """Classify intent into event_type + payload. Shape matches IntentClassifier.

        Retries on transient errors (provider 404, bad JSON) up to MAX_RETRIES times
        with exponential backoff. openrouter/free routes to multiple providers; some
        return 404/malformed responses, a retry often hits a working provider.
        """
        start = time.perf_counter()
        # A greeting needs no model (fixed rule, same form as an answer of the model)
        fixed = fixed_rule(intent_text)
        if fixed is not None:
            logger.info(f"[YamlClassifier] {fixed['event_type']} by fixed rule")
            return fixed
        if self._own_client is None:
            return self._fallback(intent_text, "no client", unreachable=True)
        prompt = PROMPT_TEMPLATE.replace("$EVENT_BLOCK$", self._event_block).replace("$INTENT$", intent_text)

        logger.debug(f"[YamlClassifier] prompt size: {len(prompt)} chars")

        retries = getattr(self, "_retries", MAX_RETRIES)
        last_error: Optional[str] = None
        unreachable = False   # OpenFang gave no answer at all (no agent, refused, timeout)
        for attempt in range(1, retries + 1):
            # --- LLM call ---
            try:
                from llm_config import token_kwargs
                response = self._own_client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    **token_kwargs(self._model, 300),
                )
                content = (response.choices[0].message.content or "").strip()
                logger.debug(f"[YamlClassifier] raw response (try {attempt}): {content[:200]}")
            except Exception as e:
                last_error = f"LLM error: {e}"
                unreachable = getattr(self, "_openfang", False)
                logger.warning(f"[YamlClassifier] try {attempt}/{retries} LLM call failed: {e}")
                if attempt < retries:
                    await asyncio.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))
                continue

            # --- JSON parse ---
            extracted = self._extract_json(content)
            try:
                result = json.loads(extracted)
            except json.JSONDecodeError as e:
                last_error = f"parse error: {e}"
                logger.warning(f"[YamlClassifier] try {attempt}/{retries} JSON parse failed: {e} / content={content[:200]}")
                if attempt < retries:
                    await asyncio.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))
                continue

            # --- Success ---
            event_type = result.get("event_type") or "conversation.unknown"
            payload = result.get("payload") or {}
            if not isinstance(payload, dict):
                payload = {}
            response_hint = result.get("response_hint") or f"Ich bearbeite {event_type}..."

            latency_ms = (time.perf_counter() - start) * 1000
            logger.info(f"[YamlClassifier] {event_type} in {latency_ms:.0f}ms (try {attempt})")

            return {
                "event_type": event_type,
                "payload": payload,
                "parameters": payload,  # HybridRouter reads .get("parameters")
                "response_hint": response_hint,
            }

        # All retries exhausted
        logger.warning(f"[YamlClassifier] exhausted {retries} retries: {last_error}")
        return self._fallback(intent_text, last_error or "unknown error", unreachable=unreachable)

    @staticmethod
    def _extract_json(content: str) -> str:
        """Strip markdown fences and explanatory text to isolate the first JSON object."""
        if "```json" in content:
            content = content.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in content:
            content = content.split("```", 1)[1].split("```", 1)[0].strip()
        elif not content.startswith("{") and "{" in content:
            content = content[content.find("{"):]

        if content.startswith("{"):
            brace_count = 0
            end_pos = 0
            for i, char in enumerate(content):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break
            if end_pos > 0:
                content = content[:end_pos]
        return content

    @staticmethod
    def _fallback(intent_text: str, reason: str, unreachable: bool = False) -> Dict[str, Any]:
        pl = {"original_text": intent_text, "_fallback_reason": reason}
        if unreachable:
            pl[NO_CLASSIFIER] = True
        return {
            "event_type": "conversation.unknown",
            "payload": pl,
            "parameters": pl,
            "response_hint": "Ich habe das nicht verstanden.",
        }


_classifier: Optional[YamlClassifier] = None


def get_yaml_classifier() -> YamlClassifier:
    """Get or create YamlClassifier singleton."""
    global _classifier
    if _classifier is None:
        _classifier = YamlClassifier()
    return _classifier
