"""
DroPE Reference Resolver - Resolves ambiguous references using conversation history.

Uses DroPE-SmolLM-135M (Sakana AI) for 32K extended context.

Problem:
    User: "Starte Docker Container"
    User: "Stopp den Container"
    User: "Mach das nochmal"  ← What is "das"? Classifier doesn't know!

Solution:
    Use conversation history + DroPE to resolve references:
    "Mach das nochmal" → "Stopp den Container"

References:
    - DroPE Paper: https://arxiv.org/abs/2401.14578
    - HuggingFace: https://huggingface.co/SakanaAI/DroPE-SmolLM-135M-32K
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# German reference words that indicate ambiguous utterances
AMBIGUOUS_WORDS = [
    "das", "es", "die", "den", "dem", "dessen",  # Pronouns
    "nochmal", "wieder", "erneut",  # Repetition
    "auch", "so", "davon", "damit", "dazu",  # References
    "gleiche", "selbe", "dasselbe",  # Same
]


class DroPEReferenceResolver:
    """
    Resolves ambiguous references in user utterances using DroPE model.

    Uses conversation history from ConversationRouter to provide context
    for resolving pronouns and references like "das", "es", "nochmal".

    Example:
        resolver = DroPEReferenceResolver()
        history = "User: Öffne Chrome\\nAssistant: Chrome geöffnet"
        resolved = resolver.resolve("Schließ es", history)
        # Returns: "Schließe Chrome"
    """

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the resolver.

        Args:
            model_name: HuggingFace model name. Defaults to env var or SmolLM-135M.
        """
        self.model_name = model_name or os.getenv(
            "DROPE_MODEL",
            "SakanaAI/DroPE-SmolLM-135M-32K"
        )
        self._model = None
        self._tokenizer = None
        self._available: Optional[bool] = None
        self._device = None

    @property
    def is_available(self) -> bool:
        """Check if DroPE resolver is available and enabled."""
        if self._available is None:
            self._available = self._check_availability()
        return self._available

    def _check_availability(self) -> bool:
        """Check if feature is enabled and dependencies are installed."""
        # Check feature flag
        if os.getenv("USE_DROPE_RESOLVER", "false").lower() != "true":
            logger.debug("DroPE resolver disabled (USE_DROPE_RESOLVER != true)")
            return False

        # Check dependencies
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM
            logger.debug("DroPE dependencies available (torch, transformers)")
            return True
        except ImportError as e:
            logger.warning(f"DroPE unavailable: {e}")
            return False

    def _load_model(self):
        """Lazy-load the DroPE model on first use."""
        if self._model is not None:
            return

        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        logger.info(f"Loading DroPE model: {self.model_name}")

        # Determine device
        if torch.cuda.is_available():
            self._device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self._device = "mps"
        else:
            self._device = "cpu"

        logger.info(f"DroPE using device: {self._device}")

        # Load tokenizer
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)

        # Load model with appropriate dtype
        dtype = torch.float16 if self._device != "cpu" else torch.float32

        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=dtype,
            device_map="auto" if self._device == "cuda" else None,
            low_cpu_mem_usage=True
        )

        if self._device != "cuda":
            self._model = self._model.to(self._device)

        logger.info(f"DroPE model loaded successfully")

    def needs_resolution(self, utterance: str) -> bool:
        """
        Check if utterance contains ambiguous references that need resolution.

        Args:
            utterance: User's input text

        Returns:
            True if the utterance likely contains references needing resolution
        """
        text_lower = utterance.lower()
        words = text_lower.split()

        # Check for reference words
        for word in words:
            # Strip punctuation for comparison
            clean_word = word.strip(".,!?;:")
            if clean_word in AMBIGUOUS_WORDS:
                return True

        # Very short commands (1-2 words) likely need context
        if len(words) <= 2:
            return True

        return False

    def resolve(self, utterance: str, conversation_history: str,
                session_store=None, session_key=None) -> str:
        """
        Resolve ambiguous references using conversation history.

        Args:
            utterance: Current user input (e.g., "Mach das nochmal")
            conversation_history: Past conversation context from ConversationRouter
            session_store: Optional SessionStore for last_route lookup
            session_key: Optional SessionKey for session-aware resolution

        Returns:
            Resolved utterance with concrete references, or original if resolution fails
        """
        # Skip if not available
        if not self.is_available:
            return utterance

        # Skip if no ambiguous references detected
        if not self.needs_resolution(utterance):
            logger.debug(f"[DroPE] No resolution needed for: {utterance}")
            return utterance

        # Try session last_route for "nochmal" / "wieder" references
        if session_store and session_key:
            try:
                entry = session_store.get_or_create(session_key)
                if entry.last_route:
                    text_lower = utterance.lower()
                    if any(w in text_lower for w in ["nochmal", "wieder", "erneut"]):
                        resolved = f"Wiederhole: {entry.last_route.event_type}"
                        logger.info(f"[DroPE] Session last_route: '{utterance}' -> '{resolved}'")
                        return resolved
            except Exception as e:
                logger.debug(f"[DroPE] Session last_route lookup failed: {e}")

        # Skip if no history to resolve from
        if not conversation_history or not conversation_history.strip():
            logger.debug(f"[DroPE] No history available for resolution")
            return utterance

        try:
            # Load model on first use
            self._load_model()

            # Build prompt
            prompt = self._build_prompt(utterance, conversation_history)

            # Run inference
            resolved = self._run_inference(prompt)

            # Validate and return
            if resolved and len(resolved) > 3 and resolved != utterance:
                logger.info(f"[DroPE] '{utterance}' → '{resolved}'")
                return resolved

            return utterance

        except Exception as e:
            logger.warning(f"[DroPE] Resolution failed: {e}")
            return utterance

    def _build_prompt(self, utterance: str, conversation_history: str) -> str:
        """Build the prompt for DroPE inference."""
        return f"""Konversationsverlauf:
{conversation_history}

Aktuelle Anfrage: "{utterance}"

Der User verwendet eine Referenz wie "das", "es" oder "nochmal".
Was meint der User konkret? Antworte NUR mit der aufgelösten Anfrage (1 Satz):"""

    def _run_inference(self, prompt: str) -> str:
        """Run DroPE model inference."""
        import torch

        # Tokenize
        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=False)
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

        # Generate
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=50,
                temperature=0.3,
                do_sample=True,
                pad_token_id=self._tokenizer.eos_token_id,
                eos_token_id=self._tokenizer.eos_token_id,
            )

        # Decode (only new tokens)
        new_tokens = outputs[0][inputs['input_ids'].shape[1]:]
        resolved = self._tokenizer.decode(new_tokens, skip_special_tokens=True)

        # Clean up: take first line, strip whitespace
        resolved = resolved.strip()
        if '\n' in resolved:
            resolved = resolved.split('\n')[0].strip()

        # Remove quotes if present
        if resolved.startswith('"') and resolved.endswith('"'):
            resolved = resolved[1:-1]

        return resolved


# =============================================================================
# Singleton Pattern
# =============================================================================

_resolver: Optional[DroPEReferenceResolver] = None


def get_reference_resolver() -> Optional[DroPEReferenceResolver]:
    """
    Get the singleton DroPE reference resolver.

    Returns:
        DroPEReferenceResolver instance if enabled, None otherwise
    """
    logger.debug("get_reference_resolver called")
    global _resolver

    # Check feature flag first
    if os.getenv("USE_DROPE_RESOLVER", "false").lower() != "true":
        return None

    if _resolver is None:
        _resolver = DroPEReferenceResolver()

    return _resolver


def reset_reference_resolver():
    """Reset the singleton (for testing)."""
    global _resolver
    _resolver = None
