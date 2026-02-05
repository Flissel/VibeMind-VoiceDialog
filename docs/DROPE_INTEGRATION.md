# DroPE Integration for Extended Context

Implementation documentation for DroPE-based reference resolution in VibeMind Voice Dialog.

**Status:** Implemented in `python/swarm/orchestrator/reference_resolver.py`

## Problem Statement

Current Intent Classification sees **only the current utterance**:

```
User: "Starte Docker Container"
User: "Zeig die Logs"
User: "Stopp den Container"
User: "Config anpassen"
User: "Die von nginx"
User: "Mach das nochmal"  ← Was ist "das"? Classifier weiß es nicht!
```

The `IntentClassifier` receives `"Mach das nochmal"` without conversation history, making reference resolution impossible.

## Solution: DroPE + Local Conversation Buffer

**DroPE** (Sakana AI) extends small LLMs from 4K → 32K context without retraining. Combined with a local conversation buffer, we can resolve references like "das", "es", "nochmal".

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    VibeMind Voice + DroPE                      │
│                                                                │
│   User Audio                                                   │
│       │                                                        │
│       ▼                                                        │
│   ┌──────────────┐                                            │
│   │  STT (Whisper)│                                            │
│   └──────┬───────┘                                            │
│          │                                                     │
│          ▼                                                     │
│   "Mach das nochmal"                                          │
│          │                                                     │
│          ├──────────────────────┐                             │
│          │                      ▼                              │
│          │            ┌─────────────────────┐                 │
│          │            │ ConversationBuffer  │                 │
│          │            │ (100 turns, RAM)    │                 │
│          │            │                     │                 │
│          │            │ User: Starte Docker │                 │
│          │            │ Asst: Läuft         │                 │
│          │            │ User: Config nginx  │                 │
│          │            │ Asst: Angepasst     │                 │
│          │            │ ...                 │                 │
│          │            └─────────┬───────────┘                 │
│          │                      │                              │
│          ▼                      ▼                              │
│   ┌──────────────────────────────────────┐                    │
│   │       DroPE-SmolLM-135M              │                    │
│   │       (Extended 32K Context)         │                    │
│   │                                      │                    │
│   │  Input: utterance + full history     │                    │
│   │  Output: "nginx Config anpassen"     │                    │
│   └──────────────────┬───────────────────┘                    │
│                      │                                         │
│                      ▼                                         │
│   ┌──────────────────────────────────────┐                    │
│   │       IntentClassifier               │                    │
│   │       (existing, unchanged)          │                    │
│   │                                      │                    │
│   │  Input: "nginx Config anpassen"      │                    │
│   │  Output: desktop.task / config.edit  │                    │
│   └──────────────────┬───────────────────┘                    │
│                      │                                         │
│                      ▼                                         │
│              Backend Execution                                 │
│                      │                                         │
│                      ▼                                         │
│              TTS (Rachel)                                      │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Components

### 1. ConversationBuffer (Local, RAM)

**File:** `python/memory/conversation_buffer.py`

```python
class ConversationBuffer:
    """
    Local in-memory conversation history for DroPE context.

    NOT Supermemory - just a simple list in RAM for fast access.
    Resets on session end.
    """

    def __init__(self, max_turns: int = 100):
        self.turns: List[Dict] = []
        self.max_turns = max_turns

    def add_user(self, text: str) -> None:
        self.turns.append({"role": "user", "text": text, "ts": time.time()})
        self._trim()

    def add_assistant(self, text: str) -> None:
        self.turns.append({"role": "assistant", "text": text, "ts": time.time()})
        self._trim()

    def _trim(self) -> None:
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def get_context(self) -> str:
        """Format for DroPE prompt injection."""
        return "\n".join([
            f"{t['role'].capitalize()}: {t['text']}"
            for t in self.turns
        ])

    def clear(self) -> None:
        self.turns = []
```

### 2. DroPE Reference Resolver

**File:** `python/swarm/orchestrator/reference_resolver.py`

```python
class DroPEReferenceResolver:
    """
    Resolves ambiguous references using DroPE extended context.

    "das", "es", "nochmal", "wieder", "auch" → concrete actions
    """

    AMBIGUOUS_WORDS = ["das", "es", "die", "nochmal", "wieder", "auch", "so", "davon"]

    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("SakanaAI/DroPE-SmolLM-135M-32K")
        self.model = AutoModelForCausalLM.from_pretrained(
            "SakanaAI/DroPE-SmolLM-135M-32K",
            torch_dtype=torch.float16
        )
        self.conversation_buffer = ConversationBuffer(max_turns=100)

    def needs_resolution(self, utterance: str) -> bool:
        """Quick check if DroPE is needed."""
        text_lower = utterance.lower()
        return any(word in text_lower for word in self.AMBIGUOUS_WORDS)

    def resolve(self, utterance: str) -> str:
        """
        Resolve ambiguous references using conversation history.

        Returns: Resolved utterance with concrete references
        """
        if not self.needs_resolution(utterance):
            return utterance  # Pass through unchanged

        context = self.conversation_buffer.get_context()

        prompt = f"""Konversationsverlauf:
{context}

Aktuelle Anfrage: "{utterance}"

Der User verwendet eine Referenz wie "das", "es" oder "nochmal".
Was meint der User konkret? Antworte NUR mit der aufgelösten Anfrage (1 Satz):"""

        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=False)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=50,
                temperature=0.3,
                do_sample=True
            )

        resolved = self.tokenizer.decode(
            outputs[0][inputs['input_ids'].shape[1]:],
            skip_special_tokens=True
        ).strip()

        return resolved

    def add_turn(self, role: str, text: str) -> None:
        """Add a turn to the conversation buffer."""
        if role == "user":
            self.conversation_buffer.add_user(text)
        else:
            self.conversation_buffer.add_assistant(text)
```

### 3. Integration Point

**File:** `python/swarm/orchestrator/intent_orchestrator.py` (modify)

```python
class IntentOrchestrator:
    def __init__(self):
        self.classifier = IntentClassifier()
        self.reference_resolver = DroPEReferenceResolver()  # NEW
        # ...

    async def process_intent(self, user_text: str) -> Dict[str, Any]:
        # 1. Add to conversation buffer
        self.reference_resolver.add_turn("user", user_text)

        # 2. Resolve references (DroPE)
        resolved_text = self.reference_resolver.resolve(user_text)

        if resolved_text != user_text:
            logger.info(f"[DroPE] '{user_text}' → '{resolved_text}'")

        # 3. Classify (existing flow)
        result = await self.classifier.classify(resolved_text)

        # 4. Add response to buffer
        response_hint = result.get("response_hint", "")
        if response_hint:
            self.reference_resolver.add_turn("assistant", response_hint)

        return result
```

## Model Options

| Model | Parameters | Context | Speed | Use Case |
|-------|------------|---------|-------|----------|
| DroPE-SmolLM-135M | 135M | 32K | ~100ms | Default, fast |
| DroPE-SmolLM-360M | 360M | 32K | ~200ms | Better quality |
| DroPE-LLaMA-2-7B | 7B | 32K | ~1s+ | Best quality (needs GPU) |

**Recommendation:** Start with `DroPE-SmolLM-135M-32K` for voice dialog latency requirements.

## Latency Budget

| Step | Target | Notes |
|------|--------|-------|
| STT (Whisper) | ~200ms | Existing |
| DroPE Resolve | ~100ms | New (135M is fast) |
| Intent Classify | ~150ms | Existing |
| Tool Execute | variable | Existing |
| TTS (Rachel) | ~200ms | Existing |
| **Total** | **~650ms + Execute** | Acceptable for voice |

## Optimization: Skip DroPE When Not Needed

```python
def needs_resolution(self, utterance: str) -> bool:
    """Only invoke DroPE for ambiguous utterances."""
    text_lower = utterance.lower()

    # Check for reference words
    if any(word in text_lower for word in self.AMBIGUOUS_WORDS):
        return True

    # Check for very short commands (likely need context)
    if len(utterance.split()) <= 2:
        return True

    return False
```

## Configuration

Add to `.env`:

```bash
# DroPE Reference Resolution
USE_DROPE_RESOLVER=true
DROPE_MODEL=SakanaAI/DroPE-SmolLM-135M-32K
DROPE_MAX_CONTEXT_TURNS=100
```

## Test Cases

```python
# Reference resolution test cases
TEST_CONVERSATIONS = [
    {
        "history": [
            ("user", "Starte Docker Container xyz"),
            ("assistant", "Container xyz läuft"),
            ("user", "Zeig die Logs"),
            ("assistant", "Hier sind die Logs..."),
            ("user", "Stopp den Container"),
            ("assistant", "Container gestoppt"),
        ],
        "input": "Mach das nochmal",
        "expected": "Stopp den Container xyz",  # or similar
    },
    {
        "history": [
            ("user", "Öffne die nginx Config"),
            ("assistant", "Config geöffnet"),
            ("user", "Ändere den Port auf 8080"),
            ("assistant", "Port geändert"),
        ],
        "input": "Speichere das",
        "expected": "Speichere die nginx Config",
    },
]
```

## Relation to Supermemory

| System | Purpose | Scope | Storage |
|--------|---------|-------|---------|
| **ConversationBuffer** | Current session context | Single session | RAM |
| **Supermemory** | Cross-session memory | All sessions | Cloud API |
| **DroPE** | Reference resolution | Current session | Model inference |

ConversationBuffer + DroPE handles **within-session** references.
Supermemory handles **cross-session** memory ("Was haben wir letzte Woche besprochen?").

## Files

| File | Purpose |
|------|---------|
| `python/memory/conversation_buffer.py` | Local turn storage |
| `python/swarm/orchestrator/reference_resolver.py` | DroPE integration |
| `python/swarm/orchestrator/intent_orchestrator.py` | Wire up resolver |
| `python/config.py` | DROPE_* config |

## References

**DroPE (Sakana AI):**

- Paper: [DroPE: Dropping Positional Encoding for Length Extrapolation](https://arxiv.org/abs/2401.14578)
- GitHub: [https://github.com/SakanaAI/DroPE](https://github.com/SakanaAI/DroPE)
- HuggingFace Models:
  - [SakanaAI/DroPE-SmolLM-135M-32K](https://huggingface.co/SakanaAI/DroPE-SmolLM-135M-32K)
  - [SakanaAI/DroPE-SmolLM-360M-32K](https://huggingface.co/SakanaAI/DroPE-SmolLM-360M-32K)
  - [SakanaAI/DroPE-LLaMA-2-7B-32K](https://huggingface.co/SakanaAI/DroPE-LLaMA-2-7B-32K)

**Concept:**

- DroPE removes/recalibrates positional encodings to extend context length
- 4K trained model → 32K inference without retraining
- Key insight: Position info less critical for long-range dependencies
