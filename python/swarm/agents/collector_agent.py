"""
Collector Agent - Accumulates short/incomplete inputs before classification.

Part of the 3-Agent Enhancement Pipeline:
1. CollectorAgent - Accumulates short inputs
2. IntentEnhancer - Normalizes and enhances input
3. ExecutionValidator - Validates execution and triggers learning

Purpose:
- Collect short/unclear inputs (<3 words)
- Use LLM to detect incomplete/hesitant inputs (multi-lingual)
- Buffer until timeout or complete command detected
- Combine accumulated inputs for better classification
"""

import asyncio
import time
import logging
import os
from dataclasses import dataclass, field

from llm_config import token_kwargs
from typing import Optional, List, Callable, Any
from enum import Enum

logger = logging.getLogger(__name__)


class CollectorState(Enum):
    IDLE = "idle"
    ACCUMULATING = "accumulating"
    READY = "ready"


@dataclass
class AccumulatedInput:
    """Represents accumulated user input."""
    original_inputs: List[str] = field(default_factory=list)
    combined_text: str = ""
    started_at: float = 0.0
    last_input_at: float = 0.0

    @property
    def word_count(self) -> int:
        return len(self.combined_text.split())

    @property
    def age_seconds(self) -> float:
        if self.started_at == 0:
            return 0
        return time.time() - self.started_at


@dataclass
class CollectorConfig:
    """Configuration for the Collector Agent."""
    min_words_threshold: int = 3  # Inputs with fewer words always accumulate
    max_accumulation_time: float = 2.0  # Max seconds to wait
    silence_timeout: float = 1.5  # Seconds of silence to trigger flush
    max_accumulated_inputs: int = 5  # Max inputs to buffer
    long_input_threshold: int = 10  # Long inputs skip accumulation

    # LLM settings for completeness detection (via OpenRouter)
    llm_model: str = "openai/gpt-4o-mini"  # OpenRouter model path
    use_llm_detection: bool = True  # Enable/disable LLM-based detection

    # Action verbs that indicate a complete command (skip accumulation)
    # Commands starting with these words are executed immediately
    action_verbs: tuple = (
        # German action verbs
        "geh", "gehe", "zeig", "zeige", "liste", "erstelle", "lösche", "loesche",
        "navigiere", "zurück", "zurueck", "öffne", "oeffne", "schließe", "schliesse",
        "starte", "stoppe", "beende", "speichere", "verbinde", "finde", "suche",
        "aktualisiere", "bearbeite", "ändere", "aendere", "wechsle", "alle",
        # English action verbs
        "go", "show", "list", "create", "delete", "navigate", "back", "open",
        "close", "start", "stop", "end", "save", "connect", "find", "search",
        "update", "edit", "change", "switch", "all",
        # Conversational / greetings — always execute immediately
        "hi", "hey", "hallo", "hello", "hei", "ciao", "ok", "okay", "ja", "nein",
        "danke", "thanks", "status", "help", "hilfe", "was", "wie", "wo", "wer",
    )


class CollectorAgent:
    """
    Accumulates short/incomplete inputs before intent classification.
    Uses LLM for multi-lingual completeness detection.

    Flow:
    1. User says short phrase -> accumulate
    2. User adds more -> combine
    3. Timeout or complete command detected -> flush combined text

    Example:
        Input 1: "äh die ideen..."  -> accumulate (LLM: INCOMPLETE)
        Input 2: "verbinden oder so" -> accumulate
        Timeout: -> flush "äh die ideen verbinden oder so"
    """

    def __init__(self, config: Optional[CollectorConfig] = None):
        self.config = config or CollectorConfig()
        self.buffer = AccumulatedInput()
        self.state = CollectorState.IDLE
        self._timeout_task: Optional[asyncio.Task] = None
        self._on_flush_callback: Optional[Callable[[str], Any]] = None
        self._openai_client = None

    def _get_openai_client(self):
        """Lazy initialization of OpenRouter client (OpenAI-compatible)."""
        if self._openai_client is None:
            try:
                from openai import AsyncOpenAI, OpenAIError

                api_key = os.getenv("OPENROUTER_API_KEY")
                if not api_key:
                    logger.warning("[Collector] OPENROUTER_API_KEY not set, LLM detection disabled")
                    self.config.use_llm_detection = False
                    return None

                self._openai_client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key
                )
            except ImportError:
                logger.warning("[Collector] OpenAI package not installed, LLM detection disabled")
                self.config.use_llm_detection = False
            except OpenAIError as e:
                logger.warning(f"[Collector] OpenRouter client init failed: {e}, LLM detection disabled")
                self.config.use_llm_detection = False
            except Exception as e:
                logger.warning(f"[Collector] Failed to initialize OpenRouter: {e}, LLM detection disabled")
                self.config.use_llm_detection = False
        return self._openai_client

    def set_flush_callback(self, callback: Callable[[str], Any]):
        """Set callback to be called when buffer is flushed."""
        self._on_flush_callback = callback

    async def _is_complete_command(self, text: str) -> bool:
        """
        Use LLM to determine if input is a complete command (multi-lingual).

        Returns True if the input appears to be a complete, actionable command.
        Returns False if it's a fragment, hesitation, or correction.
        """
        if not self.config.use_llm_detection:
            # Fallback: assume complete if 3+ words
            return len(text.split()) >= self.config.min_words_threshold

        client = self._get_openai_client()
        if client is None:
            return len(text.split()) >= self.config.min_words_threshold

        try:
            response = await client.chat.completions.create(
                model=self.config.llm_model,
                messages=[{
                    "role": "system",
                    "content": """Classify if this voice input is a COMPLETE command or INCOMPLETE.

COMPLETE: Clear action request in any language that can be executed:
- "Delete the bubble" (English single action)
- "Alle Bubbles auflisten" (German single action)
- "Créer une nouvelle idée" (French single action)
- "Show me the projects"
- "Navigiere mich in den Marketing Space" (German navigation)
- "Gehe in den Debug Space" (German navigation)
- "Take me to the Ideas space" (English navigation)
- "Go to the Projects area" (English navigation)
- "Navigate to space X and create idea Y" (English multi-action)
- "Geh in Space X und erstelle eine Idee" (German multi-action)
- "Lösche den Space Test dann erstelle einen neuen" (German sequential)
- "First show me the projects, then create a new one" (English sequential)
- "Take me to Ideas space and add a note" (English compound)
- "Navigiere in den Space und erstelle dort eine Notiz" (German compound)

INCOMPLETE: Fragment, hesitation, correction, or unclear:
- "äh..." / "um..."
- "nein warte" / "no wait"
- "die ideen..." (trailing off)
- Single words without clear intent
- "eigentlich" / "actually" (hedging)
- Sentences ending with "..." (trailing off)

Reply ONLY with: COMPLETE or INCOMPLETE"""
                }, {
                    "role": "user",
                    "content": text
                }],
                temperature=0,
                **token_kwargs(self.config.llm_model, 10)
            )
            result = response.choices[0].message.content.strip().upper()
            is_complete = result == "COMPLETE"
            logger.debug(f"[Collector] LLM classification for '{text}': {result}")
            return is_complete
        except Exception as e:
            logger.warning(f"[Collector] LLM classification failed: {e}, falling back to word count")
            return len(text.split()) >= self.config.min_words_threshold

    async def should_accumulate(self, text: str) -> bool:
        """
        Determines if input should be accumulated or processed immediately.
        Uses LLM for multi-lingual completeness detection.

        Accumulate when:
        - Input is very short (<3 words)
        - LLM detects incomplete/hesitant input
        - Currently in accumulating state

        Don't accumulate when:
        - Input is long (>=10 words)
        - LLM detects complete command
        """
        text_lower = text.lower().strip()
        words = text_lower.split()
        word_count = len(words)

        # Long inputs skip accumulation (definitely complete)
        if word_count >= self.config.long_input_threshold:
            logger.debug(f"[Collector] Long input ({word_count} words) - skip accumulation")
            return False

        # Action verb at the beginning OR end = execute immediately (even for short inputs)
        # This handles commands like "geh rein", "zeig alle", "zurück",
        # and also "mirofish status", "video status", "rose status" where
        # the action keyword is in the second position.
        if words and any(w in self.config.action_verbs for w in words):
            _matched = [w for w in words if w in self.config.action_verbs]
            logger.debug(f"[Collector] Action verb {_matched} detected - skip accumulation")
            return False

        # Very short inputs always accumulate (1-2 words) - unless they have action verbs (checked above)
        if word_count < self.config.min_words_threshold:
            logger.debug(f"[Collector] Short input ({word_count} words) - accumulate")
            return True

        # Medium-length inputs: use LLM to detect completeness
        is_complete = await self._is_complete_command(text)
        if is_complete:
            logger.debug(f"[Collector] LLM detected complete command - skip accumulation")
            return False

        # LLM says incomplete, or already accumulating
        if self.state == CollectorState.ACCUMULATING:
            logger.debug(f"[Collector] Already accumulating - continue")
        else:
            logger.debug(f"[Collector] LLM detected incomplete input - accumulate")
        return True

    async def collect(self, text: str) -> Optional[str]:
        """
        Process input - accumulate or return combined text.

        Args:
            text: User input text

        Returns:
            None if accumulating, combined text if ready to process
        """
        text = text.strip()
        if not text:
            return None

        # Cancel existing timeout
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()

        if await self.should_accumulate(text):
            # Add to buffer
            if self.state == CollectorState.IDLE:
                self.buffer = AccumulatedInput(
                    original_inputs=[text],
                    combined_text=text,
                    started_at=time.time(),
                    last_input_at=time.time()
                )
                self.state = CollectorState.ACCUMULATING
            else:
                self.buffer.original_inputs.append(text)
                self.buffer.combined_text = " ".join(self.buffer.original_inputs)
                self.buffer.last_input_at = time.time()

            # Check max inputs
            if len(self.buffer.original_inputs) >= self.config.max_accumulated_inputs:
                logger.debug(f"[Collector] Max inputs reached - flushing")
                return self._flush()

            # Start timeout
            self._timeout_task = asyncio.create_task(self._timeout_handler())

            logger.info(f"[Collector] Accumulating: '{text}' (buffer: {len(self.buffer.original_inputs)} inputs)")
            return None
        else:
            # Not accumulating - combine with buffer if exists
            if self.state == CollectorState.ACCUMULATING:
                self.buffer.original_inputs.append(text)
                self.buffer.combined_text = " ".join(self.buffer.original_inputs)
                return self._flush()
            else:
                # Direct pass-through
                return text

    async def _timeout_handler(self):
        """Handle silence timeout - flush buffer after delay."""
        try:
            await asyncio.sleep(self.config.silence_timeout)
            if self.state == CollectorState.ACCUMULATING:
                logger.info(f"[Collector] Timeout - flushing buffer")
                result = self._flush()
                if self._on_flush_callback and result:
                    await self._on_flush_callback(result)
        except asyncio.CancelledError:
            pass  # Cancelled by new input - expected

    def _flush(self) -> str:
        """Flush buffer and return combined text."""
        if self.state != CollectorState.ACCUMULATING:
            return ""

        combined = self.buffer.combined_text
        inputs_count = len(self.buffer.original_inputs)

        logger.info(f"[Collector] Flushed {inputs_count} inputs: '{combined}'")

        # Reset state
        self.buffer = AccumulatedInput()
        self.state = CollectorState.IDLE

        return combined

    def force_flush(self) -> Optional[str]:
        """Force flush buffer immediately."""
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()

        if self.state == CollectorState.ACCUMULATING:
            return self._flush()
        return None

    def reset(self):
        """Reset collector state."""
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
        self.buffer = AccumulatedInput()
        self.state = CollectorState.IDLE

    @property
    def is_accumulating(self) -> bool:
        return self.state == CollectorState.ACCUMULATING

    @property
    def current_buffer(self) -> Optional[str]:
        if self.state == CollectorState.ACCUMULATING:
            return self.buffer.combined_text
        return None


# Singleton instance
_collector_agent: Optional[CollectorAgent] = None


def get_collector_agent() -> CollectorAgent:
    """Get or create the singleton CollectorAgent instance."""
    global _collector_agent
    if _collector_agent is None:
        _collector_agent = CollectorAgent()
    return _collector_agent


def reset_collector_agent():
    """Reset the singleton instance."""
    global _collector_agent
    if _collector_agent:
        _collector_agent.reset()
    _collector_agent = None
