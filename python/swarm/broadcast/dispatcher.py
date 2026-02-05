"""
BroadcastDispatcher - Fan-out intent broadcast to all domain agents.

Replaces the EventRouter + Backend Agent system.
Every classified intent is sent to ALL agents simultaneously.
One agent claims responsibility; others do user profiling.

Usage:
    dispatcher = BroadcastDispatcher()
    dispatcher.register_agent(IdeasBroadcastAgent())
    dispatcher.register_agent(CodingBroadcastAgent())
    dispatcher.register_agent(DesktopBroadcastAgent())

    result = await dispatcher.broadcast(IntentPayload(
        event_type="idea.create",
        payload={"title": "Marketing"},
        user_input="Erstelle eine Idee Marketing",
    ))
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm.broadcast.base_broadcast_agent import BaseBroadcastAgent

logger = logging.getLogger(__name__)


@dataclass
class IntentPayload:
    """Classified intent ready for broadcast to all agents."""
    event_type: str
    payload: Dict[str, Any]
    user_input: str = ""
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    session_id: str = ""
    job_id: str = ""
    perspectives: Dict[str, str] = field(default_factory=dict)


@dataclass
class BroadcastResult:
    """Result of broadcasting to all agents."""
    responsible_agent: str
    execution_result: Any
    response_text: str
    profiling_insights: List[Dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None


class BroadcastDispatcher:
    """
    Fan-out dispatcher that sends every intent to all domain agents.

    Each agent independently:
    1. Evaluates if the intent is in its domain (fast, rule-based)
    2. If responsible: executes the action using its tools
    3. If not responsible: profiles the user from its perspective

    Phases:
    - Phase A: Parallel responsibility evaluation (fast, rule-based)
    - Phase B: Responsible agent executes; others profile in parallel
    """

    def __init__(self):
        self._agents: Dict[str, "BaseBroadcastAgent"] = {}
        self._initialized = False

    def register_agent(self, agent: "BaseBroadcastAgent"):
        """Register a domain agent for broadcast."""
        self._agents[agent.name] = agent
        logger.info(f"[BroadcastDispatcher] Registered agent: {agent.name} "
                     f"(domains: {agent.domain_prefixes})")

    @property
    def registered_agents(self) -> List[str]:
        """List of registered agent names."""
        return list(self._agents.keys())

    async def broadcast(self, intent: IntentPayload) -> BroadcastResult:
        """
        Broadcast intent to all registered agents simultaneously.

        Phase A: Parallel responsibility evaluation (fast, rule-based)
        Phase B: Responsible agent executes; others profile in parallel

        Args:
            intent: Classified intent with event_type, payload, etc.

        Returns:
            BroadcastResult with execution result and profiling insights
        """
        start_time = time.time()
        logger.info(
            f"[BroadcastDispatcher] Broadcasting {intent.event_type} "
            f"to {len(self._agents)} agents"
        )

        # --- Phase A: Evaluate responsibility in parallel ---
        responsible_name, responsibilities = await self._evaluate_all(intent)

        if not responsible_name:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(
                f"[BroadcastDispatcher] No agent claimed {intent.event_type}"
            )
            return BroadcastResult(
                responsible_agent="none",
                execution_result=None,
                response_text="Kein Agent ist fuer diesen Intent zustaendig.",
                duration_ms=duration_ms,
                error=f"No agent claimed responsibility for {intent.event_type}",
            )

        logger.info(
            f"[BroadcastDispatcher] {responsible_name} claims {intent.event_type} "
            f"(confidence: {responsibilities[responsible_name].confidence:.2f})"
        )

        # --- Phase B: Execute + Profile in parallel ---
        responsible_agent = self._agents[responsible_name]
        non_responsible = {
            n: a for n, a in self._agents.items()
            if n != responsible_name
        }

        # Retrieve perspectives from Supermemory before execution
        perspectives = await self._retrieve_perspectives(intent)
        intent.perspectives = perspectives

        # Execute action + profile in parallel
        execution_task = self._safe_execute(responsible_agent, intent)
        profiling_tasks = [
            self._safe_profile(name, agent, intent)
            for name, agent in non_responsible.items()
        ]

        all_results = await asyncio.gather(
            execution_task,
            *profiling_tasks,
            return_exceptions=False,  # Handled internally
        )

        execution_result = all_results[0]
        profiling_results = all_results[1:]

        # Collect profiling insights (filter None/errors)
        insights = []
        for name, result in zip(non_responsible.keys(), profiling_results):
            if result and isinstance(result, dict):
                insights.append({"agent": name, "insight": result})

        duration_ms = (time.time() - start_time) * 1000
        response_text = execution_result if isinstance(execution_result, str) else str(execution_result)

        logger.info(
            f"[BroadcastDispatcher] Completed {intent.event_type} via {responsible_name} "
            f"({duration_ms:.0f}ms, {len(insights)} profiling insights)"
        )

        return BroadcastResult(
            responsible_agent=responsible_name,
            execution_result=execution_result,
            response_text=response_text,
            profiling_insights=insights,
            duration_ms=duration_ms,
        )

    async def _evaluate_all(self, intent: IntentPayload):
        """
        Evaluate responsibility across all agents in parallel.

        Returns:
            Tuple of (responsible_agent_name, responsibilities_dict)
        """
        eval_tasks = {
            name: agent.evaluate_responsibility(intent)
            for name, agent in self._agents.items()
        }

        eval_results = await asyncio.gather(
            *eval_tasks.values(),
            return_exceptions=True,
        )

        responsibilities = {}
        responsible_name = None
        highest_confidence = 0.0

        for name, result in zip(eval_tasks.keys(), eval_results):
            if isinstance(result, Exception):
                logger.error(
                    f"[BroadcastDispatcher] {name} evaluation failed: {result}"
                )
                continue

            responsibilities[name] = result

            if result.is_responsible and result.confidence > highest_confidence:
                responsible_name = name
                highest_confidence = result.confidence

        return responsible_name, responsibilities

    async def _safe_execute(self, agent: "BaseBroadcastAgent", intent: IntentPayload) -> Any:
        """Execute with error handling."""
        try:
            return await agent.execute(intent)
        except Exception as e:
            logger.error(
                f"[BroadcastDispatcher] {agent.name} execution failed: {e}",
                exc_info=True,
            )
            return f"Fehler bei der Ausfuehrung: {e}"

    async def _safe_profile(
        self, name: str, agent: "BaseBroadcastAgent", intent: IntentPayload
    ) -> Optional[Dict[str, Any]]:
        """Profile user with error handling. Returns None on failure."""
        try:
            return await agent.profile_user(intent)
        except Exception as e:
            logger.debug(
                f"[BroadcastDispatcher] {name} profiling failed (non-critical): {e}"
            )
            return None

    async def _retrieve_perspectives(
        self, intent: IntentPayload
    ) -> Dict[str, str]:
        """
        Retrieve stored perspectives from Supermemory to enrich execution.

        Searches across all agent perspectives for relevant user behavior data.
        """
        try:
            from memory import get_user_profile_service
            profile_service = get_user_profile_service()
            if not profile_service or not profile_service.is_available:
                return {}

            context = await profile_service.get_user_context()
            if context:
                return {"user_profile": context}
        except Exception as e:
            logger.debug(f"[BroadcastDispatcher] Perspective retrieval failed: {e}")

        return {}


# --- Singleton ---

_dispatcher: Optional[BroadcastDispatcher] = None


def get_broadcast_dispatcher() -> BroadcastDispatcher:
    """Get or create BroadcastDispatcher singleton."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = BroadcastDispatcher()
    return _dispatcher


def reset_broadcast_dispatcher():
    """Reset singleton (for testing)."""
    global _dispatcher
    _dispatcher = None


__all__ = [
    "BroadcastDispatcher",
    "IntentPayload",
    "BroadcastResult",
    "get_broadcast_dispatcher",
    "reset_broadcast_dispatcher",
]
