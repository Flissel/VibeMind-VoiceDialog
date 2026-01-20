"""
ReasoningLogger - Central service for capturing and logging execution reasoning.

Integrates with:
- EventBus (Redis Streams) for optional real-time forwarding
- JSONL files for persistent storage
- NotificationQueue for deferred voice feedback
"""

import json
import uuid
import time
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from swarm.reasoning.reasoning_event import ReasoningEvent, ReasoningContext

logger = logging.getLogger(__name__)


class ReasoningLogger:
    """
    Central service for capturing and publishing reasoning events.

    Captures reasoning at each layer:
    - Intent classification (why this classification?)
    - Dependency ordering (why this order?)
    - Tool execution (what's being done?)
    - Result formatting (what happened?)
    """

    STREAM_REASONING = "events:reasoning"

    def __init__(
        self,
        log_dir: str = None,
        enable_redis: bool = True,
    ):
        """
        Initialize the ReasoningLogger.

        Args:
            log_dir: Directory for JSONL logs (default: logs/reasoning)
            enable_redis: Whether to publish to Redis stream (optional)
        """
        self._log_dir = Path(log_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "logs", "reasoning"
        ))
        self._log_dir.mkdir(parents=True, exist_ok=True)

        self._enable_redis = enable_redis
        self._bus = None  # Lazy-loaded

        # Active reasoning contexts by job_id
        self._contexts: Dict[str, ReasoningContext] = {}

        logger.info(f"[ReasoningLogger] Initialized, logs: {self._log_dir}")

    @property
    def bus(self):
        """Lazy-load EventBus to avoid circular imports."""
        if self._bus is None and self._enable_redis:
            try:
                from swarm.event_bus import get_event_bus
                self._bus = get_event_bus()
            except Exception as e:
                logger.warning(f"[ReasoningLogger] Could not load EventBus: {e}")
                self._enable_redis = False
        return self._bus

    # =========================================================================
    # Public API - Job Lifecycle
    # =========================================================================

    def start_job(
        self,
        job_id: str,
        session_id: Optional[str] = None,
        user_input: str = "",
    ) -> ReasoningContext:
        """
        Start tracking reasoning for a new job.

        Args:
            job_id: Unique job identifier
            session_id: User session ID
            user_input: Original user input

        Returns:
            ReasoningContext for this job
        """
        ctx = ReasoningContext(
            job_id=job_id,
            session_id=session_id,
            user_input=user_input,
            start_time=time.time(),
        )
        self._contexts[job_id] = ctx
        logger.debug(f"[ReasoningLogger] Started job {job_id}")
        return ctx

    def end_job(self, job_id: str) -> Optional[ReasoningContext]:
        """
        End tracking for a job and return the context.

        Args:
            job_id: Job identifier

        Returns:
            ReasoningContext or None if not found
        """
        ctx = self._contexts.pop(job_id, None)
        if ctx:
            logger.debug(f"[ReasoningLogger] Ended job {job_id}, {len(ctx.events)} events")
        return ctx

    def get_context(self, job_id: str) -> Optional[ReasoningContext]:
        """Get the reasoning context for a job."""
        return self._contexts.get(job_id)

    # =========================================================================
    # Public API - Intent Level
    # =========================================================================

    async def log_intent_reasoning(
        self,
        job_id: str,
        event_type: str,
        confidence: float,
        reasoning: str,
        alternatives: List[Dict] = None,
        used_rules: List[str] = None,
    ):
        """
        Log intent classification reasoning.

        Args:
            job_id: Job identifier
            event_type: Classified intent type (e.g., "bubble.create")
            confidence: Confidence score (0-1)
            reasoning: Explanation of classification
            alternatives: Other considered intents
            used_rules: RAG rules used for classification
        """
        event = ReasoningEvent(
            event_id=str(uuid.uuid4()),
            job_id=job_id,
            session_id=self._get_session_id(job_id),
            level="intent",
            phase="completed",
            title=f"Classified as {event_type}",
            reasoning=reasoning,
            metadata={
                "event_type": event_type,
                "alternatives": alternatives or [],
                "used_rules": used_rules or [],
            },
            confidence=confidence,
        )
        await self._publish_and_store(event)

    # =========================================================================
    # Public API - Dependency Level
    # =========================================================================

    async def log_dependency_reasoning(
        self,
        job_id: str,
        ordered_steps: List[Dict],
        reasoning: str,
    ):
        """
        Log dependency ordering reasoning.

        Args:
            job_id: Job identifier
            ordered_steps: Steps in execution order
            reasoning: Explanation of ordering
        """
        event = ReasoningEvent(
            event_id=str(uuid.uuid4()),
            job_id=job_id,
            session_id=self._get_session_id(job_id),
            level="dependency",
            phase="completed",
            title=f"Ordered {len(ordered_steps)} steps",
            reasoning=reasoning,
            metadata={
                "steps": [s.get("event_type", str(s)) for s in ordered_steps],
                "step_count": len(ordered_steps),
            },
            total_steps=len(ordered_steps),
        )
        await self._publish_and_store(event)

    # =========================================================================
    # Public API - Tool Level
    # =========================================================================

    async def log_tool_start(
        self,
        job_id: str,
        tool_name: str,
        params: Dict[str, Any],
        step_index: int = 1,
        total_steps: int = 1,
        reasoning: str = "",
    ):
        """
        Log tool execution start.

        Args:
            job_id: Job identifier
            tool_name: Name of the tool being executed
            params: Tool parameters
            step_index: Current step number (1-based)
            total_steps: Total number of steps
            reasoning: Why this tool is being executed
        """
        event = ReasoningEvent(
            event_id=str(uuid.uuid4()),
            job_id=job_id,
            session_id=self._get_session_id(job_id),
            level="tool",
            phase="started",
            title=f"Executing {tool_name}",
            reasoning=reasoning or f"Starting {tool_name}",
            metadata={
                "tool_name": tool_name,
                "params": self._safe_params(params),
            },
            step_index=step_index,
            total_steps=total_steps,
        )
        await self._publish_and_store(event)

    async def log_tool_complete(
        self,
        job_id: str,
        tool_name: str,
        result: Any,
        step_index: int = 1,
        total_steps: int = 1,
        latency_ms: float = 0,
    ):
        """
        Log tool execution completion.

        Args:
            job_id: Job identifier
            tool_name: Name of the tool
            result: Tool execution result
            step_index: Current step number
            total_steps: Total number of steps
            latency_ms: Execution time in milliseconds
        """
        event = ReasoningEvent(
            event_id=str(uuid.uuid4()),
            job_id=job_id,
            session_id=self._get_session_id(job_id),
            level="tool",
            phase="completed",
            title=f"Completed {tool_name}",
            reasoning=f"Executed in {latency_ms:.0f}ms",
            metadata={
                "tool_name": tool_name,
                "result_preview": str(result)[:200] if result else "",
                "latency_ms": latency_ms,
            },
            step_index=step_index,
            total_steps=total_steps,
        )
        await self._publish_and_store(event)

    async def log_tool_error(
        self,
        job_id: str,
        tool_name: str,
        error: str,
        step_index: int = 1,
        total_steps: int = 1,
    ):
        """
        Log tool execution error.

        Args:
            job_id: Job identifier
            tool_name: Name of the tool
            error: Error message
            step_index: Current step number
            total_steps: Total number of steps
        """
        event = ReasoningEvent(
            event_id=str(uuid.uuid4()),
            job_id=job_id,
            session_id=self._get_session_id(job_id),
            level="tool",
            phase="error",
            title=f"Error in {tool_name}",
            reasoning=error,
            metadata={
                "tool_name": tool_name,
                "error": error,
            },
            step_index=step_index,
            total_steps=total_steps,
        )
        await self._publish_and_store(event)

    # =========================================================================
    # Public API - Result Level
    # =========================================================================

    async def log_result_reasoning(
        self,
        job_id: str,
        summary: str,
        voice_response: str = "",
    ):
        """
        Log final result reasoning.

        Args:
            job_id: Job identifier
            summary: Execution summary
            voice_response: Response for voice output
        """
        event = ReasoningEvent(
            event_id=str(uuid.uuid4()),
            job_id=job_id,
            session_id=self._get_session_id(job_id),
            level="result",
            phase="completed",
            title="Execution Complete",
            reasoning=summary,
            metadata={
                "voice_response": voice_response,
            },
        )
        await self._publish_and_store(event)

        # Update context summary
        ctx = self._contexts.get(job_id)
        if ctx:
            ctx.execution_summary = summary

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _get_session_id(self, job_id: str) -> Optional[str]:
        """Get session ID for a job."""
        ctx = self._contexts.get(job_id)
        return ctx.session_id if ctx else None

    def _safe_params(self, params: Dict) -> Dict:
        """Remove sensitive data from params."""
        if not params:
            return {}
        safe = {}
        for key, value in params.items():
            if key.lower() in ("password", "api_key", "secret", "token"):
                safe[key] = "***"
            elif isinstance(value, str) and len(value) > 500:
                safe[key] = value[:500] + "..."
            else:
                safe[key] = value
        return safe

    async def _publish_and_store(self, event: ReasoningEvent):
        """Publish to Redis and persist to JSONL."""
        # Add to context
        ctx = self._contexts.get(event.job_id)
        if ctx:
            ctx.add_event(event)

        # Publish to Redis stream (optional, non-blocking)
        if self._enable_redis and self.bus:
            try:
                from swarm.event_bus import SwarmEvent
                swarm_event = SwarmEvent(
                    stream=self.STREAM_REASONING,
                    event_type=f"reasoning.{event.level}.{event.phase}",
                    payload=event.to_dict(),
                    job_id=event.job_id,
                )
                await self.bus.publish(swarm_event)
            except Exception as e:
                logger.debug(f"[ReasoningLogger] Redis publish failed (non-critical): {e}")

        # Persist to JSONL
        self._write_to_log(event)

    def _write_to_log(self, event: ReasoningEvent):
        """Write event to daily JSONL file."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self._log_dir / f"reasoning_{today}.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(event.to_json() + "\n")
        except Exception as e:
            logger.error(f"[ReasoningLogger] Failed to write log: {e}")

    def get_recent_events(
        self,
        job_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ReasoningEvent]:
        """
        Get recent reasoning events from the current day's log.

        Args:
            job_id: Filter by job ID (optional)
            limit: Maximum events to return

        Returns:
            List of ReasoningEvent
        """
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self._log_dir / f"reasoning_{today}.jsonl"

        if not log_file.exists():
            return []

        events = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if job_id and data.get("job_id") != job_id:
                            continue
                        events.append(ReasoningEvent.from_dict(data))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"[ReasoningLogger] Failed to read logs: {e}")

        return events[-limit:]


# =============================================================================
# SINGLETON
# =============================================================================

_reasoning_logger: Optional[ReasoningLogger] = None


def get_reasoning_logger() -> ReasoningLogger:
    """Get or create the singleton ReasoningLogger."""
    global _reasoning_logger
    if _reasoning_logger is None:
        _reasoning_logger = ReasoningLogger()
    return _reasoning_logger


__all__ = ["ReasoningLogger", "get_reasoning_logger"]
