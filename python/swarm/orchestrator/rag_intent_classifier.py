"""
RAG Intent Classifier

Uses Supermemory's semantic search to find relevant intent rules,
then passes them to an LLM for final classification.

This replaces hardcoded keyword matching with a more flexible,
semantically-aware approach.

Architecture:
    User Input -> Supermemory Search -> Top-K Rules -> LLM + Rules -> Intent
"""

import logging
import json
import os
import asyncio
import concurrent.futures
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from data.intent_rule_repository import (
    IntentRuleRepository,
    IntentRule,
    get_intent_rule_repository,
)

# Import status monitor for operation tracking
try:
    from swarm.monitoring.system_status import get_status_monitor
    _monitor = get_status_monitor()
except ImportError:
    _monitor = None

logger = logging.getLogger(__name__)


@dataclass
class RAGClassificationResult:
    """Result of RAG-based intent classification."""
    event_type: str
    confidence: float
    reasoning: str
    used_rules: List[str]  # intent_types of rules used for context
    payload: Dict[str, Any]
    user_input: str = ""  # Original transcript for fallback parameter extraction
    # Multi-step support
    is_multi_step: bool = False
    steps: List[Dict[str, Any]] = field(default_factory=list)


# LLM Prompt Template for classification with retrieved rules
RAG_CLASSIFIER_PROMPT = """Du bist ein Intent-Classifier für eine Voice-AI Anwendung.

{context_section}
## Relevante Intent-Regeln (semantisch ähnlich zur Anfrage)

{rules_context}

## Aufgabe

Analysiere die Benutzeranfrage und klassifiziere sie basierend auf den obigen Regeln.

WICHTIG:
- Wähle den Intent-Typ mit der höchsten semantischen Übereinstimmung
- Wenn KEINE spezifischen Namen genannt werden (wie "Idee A mit Idee B"), ist es KEIN idea.connect!
- "die Ideen verlinken" (Plural, unspezifisch) -> idea.auto_link
- "Verbinde X mit Y" (zwei Namen) -> idea.connect
- Bei Unsicherheit: Wähle den Intent mit höherer Priorität

KREATION vs EXPANSION:
- "Neue Idee:" am Anfang -> idea.create (NICHT idea.expand!)
- "Notiere", "Speichere", "Merke dir" -> idea.create
- Der INHALT der Idee (z.B. "beheben", "verbessern", "ändern") bestimmt NICHT den Intent!
- idea.expand ist NUR wenn der User explizit sagt "erweitere die bestehenden Ideen"

## MULTI-STEP ERKENNUNG (VOLLSTÄNDIGER ACTION PLAN)

Wenn die Anfrage MEHRERE unterschiedliche Aktionen enthält, setze "is_multi_step": true.

Für Multi-Step MUSS jeder Step haben:
- event_type: Die Capability
- payload: ALLE extrahierten Parameter (KRITISCH!)
- depends_on: Index des vorherigen Steps (wenn Ergebnis benötigt)
- output_ref: Was dieser Step produziert (optional, für Verkettung)

WICHTIG: Extrahiere die Parameter für JEDEN Step separat aus dem User-Text!

Beispiele für Multi-Step:

1. "Finde die In-Hand-Analyse und klassifiziere sie"
{{
    "is_multi_step": true,
    "steps": [
        {{"event_type": "idea.find", "payload": {{"query": "In-Hand-Analyse"}}, "output_ref": "found_idea"}},
        {{"event_type": "idea.classify", "payload": {{"idea_name": "In-Hand-Analyse"}}, "depends_on": 0}}
    ]
}}

2. "Update Desktop Automation mit Features und formatiere als Tabelle"
{{
    "is_multi_step": true,
    "steps": [
        {{"event_type": "idea.update", "payload": {{"idea_name": "Desktop Automation", "topic": "Features fuer Desktop Automatisierung", "mode": "generate"}}}},
        {{"event_type": "idea.format_table", "payload": {{"idea_name": "Desktop Automation"}}, "depends_on": 0}}
    ]
}}

3. "Gehe in den Space Test und zeige die Ideen"
{{
    "is_multi_step": true,
    "steps": [
        {{"event_type": "bubble.enter", "payload": {{"bubble_name": "Test"}}}},
        {{"event_type": "idea.list", "payload": {{}}, "depends_on": 0}}
    ]
}}

Einzelne Aktionen sind KEIN Multi-Step:
- "Lösche alle Ideen" → KEIN Multi-Step (eine Aktion)
- "Erstelle eine Idee über Marketing" → KEIN Multi-Step (eine Aktion)

## Benutzeranfrage

"{user_input}"

## PARAMETER EXTRAKTION (KRITISCH!)

Du MUSST alle Parameter aus der Benutzeranfrage extrahieren und im payload zurückgeben!

Parameter-Referenz:
- bubble.create: {{"title": "Space-Name"}}
- bubble.enter: {{"bubble_name": "Space-Name"}}
- bubble.delete: {{"bubble_name": "Space-Name"}}
- bubble.update: {{"new_title": "Neuer-Name"}} (oder {{"new_description": "Neue Beschreibung"}})
- idea.create: {{"title": "Idee-Titel", "content": "Optionaler Inhalt"}}
- idea.delete: {{"idea_name": "Idee-Name"}} oder {{}} für alle
- idea.find: {{"query": "Suchbegriff"}}
- idea.connect: {{"source": "Idee A", "target": "Idee B"}}
- idea.update:
  - Literal (User gibt expliziten Text): {{"idea_name": "Name", "new_content": "Der exakte neue Text", "mode": "literal"}}
  - Generieren (User will Content erzeugen lassen): {{"idea_name": "Name", "topic": "Was generiert werden soll", "mode": "generate"}}
  WICHTIG: Bei "update mit Features über X" oder "schreib X" → mode="generate", topic="X"
  NIEMALS den User-Prompt als new_content kopieren!
- idea.format_table: {{"idea_name": "Name", "custom_columns": ["Spalte1", "Spalte2"]}}
- idea.summarize: {{"idea_name": "Name", "style": "concise"}} (style: concise|detailed|actionable)
- idea.whitepaper: {{"start_node": "Idee-Name"}}
- idea.expand: {{"idea_name": "Name", "count": 3}}
- idea.classify: {{"idea_name": "Name"}} (optional - wenn leer, nutze aktuelle/Root-Idee)
- idea.auto_link: {{}} (keine Parameter nötig)
- idea.analyze_links: {{}} (keine Parameter nötig)

## Antwortformat (NUR JSON)

Für EINZELNE Aktionen - EXTRAHIERE ALLE PARAMETER:
Eingabe: "Erstelle Space Marketing"
{{
    "event_type": "bubble.create",
    "confidence": 0.95,
    "reasoning": "User will Space 'Marketing' erstellen",
    "payload": {{"title": "Marketing"}},
    "is_multi_step": false
}}

Eingabe: "Gehe in den Space Projekte"
{{
    "event_type": "bubble.enter",
    "confidence": 0.95,
    "reasoning": "User will in Space 'Projekte' wechseln",
    "payload": {{"bubble_name": "Projekte"}},
    "is_multi_step": false
}}

Für MULTI-STEP - EXTRAHIERE ALLE PARAMETER PRO SCHRITT:
Eingabe: "Erstelle Space Businessplan, gehe hinein und erstelle eine Idee Roadmap"
{{
    "event_type": "multi_step",
    "confidence": 0.90,
    "reasoning": "3 Aktionen: Space erstellen, hinein gehen, Idee erstellen",
    "payload": {{}},
    "is_multi_step": true,
    "steps": [
        {{"event_type": "bubble.create", "payload": {{"title": "Businessplan"}}}},
        {{"event_type": "bubble.enter", "payload": {{"bubble_name": "Businessplan"}}, "depends_on": 0}},
        {{"event_type": "idea.create", "payload": {{"title": "Roadmap"}}, "depends_on": 1}}
    ]
}}

Eingabe: "Liste alle Ideen und lösche sie"
{{
    "event_type": "multi_step",
    "confidence": 0.90,
    "reasoning": "2 Aktionen: Auflisten dann Löschen",
    "payload": {{}},
    "is_multi_step": true,
    "steps": [
        {{"event_type": "idea.list", "payload": {{}}}},
        {{"event_type": "idea.delete", "payload": {{}}, "depends_on": 0}}
    ]
}}

WICHTIG: Wenn ein Name/Titel im Text genannt wird, MUSS er im payload stehen!

Antworte NUR mit dem JSON-Objekt:"""


class RAGIntentClassifier:
    """
    RAG-based intent classifier using Supermemory for rule retrieval.

    Flow:
    1. User input -> Supermemory semantic search
    2. Top-K relevant rules retrieved
    3. Rules + input -> LLM for classification
    4. Structured result with confidence and reasoning
    """

    def __init__(
        self,
        rule_repo: Optional[IntentRuleRepository] = None,
        model: str = None,
        top_k: int = 5,
    ):
        """
        Initialize the RAG classifier.

        Args:
            rule_repo: IntentRuleRepository instance (or use singleton)
            model: LLM model to use for classification (default: RAG_CLASSIFIER_MODEL env or Claude Opus 4.5)
            top_k: Number of rules to retrieve for context
        """
        self.rule_repo = rule_repo or get_intent_rule_repository()
        # Use env var for model, default to Claude Opus 4.5 (best quality)
        self.model = model or os.getenv("RAG_CLASSIFIER_MODEL", "anthropic/claude-opus-4.5")
        self.top_k = top_k

        # LLM client (lazy init)
        self._llm_client = None

        logger.info(f"[RAGIntentClassifier] Initialized with model={model}, top_k={top_k}")

    @property
    def llm_client(self):
        """Lazy-load the LLM client."""
        import sys as _sys
        if self._llm_client is None:
            try:
                from openai import OpenAI
                api_key = os.getenv("OPENROUTER_API_KEY")
                if api_key:
                    print(f"[Python DEBUG] [RAG] Creating OpenRouter client (key={api_key[:20]}...)", file=_sys.stderr, flush=True)
                    self._llm_client = OpenAI(
                        api_key=api_key,
                        base_url="https://openrouter.ai/api/v1",
                        timeout=10.0,  # 10 second timeout for ElevenLabs compatibility
                    )
                    print(f"[Python DEBUG] [RAG] OpenRouter client created successfully", file=_sys.stderr, flush=True)
                else:
                    print(f"[Python DEBUG] [RAG] ERROR: OPENROUTER_API_KEY not set!", file=_sys.stderr, flush=True)
                    logger.warning("[RAGIntentClassifier] OPENROUTER_API_KEY not set")
            except ImportError as e:
                print(f"[Python DEBUG] [RAG] ERROR: OpenAI library not installed: {e}", file=_sys.stderr, flush=True)
                logger.error("[RAGIntentClassifier] OpenAI library not installed")
        return self._llm_client

    async def classify(
        self,
        user_input: str,
        bubble_context: Optional[Dict[str, Any]] = None
    ) -> RAGClassificationResult:
        """
        Classify user intent using RAG approach.

        Args:
            user_input: The user's voice/text input
            bubble_context: Optional context about current bubble and ideas

        Returns:
            RAGClassificationResult with event_type, confidence, etc.
        """
        import sys as _sys
        print(f"[Python DEBUG] [RAG] classify() called: {user_input[:50]}...", file=_sys.stderr, flush=True)

        # 1. Retrieve relevant rules from Supermemory
        print(f"[Python DEBUG] [RAG] Step 1: Searching rules...", file=_sys.stderr, flush=True)
        relevant_rules = self.rule_repo.search_similar(user_input, top_k=self.top_k)

        if not relevant_rules:
            print(f"[Python DEBUG] [RAG] No rules found - using fallback", file=_sys.stderr, flush=True)
            logger.warning(f"[RAGIntentClassifier] No rules found for: {user_input[:50]}...")
            return self._fallback_classification(user_input)

        # 2. Build context from rules
        rules_context = self._build_rules_context(relevant_rules)
        used_rule_types = [rule.intent_type for rule in relevant_rules]
        print(f"[Python DEBUG] [RAG] Step 2: Found {len(relevant_rules)} rules: {used_rule_types}", file=_sys.stderr, flush=True)

        logger.info(f"[RAGIntentClassifier] Retrieved rules: {used_rule_types}")

        # 3. Call LLM with rules as context
        print(f"[Python DEBUG] [RAG] Step 3: Calling LLM (model={self.model})...", file=_sys.stderr, flush=True)
        try:
            # Check LLM client availability
            if not self.llm_client:
                print(f"[Python DEBUG] [RAG] ERROR: LLM client is None! Check OPENROUTER_API_KEY", file=_sys.stderr, flush=True)
                raise ValueError("LLM client not available - check OPENROUTER_API_KEY")

            result = await self._call_llm(user_input, rules_context, bubble_context)
            result.used_rules = used_rule_types
            print(f"[Python DEBUG] [RAG] Step 4: LLM returned: {result.event_type} ({result.confidence:.0%})", file=_sys.stderr, flush=True)
            return result
        except Exception as e:
            print(f"[Python DEBUG] [RAG] ERROR in LLM call: {type(e).__name__}: {e}", file=_sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=_sys.stderr)
            logger.error(f"[RAGIntentClassifier] LLM call failed: {e}")
            return self._fallback_classification(user_input, relevant_rules)

    def _build_rules_context(self, rules: List[IntentRule]) -> str:
        """Build context string from retrieved rules."""
        context_parts = []
        for i, rule in enumerate(rules, 1):
            examples_str = ", ".join(f'"{ex}"' for ex in rule.examples[:3])
            context_parts.append(
                f"{i}. **{rule.intent_type}** (Priorität: {rule.priority})\n"
                f"   Beschreibung: {rule.description}\n"
                f"   Beispiele: {examples_str}"
            )
        return "\n\n".join(context_parts)

    async def _call_llm(
        self,
        user_input: str,
        rules_context: str,
        bubble_context: Optional[Dict[str, Any]] = None
    ) -> RAGClassificationResult:
        """Call the LLM for classification."""
        if not self.llm_client:
            raise ValueError("LLM client not available")

        # Build context section from bubble context
        context_section = ""
        if bubble_context and bubble_context.get("bubble_id"):
            idea_titles = bubble_context.get("idea_titles", [])
            ideas_str = ", ".join(idea_titles[:10]) if idea_titles else "keine"
            context_section = (
                f"## Aktueller Kontext\n\n"
                f"- Aktueller Space: {bubble_context.get('bubble_name', 'Unbekannt')}\n"
                f"- Anzahl Ideen: {bubble_context.get('idea_count', 0)}\n"
                f"- Ideen: {ideas_str}\n\n"
            )

        prompt = RAG_CLASSIFIER_PROMPT.format(
            context_section=context_section,
            rules_context=rules_context,
            user_input=user_input,
        )

        # Run sync OpenAI call in thread pool to avoid blocking event loop
        import time as _time
        import sys as _sys

        def _sync_llm_call():
            start = _time.perf_counter()
            # Track with status monitor
            op_id = None
            if _monitor:
                op_id = _monitor.start_operation(
                    "llm_call",
                    f"RAG classify: {user_input[:40]}...",
                    {"model": self.model}
                )
            print(f"[Python DEBUG] [RAG LLM] Calling {self.model}...", file=_sys.stderr, flush=True)
            try:
                result = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Du bist ein präziser Intent-Classifier. Antworte nur mit JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=2048,  # Sufficient for 30+ step multi-step responses
                )
                elapsed = _time.perf_counter() - start
                print(f"[Python DEBUG] [RAG LLM] Completed in {elapsed:.2f}s", file=_sys.stderr, flush=True)
                if _monitor and op_id:
                    _monitor.complete_operation(op_id, success=True)
                return result
            except Exception as e:
                elapsed = _time.perf_counter() - start
                print(f"[Python DEBUG] [RAG LLM] FAILED after {elapsed:.2f}s: {e}", file=_sys.stderr, flush=True)
                if _monitor and op_id:
                    _monitor.complete_operation(op_id, success=False, error=str(e))
                raise

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            response = await loop.run_in_executor(pool, _sync_llm_call)

        # Detect truncation - critical for debugging multi-step failures
        if response.choices[0].finish_reason == "length":
            logger.warning(f"[RAGIntentClassifier] Response TRUNCATED! max_tokens too low. Input: {user_input[:50]}...")

        response_text = response.choices[0].message.content.strip()

        # Parse JSON response
        try:
            # Clean up potential markdown formatting
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            data = json.loads(response_text)

            # Extract multi-step data
            is_multi_step = data.get("is_multi_step", False)
            steps = data.get("steps", [])

            # Log multi-step detection
            if is_multi_step:
                logger.info(f"[RAGIntentClassifier] Multi-step detected: {len(steps)} steps")

            return RAGClassificationResult(
                event_type=data.get("event_type", "conversation.unknown"),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                used_rules=[],  # Will be filled by caller
                payload=data.get("payload", {}),
                user_input=user_input,  # Preserve original transcript
                is_multi_step=is_multi_step,
                steps=steps,
            )
        except json.JSONDecodeError as e:
            logger.error(f"[RAGIntentClassifier] Failed to parse LLM response: {response_text[:100]}")
            raise ValueError(f"Invalid JSON response: {e}")

    def _fallback_classification(
        self,
        user_input: str,
        rules: Optional[List[IntentRule]] = None,
    ) -> RAGClassificationResult:
        """
        Fallback classification when LLM is unavailable.

        Uses simple heuristics based on retrieved rules.
        """
        if rules and len(rules) > 0:
            # Use the highest-priority rule
            best_rule = max(rules, key=lambda r: r.priority)
            return RAGClassificationResult(
                event_type=best_rule.intent_type,
                confidence=0.5,
                reasoning=f"Fallback: Beste Übereinstimmung mit {best_rule.description}",
                used_rules=[best_rule.intent_type],
                payload={},
                user_input=user_input,  # Preserve transcript
            )

        return RAGClassificationResult(
            event_type="conversation.unknown",
            confidence=0.3,
            reasoning="Keine passende Regel gefunden",
            used_rules=[],
            payload={},
            user_input=user_input,  # Preserve transcript
        )


# =============================================================================
# SINGLETON
# =============================================================================

_classifier: Optional[RAGIntentClassifier] = None


def get_rag_intent_classifier() -> RAGIntentClassifier:
    """Get or create the singleton RAGIntentClassifier."""
    global _classifier
    if _classifier is None:
        _classifier = RAGIntentClassifier()
    return _classifier


__all__ = [
    "RAGIntentClassifier",
    "RAGClassificationResult",
    "get_rag_intent_classifier",
]
