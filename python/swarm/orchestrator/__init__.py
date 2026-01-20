"""
Orchestrator - Intent classification and event seeding for VibeMind

The orchestrator receives user intent from Rachel (voice interface),
classifies it using LLM, and seeds events to Redis for backend agents.

Components:
- IntentClassifier: LLM-based intent → event_type + payload (legacy)
- IntentOrchestrator: Coordinates classification, routing, and seeding
- ToolOrchestrator: Sonnet-based agentic tool orchestration (Phase 11)
- RAGIntentClassifier: Supermemory-based semantic intent classification
- NotificationQueue: Stores pending task results for async feedback
- ResponseGenerator: LLM-based result formatting for voice output
- SystemContextStore: Short-term knowledge store for Smart Rachel

Phase 13 - Multi-Agent Intent Analysis:
- IntentAnalysisTeam: Parallel hypothesis generation (swarm.analysis)
- ConversionAI: Personalized AI responses (swarm.conversion)
- UserContext: Context-aware processing (swarm.analysis)

Enable options:
- USE_TOOL_ORCHESTRATOR=true  (Phase 11 - Sonnet native tool calling)
- USE_INTENT_ANALYSIS=true    (Phase 13 - Multi-agent parallel analysis)
- USE_RAG_CLASSIFIER=true     (Supermemory semantic intent classification)
"""

from swarm.orchestrator.intent_classifier import IntentClassifier
from swarm.orchestrator.intent_orchestrator import IntentOrchestrator, get_orchestrator
from swarm.orchestrator.notification_queue import (
    NotificationQueue,
    Notification,
    get_notification_queue,
)
from swarm.orchestrator.response_generator import (
    ResponseGenerator,
    get_response_generator,
)
from swarm.orchestrator.system_context_store import (
    SystemContextStore,
    ContextEntry,
    get_system_context_store,
)

# RAG Intent Classifier (Supermemory-based semantic search)
try:
    from swarm.orchestrator.rag_intent_classifier import (
        RAGIntentClassifier,
        RAGClassificationResult,
        get_rag_intent_classifier,
    )
    HAS_RAG_CLASSIFIER = True
except ImportError:
    HAS_RAG_CLASSIFIER = False

# Phase 11: ToolOrchestrator (Sonnet native tool calling)
try:
    from swarm.orchestrator.tool_orchestrator import (
        ToolOrchestrator,
        ToolCall,
        ToolResult,
        OrchestrationResult as ToolOrchestrationResult,
        get_tool_orchestrator,
    )
    from swarm.orchestrator.tool_definitions import (
        get_all_tools,
        get_tool_count,
        TOOL_TO_EVENT_TYPE,
    )
    HAS_TOOL_ORCHESTRATOR = True
except ImportError:
    HAS_TOOL_ORCHESTRATOR = False

__all__ = [
    # Legacy classifier
    "IntentClassifier",
    # Main orchestrator
    "IntentOrchestrator",
    "get_orchestrator",
    # Notifications
    "NotificationQueue",
    "Notification",
    "get_notification_queue",
    # Response generation
    "ResponseGenerator",
    "get_response_generator",
    # Context store
    "SystemContextStore",
    "ContextEntry",
    "get_system_context_store",
]

# Add RAG classifier exports if available
if HAS_RAG_CLASSIFIER:
    __all__.extend([
        "RAGIntentClassifier",
        "RAGClassificationResult",
        "get_rag_intent_classifier",
        "HAS_RAG_CLASSIFIER",
    ])

# Add ToolOrchestrator exports if available
if HAS_TOOL_ORCHESTRATOR:
    __all__.extend([
        "ToolOrchestrator",
        "ToolCall",
        "ToolResult",
        "ToolOrchestrationResult",
        "get_tool_orchestrator",
        "get_all_tools",
        "get_tool_count",
        "TOOL_TO_EVENT_TYPE",
        "HAS_TOOL_ORCHESTRATOR",
    ])
