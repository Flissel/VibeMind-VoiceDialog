"""
Base class for StreamListeners.

Each listener is an LLM with a domain-specific system prompt that
evaluates user input and returns a confidence score. No keywords —
pure LLM evaluation.
"""

import json
import time
import logging
import asyncio
import concurrent.futures
from abc import ABC, abstractmethod
from typing import Optional

from .models import ListenerEvaluation, EvalContext

logger = logging.getLogger(__name__)

_logger = logging.getLogger(__name__)


EVALUATION_PROMPT_TEMPLATE = """Du bist der {space_name}-Experte im VibeMind System.
Bewerte ob die folgende Benutzeranfrage in deinen Zustaendigkeitsbereich faellt.

## Dein Bereich

{event_types_description}

## Konversation bisher

{conversation_history}

## Aktueller Kontext

{context_info}

## Aktuelle Anfrage

"{user_input}"

## Antwort

Antworte NUR als JSON (kein Markdown, keine Erklaerung):
{{
  "confidence": 0.0-1.0,
  "event_type": "prefix.action",
  "payload": {{}},
  "reasoning": "Kurze Begruendung",
  "mode": "execute"
}}

Regeln:
- confidence 0.0 = definitiv nicht mein Bereich
- confidence 0.3-0.5 = koennte mein Bereich sein
- confidence 0.7-1.0 = definitiv mein Bereich
- event_type MUSS einer der oben gelisteten konkreten Event-Types sein (z.B. "bubble.list", "desktop.open_app", "messaging.send") — NICHT "prefix.action" oder "none"
- Wenn du eine Leseanfrage direkt beantworten kannst, setze mode="direct_answer" und fuege "direct_answer": "..." hinzu
- Extrahiere alle relevanten Parameter in payload
- Wenn die Anfrage nicht in deinen Bereich faellt, setze confidence auf 0.0 und event_type auf "none"
"""


class BaseStreamListener(ABC):
    """
    Abstract base for domain-specific StreamListeners.

    Each subclass provides a system_prompt describing its domain,
    event types, and examples. The evaluate() method makes an LLM call
    to determine if the input belongs to this listener's domain.
    """

    def __init__(self):
        self._client = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Listener identifier, e.g. 'ideas', 'coding'."""
        pass

    @property
    @abstractmethod
    def event_types_description(self) -> str:
        """
        Domain-specific description of event types with examples.
        Inserted into the evaluation prompt.
        """
        pass

    @property
    def client(self):
        """Lazy-load shared OpenRouter client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def set_client(self, client):
        """Set shared client (injected by dispatcher)."""
        self._client = client

    def _create_client(self):
        """Create client as fallback via llm_config."""
        try:
            from llm_config import get_client
            return get_client("stream_listener")
        except Exception as e:
            logger.error(f"[{self.name}] Failed to create LLM client: {e}")
        return None

    async def evaluate(
        self, text: str, context: EvalContext, model: str = "openai/gpt-4o-mini", temperature: float = 0.1
    ) -> ListenerEvaluation:
        """
        LLM-based evaluation of whether input belongs to this domain.

        Args:
            text: User input text
            context: Conversation history and state
            model: LLM model to use
            temperature: LLM temperature

        Returns:
            ListenerEvaluation with confidence, event_type, payload
        """
        start = time.perf_counter()

        # Build conversation history string
        history_str = "Keine bisherige Konversation."
        if context.conversation_history:
            lines = []
            for msg in context.conversation_history[-5:]:
                speaker = msg.get("speaker", "?")
                text_content = msg.get("text", "")
                lines.append(f"  {speaker}: {text_content}")
            history_str = "\n".join(lines)

        # Build context info
        context_parts = []
        if context.current_bubble:
            context_parts.append(f"Aktuelle Bubble: {context.current_bubble}")
        if context.idea_count:
            context_parts.append(f"Anzahl Ideen: {context.idea_count}")
        context_info = "\n".join(context_parts) if context_parts else "Kein spezieller Kontext."

        # Format prompt
        prompt = EVALUATION_PROMPT_TEMPLATE.format(
            space_name=self.name.capitalize(),
            event_types_description=self.event_types_description,
            conversation_history=history_str,
            context_info=context_info,
            user_input=text,
        )

        # LLM call in thread pool (sync client)
        try:
            response_text = await self._call_llm(prompt, model, temperature)
            evaluation = self._parse_response(response_text, text)
            evaluation.latency_ms = (time.perf_counter() - start) * 1000
            return evaluation
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            err_type = type(e).__name__
            logger.warning(f"[{self.name}] LLM evaluation failed ({elapsed:.0f}ms): {err_type}: {e}")
            _logger.debug(f"[STREAM LISTENER] {self.name} eval failed: {err_type}: {e}")
            return ListenerEvaluation(
                space=self.name,
                confidence=0.0,
                event_type="none",
                reasoning=f"Evaluation failed: {err_type}: {e}",
                latency_ms=elapsed,
            )

    # Shared thread pool for all listeners — avoids creating a new
    # ThreadPoolExecutor per call and prevents the "with" context manager
    # from blocking the event loop on shutdown(wait=True) when tasks are
    # cancelled by asyncio.wait_for timeout.
    _shared_pool = concurrent.futures.ThreadPoolExecutor(max_workers=16)

    async def _call_llm(self, prompt: str, model: str, temperature: float) -> str:
        """Execute LLM call in shared thread pool."""
        if not self.client:
            raise ValueError("No LLM client available — check OPENROUTER_API_KEY")

        def _sync_call():
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=300,
            )
            return response.choices[0].message.content.strip()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._shared_pool, _sync_call)

    def _parse_response(self, response_text: str, original_input: str) -> ListenerEvaluation:
        """Parse JSON response from LLM into ListenerEvaluation."""
        # Strip markdown code fences
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            start_idx = text.find("{")
            end_idx = text.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                try:
                    data = json.loads(text[start_idx:end_idx])
                except json.JSONDecodeError:
                    logger.warning(f"[{self.name}] Could not parse JSON: {text[:100]}")
                    return ListenerEvaluation(
                        space=self.name,
                        confidence=0.0,
                        event_type="none",
                        reasoning="JSON parse error",
                    )
            else:
                return ListenerEvaluation(
                    space=self.name,
                    confidence=0.0,
                    event_type="none",
                    reasoning="No JSON in response",
                )

        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        mode = data.get("mode", "execute")
        direct_answer = data.get("direct_answer", "")

        return ListenerEvaluation(
            space=self.name,
            confidence=confidence,
            event_type=data.get("event_type", "none"),
            payload=data.get("payload", {}),
            reasoning=data.get("reasoning", ""),
            mode=mode,
            direct_answer=direct_answer,
        )
