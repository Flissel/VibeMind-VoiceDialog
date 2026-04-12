"""
Intent Orchestrator - Central coordination for user intent processing

Receives user intent from Rachel (voice interface), classifies it,
routes to the correct Redis stream, and tracks job status.

Supports synchronous fallback mode when Redis is not available.

Phase 13: Multi-Agent Intent Analysis System
- IntentAnalysisTeam for parallel hypothesis generation
- ConversionAI for personalized responses
- UserContext for context-aware processing
"""

import asyncio
import logging
import sys
import time
import uuid
import os
from typing import Dict, Any, Optional, Callable, List

from dataclasses import dataclass

from swarm.orchestrator.intent_classifier import IntentClassifier, get_intent_classifier
from swarm.event_team import get_task_seeder, get_event_router, TaskContext
from swarm.event_team.job_manager import get_job_manager

# Import EventBus for stream constants
try:
    from swarm.event_bus import EventBus, STREAM_TASKS_SHUTTLES
    HAS_EVENT_BUS = True
except ImportError:
    HAS_EVENT_BUS = False
    STREAM_TASKS_SHUTTLES = "events:tasks:shuttles"  # Fallback constant

# Task Memory for persistent task tracking (SQLite-based)
try:
    from data.task_memory_repository import get_task_memory_repository
    HAS_TASK_MEMORY = True
except ImportError:
    HAS_TASK_MEMORY = False

# Supermemory-based memory services (async, system-wide)
try:
    from memory import (
        get_task_memory_service,
        get_conversation_memory_service,
        get_user_profile_service,
        get_conversation_router,  # For routing context enrichment
    )
    HAS_SUPERMEMORY_SERVICES = True
except ImportError:
    HAS_SUPERMEMORY_SERVICES = False
    get_task_memory_service = None
    get_conversation_memory_service = None
    get_user_profile_service = None
    get_conversation_router = None

# Phase 17: Real-Time Evaluation for intent feedback
try:
    from swarm.evaluation.realtime_evaluator import get_realtime_evaluator, RealtimeEvaluator
    HAS_REALTIME_EVAL = True
except ImportError:
    HAS_REALTIME_EVAL = False

# System status monitoring
try:
    from swarm.monitoring.system_status import get_status_monitor
    _status_monitor = get_status_monitor()
except ImportError:
    _status_monitor = None

# Optional ToolOrchestrator import (Phase 11)
try:
    from swarm.orchestrator.tool_orchestrator import ToolOrchestrator, get_tool_orchestrator
    HAS_TOOL_ORCHESTRATOR = True
except ImportError:
    HAS_TOOL_ORCHESTRATOR = False

# Phase 13: Multi-Agent Intent Analysis imports
try:
    from swarm.analysis import (
        IntentAnalysisTeam,
        IntentHypothesis,
        get_intent_analysis_team,
        UserContext,
        UserContextBuilder,
        get_user_context_builder,
    )
    from swarm.conversion import (
        ConversionAI,
        get_conversion_ai,
    )
    HAS_INTENT_ANALYSIS = True
except ImportError as e:
    HAS_INTENT_ANALYSIS = False

# Tool execution logging
try:
    from swarm.logging.tool_logger import get_tool_logger
    HAS_TOOL_LOGGER = True
except ImportError:
    HAS_TOOL_LOGGER = False
    get_tool_logger = None

# UI event broadcasting for tool_failed events
try:
    from tools.workspace_tools import _broadcast_to_electron
    HAS_BROADCAST = True
except ImportError:
    HAS_BROADCAST = False
    _broadcast_to_electron = None

# Reasoning Logger for multi-step execution tracking
try:
    from swarm.reasoning import get_reasoning_logger
    HAS_REASONING_LOGGER = True
except ImportError:
    HAS_REASONING_LOGGER = False
    get_reasoning_logger = None

logger = logging.getLogger(__name__)

# Events the Brain can handle WITHOUT LLM-extracted parameters.
# These are lists, stats, greetings, toggles — commands that either
# take no arguments or whose arguments are implicit (e.g. "current bubble"
# means "the bubble I'm in right now"). Everything NOT in this set
# needs the LLM to extract title, description, query, etc. from the
# user's free-form text.
_BRAIN_PARAMETERLESS_EVENTS = frozenset({
    # Bubbles — read-only / navigation
    "bubble.list", "bubble.stats", "bubble.current", "bubble.back", "bubble.exit",
    # Ideas — read-only
    "idea.list", "idea.current_space",
    # Conversation
    "conversation.greeting", "conversation.farewell", "conversation.unknown",
    "conversation.listening", "conversation.help",
    # Evaluation feedback
    "evaluation.correct", "evaluation.incorrect",
    # Desktop — parameterless actions
    "desktop.screenshot",
    # Schedule — read-only
    "schedule.list", "schedule.status",
    # N8n — read-only
    "n8n.list", "n8n.status",
    # Code — read-only
    "code.list", "code.status",
    # AgentFarm — read-only
    "agentfarm.list_teams", "agentfarm.list_templates", "agentfarm.status",
    # Video — read-only
    "video.status", "video.team_status",
    # Roarboot — read-only
    "roarboot.status",
    # Minibook — read-only
    "minibook.status", "minibook.list_projects",
    # MiroFish — read-only
    "mirofish.status",
    # Flowzen — read-only
    "rose.status",
    # OpenClaw — read-only
    "openclaw.status", "openclaw.notifications",
    # Docker controls (no params, just toggle)
    "roarboot.docker.start", "roarboot.docker.stop",
    "mirofish.docker.start", "mirofish.docker.stop", "mirofish.docker.status",
    # Desktop task list (no params)
    "desktop.task.list",
})

# RAG Intent Classifier (Supermemory-based semantic search)
# Must be after logger definition
try:
    from swarm.orchestrator.rag_intent_classifier import (
        RAGIntentClassifier,
        get_rag_intent_classifier,
    )
    from data.intent_rule_repository import get_intent_rule_repository
    HAS_RAG_CLASSIFIER = True
except ImportError as e:
    HAS_RAG_CLASSIFIER = False
    logger.debug(f"RAG classifier not available: {e}")

# Enhancement Pipeline (3-Agent System for improved intent classification)
try:
    from swarm.agents.collector_agent import CollectorAgent, get_collector_agent
    from swarm.agents.intent_enhancer import IntentEnhancer, get_intent_enhancer
    from swarm.agents.execution_validator import (
        ExecutionValidator,
        EvolutionaryValidator,
        get_execution_validator,
        ExecutionFeedback
    )
    HAS_ENHANCEMENT_PIPELINE = True
except ImportError as e:
    HAS_ENHANCEMENT_PIPELINE = False
    logger.debug(f"Enhancement pipeline not available: {e}")

# Real-time state tracking for Rachel's system awareness
try:
    from swarm.context.real_time_state import get_real_time_state
    HAS_REAL_TIME_STATE = True
except ImportError:
    HAS_REAL_TIME_STATE = False
    get_real_time_state = None

# Session context for system-wide context availability
try:
    from swarm.context.session_context import (
        set_session_context,
        clear_session_context,
        get_session_context,
    )
    HAS_SESSION_CONTEXT = True
except ImportError:
    HAS_SESSION_CONTEXT = False
    set_session_context = None
    clear_session_context = None
    get_session_context = None

# DroPE Reference Resolver (for "das", "nochmal", "es" resolution)
try:
    from swarm.orchestrator.reference_resolver import get_reference_resolver
    HAS_DROPE_RESOLVER = True
except ImportError:
    HAS_DROPE_RESOLVER = False
    get_reference_resolver = None

# Extracted modules for sync execution and result formatting
from swarm.orchestrator.result_formatter import (
    OrchestrationResult,
    format_result_for_voice, format_multi_step_result,
    enrich_with_task_context, store_supermemory_task_completed, store_supermemory_task_failed
)
from swarm.orchestrator.sync_executor import SyncExecutor

# Broadcast Dispatcher (Fan-Out architecture for parallel agent evaluation + profiling)
try:
    from swarm.broadcast.dispatcher import BroadcastDispatcher, IntentPayload, BroadcastResult
    from spaces.ideas.broadcast.ideas_broadcast_agent import IdeasBroadcastAgent
    from spaces.coding.broadcast.coding_broadcast_agent import CodingBroadcastAgent
    from spaces.desktop.broadcast.desktop_broadcast_agent import DesktopBroadcastAgent
    HAS_BROADCAST = True
except ImportError as e:
    HAS_BROADCAST = False
    logger.debug(f"Broadcast dispatcher not available: {e}")

# StreamListener — LLM-based parallel intent routing (replaces keyword-based CollectorAgent)
try:
    from swarm.stream_listener import (
        get_stream_listener_dispatcher,
        EvalContext,
        ConfidenceDistribution,
    )
    HAS_STREAM_LISTENER = True
except ImportError as e:
    HAS_STREAM_LISTENER = False
    logger.debug(f"StreamListener not available: {e}")

# SpaceAgents — per-space LLM tool orchestration (Phase 2: Ideas Agent)
try:
    from swarm.space_agents import (
        get_ideas_space_agent,
        SpaceAgentContext,
        SpaceAgentResult,
    )
    HAS_SPACE_AGENTS = True
except ImportError as e:
    HAS_SPACE_AGENTS = False
    logger.debug(f"SpaceAgents not available: {e}")


# OrchestrationResult now lives in result_formatter.py (re-exported above)


class IntentOrchestrator:
    """
    Central orchestrator for user intent processing.

    Flow:
    1. Receive intent from Rachel (voice interface)
    2. Classify intent using LLM → event_type + payload
    3. Route to correct Redis stream
    4. Seed event via TaskSeeder
    5. Return job_id and response hint
    """

    # Event types that don't need backend processing
    CONVERSATIONAL_EVENTS = {
        "conversation.greeting",
        "conversation.help",
        "conversation.unknown",
        "direct_answer",
    }

    # Phase 17: Evaluation feedback events (handled specially)
    EVALUATION_EVENTS = {
        "evaluation.correct",
        "evaluation.incorrect",
        "evaluation.clarify",
        "evaluation.stats",
    }

    def __init__(self, model_client=None, use_tool_orchestrator: bool = None):
        """
        Initialize orchestrator.

        Args:
            model_client: Optional pre-configured model client
            use_tool_orchestrator: Override for USE_TOOL_ORCHESTRATOR env var
        """
        # Check if ToolOrchestrator mode is enabled (Phase 11)
        if use_tool_orchestrator is not None:
            self._use_tool_orchestrator = use_tool_orchestrator and HAS_TOOL_ORCHESTRATOR
        else:
            self._use_tool_orchestrator = (
                os.getenv("USE_TOOL_ORCHESTRATOR", "false").lower() == "true"
                and HAS_TOOL_ORCHESTRATOR
            )

        # RAG Classifier (Supermemory-based semantic search)
        # When enabled, replaces keyword-based classification with semantic search
        self._use_rag_classifier = (
            os.getenv("USE_RAG_CLASSIFIER", "true").lower() == "true"
            and HAS_RAG_CLASSIFIER
        )

        # Initialize RAG Classifier (preferred over IntentAnalysisTeam)
        self.rag_classifier = None
        self.intent_rule_repo = None
        if self._use_rag_classifier:
            try:
                self.rag_classifier = get_rag_intent_classifier()
                self.intent_rule_repo = get_intent_rule_repository()
                # Seed default rules on first init
                self.intent_rule_repo.seed_default_rules()
                logger.info("IntentOrchestrator initialized with RAGIntentClassifier (Supermemory)")
            except Exception as e:
                logger.warning(f"Failed to initialize RAG classifier: {e}")
                self._use_rag_classifier = False

        # Phase 14: AnalysisTeam-Centered Architecture
        # IntentAnalysisTeam as fallback when RAG is unavailable
        self._use_intent_analysis = HAS_INTENT_ANALYSIS and not self._use_rag_classifier

        # Initialize core analysis components (IntentAnalysisTeam) - fallback
        self.analysis_team = None
        self.context_builder = None
        self.conversion_ai = None
        if self._use_intent_analysis:
            try:
                self.analysis_team = get_intent_analysis_team()
                self.context_builder = get_user_context_builder()
                self.conversion_ai = get_conversion_ai()
                logger.info("IntentOrchestrator initialized with IntentAnalysisTeam (fallback)")
            except Exception as e:
                logger.warning(f"Failed to initialize core analysis components: {e}")
                self._use_intent_analysis = False

        # Initialize extension agents (ToolOrchestrator and Legacy)
        if self._use_tool_orchestrator:
            self.tool_orchestrator = get_tool_orchestrator()
            self.classifier = None  # Disable legacy when using ToolOrchestrator
            logger.info("IntentOrchestrator extension: ToolOrchestrator (parallel processing)")
        else:
            self.classifier = get_intent_classifier(model_client)
            self.tool_orchestrator = None
            logger.info("IntentOrchestrator extension: Legacy IntentClassifier (parallel processing)")

        self.seeder = get_task_seeder()
        self.router = get_event_router()
        self.job_manager = get_job_manager()

        # Task Memory for persistent tracking across sessions
        self.task_memory = None
        if HAS_TASK_MEMORY:
            try:
                self.task_memory = get_task_memory_repository()
                logger.info("Task Memory initialized for persistent task tracking")
            except Exception as e:
                logger.warning(f"Could not initialize Task Memory: {e}")

        # Supermemory-based services for system-wide memory
        self.sm_task_memory = None
        self.sm_conversation_memory = None
        self.sm_user_profile = None
        if HAS_SUPERMEMORY_SERVICES:
            try:
                self.sm_task_memory = get_task_memory_service()
                if self.sm_task_memory and self.sm_task_memory.is_available:
                    logger.info("Supermemory TaskMemoryService initialized")
            except Exception as e:
                logger.debug(f"TaskMemoryService not available: {e}")

            try:
                self.sm_conversation_memory = get_conversation_memory_service()
                if self.sm_conversation_memory and self.sm_conversation_memory.is_available:
                    logger.info("Supermemory ConversationMemoryService initialized")
            except Exception as e:
                logger.debug(f"ConversationMemoryService not available: {e}")

            try:
                self.sm_user_profile = get_user_profile_service()
                if self.sm_user_profile and self.sm_user_profile.is_available:
                    logger.info("Supermemory UserProfileService initialized")
            except Exception as e:
                logger.debug(f"UserProfileService not available: {e}")

        # Conversation Router for routing context enrichment
        # Provides past conversation context to improve intent classification
        self.conversation_router = None
        if HAS_SUPERMEMORY_SERVICES and get_conversation_router:
            try:
                # Default user/session - will be overridden per-request
                self.conversation_router = get_conversation_router("default", "default")
                if self.conversation_router and self.conversation_router.is_available:
                    logger.info("ConversationRouter initialized for routing context enrichment")
            except Exception as e:
                logger.debug(f"ConversationRouter not available: {e}")

        # Phase 17: Real-Time Evaluation for intent feedback
        self.realtime_evaluator = None
        if HAS_REALTIME_EVAL:
            try:
                self.realtime_evaluator = get_realtime_evaluator()
                logger.info("RealtimeEvaluator initialized for intent feedback tracking")
            except Exception as e:
                logger.warning(f"Could not initialize RealtimeEvaluator: {e}")

        # Reasoning Logger for multi-step execution tracking
        self.reasoning_logger = None
        if HAS_REASONING_LOGGER:
            try:
                self.reasoning_logger = get_reasoning_logger()
                logger.info("ReasoningLogger initialized for multi-step execution tracking")
            except Exception as e:
                logger.warning(f"Could not initialize ReasoningLogger: {e}")

        # Check Redis availability for fallback mode
        self._redis_available = self._check_redis()

        # Enhancement Pipeline (3-Agent System) for improved classification
        self._use_enhancement_pipeline = (
            os.getenv("USE_ENHANCEMENT_PIPELINE", "true").lower() == "true"
            and HAS_ENHANCEMENT_PIPELINE
        )
        self.collector_agent = None
        self.intent_enhancer = None
        self.execution_validator = None
        if self._use_enhancement_pipeline:
            try:
                self.collector_agent = get_collector_agent()
                self.intent_enhancer = get_intent_enhancer()
                self.execution_validator = get_execution_validator()
                # Connect enhancer to validator for rule learning
                self.execution_validator.set_enhancer(self.intent_enhancer)
                logger.info("Enhancement Pipeline initialized (Collector + Enhancer + Validator)")
            except Exception as e:
                logger.warning(f"Failed to initialize Enhancement Pipeline: {e}")
                self._use_enhancement_pipeline = False

        # StreamListener — LLM-based parallel intent routing
        # When enabled, replaces CollectorAgent + IntentClassifier with parallel LLM listeners
        self._use_stream_listener = (
            os.getenv("USE_STREAM_LISTENER", "false").lower() == "true"
            and HAS_STREAM_LISTENER
        )
        self._stream_dispatcher = None
        if self._use_stream_listener:
            try:
                self._stream_dispatcher = get_stream_listener_dispatcher()
                logger.info("StreamListener initialized (LLM-based parallel routing)")
                logger.debug("[STREAM LISTENER] Initialized with all domain listeners")
            except Exception as e:
                logger.warning(f"Failed to initialize StreamListener: {e}")
                self._use_stream_listener = False

        # SpaceAgents — per-space LLM tool orchestration
        # When enabled, StreamListener routes to space-specific agents instead of flat _process_sync
        self._use_space_agents = (
            os.getenv("USE_SPACE_AGENTS", "false").lower() == "true"
            and HAS_SPACE_AGENTS
        )
        self._space_agents: Dict[str, Any] = {}
        if self._use_space_agents:
            try:
                self._space_agents["ideas"] = get_ideas_space_agent()
                logger.info("SpaceAgents initialized (ideas)")
                logger.debug("[SPACE AGENTS] Ideas agent initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize SpaceAgents: {e}")
                self._use_space_agents = False

        # MinibookHub — Central execution hub (Phase: Minibook als zentraler Hub)
        # When USE_MINIBOOK_HUB=true, all intents route through Minibook
        self._minibook_hub = None

        # HybridRouter — Tier-based deterministic routing (Phase 0)
        # Resolves 90% of intents without LLM. Falls through to MinibookHub for multi-space.
        self._hybrid_router = None
        if os.getenv("USE_HYBRID_ROUTER", "true").lower() == "true":
            try:
                from swarm.routing.hybrid_router import HybridRouter
                self._hybrid_router = HybridRouter()
                logger.info("HybridRouter enabled (Phase 0 routing)")
            except Exception as e:
                logger.warning(f"HybridRouter init failed, using MinibookHub only: {e}")

        # Brain Shadow Observer — watches routing decisions, trains SpaceRoutingHead
        self._brain_shadow = None
        try:
            from swarm.routing.brain_shadow import BrainShadowObserver
            self._brain_shadow = BrainShadowObserver()
            logger.info("BrainShadowObserver enabled (shadow mode)")
        except Exception as e:
            logger.warning(f"BrainShadowObserver not available: {e}")

        # Brain Event Shadow Observer — watches LLM classifications,
        # trains EventRoutingHead, and (once graduated) replaces the LLM
        # classifier on the hot path. Independent from _brain_shadow above.
        self._brain_event_shadow = None
        try:
            from swarm.routing.brain_event_shadow import BrainEventShadowObserver
            self._brain_event_shadow = BrainEventShadowObserver()
            logger.info("BrainEventShadowObserver enabled (event-classification shadow mode)")
        except Exception as e:
            logger.warning(f"BrainEventShadowObserver not available: {e}")

        # Most recent brain classification per session (in-memory cache),
        # used by Phase F (user-correction signal) to know what to retrain on.
        self._last_brain_classify: Dict[str, Dict[str, Any]] = {}
        self._BRAIN_EVENT_MIN_CONFIDENCE = float(
            os.getenv("BRAIN_EVENT_MIN_CONFIDENCE", "0.7")
        )
        # When True, skip the graduation requirement (500 samples at 95%)
        # and let the Brain event-classifier fire immediately. Analogous to
        # BRAIN_BRIDGE_FORCE_ACTIVE for the space router.
        self._brain_event_force_active = (
            os.getenv("BRAIN_EVENT_FORCE_ACTIVE", "false").lower() == "true"
        )

        # Brain + OpenFang Bridge — instantiated when EITHER:
        #  - USE_BRAIN_BRIDGE=true → Phase -1 full Brain→OpenFang orchestration
        #    (activates after brain_shadow graduates to 95% routing accuracy)
        #  - USE_OPENFANG_DIRECT=true → Phase 0 HybridRouter can route tools
        #    through OpenFang agents using the bridge's ensure_agent/send helpers
        self._brain_bridge = None
        _use_brain_bridge = os.getenv("USE_BRAIN_BRIDGE", "false").lower() == "true"
        self._use_openfang_direct = os.getenv("USE_OPENFANG_DIRECT", "false").lower() == "true"
        if (_use_brain_bridge or self._use_openfang_direct) and self._brain_shadow:
            try:
                from swarm.routing.brain_openfang_bridge import BrainOpenFangBridge
                openfang_url = os.getenv("OPENFANG_URL", "http://localhost:4200")
                self._brain_bridge = BrainOpenFangBridge(
                    brain_url=self._brain_shadow._brain_url,
                    openfang_url=openfang_url,
                )
                _modes = []
                if _use_brain_bridge:
                    _modes.append("Phase -1 orchestration")
                if self._use_openfang_direct:
                    _modes.append("Phase 0 OpenFang direct")
                logger.info(
                    f"BrainOpenFangBridge enabled ({', '.join(_modes)})"
                )
            except Exception as e:
                logger.warning(f"BrainOpenFangBridge init failed: {e}")

        # Direct tool executors for synchronous fallback AND multi-step execution
        # Multi-step always uses direct execution, so we always load tools
        from swarm.orchestrator.tool_registry import ToolRegistry
        _registry = ToolRegistry()
        self._tool_executors: Dict[str, Callable] = _registry.load_all(
            realtime_evaluator=self.realtime_evaluator,
        )
        self._param_mappings = _registry.get_param_mappings()

        # Broadcast Dispatcher (Fan-Out architecture)
        # When enabled, every classified intent is broadcast to ALL domain agents.
        # The responsible agent executes; non-responsible agents do user profiling.
        self._use_broadcast_mode = (
            os.getenv("USE_BROADCAST_MODE", "false").lower() == "true"
            and HAS_BROADCAST
        )
        self._broadcast_dispatcher = None
        if self._use_broadcast_mode:
            try:
                self._broadcast_dispatcher = BroadcastDispatcher()
                self._broadcast_dispatcher.register_agent(IdeasBroadcastAgent())
                self._broadcast_dispatcher.register_agent(CodingBroadcastAgent())
                self._broadcast_dispatcher.register_agent(DesktopBroadcastAgent())
                logger.info("BroadcastDispatcher initialized with 3 domain agents (Fan-Out mode)")
            except Exception as e:
                logger.warning(f"Failed to initialize BroadcastDispatcher: {e}")
                self._use_broadcast_mode = False

        if self._use_broadcast_mode:
            logger.info("IntentOrchestrator initialized (BROADCAST Fan-Out mode)")
        elif not self._redis_available and not self._use_tool_orchestrator:
            logger.info("IntentOrchestrator initialized (SYNC fallback mode - no Redis)")
        elif not self._use_tool_orchestrator:
            logger.info("IntentOrchestrator initialized (Redis mode)")
        else:
            logger.info("IntentOrchestrator initialized (Tool orchestrator mode + multi-step tools)")

        # SyncExecutor for delegating sync and multi-step tool execution
        self._sync_executor = SyncExecutor(
            tool_executors=self._tool_executors,
            task_memory=self.task_memory,
            reasoning_logger=self.reasoning_logger,
            broadcast_dispatcher=getattr(self, '_broadcast_dispatcher', None),
            sm_task_memory=self.sm_task_memory,
            sm_user_profile=self.sm_user_profile,
            sm_conversation_memory=self.sm_conversation_memory,
            use_broadcast_mode=self._use_broadcast_mode,
            param_mappings=self._param_mappings,
        )

    def _looks_like_multi_step(self, text: str) -> bool:
        """
        Quick heuristic to detect multi-action sentences.

        Multi-step commands should bypass the CollectorAgent since they are
        already complete sentences with multiple actions.

        Examples:
        - "Geh in Space X und erstelle eine Idee"
        - "Navigate to Marketing and create a note"
        - "Lösche den Space dann erstelle einen neuen"
        """
        text_lower = text.lower()
        # German and English connectors indicating multiple actions
        connectors = [
            ' und ', ' and ',           # "X and Y"
            ' dann ', ' then ',          # "X then Y"
            ' danach ', ' after ',       # "after X do Y"
            ' sowie ', ' also ',         # "X also Y"
            ', erstelle ', ', create ',  # "go to X, create Y"
            ', lösche ', ', delete ',    # "do X, delete Y"
            ' und erstelle ', ' and create ',  # Combined
            ' und lösche ', ' and delete ',    # Combined
        ]
        return any(c in text_lower for c in connectors)

    def _check_redis(self) -> bool:
        """Check if Redis is available.

        Note: FORCE_SYNC_MODE=true environment variable can bypass Redis
        entirely and use direct tool execution. This is useful when Redis
        is available but the backend agents have event loop issues.
        """
        # Check for Redis mode opt-in (default is SYNC mode for reliability)
        # Redis mode requires backend agents to be running to consume events
        use_redis = os.getenv("USE_REDIS_MODE", "false").lower() == "true"
        if not use_redis:
            logger.info("SYNC mode (default) - tools execute directly without Redis")
            return False

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        try:
            import redis
            # Use 1 second timeout to fail fast if Redis is not available
            r = redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
            r.ping()
            logger.info(f"Redis available at {redis_url}")
            return True
        except ImportError:
            logger.warning("redis package not installed - using synchronous fallback")
            return False
        except Exception as e:
            logger.warning(f"Redis not available ({e}) - using synchronous fallback")
            return False

    async def _store_memory_for_intent(
        self,
        intent_text: str,
        result: OrchestrationResult,
        context: Optional[TaskContext] = None,
    ) -> None:
        """
        Store intent data to all Supermemory services (non-blocking).

        Called after every successful intent processing to ensure all 4
        memory services receive data for every intent, regardless of
        which routing path was taken (HybridRouter, MinibookHub, RAG, etc.).
        """
        if not HAS_SUPERMEMORY_SERVICES:
            return

        session_id = context.session_id if context else "default"
        user_id = context.user_id if context else "default"

        # 1. ConversationRouter — store interaction for semantic routing context
        if self.conversation_router and self.conversation_router.is_available:
            try:
                await self.conversation_router.store_interaction(
                    user_input=intent_text,
                    classified_intent=result.event_type,
                    confidence=0.0,
                    agent_response=result.response_hint or "",
                    parameters={}
                )
            except Exception as e:
                logger.debug(f"[Memory] ConversationRouter store failed: {e}")

        # 2. UserProfileService — track intent usage for habit learning
        if self.sm_user_profile and self.sm_user_profile.is_available:
            try:
                await self.sm_user_profile.track_intent_usage(result.event_type)
            except Exception as e:
                logger.debug(f"[Memory] UserProfile tracking failed: {e}")

        # 3. ConversationMemoryService — store user/assistant exchange
        if self.sm_conversation_memory and self.sm_conversation_memory.is_available:
            try:
                await self.sm_conversation_memory.store_message_pair(
                    session_id=session_id,
                    user_message=intent_text,
                    assistant_response=result.response_hint or "",
                    agent_name="rachel"
                )
            except Exception as e:
                logger.debug(f"[Memory] ConversationMemory store failed: {e}")

        # 4. TaskMemoryService — task tracking is handled by SyncExecutor
        #    (store_supermemory_task_completed/failed) after tool execution.
        #    For conversational events that skip tools, store explicitly.
        if result.is_conversational and self.sm_task_memory and self.sm_task_memory.is_available:
            try:
                await self.sm_task_memory.store_task_completed(
                    task_id=result.job_id or f"conv-{result.event_type}",
                    intent_type=result.event_type,
                    result=result.response_hint or "",
                    duration_ms=0,
                    session_id=session_id
                )
            except Exception as e:
                logger.debug(f"[Memory] TaskMemory conversational store failed: {e}")

    def set_minibook_hub(self, hub) -> None:
        """Set the MinibookHub for centralized execution dispatch."""
        self._minibook_hub = hub
        logger.info("MinibookHub connected to IntentOrchestrator")

    # NOTE: _load_direct_tools() and _load_evaluation_tools() have been extracted
    # to swarm.orchestrator.tool_registry.ToolRegistry. See __init__ for usage.

    async def process_intent(
        self,
        intent_text: str,
        context: Optional[TaskContext] = None,
        domain_hint: Optional[str] = None
    ) -> OrchestrationResult:
        """
        Process user intent through the full orchestration pipeline.

        NEW ARCHITECTURE (Phase 14): AnalysisTeam-Centered System
        ========================================================
        1. IntentAnalysisTeam: Always runs first for hypothesis generation
        2. Parallel Agent Processing: ToolOrchestrator + Legacy as extensions
        3. Enhanced Reasoning: Multi-hypothesis merging and validation
        4. Fallback Strategy: Graceful degradation if components fail

        Flow:
        - Build user context
        - Run IntentAnalysisTeam (core analysis)
        - Run parallel agent extensions (ToolOrchestrator, Legacy)
        - Merge hypotheses and select best result
        - Execute via appropriate backend (Redis/sync)

        Args:
            intent_text: Natural language user request
            context: Optional task context (user_id, session_id, etc.)
            domain_hint: Optional domain hint for direct routing (ideas, bubbles, desktop, coding, shuttles)
                        If provided, skips domain detection and routes to the specified domain stream.

        Returns:
            OrchestrationResult with job_id, event_type, and response_hint
        """
        context = context or TaskContext()
        # Ensure user_input is set for logging/debugging
        if not context.user_input:
            context.user_input = intent_text

        # =====================================================================
        # USER-CORRECTION SIGNAL (Phase F)
        # =====================================================================
        # If the previous turn produced a brain classification AND the current
        # turn looks like a correction ("nein", "stop", "falsch", "ich meinte"),
        # send negative reward to the brain for that previous routing_id.
        try:
            _sess_id = context.session_id or "default"
            _last = self._last_brain_classify.get(_sess_id)
            if _last and (time.time() - _last.get("ts", 0)) < 60:
                _txt = (intent_text or "").strip().lower()
                _correction_markers = (
                    "nein", "no.", "falsch", "stop", "halt", "abbrechen",
                    "ich meinte", "i meant", "wrong", "not what i wanted",
                    "das war falsch", "meine ich nicht", "doch nicht",
                )
                if any(_txt.startswith(m) or _txt == m.rstrip(".") for m in _correction_markers) \
                        or any(m in _txt for m in ("ich meinte", "i meant", "meine ich nicht")):
                    if self._brain_event_shadow and _last.get("routing_id"):
                        asyncio.create_task(self._brain_event_shadow.reward(
                            routing_id=_last["routing_id"],
                            success=False,
                        ))
                        logger.info(
                            f"[BrainEvent] correction detected, "
                            f"penalizing previous classification "
                            f"'{_last.get('event_type')}' for '{_last.get('user_text', '')[:40]}'"
                        )
                    # Clear the cache so we don't double-penalize
                    self._last_brain_classify.pop(_sess_id, None)
        except Exception as _corr_err:
            logger.debug(f"[BrainEvent] correction detection error: {_corr_err}")

        # Set system-wide session context for tools to access
        if HAS_SESSION_CONTEXT and set_session_context:
            try:
                # Get conversation history if available
                conv_history = []
                if context.session_id:
                    try:
                        from data import ConversationRepository
                        conv_repo = ConversationRepository()
                        recent_msgs = conv_repo.get_messages_for_session(
                            context.session_id,
                            limit=10
                        )
                        conv_history = [
                            {"speaker": m.speaker, "text": m.text, "timestamp": m.timestamp}
                            for m in recent_msgs
                        ]
                    except Exception:
                        pass

                set_session_context(
                    session_id=context.session_id or "default",
                    user_id=context.user_id or "default",
                    user_input=intent_text,
                    conversation_history=conv_history,
                )
            except Exception as ctx_err:
                logger.debug(f"[SessionContext] Setup error: {ctx_err}")

        try:
            # =================================================================
            # PHASE 0: DOMAIN-SPECIFIC ROUTING (if domain_hint provided)
            # =================================================================
            if domain_hint:
                logger.info(f"[DomainRouter] Direct routing to domain: {domain_hint}")
                domain_result = await self._route_to_domain(intent_text, domain_hint, context)
                if domain_result:
                    self._log_classification(intent_text, domain_result, context)
                    asyncio.create_task(self._store_memory_for_intent(
                        intent_text, domain_result, context
                    ))
                    return domain_result
                # If domain routing failed, continue to normal analysis
                logger.warning(f"[DomainRouter] Domain routing failed, falling back to analysis")

            # =================================================================
            # PHASE -1: BRAIN + OPENFANG (context-aware routing + execution)
            # =================================================================
            # Activated only when Brain has graduated to active mode (95% accuracy),
            # OR when BRAIN_BRIDGE_FORCE_ACTIVE=true for evaluation/testing.
            # Routes via Brain with full workspace context, executes via OpenFang.
            # Falls through to HybridRouter on failure or low confidence.
            _brain_ready = (
                self._brain_bridge
                and self._brain_shadow
                and (self._brain_shadow._active
                     or os.getenv("BRAIN_BRIDGE_FORCE_ACTIVE", "false").lower() == "true")
                and not domain_hint
                and not self._brain_event_force_active  # Phase 0 has priority when event-brain is force-active
            )
            if _brain_ready:
                try:
                    # Pre-classify for event_type hint.
                    # Priority:
                    #   1. EventRoutingHead (Brain, local, <50ms) when graduated
                    #   2. LLM classifier (fallback, ~500ms)
                    _pre_event = ""
                    _pre_event_brain_routing_id = ""
                    _user_id_pre = getattr(context, 'user_id', None) if context else None

                    if (self._brain_event_shadow
                            and (self._brain_event_shadow.brain_active
                                 or self._brain_event_force_active)):
                        try:
                            _brain_cls = await self._brain_event_shadow.classify_via_brain(
                                intent_text, user_id=_user_id_pre,
                            )
                            if _brain_cls and _brain_cls.get("confidence", 0) >= self._BRAIN_EVENT_MIN_CONFIDENCE:
                                _pre_event = _brain_cls.get("event_type", "")
                                _pre_event_brain_routing_id = _brain_cls.get("routing_id", "")
                                logger.info(
                                    f"[BrainBridge] pre-classification via EventRoutingHead: "
                                    f"'{_pre_event}' ({_brain_cls.get('confidence', 0):.0%})"
                                )
                        except Exception as be_err:
                            logger.debug(f"[BrainBridge] EventRoutingHead pre-cls failed: {be_err}")

                    # Fallback to LLM if Event-Brain didn't hit
                    if not _pre_event:
                        try:
                            from swarm.orchestrator.intent_classifier import IntentClassifier
                            _pre_cls = IntentClassifier()
                            _pre_result = await _pre_cls.classify(intent_text)
                            _pre_event = _pre_result.get("event_type", "") if _pre_result else ""
                            # Shadow-train the Event-Brain from the LLM answer
                            if self._brain_event_shadow and _pre_event:
                                asyncio.create_task(self._brain_event_shadow.observe(
                                    user_text=intent_text,
                                    actual_event_type=_pre_event,
                                    user_id=_user_id_pre,
                                ))
                        except Exception:
                            pass

                    bridge_result = await self._brain_bridge.execute(
                        intent_text=intent_text,
                        context=context,
                        pre_classification=_pre_event,
                    )
                    if bridge_result and not bridge_result.error:
                        # Reward the Event-Brain if its classification drove this path
                        if _pre_event_brain_routing_id and self._brain_event_shadow:
                            asyncio.create_task(self._brain_event_shadow.reward(
                                routing_id=_pre_event_brain_routing_id, success=True,
                            ))
                        asyncio.create_task(self._store_memory_for_intent(
                            intent_text, bridge_result, context
                        ))
                        return bridge_result
                    # None or error → fall through to HybridRouter
                    if _pre_event_brain_routing_id and self._brain_event_shadow:
                        asyncio.create_task(self._brain_event_shadow.reward(
                            routing_id=_pre_event_brain_routing_id, success=False,
                        ))
                except Exception as bridge_err:
                    logger.warning(f"[BrainBridge] Phase -1 failed, falling through: {bridge_err}")

            # =================================================================
            # PHASE 0: HYBRID ROUTER (deterministic fast-path)
            # =================================================================
            # Tiers 1-4: Resolve deterministically without MinibookHub roundtrip.
            # Tier 5 (multi-space): Delegates to MinibookHub.
            if self._hybrid_router and not domain_hint:
                try:
                    # =========================================================
                    # CLASSIFY: Brain first, LLM as fallback
                    # =========================================================
                    # If the Brain event-classifier has graduated AND its
                    # confidence on this input clears the threshold, we skip
                    # the LLM entirely. Otherwise we fall through to the LLM
                    # and use its answer as supervised training for the Brain.
                    _classification: Optional[Dict[str, Any]] = None
                    _pre_event_type = ""
                    _brain_routing_id = ""

                    # 0. Multi-step gate — Brain only handles single-step intents.
                    # If the user combined multiple actions with a connector
                    # ("erstelle idee und füge sie der bubble hinzu"), defer
                    # straight to the LLM which returns is_multi_step=true.
                    _is_multi_step = False
                    try:
                        from swarm.orchestrator.multi_step_detector import looks_multi_step
                        _is_multi_step = looks_multi_step(intent_text)
                        if _is_multi_step:
                            logger.info(
                                f"[BrainEvent] multi-step detected in "
                                f"'{intent_text[:60]}', deferring to LLM"
                            )
                    except Exception:
                        pass

                    # 0. REGEX FAST-PATH — match obvious command patterns without LLM/Brain.
                    # Saves us when OpenRouter is rate-limited or Brain is undertrained.
                    # Runs BEFORE Brain/LLM so it short-circuits quickly.
                    _regex_fast_paths = [
                        # (event_type, param_key, pattern)
                        ("bubble.delete", "bubble_name",
                         r"^\s*(?:l[öo]esche|entferne|delete|remove)\s+(?:die\s+|the\s+)?(?:bubble|space)\s+(.+?)\s*[.!?]?\s*$"),
                        ("bubble.enter", "bubble_name",
                         r"^\s*(?:geh|oeffne|open|enter|wechsle|betrete)\s+(?:in\s+|zu\s+|to\s+|die\s+)?(?:bubble|space)\s+(.+?)\s*[.!?]?\s*$"),
                        ("bubble.find", "query",
                         r"^\s*(?:finde|suche|find|search)\s+(?:bubble|space)\s+(.+?)\s*[.!?]?\s*$"),
                    ]
                    import re as _re_mod
                    for _evt, _pkey, _pat in _regex_fast_paths:
                        _m = _re_mod.match(_pat, intent_text, _re_mod.IGNORECASE)
                        if _m:
                            _val = _m.group(1).strip().rstrip(".,!?").strip()
                            if _val:
                                _pre_event_type = _evt
                                _classification = {
                                    "event_type": _evt,
                                    "parameters": {_pkey: _val},
                                    "payload": {_pkey: _val},
                                }
                                logger.info(
                                    f"[RegexFastPath] '{_evt}' param {_pkey}='{_val}' "
                                    f"— skipping Brain/LLM entirely"
                                )
                                break

                    # 1. Brain-first attempt (only when graduated AND single-step
                    #    AND the event doesn't need LLM-extracted parameters).
                    #
                    # The Brain classifies event_type but cannot extract
                    # parameters from the user's text (title, description,
                    # name, query, etc.). For events that need params, we
                    # MUST fall through to the LLM, which returns them in
                    # payload. Events in _BRAIN_PARAMETERLESS_EVENTS are
                    # safe to execute without LLM params — they're lists,
                    # stats, greetings, toggles, etc.
                    _user_id_for_brain = getattr(context, 'user_id', None) if context else None
                    if (_classification is None and not _is_multi_step
                            and self._brain_event_shadow
                            and (self._brain_event_shadow.brain_active
                                 or self._brain_event_force_active)):
                        try:
                            brain_cls = await self._brain_event_shadow.classify_via_brain(
                                intent_text,
                                user_id=_user_id_for_brain,
                            )
                            # Fast-path: Brain says bubble.delete / bubble.enter / idea.delete
                            # → extract name with regex, skip LLM entirely.
                            # This avoids LLM rate limits for simple "Lösche Bubble X" commands.
                            _regex_extractable = {
                                "bubble.delete": ("bubble_name", [
                                    r"(?:l[öo]esche|entferne|delete|remove)\s+(?:die\s+|the\s+)?(?:bubble|space)\s+(.+?)(?:\s*$|[,.!?])",
                                    r"(?:bubble|space)\s+(.+?)\s+(?:l[öo]eschen|entfernen|delete|remove)",
                                ]),
                                "bubble.enter": ("bubble_name", [
                                    r"(?:geh|oeffne|open|enter|wechsle|betrete)\s+(?:in\s+|zu\s+|to\s+|die\s+)?(?:bubble|space)\s+(.+?)(?:\s*$|[,.!?])",
                                ]),
                                "bubble.find": ("query", [
                                    r"(?:finde|suche|find|such)\s+(?:bubble|space)\s+(.+?)(?:\s*$|[,.!?])",
                                ]),
                                "idea.delete": ("idea_name", [
                                    r"(?:l[öo]esche|entferne|delete|remove)\s+(?:die\s+|the\s+)?(?:idee|idea|note|notiz)\s+(.+?)(?:\s*$|[,.!?])",
                                ]),
                            }
                            _bc_event = brain_cls.get("event_type", "") if brain_cls else ""
                            _bc_conf = brain_cls.get("confidence", 0) if brain_cls else 0

                            if (brain_cls
                                    and _bc_conf >= self._BRAIN_EVENT_MIN_CONFIDENCE
                                    and _bc_event in _regex_extractable):
                                import re as _re
                                param_key, patterns = _regex_extractable[_bc_event]
                                extracted = None
                                for pat in patterns:
                                    m = _re.search(pat, intent_text, _re.IGNORECASE)
                                    if m:
                                        extracted = m.group(1).strip().rstrip(".,!?").strip()
                                        break
                                if extracted:
                                    _pre_event_type = _bc_event
                                    _brain_routing_id = brain_cls.get("routing_id", "")
                                    _classification = {
                                        "event_type": _pre_event_type,
                                        "parameters": {param_key: extracted},
                                        "payload": {param_key: extracted},
                                        "_brain_routing_id": _brain_routing_id,
                                    }
                                    logger.info(
                                        f"[BrainEvent+Regex] '{_pre_event_type}' ({_bc_conf:.0%}) "
                                        f"param {param_key}='{extracted}' — skipping LLM"
                                    )

                            if (_classification is None and brain_cls
                                    and _bc_conf >= self._BRAIN_EVENT_MIN_CONFIDENCE
                                    and _bc_event in _BRAIN_PARAMETERLESS_EVENTS):
                                _pre_event_type = _bc_event
                                _brain_routing_id = brain_cls.get("routing_id", "")
                                _classification = {
                                    "event_type": _pre_event_type,
                                    "parameters": {},
                                    "payload": {},
                                    "_brain_routing_id": _brain_routing_id,
                                }
                                logger.info(
                                    f"[BrainEvent] hit '{_pre_event_type}' "
                                    f"({brain_cls.get('confidence', 0):.0%}), skipping LLM"
                                )
                            elif brain_cls and brain_cls.get("confidence", 0) >= self._BRAIN_EVENT_MIN_CONFIDENCE:
                                # Brain is confident but event needs params.
                                # Route to OpenFang if available — the agent
                                # has its own Claude access and can extract
                                # params + execute in one step. Only fall
                                # through to LLM if OpenFang isn't up.
                                _needs_params_event = brain_cls.get("event_type", "")
                                _brain_routing_id = brain_cls.get("routing_id", "")
                                if self._use_openfang_direct and self._brain_bridge:
                                    try:
                                        from swarm.routing.brain_openfang_bridge import SPACE_AGENT_MAP
                                        from swarm.orchestrator.intent_classifier import IntentClassifier
                                        # Map event → space → agent
                                        _evt_space = None
                                        try:
                                            from core.space_routing_head import EVENT_SPACE_MAP
                                            _evt_space = EVENT_SPACE_MAP.get(_needs_params_event)
                                        except ImportError:
                                            pass
                                        _of_agent_name = self._brain_bridge.space_to_agent(
                                            _evt_space or "ideas"
                                        )
                                        if _of_agent_name:
                                            _of_agent_id = await asyncio.wait_for(
                                                self._brain_bridge.ensure_agent(_of_agent_name),
                                                timeout=2.0,
                                            )
                                            if _of_agent_id:
                                                _of_msg = (
                                                    f"Classify and execute this VibeMind intent.\n"
                                                    f"Event type: {_needs_params_event}\n"
                                                    f"User said: {intent_text}\n\n"
                                                    f"Extract the parameters from the user text "
                                                    f"and execute the {_needs_params_event} tool. "
                                                    f"Return a short confirmation message."
                                                )
                                                _of_response = await asyncio.wait_for(
                                                    self._brain_bridge.send_to_agent(
                                                        _of_agent_id, _of_msg
                                                    ),
                                                    timeout=10.0,
                                                )
                                                logger.info(
                                                    f"[BrainEvent+OpenFang] '{_needs_params_event}' "
                                                    f"({brain_cls.get('confidence', 0):.0%}) → "
                                                    f"OpenFang '{_of_agent_name}'"
                                                )
                                                # Reward brain for correct classification
                                                if self._brain_event_shadow and _brain_routing_id:
                                                    asyncio.create_task(
                                                        self._brain_event_shadow.reward(
                                                            routing_id=_brain_routing_id,
                                                            success=True,
                                                        )
                                                    )
                                                _of_result = OrchestrationResult(
                                                    job_id=_brain_routing_id or "",
                                                    event_type=_needs_params_event,
                                                    stream=_evt_space or "ideas",
                                                    response_hint=_of_response,
                                                )
                                                asyncio.create_task(
                                                    self._store_memory_for_intent(
                                                        intent_text, _of_result, context
                                                    )
                                                )
                                                return _of_result
                                    except Exception as of_err:
                                        logger.warning(
                                            f"[BrainEvent+OpenFang] failed: {of_err}, "
                                            f"falling through to LLM"
                                        )
                                # OpenFang not available or failed → fall through to LLM
                                logger.info(
                                    f"[BrainEvent] '{_needs_params_event}' "
                                    f"({brain_cls.get('confidence', 0):.0%}) needs params, "
                                    f"deferring to LLM"
                                )
                        except Exception as be_err:
                            logger.debug(f"[BrainEvent] classify_via_brain failed: {be_err}")

                    # 2. LLM fallback (always reached when brain didn't hit)
                    if _classification is None:
                        try:
                            # Phase 2: YAML-driven classifier for Ideas-Space intents.
                            # When USE_YAML_CLASSIFIER=true, try YAML first. It covers 37
                            # bubble.*/idea.* events with compact few-shots. If it returns
                            # conversation.unknown, fall through to the legacy classifier
                            # which covers the remaining 94 non-Ideas events.
                            _use_yaml = (
                                os.getenv("USE_YAML_CLASSIFIER", "false").lower() == "true"
                            )
                            if _use_yaml:
                                from swarm.orchestrator.yaml_classifier import get_yaml_classifier
                                _classifier = get_yaml_classifier()
                                _classification = await _classifier.classify(intent_text)
                                _pre_event_type = _classification.get("event_type", "") if _classification else ""
                                # YAML only covers Ideas-Space — if it returned unknown,
                                # retry with legacy classifier which covers all 131 events.
                                if _pre_event_type == "conversation.unknown":
                                    logger.info(f"[YamlClassifier] unknown, falling back to legacy")
                                    from swarm.orchestrator.intent_classifier import IntentClassifier
                                    _legacy = IntentClassifier()
                                    _classification = await _legacy.classify(intent_text)
                                    _pre_event_type = _classification.get("event_type", "") if _classification else ""
                            else:
                                from swarm.orchestrator.intent_classifier import IntentClassifier
                                _classifier = IntentClassifier()
                                _classification = await _classifier.classify(intent_text)
                                _pre_event_type = _classification.get("event_type", "") if _classification else ""
                            # Brain learns from the LLM ground truth (shadow training),
                            # personalized to the current user when available.
                            if self._brain_event_shadow and _pre_event_type:
                                asyncio.create_task(self._brain_event_shadow.observe(
                                    user_text=intent_text,
                                    actual_event_type=_pre_event_type,
                                    user_id=_user_id_for_brain,
                                ))
                        except Exception:
                            pass

                    # Cache the classification keyed by session for Phase F
                    # (user-correction signal). Capped at 100 entries.
                    try:
                        _sess_id = (context or {}).get("session_id", "default") if context else "default"
                        if len(self._last_brain_classify) > 100:
                            self._last_brain_classify.clear()
                        self._last_brain_classify[_sess_id] = {
                            "user_text": intent_text,
                            "event_type": _pre_event_type,
                            "routing_id": _brain_routing_id,
                            "ts": time.time(),
                        }
                    except Exception:
                        pass

                    route_result = await self._hybrid_router.resolve(
                        event_type=_pre_event_type,
                        user_input=intent_text,
                        current_space=getattr(self, '_current_space', None),
                    )

                    if route_result.tier >= 1 and route_result.tier <= 4 and route_result.multi_space is None:
                        # Single-space deterministic match → direct execute
                        logger.info(
                            f"[HybridRouter] Tier {route_result.tier}: "
                            f"{route_result.event_type} -> {route_result.space} "
                            f"({route_result.matched_by})"
                        )
                        tool_name = route_result.event_type
                        if tool_name in self._tool_executors:
                            tool_fn = self._tool_executors[tool_name]
                            try:
                                tool_params = ((_classification.get("parameters") or _classification.get("payload")) or {}) if _classification else {}
                                # Patch 2: optionally route through OpenFang agent
                                # when USE_OPENFANG_DIRECT=true AND the event
                                # actually needs remote execution. Parameterless
                                # events (lists, stats, etc.) have working local
                                # tool_executors — sending them to OpenFang just
                                # gets "VibeMind nicht verfuegbar" because the
                                # agent has no DB access.
                                response: Optional[str] = None
                                if (self._use_openfang_direct
                                        and self._brain_bridge is not None
                                        and tool_name not in _BRAIN_PARAMETERLESS_EVENTS):
                                    try:
                                        _agent_name = self._brain_bridge.space_to_agent(route_result.space)
                                        if _agent_name:
                                            _agent_id = await asyncio.wait_for(
                                                self._brain_bridge.ensure_agent(_agent_name),
                                                timeout=1.0,
                                            )
                                            if _agent_id:
                                                _of_message = (
                                                    f"Tool: {tool_name}\n"
                                                    f"Params: {tool_params}\n"
                                                    f"User: {intent_text}"
                                                )
                                                response = await asyncio.wait_for(
                                                    self._brain_bridge.send_to_agent(
                                                        _agent_id, _of_message
                                                    ),
                                                    timeout=5.0,
                                                )
                                                logger.info(
                                                    f"[HybridRouter] Executed '{tool_name}' "
                                                    f"via OpenFang agent '{_agent_name}'"
                                                )
                                    except Exception as of_err:
                                        logger.warning(
                                            f"[HybridRouter] OpenFang exec failed "
                                            f"({of_err}), falling back to local"
                                        )
                                        response = None

                                # Local execution path (original behavior, also
                                # the fallback when OpenFang routing is off or fails)
                                if response is None:
                                    result = tool_fn(tool_params)
                                    if asyncio.iscoroutine(result):
                                        result = await result
                                    if result is None:
                                        response = f"[{tool_name}] returned no result"
                                    elif isinstance(result, dict):
                                        response = result.get("message", str(result))
                                    else:
                                        response = str(result)
                                # Shadow: Brain observes this routing decision (space routing)
                                if self._brain_shadow:
                                    asyncio.create_task(self._brain_shadow.observe(
                                        user_text=intent_text,
                                        event_type=route_result.event_type,
                                        actual_space=route_result.space,
                                        success=True,
                                    ))
                                # Reward: Brain event-classifier learns from tool success
                                if self._brain_event_shadow and _brain_routing_id:
                                    asyncio.create_task(self._brain_event_shadow.reward(
                                        routing_id=_brain_routing_id,
                                        success=True,
                                    ))
                                hybrid_result = OrchestrationResult(
                                    job_id="",
                                    event_type=route_result.event_type,
                                    stream=route_result.space,
                                    response_hint=response,
                                )
                                # Memory: store intent for all services
                                asyncio.create_task(self._store_memory_for_intent(
                                    intent_text, hybrid_result, context
                                ))
                                return hybrid_result
                            except Exception as exec_err:
                                logger.warning(f"[HybridRouter] Direct exec failed: {exec_err}, falling through")
                                # Negative reward for the brain classifier — its
                                # event_type led to a tool execution failure.
                                if self._brain_event_shadow and _brain_routing_id:
                                    asyncio.create_task(self._brain_event_shadow.reward(
                                        routing_id=_brain_routing_id,
                                        success=False,
                                    ))

                    elif route_result.tier == 5 and route_result.multi_space:
                        # Multi-space → delegate to MinibookHub
                        logger.info(f"[HybridRouter] Tier 5 multi-space -> MinibookHub")
                        if self._minibook_hub:
                            hub_result = await self._minibook_hub.dispatch(intent_text, context)
                            if hub_result and getattr(hub_result, 'success', False):
                                asyncio.create_task(self._store_memory_for_intent(
                                    intent_text, hub_result, context
                                ))
                                return hub_result

                except Exception as router_err:
                    logger.warning(f"[HybridRouter] Phase 0 failed: {router_err}, falling through to MinibookHub")

            # =================================================================
            # PHASE 0.5: MINIBOOK HUB FALLBACK
            # =================================================================
            # When HybridRouter didn't resolve, try MinibookHub as fallback.
            if self._minibook_hub and not domain_hint:
                try:
                    hub_result = await self._minibook_hub.dispatch(intent_text, context)
                    if hub_result and getattr(hub_result, 'success', False):
                        logger.info(f"[MinibookHub] Dispatched: {getattr(hub_result, 'event_type', '?')}")
                        asyncio.create_task(self._store_memory_for_intent(
                            intent_text, hub_result, context
                        ))
                        return hub_result
                    logger.warning("[MinibookHub] Dispatch returned no result")
                    return OrchestrationResult(
                        job_id="",
                        event_type="minibook.timeout",
                        stream="minibook_hub",
                        response_hint="The task was sent, but MinibookHub didn't respond. Please try again.",
                        is_conversational=True,
                    )
                except Exception as hub_err:
                    logger.error(f"[MinibookHub] Dispatch failed: {hub_err}")
                    return OrchestrationResult(
                        job_id="",
                        event_type="error.minibook",
                        stream="minibook_hub",
                        response_hint="MinibookHub ist nicht erreichbar. Stelle sicher, dass der Minibook Docker laeuft.",
                        is_conversational=True,
                        error=str(hub_err),
                    )

            # =================================================================
            # PHASE 1: CORE ANALYSIS - IntentAnalysisTeam (Always runs first)
            # =================================================================
            analysis_result = await self._run_core_analysis(intent_text, context)
            if analysis_result:
                # Core analysis succeeded - use it as primary result
                self._log_classification(intent_text, analysis_result, context)
                asyncio.create_task(self._store_memory_for_intent(
                    intent_text, analysis_result, context
                ))
                return analysis_result

            # =================================================================
            # PHASE 2: PARALLEL AGENT EXTENSIONS (if core analysis fails)
            # =================================================================
            extension_results = await self._run_parallel_extensions(intent_text, context)

            # Select best result from extensions
            best_extension = self._select_best_extension(extension_results)
            if best_extension:
                self._log_classification(intent_text, best_extension, context)
                asyncio.create_task(self._store_memory_for_intent(
                    intent_text, best_extension, context
                ))
                return best_extension

            # =================================================================
            # PHASE 3: FALLBACK (if everything fails)
            # =================================================================
            fallback_result = await self._fallback_processing(intent_text, context)
            self._log_classification(intent_text, fallback_result, context)
            asyncio.create_task(self._store_memory_for_intent(
                intent_text, fallback_result, context
            ))
            return fallback_result

        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            error_result = OrchestrationResult(
                job_id="",
                event_type="error",
                stream="",
                response_hint="Es gab ein Problem bei der Verarbeitung.",
                is_conversational=True,
                error=str(e)
            )
            self._log_classification(intent_text, error_result, context)
            return error_result

    async def _route_to_domain(
        self,
        intent_text: str,
        domain: str,
        context: TaskContext
    ) -> Optional[OrchestrationResult]:
        """
        Route intent directly to a specific domain stream.

        Used when domain_hint is provided from domain-specific tools
        (send_ideas_intent, send_bubbles_intent, etc.)

        Args:
            intent_text: User input
            domain: Target domain (ideas, bubbles, desktop, coding, shuttles)
            context: Task context

        Returns:
            OrchestrationResult if successful, None if failed
        """
        logger.info(f"[DomainRouter] Routing to domain: {domain}")

        try:
            # Special handling for Shuttle domain
            if domain == "shuttles":
                logger.info(f"[DomainRouter] Shuttle domain detected, using shuttle tools")
                
                # Map shuttle domain to shuttle event types
                # shuttle.list -> list_bubbles_with_requirements
                # shuttle.get -> get_bubble_requirements
                # shuttle.process -> process_bubble_requirements
                
                # Try to extract bubble_id from intent text
                bubble_id = None
                if "bubble" in intent_text.lower():
                    # Try to extract bubble ID or name
                    import re
                    bubble_match = re.search(r'bubble\s+(?:id\s*[:=]\s*|name\s*[:=]\s*)?([a-zA-Z0-9_]+)', intent_text, re.IGNORECASE)
                    if bubble_match:
                        bubble_id = bubble_match.group(1)
                        logger.info(f"[DomainRouter] Extracted bubble_id: {bubble_id}")
                
                # Determine shuttle event type based on intent
                event_type = "shuttle.list"  # Default
                if "anforderungen" in intent_text.lower() or "requirements" in intent_text.lower():
                    if bubble_id:
                        event_type = "shuttle.get"
                    else:
                        event_type = "shuttle.list"
                elif "generieren" in intent_text.lower() or "erstellen" in intent_text.lower() or "create" in intent_text.lower():
                    event_type = "shuttle.process"
                
                # Build payload
                payload = {}
                if bubble_id:
                    payload["bubble_id"] = bubble_id
                
                # Add user input to payload
                payload["_user_input"] = intent_text
                
                # Execute via sync mode
                return await self._sync_executor.process_sync(
                    event_type=event_type,
                    payload=payload,
                    response_hint=f"Ich verarbeite deine Shuttle-Anfrage... ({event_type})",
                    user_id=context.user_id if context else "default",
                    session_id=context.session_id if context else "default"
                )

            # Use RAG classifier — smart router that can answer reads directly
            if self._use_rag_classifier and self.rag_classifier:
                # Get bubble context + system state for classifier
                bubble_context = None
                system_state = None
                try:
                    from swarm.context import get_bubble_context_provider, get_real_time_state
                    bubble_context = get_bubble_context_provider().get_current_context()
                    system_state = get_real_time_state().state
                except Exception:
                    pass

                rag_result = await self.rag_classifier.classify(
                    intent_text,
                    bubble_context=bubble_context,
                    system_state=system_state,
                )

                if rag_result and rag_result.confidence >= 0.4:
                    # DIRECT ANSWER MODE: LLM answered a read query from context
                    if rag_result.mode == "direct_answer" and rag_result.direct_answer:
                        logger.info(f"[DomainRouter] Direct answer from LLM (no backend execution)")
                        return OrchestrationResult(
                            job_id=f"direct-{str(uuid.uuid4())[:8]}",
                            event_type="direct_answer",
                            stream="local",
                            response_hint=rag_result.direct_answer,
                            is_conversational=True
                        )

                    # EXECUTE MODE: classify and route to backend
                    event_type = rag_result.event_type
                    payload = rag_result.payload.copy() if rag_result.payload else {}
                    response_hint = rag_result.reasoning or "Ich verarbeite deine Anfrage..."

                    logger.info(f"[DomainRouter] RAG classified: {event_type} ({rag_result.confidence:.0%})")

                    # Add user input to payload
                    payload["_user_input"] = intent_text

                    # Execute via sync mode
                    return await self._sync_executor.process_sync(
                        event_type=event_type,
                        payload=payload,
                        response_hint=response_hint,
                        user_id=context.user_id if context else "default",
                        session_id=context.session_id if context else "default"
                    )

            # Fallback: Use standard classifier
            classification = await self.classifier.classify(intent_text)
            if classification:
                event_type = classification.get("event_type", "unknown")
                payload = classification.get("payload", {})
                response_hint = classification.get("response_hint", "Ich verarbeite deine Anfrage...")

                # Add user input to payload
                payload["_user_input"] = intent_text

                logger.info(f"[DomainRouter] Standard classified: {event_type}")

                return await self._sync_executor.process_sync(
                    event_type=event_type,
                    payload=payload,
                    response_hint=response_hint,
                    user_id=context.user_id if context else "default",
                    session_id=context.session_id if context else "default"
                )

        except Exception as e:
            logger.error(f"[DomainRouter] Error routing to {domain}: {e}")

        return None

    async def _run_stream_listener(
        self,
        intent_text: str,
        context: TaskContext
    ) -> Optional[OrchestrationResult]:
        """
        LLM-based parallel intent routing via StreamListeners.

        All domain listeners evaluate the input in parallel and return
        a confidence distribution. The highest confidence listener wins.

        Returns:
            OrchestrationResult if a winner was found, None to fall through
        """
        import asyncio as _asyncio

        logger.debug(f"[STREAM LISTENER] Evaluating: {intent_text[:80]}...")

        # Step 1: Optional IntentEnhancer for ASR cleanup (keep this)
        enhanced_text = intent_text
        if self._use_enhancement_pipeline and self.intent_enhancer:
            try:
                from swarm.context import get_bubble_context_provider
                bubble_ctx = get_bubble_context_provider().get_current_context()
            except Exception:
                bubble_ctx = {}
            try:
                enhanced = await self.intent_enhancer.enhance(intent_text, bubble_ctx)
                if enhanced.was_enhanced:
                    enhanced_text = enhanced.normalized_text
                    logger.info(f"[StreamListener] Enhanced: '{intent_text[:60]}' -> '{enhanced_text[:60]}'")
            except Exception as e:
                logger.debug(f"[StreamListener] Enhancer failed (using original): {e}")

        # Step 2: Build evaluation context
        conversation_history = []
        try:
            from data import ConversationRepository
            conv_repo = ConversationRepository()
            session_id = context.session_id if context else None
            if session_id:
                messages = conv_repo.get_messages(session_id, limit=5)
                conversation_history = [
                    {"speaker": m.speaker, "text": m.text}
                    for m in messages
                ]
        except Exception:
            pass

        current_bubble = None
        current_bubble_id = None
        idea_count = 0
        try:
            from swarm.context import get_bubble_context_provider
            ctx = get_bubble_context_provider().get_current_context()
            current_bubble = ctx.get("bubble_name")
            current_bubble_id = ctx.get("bubble_id")
            idea_count = ctx.get("idea_count", 0)
        except Exception:
            pass

        eval_context = EvalContext(
            conversation_history=conversation_history,
            current_bubble=current_bubble,
            current_bubble_id=current_bubble_id,
            idea_count=idea_count,
        )

        # Step 3: Evaluate all listeners in parallel
        distribution = await self._stream_dispatcher.evaluate_all(enhanced_text, eval_context)

        # Step 4: Handle result
        if not distribution.winner:
            logger.debug("[STREAM LISTENER] No winner (all below threshold)")
            return None  # Fall through to traditional pipeline

        winner = distribution.winner
        logger.debug(
            f"[STREAM LISTENER] Winner: {winner.space} "
            f"({winner.confidence:.2f}) -> {winner.event_type}"
        )

        # Handle ambiguity
        if distribution.is_ambiguous:
            logger.info(
                f"[StreamListener] Ambiguous: top-2 too close. "
                f"Falling through to RAG classifier for disambiguation."
            )
            logger.debug("[STREAM LISTENER] Ambiguous, falling through")
            return None  # Fall through

        # Check if conversational event
        if winner.event_type in self.CONVERSATIONAL_EVENTS or winner.mode == "direct_answer":
            response = winner.direct_answer if winner.mode == "direct_answer" else ""
            if not response:
                response = winner.payload.get("response", winner.reasoning)
            return OrchestrationResult(
                job_id="",
                event_type=winner.event_type,
                stream="",
                response_hint=response,
                is_conversational=True,
            )

        # Step 5a: SpaceAgent execution (intelligent multi-step, if enabled)
        if (self._use_space_agents
                and winner.space in self._space_agents
                and winner.mode == "execute"):
            try:
                agent = self._space_agents[winner.space]
                agent_context = SpaceAgentContext(
                    user_input=intent_text,
                    conversation_history=conversation_history,
                    current_bubble=current_bubble,
                    current_bubble_id=current_bubble_id,
                    idea_count=idea_count,
                )
                agent_result = await agent.execute(intent_text, agent_context)

                logger.debug(
                    f"[SPACE AGENT:{winner.space}] "
                    f"{agent_result.turns} turns, "
                    f"tools={[tc.name for tc in agent_result.tool_calls]}, "
                    f"{agent_result.total_latency_ms:.0f}ms"
                )

                return OrchestrationResult(
                    job_id=f"agent-{uuid.uuid4().hex[:8]}",
                    event_type=winner.event_type,
                    stream="local",
                    response_hint=agent_result.summary,
                    is_conversational=False,
                )
            except Exception as e:
                logger.warning(f"[SpaceAgent:{winner.space}] Error, falling through to _process_sync: {e}")
                logger.debug(f"[SPACE AGENT] Error: {e}, falling through")

        # Step 5b: Flat _process_sync execution (fallback)
        payload = winner.payload or {}
        # Enrich payload with user input and conversation history
        payload["_user_input"] = intent_text
        payload["_conversation_history"] = conversation_history

        session_id = context.session_id if context else "default"
        user_id = context.user_id if context else "default"

        return await self._sync_executor.process_sync(
            event_type=winner.event_type,
            payload=payload,
            response_hint=winner.reasoning,
            user_id=user_id,
            session_id=session_id,
        )

    async def _run_core_analysis(
        self,
        intent_text: str,
        context: TaskContext
    ) -> Optional[OrchestrationResult]:
        """
        Run core analysis using RAG classifier or IntentAnalysisTeam.

        NEW: Enhancement Pipeline Integration (3-Agent System)
        ======================================================
        1. CollectorAgent: Accumulate short/unclear inputs
        2. IntentEnhancer: Normalize and enhance input for classification
        3. RAG Classifier: Classify enhanced input
        4. ExecutionValidator: Track execution for rule learning

        Priority:
        1. RAG Classifier (Supermemory-based semantic search) - preferred
        2. IntentAnalysisTeam (multi-agent) - fallback

        Args:
            intent_text: User input
            context: Task context

        Returns:
            OrchestrationResult if successful, None if failed
        """
        # =====================================================================
        # STREAM LISTENER: LLM-based parallel routing (if enabled)
        # Short-circuits CollectorAgent + Classifier when active
        # =====================================================================
        if self._use_stream_listener and self._stream_dispatcher:
            try:
                result = await self._run_stream_listener(intent_text, context)
                if result is not None:
                    return result
                # If StreamListener returned None, fall through to traditional pipeline
                logger.info("[StreamListener] No winner, falling through to traditional pipeline")
            except Exception as e:
                logger.warning(f"[StreamListener] Error, falling through: {e}")

        # Store original input for learning feedback
        original_input = intent_text
        rules_applied = []
        enhanced_input = None

        # =====================================================================
        # ENHANCEMENT PIPELINE: Collector + Enhancer (if enabled)
        # =====================================================================
        if self._use_enhancement_pipeline and self.collector_agent and self.intent_enhancer:
            try:
                # Step 1: Collector - check if we should accumulate short inputs
                # BUT skip collector for multi-step commands (they're already complete)
                # Skip collector for multi-step commands and short space-specific commands
                _space_keywords = {"n8n", "rowboat", "roarboot", "minibook", "agentfarm", "agent farm",
                                   "schedule", "desktop", "screenshot", "coding", "bubble", "exploration"}
                _has_space_keyword = any(kw in intent_text.lower() for kw in _space_keywords)
                if self._looks_like_multi_step(intent_text):
                    logger.debug(f"[Enhancement] Multi-step detected, skipping collector: '{intent_text[:40]}...'")
                    collected = intent_text  # Pass through directly
                elif _has_space_keyword:
                    logger.debug(f"[Enhancement] Space keyword detected, skipping collector: '{intent_text[:40]}...'")
                    collected = intent_text  # Pass through directly
                else:
                    collected = await self.collector_agent.collect(intent_text)
                    if collected is None:
                        # Input is being accumulated, return a "listening" response
                        logger.info(f"[Enhancement] Collector accumulating: '{intent_text[:100]}...'")
                        return OrchestrationResult(
                            job_id="",
                            event_type="conversation.listening",
                            stream="",
                            response_hint="Ich hoere zu... (mehr?)",
                            is_conversational=True
                        )
                # Use collected (possibly combined) input
                intent_text = collected

                # Step 2: Enhancer - get bubble context and enhance input
                try:
                    from swarm.context import get_bubble_context_provider
                    bubble_ctx = get_bubble_context_provider().get_current_context()
                except Exception:
                    bubble_ctx = {}

                enhanced = await self.intent_enhancer.enhance(intent_text, bubble_ctx)
                if enhanced.was_enhanced:
                    logger.info(
                        f"[Enhancement] Enhanced: '{intent_text[:100]}' -> '{enhanced.normalized_text[:100]}' "
                        f"(rules: {enhanced.rules_applied})"
                    )
                    logger.debug(f"[ENHANCER] Applied rules: {enhanced.rules_applied}")
                    intent_text = enhanced.normalized_text
                    rules_applied = enhanced.rules_applied
                    enhanced_input = enhanced

            except Exception as e:
                logger.warning(f"[Enhancement] Pipeline error (continuing with original): {e}")

        # Try RAG Classifier first (Supermemory-based)
        if self._use_rag_classifier and self.rag_classifier:
            try:
                logger.info("Running RAG classification with Supermemory")
                logger.debug(f"[RAG CLASSIFIER] Processing: {intent_text[:100]}...")

                # Get bubble context for classifier
                try:
                    from swarm.context import get_bubble_context_provider
                    bubble_context = get_bubble_context_provider().get_current_context()
                    logger.debug(f"[CONTEXT] Current: {bubble_context.get('bubble_name')}, "
                          f"Ideas: {bubble_context.get('idea_count', 0)}")
                except Exception as ctx_error:
                    logger.debug(f"[RAG] Could not get bubble context: {ctx_error}")
                    bubble_context = None

                # Get routing context from past conversations (Supermemory)
                routing_context = ""
                if self.conversation_router and self.conversation_router.is_available:
                    try:
                        routing_context = await self.conversation_router.get_routing_context(intent_text)
                        if routing_context:
                            logger.debug("[ROUTING CONTEXT] Found similar past intents")
                            logger.debug(f"[ConversationRouter] Context: {routing_context[:100]}...")
                    except Exception as router_err:
                        logger.debug(f"[ConversationRouter] Could not get routing context: {router_err}")

                # === DroPE Reference Resolution ===
                # Resolve ambiguous references like "das", "nochmal", "es" using conversation history
                logger.debug(f"[DroPE] Checking... HAS_DROPE={HAS_DROPE_RESOLVER}")
                if HAS_DROPE_RESOLVER and get_reference_resolver:
                    logger.debug("[DroPE] Getting resolver...")
                    resolver = get_reference_resolver()
                    if resolver and resolver.is_available:
                        logger.debug("[DroPE] Resolver available, calling resolve()...")
                        try:
                            resolved_text = resolver.resolve(intent_text, routing_context)
                            if resolved_text != intent_text:
                                logger.debug(f"[DroPE] Resolved: '{intent_text}' -> '{resolved_text}'")
                                logger.info(f"[DroPE] Resolved reference: '{intent_text}' → '{resolved_text}'")
                                intent_text = resolved_text
                            else:
                                logger.debug("[DroPE] No change needed")
                        except Exception as drope_err:
                            logger.debug(f"[DroPE] ERROR: {drope_err}")
                            logger.debug(f"[DroPE] Resolution skipped: {drope_err}")
                    else:
                        logger.debug("[DroPE] Resolver not available")
                else:
                    logger.debug("[DroPE] Skipped (disabled)")
                # === End DroPE ===

                # Enrich intent with routing context if available
                logger.debug("[ORCHESTRATOR] Enriching intent...")
                enriched_for_rag = intent_text
                if routing_context:
                    enriched_for_rag = f"{routing_context}\n\nAktueller Input: {intent_text}"

                logger.debug("[ORCHESTRATOR] Calling RAG classifier...")
                try:
                    result = await self.rag_classifier.classify(enriched_for_rag, bubble_context=bubble_context)
                    logger.debug(f"[ORCHESTRATOR] RAG classifier returned: {result.event_type if result else 'None'}")
                except Exception as rag_err:
                    logger.debug(f"[ORCHESTRATOR] RAG classifier EXCEPTION: {type(rag_err).__name__}: {rag_err}")
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    raise

                # Apply confidence boost from enhancement if rules were applied
                if enhanced_input and enhanced_input.confidence_boost > 0 and result:
                    original_conf = result.confidence
                    result.confidence = min(1.0, result.confidence + enhanced_input.confidence_boost)
                    logger.debug(f"[Enhancement] Confidence boosted: {original_conf:.2f} -> {result.confidence:.2f}")

                if result and result.confidence >= 0.4:
                    logger.debug(f"[RAG CLASSIFIER] Result: {result.event_type} ({result.confidence:.0%})")
                    logger.debug(f"[RAG REASONING] {result.reasoning}")
                    logger.debug(f"[RAG CLASSIFIER] Used rules: {result.used_rules}")

                    # Update real-time state for Rachel's awareness
                    if HAS_REAL_TIME_STATE and get_real_time_state:
                        try:
                            rt_state = get_real_time_state()
                            rt_state.update_intent_result(
                                result.event_type,
                                result.confidence,
                                original_text=intent_text
                            )
                            # Track location changes
                            if result.event_type == "bubble.enter":
                                bubble_name = result.payload.get("bubble_name") or result.payload.get("title")
                                if bubble_name:
                                    rt_state.update_location(bubble_name)
                            elif result.event_type == "bubble.exit":
                                rt_state.clear_location()
                        except Exception as state_err:
                            logger.debug(f"[RealTimeState] Update error: {state_err}")

                    # Log to ReasoningLogger for persistent tracking
                    try:
                        from swarm.reasoning import get_reasoning_logger
                        import uuid
                        reasoning_job_id = str(uuid.uuid4())
                        reasoning_logger = get_reasoning_logger()
                        reasoning_logger.start_job(
                            reasoning_job_id,
                            context.session_id if context else None,
                            intent_text
                        )
                        await reasoning_logger.log_intent_reasoning(
                            job_id=reasoning_job_id,
                            event_type=result.event_type,
                            confidence=result.confidence,
                            reasoning=result.reasoning,
                            used_rules=result.used_rules
                        )
                    except Exception as log_error:
                        logger.debug(f"[RAG] Could not log reasoning: {log_error}")

                    # NOTE: ConversationRouter + memory storage is now handled
                    # universally by _store_memory_for_intent() in process_intent()

                    if result.is_multi_step and result.steps:
                        logger.debug(f"[RAG MULTI-STEP] {len(result.steps)} steps detected")
                        for i, step in enumerate(result.steps):
                            logger.debug(f"[RAG MULTI-STEP] Step {i+1}: {step.get('event_type')}")

                        # Use existing multi-step processor
                        return await self._sync_executor.process_multi_step(
                            result.steps,
                            f"Ich führe {len(result.steps)} Aktionen aus...",
                            context
                        )

                    # Handle conversational events
                    if result.event_type in self.CONVERSATIONAL_EVENTS:
                        return OrchestrationResult(
                            job_id="",
                            event_type=result.event_type,
                            stream="",
                            response_hint=result.reasoning,
                            is_conversational=True
                        )

                    # Include original transcript in payload for parameter extraction
                    enriched_payload = result.payload.copy() if result.payload else {}
                    if result.user_input:
                        enriched_payload["_user_input"] = result.user_input

                    # Include conversation history for contextual resolution
                    if context and context.session_id:
                        try:
                            from data import ConversationRepository
                            conv_repo = ConversationRepository()
                            recent_messages = conv_repo.get_messages_for_session(
                                context.session_id,
                                limit=10  # Last 10 messages for context
                            )
                            if recent_messages:
                                enriched_payload["_conversation_history"] = [
                                    {
                                        "speaker": msg.speaker,
                                        "text": msg.text,
                                        "timestamp": msg.timestamp
                                    }
                                    for msg in recent_messages
                                ]
                                logger.debug(f"[Orchestrator] Added {len(recent_messages)} messages to payload")
                        except Exception as conv_err:
                            logger.debug(f"[Orchestrator] Could not add conversation history: {conv_err}")

                    # Execute via sync fallback or Redis
                    if not self._redis_available:
                        sync_result = await self._sync_executor.process_sync(
                            result.event_type,
                            enriched_payload,
                            f"Ich bearbeite deine Anfrage... ({result.event_type})",
                            user_id=context.user_id if context else "default",
                            session_id=context.session_id if context else "default"
                        )

                        # Register with validator for learning (sync mode)
                        if self._use_enhancement_pipeline and self.execution_validator and sync_result.job_id:
                            try:
                                await self.execution_validator.expect_execution(
                                    job_id=sync_result.job_id,
                                    event_type=result.event_type,
                                    original_input=original_input,
                                    enhanced_input=intent_text,
                                    rules_applied=rules_applied
                                )
                                # Sync execution is immediate - validate now
                                was_successful = sync_result.error is None
                                await self.execution_validator.validate_and_learn(
                                    sync_result.job_id,
                                    force_result=was_successful
                                )
                            except Exception as val_err:
                                logger.debug(f"[Validator] Sync validation error: {val_err}")

                        return sync_result

                    # Redis mode: seed event
                    stream = self.router.get_stream(result.event_type)

                    # Try Redis seeding, fall back to sync on connection errors
                    try:
                        job_id = await self.seeder.seed_task(
                            task_type=result.event_type,
                            payload=enriched_payload,
                            context=context
                        )

                        # Track active task in real-time state
                        if HAS_REAL_TIME_STATE and get_real_time_state:
                            try:
                                rt_state = get_real_time_state()
                                rt_state.add_active_task(job_id, result.event_type, enriched_payload)
                            except Exception as track_err:
                                logger.debug(f"[RealTimeState] Task tracking error: {track_err}")

                    except ConnectionError as ce:
                        # Redis connection failed - fall back to sync mode
                        logger.warning(f"[RAG] Redis seeding failed, falling back to SYNC mode: {ce}")
                        self._redis_available = False
                        return await self._sync_executor.process_sync(
                            result.event_type,
                            enriched_payload,
                            f"Ich bearbeite deine Anfrage... ({result.event_type})",
                            user_id=context.user_id if context else "default",
                            session_id=context.session_id if context else "default"
                        )

                    # Register with validator for learning (Redis mode)
                    if self._use_enhancement_pipeline and self.execution_validator:
                        try:
                            await self.execution_validator.expect_execution(
                                job_id=job_id,
                                event_type=result.event_type,
                                original_input=original_input,
                                enhanced_input=intent_text,
                                rules_applied=rules_applied
                            )
                        except Exception as val_err:
                            logger.debug(f"[Validator] Registration error: {val_err}")

                    return OrchestrationResult(
                        job_id=job_id,
                        event_type=result.event_type,
                        stream=stream,
                        response_hint=f"Ich bearbeite deine Anfrage... ({result.event_type})",
                        is_conversational=False
                    )
                else:
                    logger.debug(f"[RAG CLASSIFIER] Low confidence: {result.confidence if result else 'None'}")

            except Exception as e:
                logger.warning(f"RAG classification failed: {e}")
                logger.debug(f"[RAG CLASSIFIER] Error: {e}")

        # Fallback to IntentAnalysisTeam
        if not self._use_intent_analysis or not self.analysis_team:
            logger.debug("Core analysis not available - IntentAnalysisTeam disabled")
            return None

        try:
            logger.info("Running core analysis with IntentAnalysisTeam")

            # Build user context
            user_context = await self.context_builder.build(
                user_id=context.user_id if context else "default",
                session_id=context.session_id if context else "default"
            )

            logger.debug(f"[CORE ANALYSIS] Context built: space={user_context.current_space}, "
                  f"recent={len(user_context.recent_actions)}")

            # Run parallel intent analysis
            hypotheses = await self.analysis_team.analyze(intent_text, user_context)

            if hypotheses:
                hyp_summary = ", ".join([f"{h.event_type}({h.confidence:.0%})" for h in hypotheses[:3]])
                logger.debug(f"[CORE ANALYSIS] Hypotheses: [{hyp_summary}]")

            # Select best hypothesis with enhanced threshold
            best = self.analysis_team.select_best(hypotheses, threshold=0.3)  # Lower threshold for core

            if not best:
                logger.debug("[CORE ANALYSIS] No confident hypothesis found")
                return None

            logger.debug(f"[CORE ANALYSIS] Selected: {best.event_type} ({best.confidence:.0%}) - {best.source}")

            # Handle conversational events
            if best.event_type in self.CONVERSATIONAL_EVENTS:
                response = await self.conversion_ai.format_response(
                    task_result="",
                    intent=best,
                    context=user_context
                ) if self.conversion_ai else best.reasoning

                return OrchestrationResult(
                    job_id="",
                    event_type=best.event_type,
                    stream="",
                    response_hint=response,
                    is_conversational=True
                )

            # Execute tool via sync fallback or Redis
            if not self._redis_available:
                result = await self._sync_executor.process_sync(
                    best.event_type,
                    best.payload,
                    f"Ich bearbeite deine Anfrage... ({best.event_type})",
                    user_id=user_context.user_id,
                    session_id=user_context.session_id
                )

                # Format with ConversionAI
                if self.conversion_ai and result.response_hint:
                    result.response_hint = await self.conversion_ai.format_response(
                        task_result=result.response_hint,
                        intent=best,
                        context=user_context
                    )

                return result

            # Redis mode: seed event
            stream = self.router.get_stream(best.event_type)

            # Try Redis seeding, fall back to sync on connection errors
            try:
                job_id = await self.seeder.seed_task(
                    task_type=best.event_type,
                    payload=best.payload,
                    context=context
                )
            except ConnectionError as ce:
                # Redis connection failed - fall back to sync mode
                logger.warning(f"[Core] Redis seeding failed, falling back to SYNC mode: {ce}")
                self._redis_available = False
                return await self._sync_executor.process_sync(
                    best.event_type,
                    best.payload,
                    f"Ich bearbeite deine Anfrage... ({best.event_type})",
                    user_id=user_context.user_id,
                    session_id=user_context.session_id
                )

            return OrchestrationResult(
                job_id=job_id,
                event_type=best.event_type,
                stream=stream,
                response_hint=f"Ich bearbeite deine Anfrage... ({best.event_type})",
                is_conversational=False
            )

        except Exception as e:
            logger.warning(f"Core analysis failed: {e}")
            return None

    async def _run_parallel_extensions(
        self,
        intent_text: str,
        context: TaskContext
    ) -> List[OrchestrationResult]:
        """
        Run parallel agent extensions when core analysis fails.

        Extensions include:
        - ToolOrchestrator (Sonnet native tool calling)
        - Legacy IntentClassifier

        Args:
            intent_text: User input
            context: Task context

        Returns:
            List of OrchestrationResult from extensions
        """
        import asyncio

        results = []
        tasks = []

        # ToolOrchestrator extension
        if self._use_tool_orchestrator and self.tool_orchestrator:
            async def run_tool_orchestrator():
                try:
                    return await self._process_with_tool_orchestrator(intent_text)
                except Exception as e:
                    logger.warning(f"ToolOrchestrator extension failed: {e}")
                    return None
            tasks.append(run_tool_orchestrator())

        # Legacy classifier extension
        if self.classifier:
            async def run_legacy_classifier():
                try:
                    return await self._process_intent_legacy(intent_text, context)
                except Exception as e:
                    logger.warning(f"Legacy classifier extension failed: {e}")
                    return None
            tasks.append(run_legacy_classifier())

        # Run all extensions in parallel
        if tasks:
            logger.info(f"Running {len(tasks)} parallel extensions")
            extension_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and None results
            for result in extension_results:
                if isinstance(result, OrchestrationResult) and result:
                    results.append(result)

        logger.info(f"Extensions completed: {len(results)} successful results")
        return results

    def _select_best_extension(self, extension_results: List[OrchestrationResult]) -> Optional[OrchestrationResult]:
        """
        Select the best result from parallel extensions.

        Selection criteria:
        1. Prefer ToolOrchestrator over Legacy (more advanced)
        2. Prefer non-error results
        3. Prefer results with actual job_ids over empty ones

        Args:
            extension_results: Results from parallel extensions

        Returns:
            Best OrchestrationResult or None
        """
        if not extension_results:
            return None

        # Prioritize by source (ToolOrchestrator > Legacy)
        tool_orchestrator_results = [r for r in extension_results if hasattr(r, '_source') and r._source == 'tool_orchestrator']
        legacy_results = [r for r in extension_results if not hasattr(r, '_source') or r._source != 'tool_orchestrator']

        # Select from ToolOrchestrator first
        candidates = tool_orchestrator_results + legacy_results

        for result in candidates:
            # Skip error results
            if result.event_type == "error":
                continue
            # Prefer results with job_ids (indicates successful processing)
            if result.job_id:
                return result
            # Accept conversational results
            if result.is_conversational:
                return result

        # If no good results, return the first non-error one
        non_error_results = [r for r in candidates if r.event_type != "error"]
        return non_error_results[0] if non_error_results else None

    async def _fallback_processing(
        self,
        intent_text: str,
        context: TaskContext
    ) -> OrchestrationResult:
        """
        Final fallback when all other processing fails.

        Provides basic conversational response for unknown inputs.

        Args:
            intent_text: User input
            context: Task context

        Returns:
            Basic fallback OrchestrationResult
        """
        logger.warning("All processing methods failed, using fallback")

        return OrchestrationResult(
            job_id="",
            event_type="conversation.unknown",
            stream="",
            response_hint="Ich bin mir nicht sicher was du meinst. Kannst du das anders formulieren?",
            is_conversational=True,
            error="All processing methods failed"
        )

    def _log_classification(
        self,
        intent_text: str,
        result: OrchestrationResult,
        context: TaskContext
    ) -> None:
        """Log classification for real-time evaluation tracking."""
        # Broadcast to Blaue Rose activity tracker (passive, fire-and-forget)
        try:
            from spaces.flowzen.activity_tracker import get_activity_tracker
            get_activity_tracker().on_intent(result.event_type, {})
        except Exception:
            pass  # Never block intent processing for tracking

        if not self.realtime_evaluator:
            return

        # Don't log evaluation events themselves
        if result.event_type in self.EVALUATION_EVENTS:
            return

        try:
            self.realtime_evaluator.on_classification(
                session_id=context.session_id if context else "default",
                user_input=intent_text,
                result={
                    "event_type": result.event_type,
                    "payload": {},  # Payload not available in OrchestrationResult
                    "confidence": 0.0,  # Not tracked here
                }
            )
        except Exception as e:
            logger.warning(f"Failed to log classification for evaluation: {e}")

    def _get_conversational_response(self, event_type: str, intent_text: str) -> str:
        """
        Get appropriate response for conversational events.

        Phase 7: Used when post-processing corrects an event to a conversational type.

        Args:
            event_type: The conversational event type
            intent_text: Original user input

        Returns:
            Appropriate German response string
        """
        if event_type == "conversation.greeting":
            return "Hallo! Wie kann ich dir helfen?"
        elif event_type == "conversation.help":
            return ("Ich bin Rachel, deine VibeMind-Assistentin. Ich kann Bubbles erstellen und verwalten, "
                    "Ideen notieren und verbinden, und dir bei der Navigation helfen. "
                    "Frag einfach was du brauchst!")
        elif event_type == "conversation.unknown":
            return "Ich bin mir nicht sicher was du meinst. Kannst du das anders formulieren?"
        else:
            return "Ich bearbeite deine Anfrage..."

    async def _process_with_tool_orchestrator(
        self,
        intent_text: str
    ) -> OrchestrationResult:
        """
        Process intent using ToolOrchestrator (Sonnet native tool calling).

        This is the Phase 11 agentic approach that:
        1. Uses Sonnet's native tool calling (not prompt-based classification)
        2. Supports multi-step batch processing
        3. Executes tools directly and returns results
        4. Phase 7: Applies IntentClassifier post-processing rules

        Args:
            intent_text: Natural language user request

        Returns:
            OrchestrationResult with tool execution results
        """
        try:
            # ToolOrchestrator handles everything: classification + execution
            result = self.tool_orchestrator.process_sync(intent_text)

            # Determine event type from tool calls
            event_type = "batch"
            if result.tool_calls:
                event_type = result.tool_calls[0].name.replace("_", ".")

            # Phase 7 Fix: Apply IntentClassifier post-processing rules
            # This catches cases like "batch" -> "conversation.greeting"
            # that the native tool calling doesn't handle well
            classifier = get_intent_classifier()
            corrected = classifier._post_process_classification(
                {"event_type": event_type, "payload": {}},
                intent_text
            )
            corrected_event_type = corrected.get("event_type", event_type)

            if corrected_event_type != event_type:
                logger.info(f"Post-process correction: {event_type} -> {corrected_event_type}")
                event_type = corrected_event_type
                # For conversation events, update the response hint
                if event_type in self.CONVERSATIONAL_EVENTS:
                    return OrchestrationResult(
                        job_id=result.job_id,
                        event_type=event_type,
                        stream="local",
                        response_hint=self._get_conversational_response(event_type, intent_text),
                        is_conversational=True,
                        error=result.error
                    )

            orchestration_result = OrchestrationResult(
                job_id=result.job_id,
                event_type=event_type,
                stream="local",
                response_hint=result.summary,
                is_conversational=len(result.tool_calls) == 0,
                error=result.error
            )
            # Mark as ToolOrchestrator result for extension selection
            orchestration_result._source = 'tool_orchestrator'
            return orchestration_result

        except Exception as e:
            logger.error(f"ToolOrchestrator error: {e}")
            return OrchestrationResult(
                job_id="",
                event_type="error",
                stream="",
                response_hint="Es gab ein Problem bei der Verarbeitung.",
                is_conversational=True,
                error=str(e)
            )

    async def _process_with_analysis_team(
        self,
        intent_text: str,
        context: Optional[TaskContext] = None
    ) -> OrchestrationResult:
        """
        Process intent using Phase 13 Multi-Agent Analysis Team.

        This approach:
        1. Builds user context from multiple sources
        2. Runs parallel analysis through specialized agents
        3. Merges hypotheses and selects best match
        4. Uses ConversionAI for personalized response formatting

        Args:
            intent_text: Natural language user request
            context: Optional task context

        Returns:
            OrchestrationResult with enriched processing
        """
        import sys

        try:
            # 1. Build user context
            user_context = await self.context_builder.build(
                user_id=context.user_id if context else "default",
                session_id=context.session_id if context else "default"
            )

            logger.debug(f"[ANALYSIS] Building context: space={user_context.current_space}, "
                  f"recent={len(user_context.recent_actions)}")

            # 2. Run parallel intent analysis
            hypotheses = await self.analysis_team.analyze(intent_text, user_context)

            # Log hypotheses
            if hypotheses:
                hyp_summary = ", ".join([f"{h.event_type}({h.confidence:.0%})" for h in hypotheses[:3]])
                logger.debug(f"[ANALYSIS] Hypotheses: [{hyp_summary}]")

            # 3. Select best hypothesis
            best = self.analysis_team.select_best(hypotheses, threshold=0.5)

            if not best:
                # No confident hypothesis - use fallback classifier
                logger.debug("[ANALYSIS] No confident hypothesis, falling back to classifier")
                return await self._process_intent_legacy(intent_text, context)

            logger.debug(f"[ANALYSIS] Selected: {best.event_type} ({best.confidence:.0%}) - {best.source}")

            # 4. Check if conversational
            if best.event_type in self.CONVERSATIONAL_EVENTS:
                # Use ConversionAI for personalized greeting
                response = await self.conversion_ai.format_response(
                    task_result="",
                    intent=best,
                    context=user_context
                ) if self.conversion_ai else best.reasoning

                return OrchestrationResult(
                    job_id="",
                    event_type=best.event_type,
                    stream="",
                    response_hint=response,
                    is_conversational=True
                )

            # 5. Execute tool (sync fallback or Redis)
            if not self._redis_available:
                result = await self._sync_executor.process_sync(
                    best.event_type,
                    best.payload,
                    "Ich bearbeite deine Anfrage...",
                    user_id=user_context.user_id,
                    session_id=user_context.session_id
                )

                # Format result with ConversionAI
                if self.conversion_ai and result.response_hint:
                    result.response_hint = await self.conversion_ai.format_response(
                        task_result=result.response_hint,
                        intent=best,
                        context=user_context
                    )

                return result

            # Redis mode: seed event
            stream = self.router.get_stream(best.event_type)

            # Try Redis seeding, fall back to sync on connection errors
            try:
                job_id = await self.seeder.seed_task(
                    task_type=best.event_type,
                    payload=best.payload,
                    context=context or TaskContext()
                )
            except ConnectionError as ce:
                # Redis connection failed - fall back to sync mode
                logger.warning(f"[Analysis] Redis seeding failed, falling back to SYNC mode: {ce}")
                self._redis_available = False
                return await self._sync_executor.process_sync(
                    best.event_type,
                    best.payload,
                    "Ich bearbeite deine Anfrage...",
                    user_id=user_context.user_id,
                    session_id=user_context.session_id
                )

            return OrchestrationResult(
                job_id=job_id,
                event_type=best.event_type,
                stream=stream,
                response_hint=f"Ich bearbeite deine Anfrage... ({best.event_type})",
                is_conversational=False
            )

        except Exception as e:
            logger.error(f"Analysis team error: {e}")
            # Fallback to legacy processing
            return await self._process_intent_legacy(intent_text, context)

    async def _process_intent_legacy(
        self,
        intent_text: str,
        context: Optional[TaskContext] = None
    ) -> OrchestrationResult:
        """Legacy intent processing (pre-Phase 13)."""
        # This is the original process_intent logic
        context = context or TaskContext()

        try:
            classification = await self.classifier.classify(intent_text)

            # =====================================================================
            # Multi-Step Support (Phase 12)
            # If classifier detected multiple actions, process them sequentially
            # =====================================================================
            if classification.get("is_multi_step"):
                steps = classification.get("steps", [])
                response_hint = classification.get("response_hint", "Ich fuehre mehrere Aktionen aus...")

                logger.debug(f"[MULTI-STEP] {len(steps)} steps detected")
                for i, step in enumerate(steps):
                    logger.debug(f"[MULTI-STEP] Step {i+1}: {step.get('event_type')}")

                return await self._sync_executor.process_multi_step(steps, response_hint, context)

            # Single-step processing (legacy)
            event_type = classification["event_type"]
            payload = classification["payload"]
            response_hint = classification.get("response_hint", "Ich bearbeite deine Anfrage...")

            logger.debug(f"[CLASSIFICATION] type={event_type}, payload={payload}")

            if event_type in self.CONVERSATIONAL_EVENTS:
                return OrchestrationResult(
                    job_id="",
                    event_type=event_type,
                    stream="",
                    response_hint=response_hint,
                    is_conversational=True
                )

            if not self._redis_available:
                return await self._sync_executor.process_sync(
                    event_type, payload, response_hint,
                    user_id=context.user_id if context else "default",
                    session_id=context.session_id if context else None
                )

            stream = self.router.get_stream(event_type)

            # Try Redis-based seeding, fall back to sync on connection errors
            try:
                job_id = await self.seeder.seed_task(
                    task_type=event_type,
                    payload=payload,
                    context=context
                )
            except ConnectionError as ce:
                # Redis connection failed - fall back to sync mode
                logger.warning(f"[IntentOrchestrator] Redis seeding failed, falling back to SYNC mode: {ce}")
                self._redis_available = False  # Mark Redis as unavailable for future calls
                return await self._sync_executor.process_sync(
                    event_type, payload, response_hint,
                    user_id=context.user_id if context else "default",
                    session_id=context.session_id if context else None
                )

            return OrchestrationResult(
                job_id=job_id,
                event_type=event_type,
                stream=stream,
                response_hint=response_hint,
                is_conversational=False
            )

        except Exception as e:
            logger.error(f"Legacy orchestration error: {e}")
            return OrchestrationResult(
                job_id="",
                event_type="error",
                stream="",
                response_hint="Es gab ein Problem bei der Verarbeitung.",
                is_conversational=True,
                error=str(e)
            )

    async def _process_via_broadcast(
        self,
        event_type: str,
        payload: Dict[str, Any],
        response_hint: str,
        user_input: str = "",
        conversation_history: List[Dict[str, Any]] = None,
        session_id: str = None,
    ) -> OrchestrationResult:
        """
        Execute via BroadcastDispatcher (Fan-Out to all domain agents).

        The responsible agent executes the tool; non-responsible agents
        analyze the intent from their domain perspective and upload
        user-profiling insights to Supermemory.

        Args:
            event_type: Classified event type (e.g., "bubble.list")
            payload: Tool parameters
            response_hint: Default response hint from classifier
            user_input: Original user text
            conversation_history: Recent conversation messages
            session_id: Session ID for context

        Returns:
            OrchestrationResult with execution result
        """
        if not self._broadcast_dispatcher:
            logger.warning("BroadcastDispatcher not available, falling back to sync")
            return await self._sync_executor.process_sync(
                event_type=event_type,
                payload=payload,
                response_hint=response_hint,
                session_id=session_id,
            )

        try:
            intent = IntentPayload(
                event_type=event_type,
                payload=payload or {},
                user_input=user_input,
                conversation_history=conversation_history or [],
                session_id=session_id or "",
                job_id=f"broadcast-{str(uuid.uuid4())[:8]}",
            )

            logger.info(f"[Broadcast] Fan-Out for {event_type}")
            result = await self._broadcast_dispatcher.broadcast(intent)

            if result.error:
                logger.warning(f"[Broadcast] Execution error: {result.error}")
                # Fall back to sync execution on broadcast error
                return await self._sync_executor.process_sync(
                    event_type=event_type,
                    payload=payload,
                    response_hint=response_hint,
                    session_id=session_id,
                )

            # Log profiling insights count
            if result.profiling_insights:
                logger.info(
                    f"[Broadcast] {len(result.profiling_insights)} profiling insights "
                    f"from non-responsible agents ({result.duration_ms:.0f}ms)"
                )

            response_text = result.response_text or response_hint

            return OrchestrationResult(
                job_id=intent.job_id,
                event_type=event_type,
                stream="broadcast",
                response_hint=response_text,
                is_conversational=False,
            )

        except Exception as e:
            logger.error(f"[Broadcast] Error: {e}, falling back to sync")
            return await self._sync_executor.process_sync(
                event_type=event_type,
                payload=payload,
                response_hint=response_hint,
                session_id=session_id,
            )


    # ── Sync execution methods moved to swarm/orchestrator/sync_executor.py ──
    # ── Result formatting methods moved to swarm/orchestrator/result_formatter.py ──

    def process_intent_sync(
        self,
        intent_text: str,
        context: Optional[TaskContext] = None,
        domain_hint: Optional[str] = None
    ) -> OrchestrationResult:
        """
        Synchronous wrapper for process_intent.

        Args:
            intent_text: Natural language user request
            context: Optional task context
            domain_hint: Optional domain hint for direct routing (ideas, bubbles, desktop, coding, shuttles)

        Returns:
            OrchestrationResult
        """
        import asyncio
        try:
            # Check if we're already in an async context
            asyncio.get_running_loop()  # Raises RuntimeError if no loop
            # If we get here, a loop is running - use thread pool with new loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    self._run_in_new_loop,
                    intent_text,
                    context,
                    domain_hint
                )
                return future.result()
        except RuntimeError:
            # No running loop - safe to use asyncio.run
            return asyncio.run(self.process_intent(intent_text, context, domain_hint=domain_hint))

    def _run_in_new_loop(
        self,
        intent_text: str,
        context: Optional[TaskContext],
        domain_hint: Optional[str] = None
    ) -> OrchestrationResult:
        """Run async code in a new event loop (for thread pool)."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.process_intent(intent_text, context, domain_hint=domain_hint))
        finally:
            loop.close()

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a job.

        Args:
            job_id: Job ID to check

        Returns:
            Job info dict or None if not found
        """
        job = await self.job_manager.get_job(job_id)
        if job:
            return {
                "job_id": job.job_id,
                "status": job.status.value,
                "progress": job.progress,
                "stage": job.stage,
                "result": job.result,
                "error": job.error
            }
        return None


# Singleton instance
_orchestrator: Optional[IntentOrchestrator] = None


def get_orchestrator(model_client=None) -> IntentOrchestrator:
    """Get or create IntentOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IntentOrchestrator(model_client)
    return _orchestrator


__all__ = [
    "IntentOrchestrator",
    "OrchestrationResult",
    "get_orchestrator",
]
