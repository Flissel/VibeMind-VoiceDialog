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
    # Direct answer mode: LLM answers read queries from context without backend execution
    mode: str = "execute"  # "direct_answer" or "execute"
    direct_answer: str = ""  # Response text when mode=direct_answer


# LLM Prompt Template — Smart Router with direct answer + execute modes
RAG_CLASSIFIER_PROMPT = """Du bist der intelligente Router fuer VibeMind, eine Voice-AI Anwendung.
Du kannst Leseanfragen DIREKT beantworten oder Aktionen zur Ausfuehrung weiterleiten.

{context_section}

## Relevante Intent-Regeln (semantisch aehnlich zur Anfrage)

{rules_context}

## Benutzeranfrage

"{user_input}"

## Deine Aufgabe

Entscheide: Kannst du die Anfrage aus dem Kontext oben DIREKT beantworten, oder muss eine Aktion ausgefuehrt werden?

### MODUS 1: DIREKT ANTWORTEN (mode=direct_answer)

Verwende diesen Modus wenn der User nach INFORMATION fragt die im Kontext steht:
- Bubbles/Spaces auflisten, zaehlen, zeigen
- Ideen auflisten, zaehlen, zeigen
- Status-Abfragen ("wo bin ich?", "was gibt es?")
- Zusammenfassungen aus vorhandenen Daten

Antworte mit einer natuerlichen deutschen Phrase fuer Voice-Ausgabe (kurz, klar, sprechbar).

Beispiel: User fragt "Welche Spaces habe ich?"
{{
    "mode": "direct_answer",
    "answer": "Du hast 3 Spaces: Marketing, Design und Tech.",
    "confidence": 0.95
}}

Beispiel: User fragt "Wie viele Ideen sind in Marketing?"
{{
    "mode": "direct_answer",
    "answer": "Im Space Marketing sind 5 Ideen: API Design, Logo Redesign, Campaign Plan, Budget Overview und Timeline.",
    "confidence": 0.90
}}

### MODUS 2: AKTION AUSFUEHREN (mode=execute)

Verwende diesen Modus wenn der User etwas AENDERN will:
- Erstellen, loeschen, aendern, verschieben, verlinken, erweitern, formatieren
- Alles was den Zustand veraendert

WICHTIG fuer Klassifizierung:
- Wenn KEINE spezifischen Namen genannt werden -> idea.auto_link (nicht idea.connect)
- "Neue Idee:" / "Notiere" / "Merke dir" -> idea.create (NICHT idea.expand!)
- Der INHALT bestimmt NICHT den Intent!
- idea.expand NUR bei "erweitere die bestehenden Ideen"

Parameter-Referenz:
- bubble.create: {{"title": "Space-Name"}}
- bubble.enter: {{"bubble_name": "Space-Name"}}
- bubble.delete: {{"bubble_name": "Space-Name"}}
- bubble.update: {{"new_title": "Neuer-Name"}}
- idea.create: {{"title": "Idee-Titel", "content": "Optionaler Inhalt"}}
- idea.delete: {{"idea_name": "Idee-Name"}} oder {{}} fuer alle
- idea.find: {{"query": "Suchbegriff"}}
- idea.connect: {{"source": "Idee A", "target": "Idee B"}}
- idea.update:
  - Literal: {{"idea_name": "Name", "new_content": "Text", "mode": "literal"}}
  - Generieren: {{"idea_name": "Name", "topic": "Was generiert werden soll", "mode": "generate"}}
- idea.format_table: {{"idea_name": "Name", "custom_columns": ["Spalte1", "Spalte2"]}}
- idea.summarize: {{"idea_name": "Name", "style": "concise"}}
- idea.whitepaper: {{"start_node": "Idee-Name"}}
- idea.expand: {{"idea_name": "Name", "count": 3}}
- idea.classify: {{"idea_name": "Name"}}
- idea.auto_link: {{}}
- idea.analyze_links: {{}}

Beispiel: User sagt "Erstelle Space Marketing"
{{
    "mode": "execute",
    "event_type": "bubble.create",
    "confidence": 0.95,
    "reasoning": "User will Space 'Marketing' erstellen",
    "payload": {{"title": "Marketing"}},
    "is_multi_step": false
}}

### MODUS 2b: MULTI-STEP (mehrere Aktionen)

Wenn die Anfrage MEHRERE Aktionen enthaelt:

Beispiel: "Gehe in den Space Test und zeige die Ideen"
{{
    "mode": "execute",
    "event_type": "multi_step",
    "confidence": 0.90,
    "reasoning": "2 Aktionen: Space betreten, Ideen anzeigen",
    "payload": {{}},
    "is_multi_step": true,
    "steps": [
        {{"event_type": "bubble.enter", "payload": {{"bubble_name": "Test"}}}},
        {{"event_type": "idea.list", "payload": {{}}, "depends_on": 0}}
    ]
}}

Einzelne Aktionen sind KEIN Multi-Step.

## Antwortformat

Antworte NUR mit einem JSON-Objekt (mode=direct_answer oder mode=execute).
Wenn ein Name/Titel im Text steht, MUSS er im payload stehen!"""


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
        bubble_context: Optional[Dict[str, Any]] = None,
        system_state: Optional[Any] = None,
    ) -> RAGClassificationResult:
        """
        Classify user intent using RAG approach.

        The LLM can either answer read queries directly from context
        (mode=direct_answer) or classify write actions for backend
        execution (mode=execute).

        Args:
            user_input: The user's voice/text input
            bubble_context: Optional context about current bubble and ideas
            system_state: Optional SystemState with current_space, current_bubble, etc.

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

            result = await self._call_llm(user_input, rules_context, bubble_context, system_state)
            result.used_rules = used_rule_types
            mode_info = f"mode={result.mode}" if result.mode == "direct_answer" else f"{result.event_type}"
            print(f"[Python DEBUG] [RAG] Step 4: LLM returned: {mode_info} ({result.confidence:.0%})", file=_sys.stderr, flush=True)
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
        bubble_context: Optional[Dict[str, Any]] = None,
        system_state: Optional[Any] = None,
    ) -> RAGClassificationResult:
        """Call the LLM for classification or direct answer."""
        if not self.llm_client:
            raise ValueError("LLM client not available")

        # Build rich context section so LLM can answer reads directly
        context_parts = []

        # System state (where are we?)
        if system_state:
            loc = system_state.current_space or "Hauptansicht"
            if system_state.current_bubble:
                loc += f" / Bubble: {system_state.current_bubble}"
            context_parts.append(f"- Position: {loc}")

        # Current bubble details
        if bubble_context and bubble_context.get("bubble_id"):
            idea_titles = bubble_context.get("idea_titles", [])
            ideas_str = ", ".join(idea_titles[:10]) if idea_titles else "keine"
            context_parts.append(
                f"- Aktueller Space: {bubble_context.get('bubble_name', 'Unbekannt')}\n"
                f"- Ideen im Space ({bubble_context.get('idea_count', 0)}): {ideas_str}"
            )
        else:
            context_parts.append("- Kein Space betreten (Hauptansicht)")

        # All bubbles overview (so LLM can answer "welche Spaces habe ich?")
        try:
            from swarm.context.bubble_context_provider import get_bubble_context_provider
            all_bubbles = get_bubble_context_provider().get_all_bubbles_summary()
            if all_bubbles:
                bubble_lines = []
                for b in all_bubbles:
                    titles = ", ".join(b["idea_titles"][:3]) if b.get("idea_titles") else ""
                    suffix = f" ({b['idea_count']} Ideen: {titles})" if titles else f" ({b['idea_count']} Ideen)"
                    bubble_lines.append(f"  - {b['title']}{suffix}")
                context_parts.append(f"- Alle Spaces ({len(all_bubbles)}):\n" + "\n".join(bubble_lines))
            else:
                context_parts.append("- Keine Spaces vorhanden")
        except Exception as e:
            logger.debug(f"[RAG] Could not load all bubbles: {e}")

        context_section = "## Aktueller Kontext\n\n" + "\n".join(context_parts) + "\n\n" if context_parts else ""

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
                        {"role": "system", "content": "Du bist der VibeMind Smart Router. Beantworte Leseanfragen direkt oder klassifiziere Aktionen. Antworte nur mit JSON."},
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

            # Determine response mode
            mode = data.get("mode", "execute")

            # MODE: direct_answer — LLM answered the read query from context
            if mode == "direct_answer":
                answer = data.get("answer", "")
                logger.info(f"[RAGIntentClassifier] Direct answer: {answer[:60]}...")
                return RAGClassificationResult(
                    event_type="direct_answer",
                    confidence=float(data.get("confidence", 0.9)),
                    reasoning=data.get("reasoning", "Direct answer from context"),
                    used_rules=[],
                    payload={},
                    user_input=user_input,
                    mode="direct_answer",
                    direct_answer=answer,
                )

            # MODE: execute — classification for backend execution
            is_multi_step = data.get("is_multi_step", False)
            steps = data.get("steps", [])

            if is_multi_step:
                logger.info(f"[RAGIntentClassifier] Multi-step detected: {len(steps)} steps")

            return RAGClassificationResult(
                event_type=data.get("event_type", "conversation.unknown"),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                used_rules=[],  # Will be filled by caller
                payload=data.get("payload", {}),
                user_input=user_input,
                is_multi_step=is_multi_step,
                steps=steps,
                mode="execute",
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
