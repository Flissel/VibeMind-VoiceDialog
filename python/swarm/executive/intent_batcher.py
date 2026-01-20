"""
Intent Batcher - Collects rapid-fire intents into batched action plans.

When users speak quickly (e.g., "Create a space, add an idea, then connect them"),
this module batches those intents into a single ActionPlan with proper
dependency ordering.

Architecture:
    User Voice Inputs (rapid-fire)
           ↓
    [IntentBatcher]
        ├─ Collects intents in time window (default 1s)
        ├─ Detects intent dependencies
        └─ Groups into ActionPlan
           ↓
    [IntentOrchestrator] (existing)
           ↓
    [Redis Streams] (existing)
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class Intent:
    """A single classified intent from user input."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    text: str = ""
    event_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "event_type": self.event_type,
            "payload": self.payload,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ActionPlan:
    """
    A batch of related intents with execution order.

    Contains dependency graph for proper sequencing.
    E.g., bubble.create must complete before idea.create in that bubble.
    """

    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    intents: List[Intent] = field(default_factory=list)
    event_sequence: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: Dict[int, List[int]] = field(default_factory=dict)  # {seq_id: [depends_on_seq_ids]}
    status: str = "pending"  # pending, executing, completed, failed
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "plan_id": self.plan_id,
            "intents": [i.to_dict() for i in self.intents],
            "event_sequence": self.event_sequence,
            "dependencies": self.dependencies,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "results": self.results,
        }

    def get_execution_order(self) -> List[int]:
        """
        Topological sort of events based on dependencies.

        Returns sequence IDs in order they should be executed.
        """
        # Build adjacency list (reverse of dependencies)
        num_events = len(self.event_sequence)
        in_degree = {i: 0 for i in range(num_events)}
        graph = {i: [] for i in range(num_events)}

        for seq_id, deps in self.dependencies.items():
            for dep_id in deps:
                graph[dep_id].append(seq_id)
                in_degree[seq_id] += 1

        # Kahn's algorithm
        queue = [i for i in range(num_events) if in_degree[i] == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)

            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(order) != num_events:
            logger.warning("Circular dependency detected, falling back to original order")
            return list(range(num_events))

        return order


class IntentBatcher:
    """
    Collects rapid-fire intents into batched action plans.

    Usage:
        batcher = IntentBatcher(time_window_ms=1000)
        batcher.on_batch_ready = my_callback

        await batcher.add_intent(intent1)
        await batcher.add_intent(intent2)  # Within 1s
        # -> my_callback receives ActionPlan with both intents
    """

    # Intent types that create entities other intents may reference
    CREATOR_INTENTS = {"bubble.create", "idea.create", "code.generate"}

    # Intent types that reference entities created by CREATOR_INTENTS
    DEPENDENT_INTENTS = {
        "bubble.enter": "bubble.create",
        "idea.create": "bubble.create",  # idea depends on bubble existing
        "idea.update": "idea.create",
        "idea.connect": "idea.create",
        "idea.delete": "idea.create",
        "idea.expand": "idea.create",
        "idea.move": "bubble.create",
    }

    def __init__(self, time_window_ms: int = 1000):
        """
        Initialize the intent batcher.

        Args:
            time_window_ms: Time window to collect intents (default 1s)
        """
        self.time_window_ms = time_window_ms
        self._pending_intents: List[Intent] = []
        self._batch_timer: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        # Callback when batch is ready
        self.on_batch_ready: Optional[Callable[[ActionPlan], Awaitable[None]]] = None

        logger.info(f"IntentBatcher initialized with {time_window_ms}ms window")

    async def add_intent(self, intent: Intent) -> None:
        """
        Add an intent to the pending batch.

        Resets the batch timer on each new intent.

        Args:
            intent: The classified intent to add
        """
        async with self._lock:
            self._pending_intents.append(intent)
            logger.debug(f"Added intent to batch: {intent.event_type} (total: {len(self._pending_intents)})")

            # Cancel existing timer and start new one
            if self._batch_timer and not self._batch_timer.done():
                self._batch_timer.cancel()
                try:
                    await self._batch_timer
                except asyncio.CancelledError:
                    pass

            # Start new timer
            self._batch_timer = asyncio.create_task(self._finalize_batch_after_timeout())

    async def _finalize_batch_after_timeout(self) -> None:
        """Wait for timeout, then finalize the batch."""
        try:
            await asyncio.sleep(self.time_window_ms / 1000)

            async with self._lock:
                if self._pending_intents:
                    plan = self._create_action_plan(self._pending_intents.copy())
                    self._pending_intents = []

                    logger.info(f"Batch finalized: {len(plan.intents)} intents -> ActionPlan {plan.plan_id}")

                    if self.on_batch_ready:
                        await self.on_batch_ready(plan)

        except asyncio.CancelledError:
            # Timer was cancelled by new intent
            pass

    def _create_action_plan(self, intents: List[Intent]) -> ActionPlan:
        """
        Convert intents to an action plan with dependencies.

        Detects relationships between intents:
        - bubble.create must complete before idea.create
        - idea.create must complete before idea.connect

        Args:
            intents: List of intents to batch

        Returns:
            ActionPlan with dependency graph
        """
        event_sequence = []
        dependencies: Dict[int, List[int]] = {}

        # Track creator intent indices for dependency resolution
        creator_indices: Dict[str, int] = {}  # event_type -> index

        for i, intent in enumerate(intents):
            event = {
                "sequence_id": i,
                "event_type": intent.event_type,
                "payload": intent.payload,
                "original_text": intent.text,
            }
            event_sequence.append(event)

            # Track if this is a creator intent
            if intent.event_type in self.CREATOR_INTENTS:
                creator_indices[intent.event_type] = i

            # Check for dependencies
            if intent.event_type in self.DEPENDENT_INTENTS:
                depends_on = self.DEPENDENT_INTENTS[intent.event_type]
                if depends_on in creator_indices:
                    dep_index = creator_indices[depends_on]
                    dependencies[i] = dependencies.get(i, []) + [dep_index]
                    logger.debug(f"Dependency: {intent.event_type}[{i}] depends on {depends_on}[{dep_index}]")

        return ActionPlan(
            intents=intents,
            event_sequence=event_sequence,
            dependencies=dependencies,
        )

    async def flush(self) -> Optional[ActionPlan]:
        """
        Force finalize current batch immediately.

        Returns:
            ActionPlan if there were pending intents, None otherwise
        """
        async with self._lock:
            # Cancel timer
            if self._batch_timer and not self._batch_timer.done():
                self._batch_timer.cancel()
                try:
                    await self._batch_timer
                except asyncio.CancelledError:
                    pass

            if not self._pending_intents:
                return None

            plan = self._create_action_plan(self._pending_intents.copy())
            self._pending_intents = []

            logger.info(f"Batch flushed: {len(plan.intents)} intents -> ActionPlan {plan.plan_id}")
            return plan

    def get_pending_count(self) -> int:
        """Get number of pending intents."""
        return len(self._pending_intents)

    async def clear(self) -> None:
        """Clear all pending intents without processing."""
        async with self._lock:
            if self._batch_timer and not self._batch_timer.done():
                self._batch_timer.cancel()
            self._pending_intents = []
            logger.info("IntentBatcher cleared")


__all__ = ["IntentBatcher", "Intent", "ActionPlan"]
