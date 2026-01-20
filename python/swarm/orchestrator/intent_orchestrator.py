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

# Reasoning Logger for multi-step execution tracking
try:
    from swarm.reasoning import get_reasoning_logger
    HAS_REASONING_LOGGER = True
except ImportError:
    HAS_REASONING_LOGGER = False
    get_reasoning_logger = None

logger = logging.getLogger(__name__)

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


@dataclass
class OrchestrationResult:
    """Result of intent orchestration."""
    job_id: str
    event_type: str
    stream: str
    response_hint: str
    is_conversational: bool = False
    error: Optional[str] = None


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

        # Direct tool executors for synchronous fallback AND multi-step execution
        # Multi-step always uses direct execution, so we always load tools
        self._tool_executors: Dict[str, Callable] = {}
        self._load_direct_tools()  # Always load - needed for multi-step execution

        if not self._redis_available and not self._use_tool_orchestrator:
            logger.info("IntentOrchestrator initialized (SYNC fallback mode - no Redis)")
        elif not self._use_tool_orchestrator:
            logger.info("IntentOrchestrator initialized (Redis mode)")
        else:
            logger.info("IntentOrchestrator initialized (Tool orchestrator mode + multi-step tools)")

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

    def _load_direct_tools(self):
        """Load tool implementations for direct synchronous execution."""
        # === BUBBLE TOOLS (all) ===
        try:
            from tools.bubble_tools import (
                list_bubbles, create_bubble, enter_bubble,
                exit_bubble, delete_bubble, get_bubble_stats,
                score_bubble, promote_bubble
            )
            self._tool_executors.update({
                "bubble.list": list_bubbles,
                "bubble.create": create_bubble,
                "bubble.enter": enter_bubble,
                "bubble.exit": exit_bubble,
                "bubble.delete": delete_bubble,
                "bubble.stats": get_bubble_stats,
                "bubble.score": score_bubble,
                "bubble.promote": promote_bubble,
            })
            logger.info("Loaded bubble tools for sync fallback (8 tools)")
        except ImportError as e:
            logger.warning(f"Could not load bubble tools: {e}")

        # === IDEA TOOLS (all) ===
        try:
            from tools.idea_tools import (
                create_idea, list_ideas, find_idea, delete_idea,
                update_idea, connect_ideas, add_image, get_current_space,
                expand_ideas, move_idea, auto_link_ideas, analyze_and_suggest_links
            )
            self._tool_executors.update({
                "idea.create": create_idea,
                "idea.list": list_ideas,
                "idea.find": find_idea,
                "idea.delete": delete_idea,
                "idea.update": update_idea,
                "idea.connect": connect_ideas,
                "idea.add_image": add_image,
                "idea.expand": expand_ideas,
                "idea.move": move_idea,
                "idea.auto_link": auto_link_ideas,
                "idea.analyze_links": analyze_and_suggest_links,
                "bubble.current": get_current_space,
            })
            logger.info("Loaded idea tools for sync fallback (12 tools)")
        except ImportError as e:
            logger.warning(f"Could not load idea tools: {e}")

        # === CODING TOOLS ===
        try:
            from tools.coding_tools import (
                generate_code, get_generation_status, start_preview,
                stop_preview, list_generated_projects, cancel_generation,
                exit_project
            )
            self._tool_executors.update({
                "code.generate": generate_code,
                "code.status": get_generation_status,
                "code.preview.start": start_preview,
                "code.preview.stop": stop_preview,
                "code.list": list_generated_projects,
                "code.cancel": cancel_generation,
                "code.exit": exit_project,
            })
            logger.info("Loaded coding tools for sync fallback (7 tools)")
        except ImportError as e:
            logger.warning(f"Could not load coding tools: {e}")

        # === DESKTOP TOOLS (with sync wrappers) ===
        try:
            from tools.desktop_tools import (
                execute_desktop_task, click_element, type_text,
                press_key, take_screenshot, scroll_screen
            )
            import asyncio
            import concurrent.futures

            def _run_async(coro):
                """Run async function synchronously."""
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(asyncio.run, coro)
                            return future.result()
                    return loop.run_until_complete(coro)
                except RuntimeError:
                    return asyncio.run(coro)

            def _format_desktop_result(result):
                """Format desktop tool result for voice output."""
                if isinstance(result, dict):
                    if result.get("success"):
                        return result.get("message", "Erledigt.")
                    else:
                        return f"Fehler: {result.get('error', result.get('message', 'Unbekannter Fehler'))}"
                return str(result)

            # Sync wrapper functions for desktop tools
            def desktop_task_sync(params):
                goal = params.get("goal", "") or params.get("description", "")
                if not goal:
                    return "Was soll ich auf dem Desktop machen?"
                result = _run_async(execute_desktop_task(goal))
                return _format_desktop_result(result)

            def click_element_sync(params):
                desc = params.get("element_description", "") or params.get("description", "")
                if not desc:
                    return "Welches Element soll ich anklicken?"
                result = _run_async(click_element(desc))
                return _format_desktop_result(result)

            def type_text_sync(params):
                text = params.get("text", "")
                if not text:
                    return "Was soll ich tippen?"
                result = _run_async(type_text(text))
                return _format_desktop_result(result)

            def press_key_sync(params):
                key = params.get("key", "")
                if not key:
                    return "Welche Taste soll ich druecken?"
                result = _run_async(press_key(key))
                return _format_desktop_result(result)

            def take_screenshot_sync(params):
                result = _run_async(take_screenshot())
                return _format_desktop_result(result)

            def scroll_screen_sync(params):
                direction = params.get("direction", "down")
                amount = params.get("amount", 3)
                result = _run_async(scroll_screen(direction, amount))
                return _format_desktop_result(result)

            self._tool_executors.update({
                "desktop.task": desktop_task_sync,
                "desktop.open_app": desktop_task_sync,  # Alias - open_app uses task
                "desktop.click": click_element_sync,
                "desktop.type": type_text_sync,
                "desktop.press_key": press_key_sync,
                "desktop.screenshot": take_screenshot_sync,
                "desktop.scroll": scroll_screen_sync,
            })
            logger.info("Loaded desktop tools for sync fallback (7 tools)")
        except ImportError as e:
            logger.warning(f"Could not load desktop tools: {e}")

        # === EVALUATION TOOLS (Phase 17) ===
        self._load_evaluation_tools()

        # === SUMMARY TOOLS ===
        try:
            from tools.summary_tools import (
                summarize_idea, generate_white_paper,
                list_summaries, get_summary
            )
            self._tool_executors.update({
                "idea.summarize": summarize_idea,
                "idea.whitepaper": generate_white_paper,
                "summary.list": list_summaries,
                "summary.get": get_summary,
            })
            logger.info("Loaded summary tools for sync fallback (4 tools)")
        except ImportError as e:
            logger.warning(f"Could not load summary tools: {e}")

        # === TASK MEMORY TOOLS (Supermemory-based) ===
        try:
            from tools.task_memory_tools import (
                get_tasks_today, get_recent_tasks,
                search_task_history, get_task_stats
            )
            self._tool_executors.update({
                "task.list_today": get_tasks_today,
                "task.recent": get_recent_tasks,
                "task.search": search_task_history,
                "task.stats": get_task_stats,
            })
            logger.info("Loaded task memory tools for sync fallback (4 tools)")
        except ImportError as e:
            logger.debug(f"Could not load task memory tools: {e}")

        # === SYSTEM TASK STATUS TOOLS (Real-time Redis monitoring) ===
        try:
            from tools.task_status_tools import (
                list_active_tasks, get_queue_status,
                get_recent_completions
            )
            self._tool_executors.update({
                "system.active_tasks": list_active_tasks,
                "system.queue_status": get_queue_status,
                "system.recent_completions": get_recent_completions,
            })
            logger.info("Loaded task status tools for sync fallback (3 tools)")
        except ImportError as e:
            logger.debug(f"Could not load task status tools: {e}")

        logger.info(f"Loaded {len(self._tool_executors)} tools for sync fallback")

    def _load_evaluation_tools(self):
        """Load evaluation feedback tools for Phase 17."""
        def eval_correct(params):
            if self.realtime_evaluator:
                return self.realtime_evaluator.on_feedback("correct")
            return "Danke fuer das Feedback!"

        def eval_incorrect(params):
            if self.realtime_evaluator:
                return self.realtime_evaluator.on_feedback("incorrect")
            return "Danke fuer die Korrektur! Was meintest du stattdessen?"

        def eval_clarify(params):
            if self.realtime_evaluator:
                correction = params.get("correction", "") or params.get("intended_action", "")
                return self.realtime_evaluator.on_clarification(correction)
            return "Verstanden, danke!"

        def eval_stats(params):
            if self.realtime_evaluator:
                return self.realtime_evaluator.format_stats_for_voice()
            return "Statistiken sind momentan nicht verfuegbar."

        self._tool_executors.update({
            "evaluation.correct": eval_correct,
            "evaluation.incorrect": eval_incorrect,
            "evaluation.clarify": eval_clarify,
            "evaluation.stats": eval_stats,
        })
        logger.info("Loaded evaluation tools for sync fallback (4 tools)")

    async def process_intent(
        self,
        intent_text: str,
        context: Optional[TaskContext] = None
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

        Returns:
            OrchestrationResult with job_id, event_type, and response_hint
        """
        context = context or TaskContext()
        # Ensure user_input is set for logging/debugging
        if not context.user_input:
            context.user_input = intent_text

        try:
            # =================================================================
            # PHASE 1: CORE ANALYSIS - IntentAnalysisTeam (Always runs first)
            # =================================================================
            analysis_result = await self._run_core_analysis(intent_text, context)
            if analysis_result:
                # Core analysis succeeded - use it as primary result
                self._log_classification(intent_text, analysis_result, context)
                return analysis_result

            # =================================================================
            # PHASE 2: PARALLEL AGENT EXTENSIONS (if core analysis fails)
            # =================================================================
            extension_results = await self._run_parallel_extensions(intent_text, context)

            # Select best result from extensions
            best_extension = self._select_best_extension(extension_results)
            if best_extension:
                self._log_classification(intent_text, best_extension, context)
                return best_extension

            # =================================================================
            # PHASE 3: FALLBACK (if everything fails)
            # =================================================================
            fallback_result = await self._fallback_processing(intent_text, context)
            self._log_classification(intent_text, fallback_result, context)
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
                collected = await self.collector_agent.collect(intent_text)
                if collected is None:
                    # Input is being accumulated, return a "listening" response
                    logger.info(f"[Enhancement] Collector accumulating: '{intent_text[:30]}...'")
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
                        f"[Enhancement] Enhanced: '{intent_text[:40]}' -> '{enhanced.normalized_text[:40]}' "
                        f"(rules: {enhanced.rules_applied})"
                    )
                    print(f"[Python DEBUG] [ENHANCER] Applied rules: {enhanced.rules_applied}", file=sys.stderr)
                    intent_text = enhanced.normalized_text
                    rules_applied = enhanced.rules_applied
                    enhanced_input = enhanced

            except Exception as e:
                logger.warning(f"[Enhancement] Pipeline error (continuing with original): {e}")

        # Try RAG Classifier first (Supermemory-based)
        if self._use_rag_classifier and self.rag_classifier:
            try:
                logger.info("Running RAG classification with Supermemory")
                print(f"[Python DEBUG] [RAG CLASSIFIER] Processing: {intent_text[:60]}...", file=sys.stderr)

                # Get bubble context for classifier
                try:
                    from swarm.context import get_bubble_context_provider
                    bubble_context = get_bubble_context_provider().get_current_context()
                    print(f"[Python DEBUG] [CONTEXT] Current: {bubble_context.get('bubble_name')}, "
                          f"Ideas: {bubble_context.get('idea_count', 0)}", file=sys.stderr)
                except Exception as ctx_error:
                    logger.debug(f"[RAG] Could not get bubble context: {ctx_error}")
                    bubble_context = None

                # Get routing context from past conversations (Supermemory)
                routing_context = ""
                if self.conversation_router and self.conversation_router.is_available:
                    try:
                        routing_context = await self.conversation_router.get_routing_context(intent_text)
                        if routing_context:
                            print(f"[Python DEBUG] [ROUTING CONTEXT] Found similar past intents", file=sys.stderr)
                            logger.debug(f"[ConversationRouter] Context: {routing_context[:100]}...")
                    except Exception as router_err:
                        logger.debug(f"[ConversationRouter] Could not get routing context: {router_err}")

                # Enrich intent with routing context if available
                enriched_for_rag = intent_text
                if routing_context:
                    enriched_for_rag = f"{routing_context}\n\nAktueller Input: {intent_text}"

                result = await self.rag_classifier.classify(enriched_for_rag, bubble_context=bubble_context)

                # Apply confidence boost from enhancement if rules were applied
                if enhanced_input and enhanced_input.confidence_boost > 0 and result:
                    original_conf = result.confidence
                    result.confidence = min(1.0, result.confidence + enhanced_input.confidence_boost)
                    logger.debug(f"[Enhancement] Confidence boosted: {original_conf:.2f} -> {result.confidence:.2f}")

                if result and result.confidence >= 0.4:
                    print(f"[Python DEBUG] [RAG CLASSIFIER] Result: {result.event_type} ({result.confidence:.0%})", file=sys.stderr)
                    print(f"[Python DEBUG] [RAG REASONING] {result.reasoning}", file=sys.stderr)
                    print(f"[Python DEBUG] [RAG CLASSIFIER] Used rules: {result.used_rules}", file=sys.stderr)

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

                    # Handle MULTI-STEP requests
                    # Store interaction in ConversationRouter for future context
                    if self.conversation_router and self.conversation_router.is_available:
                        try:
                            await self.conversation_router.store_interaction(
                                user_input=original_input,
                                classified_intent=result.event_type,
                                confidence=result.confidence,
                                agent_response=result.reasoning or "",
                                parameters=result.payload
                            )
                            logger.debug(f"[ConversationRouter] Stored: {original_input[:30]}... -> {result.event_type}")
                        except Exception as store_err:
                            logger.debug(f"[ConversationRouter] Failed to store interaction: {store_err}")

                    if result.is_multi_step and result.steps:
                        print(f"[Python DEBUG] [RAG MULTI-STEP] {len(result.steps)} steps detected", file=sys.stderr)
                        for i, step in enumerate(result.steps):
                            print(f"[Python DEBUG] [RAG MULTI-STEP] Step {i+1}: {step.get('event_type')}", file=sys.stderr)

                        # Use existing multi-step processor
                        return await self._process_multi_step(
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

                    # Execute via sync fallback or Redis
                    if not self._redis_available:
                        sync_result = await self._process_sync(
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
                        return await self._process_sync(
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
                    print(f"[Python DEBUG] [RAG CLASSIFIER] Low confidence: {result.confidence if result else 'None'}", file=sys.stderr)

            except Exception as e:
                logger.warning(f"RAG classification failed: {e}")
                print(f"[Python DEBUG] [RAG CLASSIFIER] Error: {e}", file=sys.stderr)

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

            print(f"[Python DEBUG] [CORE ANALYSIS] Context built: space={user_context.current_space}, "
                  f"recent={len(user_context.recent_actions)}", file=sys.stderr)

            # Run parallel intent analysis
            hypotheses = await self.analysis_team.analyze(intent_text, user_context)

            if hypotheses:
                hyp_summary = ", ".join([f"{h.event_type}({h.confidence:.0%})" for h in hypotheses[:3]])
                print(f"[Python DEBUG] [CORE ANALYSIS] Hypotheses: [{hyp_summary}]", file=sys.stderr)

            # Select best hypothesis with enhanced threshold
            best = self.analysis_team.select_best(hypotheses, threshold=0.3)  # Lower threshold for core

            if not best:
                print(f"[Python DEBUG] [CORE ANALYSIS] No confident hypothesis found", file=sys.stderr)
                return None

            print(f"[Python DEBUG] [CORE ANALYSIS] Selected: {best.event_type} ({best.confidence:.0%}) - {best.source}", file=sys.stderr)

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
                result = await self._process_sync(
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
                return await self._process_sync(
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

            print(f"[Python DEBUG] [ANALYSIS] Building context: space={user_context.current_space}, "
                  f"recent={len(user_context.recent_actions)}", file=sys.stderr)

            # 2. Run parallel intent analysis
            hypotheses = await self.analysis_team.analyze(intent_text, user_context)

            # Log hypotheses
            if hypotheses:
                hyp_summary = ", ".join([f"{h.event_type}({h.confidence:.0%})" for h in hypotheses[:3]])
                print(f"[Python DEBUG] [ANALYSIS] Hypotheses: [{hyp_summary}]", file=sys.stderr)

            # 3. Select best hypothesis
            best = self.analysis_team.select_best(hypotheses, threshold=0.5)

            if not best:
                # No confident hypothesis - use fallback classifier
                print(f"[Python DEBUG] [ANALYSIS] No confident hypothesis, falling back to classifier", file=sys.stderr)
                return await self._process_intent_legacy(intent_text, context)

            print(f"[Python DEBUG] [ANALYSIS] Selected: {best.event_type} ({best.confidence:.0%}) - {best.source}", file=sys.stderr)

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
                result = await self._process_sync(
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
                return await self._process_sync(
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

                import sys
                print(f"[Python DEBUG] [MULTI-STEP] {len(steps)} steps detected", file=sys.stderr)
                for i, step in enumerate(steps):
                    print(f"[Python DEBUG] [MULTI-STEP] Step {i+1}: {step.get('event_type')}", file=sys.stderr)

                return await self._process_multi_step(steps, response_hint, context)

            # Single-step processing (legacy)
            event_type = classification["event_type"]
            payload = classification["payload"]
            response_hint = classification.get("response_hint", "Ich bearbeite deine Anfrage...")

            import sys
            print(f"[Python DEBUG] [CLASSIFICATION] type={event_type}, payload={payload}", file=sys.stderr)

            if event_type in self.CONVERSATIONAL_EVENTS:
                return OrchestrationResult(
                    job_id="",
                    event_type=event_type,
                    stream="",
                    response_hint=response_hint,
                    is_conversational=True
                )

            if not self._redis_available:
                return await self._process_sync(
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
                return await self._process_sync(
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

    async def _process_sync(
        self,
        event_type: str,
        payload: Dict[str, Any],
        response_hint: str,
        user_id: str = "default",
        session_id: str = None
    ) -> OrchestrationResult:
        """
        Execute tool directly without Redis (synchronous fallback).

        Args:
            event_type: Classified event type (e.g., "bubble.list")
            payload: Tool parameters
            response_hint: Default response hint from classifier
            user_id: User ID for task tracking
            session_id: Session ID for task tracking

        Returns:
            OrchestrationResult with actual tool result in response_hint
        """
        executor = self._tool_executors.get(event_type)
        task_id = None

        # Create task in TaskMemory for tracking (non-trivial events only)
        if self.task_memory and event_type not in self.CONVERSATIONAL_EVENTS:
            try:
                # Generate task title from event type and payload
                title_parts = [event_type]
                if payload:
                    # Add key info from payload
                    for key in ["title", "name", "query", "idea_name", "bubble_name"]:
                        if key in payload and payload[key]:
                            title_parts.append(str(payload[key])[:30])
                            break
                task_title = ": ".join(title_parts)

                task = self.task_memory.create_task(
                    title=task_title,
                    intent_type=event_type,
                    payload=payload or {},
                    user_id=user_id,
                    session_id=session_id
                )
                task_id = task.id
                self.task_memory.start_task(task_id)
                logger.debug(f"Created task {task_id} for {event_type}")
            except Exception as e:
                logger.warning(f"Could not create task in TaskMemory: {e}")

        if executor:
            try:
                logger.info(f"SYNC fallback: Executing {event_type} directly")
                # Tools expect a single params dict, not keyword arguments
                start_time = time.perf_counter()
                result = executor(payload) if payload else executor({})
                latency_ms = (time.perf_counter() - start_time) * 1000

                # Format result for voice output
                result_str = self._format_result_for_voice(event_type, result)

                # Log tool execution
                if HAS_TOOL_LOGGER and get_tool_logger:
                    get_tool_logger().log_execution(
                        tool_name=event_type,
                        params=payload or {},
                        result=result_str,
                        latency_ms=latency_ms,
                        success=True,
                        source_event=event_type
                    )

                # Complete task in TaskMemory
                if self.task_memory and task_id:
                    try:
                        self.task_memory.complete_task(task_id, result_str)
                        logger.debug(f"Completed task {task_id}")
                    except Exception as e:
                        logger.warning(f"Could not complete task: {e}")

                # Store to Supermemory (non-blocking)
                job_id_final = task_id or f"sync-{str(uuid.uuid4())[:8]}"
                import asyncio
                asyncio.create_task(self._store_supermemory_task_completed(
                    job_id=job_id_final,
                    event_type=event_type,
                    result=result_str,
                    duration_ms=int(latency_ms),
                    session_id=session_id
                ))

                return OrchestrationResult(
                    job_id=job_id_final,
                    event_type=event_type,
                    stream="local",
                    response_hint=result_str,
                    is_conversational=False
                )
            except TypeError as e:
                # Handle parameter mismatch - try with empty dict
                logger.warning(f"Parameter mismatch for {event_type}: {e}, trying with empty params")
                try:
                    start_time = time.perf_counter()
                    result = executor({})
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    result_str = self._format_result_for_voice(event_type, result)

                    # Log tool execution (fallback with empty params)
                    if HAS_TOOL_LOGGER and get_tool_logger:
                        get_tool_logger().log_execution(
                            tool_name=event_type,
                            params={},
                            result=result_str,
                            latency_ms=latency_ms,
                            success=True,
                            source_event=event_type
                        )

                    # Complete task even with empty params
                    if self.task_memory and task_id:
                        self.task_memory.complete_task(task_id, result_str)

                    # Store to Supermemory (non-blocking)
                    job_id_fallback = task_id or f"sync-{str(uuid.uuid4())[:8]}"
                    import asyncio
                    asyncio.create_task(self._store_supermemory_task_completed(
                        job_id=job_id_fallback,
                        event_type=event_type,
                        result=result_str,
                        duration_ms=int(latency_ms),
                        session_id=session_id
                    ))

                    return OrchestrationResult(
                        job_id=job_id_fallback,
                        event_type=event_type,
                        stream="local",
                        response_hint=result_str,
                        is_conversational=False
                    )
                except Exception as e2:
                    logger.error(f"Sync execution failed: {e2}")
                    # Log failed execution
                    if HAS_TOOL_LOGGER and get_tool_logger:
                        get_tool_logger().log_error(
                            tool_name=event_type,
                            params={},
                            error=str(e2),
                            latency_ms=0
                        )
                    # Mark task as failed
                    if self.task_memory and task_id:
                        self.task_memory.update_task_status(task_id, "blocked", error=str(e2))
                    # Store failure to Supermemory (non-blocking)
                    if task_id:
                        import asyncio
                        asyncio.create_task(self._store_supermemory_task_failed(
                            job_id=task_id,
                            event_type=event_type,
                            error=str(e2),
                            session_id=session_id
                        ))
            except Exception as e:
                logger.error(f"Sync execution failed for {event_type}: {e}")
                # Log failed execution
                if HAS_TOOL_LOGGER and get_tool_logger:
                    get_tool_logger().log_error(
                        tool_name=event_type,
                        params=payload or {},
                        error=str(e),
                        latency_ms=0
                    )
                # Mark task as failed
                if self.task_memory and task_id:
                    self.task_memory.update_task_status(task_id, "blocked", error=str(e))
                # Store failure to Supermemory (non-blocking)
                if task_id:
                    import asyncio
                    asyncio.create_task(self._store_supermemory_task_failed(
                        job_id=task_id,
                        event_type=event_type,
                        error=str(e),
                        session_id=session_id
                    ))

        # Fallback response if tool not available
        logger.warning(f"No sync executor for {event_type}")
        return OrchestrationResult(
            job_id="",
            event_type=event_type,
            stream="",
            response_hint=response_hint,  # Use classifier's hint
            is_conversational=True,
            error=f"Tool {event_type} nicht im Sync-Modus verfuegbar"
        )

    # =========================================================================
    # Multi-Step Execution (Phase 12)
    # Execute multiple tools in sequence with dependency ordering
    # =========================================================================

    # Intent types that create entities (from IntentBatcher)
    CREATOR_INTENTS = {"bubble.create", "idea.create", "code.generate"}

    # Intent dependencies: {dependent_intent: creator_intent}
    DEPENDENT_INTENTS = {
        "bubble.enter": "bubble.create",
        "idea.create": "bubble.create",
        "idea.update": "idea.create",
        "idea.connect": "idea.create",
        "idea.delete": "idea.create",
        "idea.expand": "idea.create",
        "idea.move": "bubble.create",
        "idea.auto_link": "idea.create",
    }

    async def _process_multi_step(
        self,
        steps: List[Dict[str, Any]],
        response_hint: str,
        context: Optional[TaskContext] = None
    ) -> OrchestrationResult:
        """
        Execute multiple tools in sequence with dependency ordering.

        Uses Kahn's algorithm for topological sorting based on
        IntentBatcher's dependency logic.

        Args:
            steps: List of {event_type, payload} dicts
            response_hint: Initial response hint from classifier
            context: Optional task context

        Returns:
            OrchestrationResult with combined results
        """
        # Generate job_id upfront for reasoning tracking
        job_id = f"multi-{uuid.uuid4().hex[:8]}"

        if not steps:
            return OrchestrationResult(
                job_id=job_id,
                event_type="multi_step",
                stream="local",
                response_hint="Keine Schritte zu ausfuehren.",
                is_conversational=True
            )

        # Start reasoning context for this job
        if self.reasoning_logger:
            user_input = context.user_input if context else ""
            self.reasoning_logger.start_job(job_id, None, user_input)

        # Order steps by dependencies
        ordered_steps = self._order_by_dependencies(steps)
        logger.info(f"Multi-step: Executing {len(ordered_steps)} steps in order")

        # Log dependency ordering reasoning
        if self.reasoning_logger:
            reasoning = self._explain_dependency_order(steps, ordered_steps)
            try:
                await self.reasoning_logger.log_dependency_reasoning(
                    job_id=job_id,
                    ordered_steps=ordered_steps,
                    reasoning=reasoning
                )
            except Exception as e:
                logger.debug(f"Reasoning log failed (non-critical): {e}")

        results = []
        all_success = True
        created_entities = {}  # Track created entity names for later steps
        total_steps = len(ordered_steps)

        for i, step in enumerate(ordered_steps):
            event_type = step.get("event_type", "")
            payload = step.get("payload", {}).copy()  # Copy to avoid modifying original

            # Enrich payload with created entities from previous steps
            # e.g., if bubble.create created "Businessplan", bubble.enter should use it
            if event_type in self.DEPENDENT_INTENTS:
                creator_type = self.DEPENDENT_INTENTS[event_type]
                if creator_type in created_entities:
                    entity_name = created_entities[creator_type]
                    logger.info(f"Multi-step: Enriching {event_type} with {creator_type} result: {entity_name}")
                    # Set appropriate parameter based on event type
                    if event_type == "bubble.enter" and not payload.get("bubble_name"):
                        payload["bubble_name"] = entity_name
                    elif event_type == "idea.create" and not payload.get("bubble_name"):
                        payload["bubble_name"] = entity_name
                    elif event_type == "idea.delete" and not payload.get("bubble_name"):
                        payload["bubble_name"] = entity_name

            # Get executor for this event type
            executor = self._tool_executors.get(event_type)
            if not executor:
                logger.warning(f"Multi-step [{i+1}/{len(ordered_steps)}]: No executor for {event_type}, skipping")
                results.append({
                    "event_type": event_type,
                    "success": False,
                    "error": f"Tool {event_type} nicht verfuegbar"
                })
                continue

            try:
                logger.info(f"Multi-step [{i+1}/{total_steps}]: Executing {event_type}")

                # Log tool start reasoning
                if self.reasoning_logger:
                    try:
                        await self.reasoning_logger.log_tool_start(
                            job_id=job_id,
                            tool_name=event_type,
                            params=payload,
                            step_index=i + 1,
                            total_steps=total_steps,
                            reasoning=f"Executing {event_type} as step {i+1} of {total_steps}"
                        )
                    except Exception as e:
                        logger.debug(f"Reasoning log failed (non-critical): {e}")

                # Execute tool with timing
                start_time = time.perf_counter()
                result = executor(payload) if payload else executor({})
                latency_ms = (time.perf_counter() - start_time) * 1000

                # Track created entities for dependency resolution
                if event_type in self.CREATOR_INTENTS:
                    entity_name = payload.get("title") or payload.get("name") or ""
                    if entity_name:
                        created_entities[event_type] = entity_name

                # Format result
                result_str = self._format_result_for_voice(event_type, result)

                # Log successful tool execution
                if HAS_TOOL_LOGGER and get_tool_logger:
                    get_tool_logger().log_execution(
                        tool_name=event_type,
                        params=payload or {},
                        result=result_str,
                        latency_ms=latency_ms,
                        success=True,
                        source_event="multi_step"
                    )

                results.append({
                    "event_type": event_type,
                    "success": True,
                    "result": result_str
                })

                # Log tool completion reasoning
                if self.reasoning_logger:
                    try:
                        await self.reasoning_logger.log_tool_complete(
                            job_id=job_id,
                            tool_name=event_type,
                            result=result_str,
                            step_index=i + 1,
                            total_steps=total_steps,
                            latency_ms=latency_ms
                        )
                    except Exception as e:
                        logger.debug(f"Reasoning log failed (non-critical): {e}")

                logger.info(f"Multi-step [{i+1}/{total_steps}]: {event_type} completed")

            except Exception as e:
                logger.error(f"Multi-step [{i+1}/{total_steps}]: {event_type} failed: {e}")
                # Log failed tool execution
                if HAS_TOOL_LOGGER and get_tool_logger:
                    get_tool_logger().log_error(
                        tool_name=event_type,
                        params=payload or {},
                        error=str(e),
                        latency_ms=0
                    )

                # Log tool error reasoning
                if self.reasoning_logger:
                    try:
                        await self.reasoning_logger.log_tool_error(
                            job_id=job_id,
                            tool_name=event_type,
                            error=str(e),
                            step_index=i + 1,
                            total_steps=total_steps
                        )
                    except Exception as re:
                        logger.debug(f"Reasoning log failed (non-critical): {re}")

                results.append({
                    "event_type": event_type,
                    "success": False,
                    "error": str(e)
                })
                all_success = False
                # Continue with remaining steps (best effort)

        # Generate summary for voice output
        summary = self._format_multi_step_result(results)

        # Log result reasoning and end job
        if self.reasoning_logger:
            try:
                await self.reasoning_logger.log_result_reasoning(
                    job_id=job_id,
                    summary=summary,
                    voice_response=summary
                )
                self.reasoning_logger.end_job(job_id)
            except Exception as e:
                logger.debug(f"Reasoning log failed (non-critical): {e}")

        return OrchestrationResult(
            job_id=job_id,
            event_type="multi_step",
            stream="local",
            response_hint=summary,
            is_conversational=False,
            error=None if all_success else "Einige Schritte fehlgeschlagen"
        )

    def _order_by_dependencies(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Order steps based on dependency rules using Kahn's algorithm.

        Args:
            steps: List of {event_type, payload} dicts

        Returns:
            Reordered list with dependencies satisfied
        """
        if len(steps) <= 1:
            return steps

        n = len(steps)

        # Build dependency graph
        creator_indices = {}  # event_type -> index
        in_degree = {i: 0 for i in range(n)}
        graph = {i: [] for i in range(n)}  # adjacency list

        for i, step in enumerate(steps):
            event_type = step.get("event_type", "")

            # Track creator intents
            if event_type in self.CREATOR_INTENTS:
                creator_indices[event_type] = i

            # Check if this step depends on a creator
            creator_type = self.DEPENDENT_INTENTS.get(event_type)
            if creator_type and creator_type in creator_indices:
                dep_index = creator_indices[creator_type]
                graph[dep_index].append(i)
                in_degree[i] += 1
                logger.debug(f"Multi-step: {event_type} (index {i}) depends on {creator_type} (index {dep_index})")

        # Kahn's algorithm for topological sort
        queue = [i for i in range(n) if in_degree[i] == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)

            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles (should not happen with our dependency rules)
        if len(order) != n:
            logger.warning("Multi-step: Circular dependency detected, using original order")
            return steps

        # Reorder steps
        ordered = [steps[i] for i in order]
        logger.debug(f"Multi-step: Reordered steps: {[s.get('event_type') for s in ordered]}")
        return ordered

    def _explain_dependency_order(
        self,
        original_steps: List[Dict[str, Any]],
        ordered_steps: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a human-readable explanation of the dependency ordering.

        Args:
            original_steps: Steps before ordering
            ordered_steps: Steps after dependency ordering

        Returns:
            Explanation string for reasoning log
        """
        if len(ordered_steps) <= 1:
            return "Single step, no ordering needed"

        original_order = [s.get("event_type", "") for s in original_steps]
        new_order = [s.get("event_type", "") for s in ordered_steps]

        if original_order == new_order:
            return f"Order unchanged: {' → '.join(new_order)}"

        # Find dependencies that caused reordering
        explanations = []
        for i, step in enumerate(ordered_steps):
            event_type = step.get("event_type", "")
            creator_type = self.DEPENDENT_INTENTS.get(event_type)
            if creator_type:
                # Find where creator is in the order
                for _, prev_step in enumerate(ordered_steps[:i]):
                    if prev_step.get("event_type") == creator_type:
                        explanations.append(f"{event_type} depends on {creator_type}")
                        break

        if explanations:
            deps = "; ".join(explanations)
            return f"Reordered based on dependencies ({deps}): {' → '.join(new_order)}"

        return f"Reordered: {' → '.join(new_order)}"

    def _format_multi_step_result(self, results: List[Dict[str, Any]]) -> str:
        """
        Format multi-step results for voice output.

        Combines successful results into a natural summary.

        Args:
            results: List of step results

        Returns:
            Voice-friendly summary string
        """
        successful = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]

        parts = []

        if successful:
            # Take most meaningful results
            for r in successful:
                result_text = r.get("result", "")
                if result_text and result_text != "Erledigt.":
                    # Truncate long results
                    if len(result_text) > 80:
                        result_text = result_text[:77] + "..."
                    parts.append(result_text)
                else:
                    parts.append(f"{r['event_type']} erledigt")

        if failed:
            fail_count = len(failed)
            parts.append(f"{fail_count} Schritt{'e' if fail_count > 1 else ''} fehlgeschlagen")

        if parts:
            # Join with natural connectors
            if len(parts) == 1:
                return parts[0]
            elif len(parts) == 2:
                return f"{parts[0]}. {parts[1]}."
            else:
                return ". ".join(parts[:3]) + "."

        return "Alle Schritte ausgefuehrt."

    def _enrich_with_task_context(self, response: str, user_context) -> str:
        """Add task memory context to response if relevant."""
        if not user_context or not hasattr(user_context, 'get_task_context_string'):
            return response

        task_context = user_context.get_task_context_string()
        if task_context:
            # Only add if not already mentioned
            if "aufgabe" not in response.lower() and "task" not in response.lower():
                return f"{response} ({task_context})"
        return response

    def _format_result_for_voice(self, event_type: str, result: Any) -> str:
        """Format tool result for natural voice output."""
        if result is None:
            return "Erledigt."

        if isinstance(result, str):
            return result

        if isinstance(result, dict):
            # Handle common result patterns
            if "message" in result:
                return result["message"]
            if "bubbles" in result:
                bubbles = result["bubbles"]
                if not bubbles:
                    return "Du hast noch keine Spaces."
                count = len(bubbles)
                names = [b.get("title", b.get("name", "Unbenannt")) for b in bubbles[:5]]
                if count <= 5:
                    return f"Du hast {count} Spaces: {', '.join(names)}."
                return f"Du hast {count} Spaces. Die ersten sind: {', '.join(names)}."
            if "ideas" in result:
                ideas = result["ideas"]
                if not ideas:
                    return "Keine Ideen gefunden."
                count = len(ideas)
                return f"Ich habe {count} Ideen gefunden."
            if "id" in result:
                # Created something
                return f"Erledigt. ID: {result['id']}"

        if isinstance(result, list):
            if not result:
                return "Keine Ergebnisse gefunden."
            return f"Ich habe {len(result)} Eintraege gefunden."

        return str(result)[:200]

    async def _store_supermemory_task_completed(
        self,
        job_id: str,
        event_type: str,
        result: str,
        duration_ms: int,
        session_id: str = None
    ) -> None:
        """Store task completion event to Supermemory (non-blocking)."""
        if self.sm_task_memory and self.sm_task_memory.is_available:
            try:
                await self.sm_task_memory.store_task_completed(
                    task_id=job_id,
                    intent_type=event_type,
                    result=result,
                    duration_ms=duration_ms,
                    session_id=session_id
                )
            except Exception as e:
                logger.debug(f"[Supermemory] Failed to store task completed: {e}")

        # Track intent usage for user profile learning
        if self.sm_user_profile and self.sm_user_profile.is_available:
            try:
                await self.sm_user_profile.track_intent_usage(event_type)
            except Exception as e:
                logger.debug(f"[Supermemory] Failed to track intent usage: {e}")

    async def _store_supermemory_task_failed(
        self,
        job_id: str,
        event_type: str,
        error: str,
        session_id: str = None
    ) -> None:
        """Store task failure event to Supermemory (non-blocking)."""
        if self.sm_task_memory and self.sm_task_memory.is_available:
            try:
                await self.sm_task_memory.store_task_failed(
                    task_id=job_id,
                    intent_type=event_type,
                    error=error,
                    session_id=session_id
                )
            except Exception as e:
                logger.debug(f"[Supermemory] Failed to store task failed: {e}")

    def process_intent_sync(
        self,
        intent_text: str,
        context: Optional[TaskContext] = None
    ) -> OrchestrationResult:
        """
        Synchronous wrapper for process_intent.

        Args:
            intent_text: Natural language user request
            context: Optional task context

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
                    context
                )
                return future.result()
        except RuntimeError:
            # No running loop - safe to use asyncio.run
            return asyncio.run(self.process_intent(intent_text, context))

    def _run_in_new_loop(
        self,
        intent_text: str,
        context: Optional[TaskContext]
    ) -> OrchestrationResult:
        """Run async code in a new event loop (for thread pool)."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.process_intent(intent_text, context))
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
