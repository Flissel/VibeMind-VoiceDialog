# Orchestrator

The `python/swarm/orchestrator/` package is the brain of VibeMind's intent processing pipeline. It receives raw user text from the voice agent and produces classified, actionable events.

## File Index

| File | Purpose |
|------|---------|
| `intent_classifier.py` | LLM prompt-based classification of user text to event_type + payload |
| `intent_orchestrator.py` | Coordination of the full preprocessing + classification pipeline |
| `rag_intent_classifier.py` | RAG-based classification using Supermemory for semantic rule lookup |
| `tool_orchestrator.py` | Multi-step request handling via Claude Sonnet |
| `reference_resolver.py` | DroPE-based resolution of ambiguous references ("das", "es", "nochmal") |
| `response_generator.py` | Generates natural language response hints for the voice agent |
| `system_context_store.py` | Stores and retrieves system state for context-aware classification |
| `notification_queue.py` | Deferred feedback queue for VoiceBridgeV2 |
| `question_queue.py` | Queue for agent clarification questions back to the user |
| `tool_definitions.py` | ElevenLabs tool schema definitions for client tool registration |

## Pipeline Flow

```
User text (from voice agent)
    |
    v
IntentOrchestrator.process()
    |
    +---> [Optional] CollectorAgent: accumulate speech fragments
    |
    +---> [Optional] IntentEnhancer: fix ASR errors, normalize dialects
    |
    +---> [Optional] DroPEReferenceResolver: resolve "das", "es", "nochmal"
    |
    +---> IntentClassifier.classify()
    |         |
    |         +---> [Optional] RAGIntentClassifier: semantic rule lookup
    |         |
    |         +---> LLM call with CLASSIFIER_PROMPT_TEMPLATE
    |         |
    |         v
    |     { event_type, payload, confidence }
    |
    +---> [Optional] ToolOrchestrator: decompose multi-step requests
    |
    +---> ResponseGenerator: create voice response hint
    |
    v
ClassifiedIntent -> EventRouter -> Backend Agent
```

## intent_classifier.py

The core classifier. Contains `CLASSIFIER_PROMPT_TEMPLATE` with all supported event types and examples.

Key class: `IntentClassifier`
- `classify(text, context) -> ClassifiedIntent`
- Uses cloud LLM (OpenRouter/OpenAI) for classification
- Returns `event_type`, `payload` dict, and `confidence` score
- Supports German and English input
- Handles all event domains: `bubble.*`, `idea.*`, `code.*`, `desktop.*`, `shuttle.*`, `schedule.*`

## intent_orchestrator.py

Coordinates the full pipeline from raw text to classified intent.

Key class: `IntentOrchestrator`
- `process(user_text, session_context) -> OrchestratorResult`
- Runs optional preprocessing steps based on configuration
- Manages conversation history for context resolution
- Integrates with memory services if enabled

## rag_intent_classifier.py

Alternative classifier that uses Supermemory for semantic rule lookup before LLM classification. Improves accuracy by finding similar past intents.

Key class: `RAGIntentClassifier`
- Searches Supermemory for top-K similar rules
- Injects matched rules into the LLM prompt as few-shot examples
- Falls back to standard classifier if Supermemory is unavailable
- Enabled via `USE_RAG_CLASSIFIER=true`

## tool_orchestrator.py

Handles complex, multi-step user requests that require multiple tool calls.

Key class: `ToolOrchestrator`
- Uses Claude Sonnet to decompose requests like "Create a bubble called Marketing and add 3 ideas"
- Plans and executes tool calls sequentially
- Tracks intermediate results for dependent steps
- Enabled via `USE_TOOL_ORCHESTRATOR=true`

## reference_resolver.py

Resolves ambiguous German references using conversation history and optionally the DroPE model.

Key class: `DroPEReferenceResolver`
- Resolves: "das" (that), "es" (it), "nochmal" (again), "die" (those)
- Uses conversation history to find the most recent relevant entity
- Example: "Mach das nochmal" -> "Stopp den Container xyz"
- Enabled via `USE_DROPE_RESOLVER=true`
- Model: `SakanaAI/DroPE-SmolLM-135M-32K`

## response_generator.py

Creates natural language response hints that the voice agent speaks to the user.

Key class: `ResponseGenerator`
- Generates German/English responses from tool results
- Keeps responses concise for voice delivery
- Formats lists, status updates, and confirmations appropriately

## system_context_store.py

Stores and retrieves system state (current bubble, active operations, recent actions) for context-aware classification.

Key class: `SystemContextStore`
- Provides current workspace context to the classifier
- Tracks navigation state (which bubble/space the user is in)
- Stores recent tool execution results

## notification_queue.py

Deferred feedback queue for VoiceBridgeV2. Queues notifications from backend agents that should be spoken to the user at the next opportunity.

Key class: `NotificationQueue`
- FIFO queue with priority support
- Used when backend agents complete async tasks
- VoiceBridgeV2 polls for pending notifications

## question_queue.py

Queue for backend agent clarification questions. When an agent needs more information, it queues a question that the voice agent will ask the user.

Key class: `QuestionQueue`
- Supports options (multiple choice) and free-text questions
- Priority levels: normal, high, urgent
- Voice agent picks up questions during next interaction

## tool_definitions.py

ElevenLabs tool schema definitions used for client tool registration.

Contains tool definition dicts in the ElevenLabs format:
```python
{
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "...",
        "parameters": { ... }
    }
}
```
