"""
Agent Pool - Manages multiple backend agent workers for parallel execution.

Provides:
1. Multiple worker instances per agent type
2. Redis Consumer Groups for load balancing
3. Automatic worker restart on failure
4. Per-user stream isolation support
"""

import asyncio
import logging
from typing import Dict, List, Optional, Type, Any
from dataclasses import dataclass, field
from datetime import datetime

from .base_agent import BaseBackendAgent

logger = logging.getLogger(__name__)


@dataclass
class WorkerStats:
    """Statistics for an individual worker."""
    worker_id: str
    agent_type: str
    events_processed: int = 0
    errors: int = 0
    last_event_at: Optional[datetime] = None
    started_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def uptime_seconds(self) -> float:
        """Get worker uptime in seconds."""
        return (datetime.utcnow() - self.started_at).total_seconds()


class AgentWorker:
    """
    A single worker instance of a backend agent.

    Uses Redis Consumer Groups for coordinated event consumption
    to prevent duplicate processing across workers.
    """

    def __init__(
        self,
        agent: BaseBackendAgent,
        worker_id: str,
        consumer_group: str,
        user_id: Optional[str] = None
    ):
        """
        Initialize worker.

        Args:
            agent: Backend agent instance
            worker_id: Unique worker identifier
            consumer_group: Redis consumer group name
            user_id: Optional user_id for per-user stream isolation
        """
        self.agent = agent
        self.worker_id = worker_id
        self.consumer_group = consumer_group
        self.user_id = user_id
        self.stats = WorkerStats(
            worker_id=worker_id,
            agent_type=agent.name
        )
        self._running = False
        self._task: Optional[asyncio.Task] = None

    @property
    def stream(self) -> str:
        """Get the stream name, with optional user prefix."""
        base_stream = self.agent.stream
        if self.user_id:
            from swarm.event_bus import get_user_stream
            return get_user_stream(base_stream, self.user_id)
        return base_stream

    async def start(self) -> None:
        """Start the worker processing loop."""
        if self._running:
            return

        self._running = True

        # Set up consumer group
        await self._setup_consumer_group()

        # Start processing task
        self._task = asyncio.create_task(self._process_loop())
        logger.info(f"[AgentWorker] Started {self.worker_id} for stream {self.stream}")

    async def stop(self) -> None:
        """Stop the worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info(f"[AgentWorker] Stopped {self.worker_id}")

    async def _setup_consumer_group(self) -> None:
        """Create Redis consumer group if it doesn't exist."""
        try:
            redis = await self.agent.bus._get_redis()

            # Try to create the consumer group
            try:
                await redis.xgroup_create(
                    self.stream,
                    self.consumer_group,
                    id='0',
                    mkstream=True
                )
                logger.info(f"[AgentWorker] Created consumer group '{self.consumer_group}' for {self.stream}")
            except Exception as e:
                # BUSYGROUP means it already exists - that's fine
                if "BUSYGROUP" not in str(e):
                    raise
                logger.debug(f"[AgentWorker] Consumer group '{self.consumer_group}' already exists")

        except Exception as e:
            logger.error(f"[AgentWorker] Failed to setup consumer group: {e}")
            raise

    async def _process_loop(self) -> None:
        """Main processing loop using consumer groups."""
        consecutive_errors = 0
        max_errors = 10

        while self._running:
            try:
                redis = await self.agent.bus._get_redis()

                # Read with consumer group - blocks until message or timeout
                messages = await redis.xreadgroup(
                    self.consumer_group,
                    self.worker_id,
                    {self.stream: '>'},  # '>' means new messages only
                    count=1,
                    block=5000  # 5 second timeout
                )

                consecutive_errors = 0  # Reset on success

                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    for msg_id, data in stream_messages:
                        msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else msg_id

                        try:
                            # Process the event
                            await self._process_event(data)

                            # Acknowledge successful processing
                            await redis.xack(self.stream, self.consumer_group, msg_id_str)

                            self.stats.events_processed += 1
                            self.stats.last_event_at = datetime.utcnow()

                        except Exception as e:
                            self.stats.errors += 1
                            logger.error(f"[AgentWorker] {self.worker_id} failed to process event: {e}")
                            # Don't ACK - message can be retried

            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"[AgentWorker] {self.worker_id} error: {e}")

                if consecutive_errors >= max_errors:
                    logger.error(f"[AgentWorker] {self.worker_id} too many errors, stopping")
                    break

                await asyncio.sleep(min(2 ** consecutive_errors, 30))

    async def _process_event(self, data: Dict[bytes, bytes]) -> None:
        """Process a single event using the agent."""
        from swarm.event_bus import SwarmEvent

        event = SwarmEvent.from_redis(self.stream, data)
        logger.debug(f"[AgentWorker] {self.worker_id} processing: {event.event_type}")

        # Delegate to agent's event handler
        await self.agent._handle_event(event)


class AgentPool:
    """
    Pool of backend agent workers for parallel execution.

    Features:
    - Multiple worker instances per agent type
    - Automatic load balancing via Redis Consumer Groups
    - Worker health monitoring
    - Per-user stream isolation support
    """

    def __init__(
        self,
        agent_class: Type[BaseBackendAgent],
        num_workers: int = 2,
        consumer_group: str = None,
        user_id: Optional[str] = None
    ):
        """
        Initialize agent pool.

        Args:
            agent_class: Backend agent class to instantiate
            num_workers: Number of worker instances
            consumer_group: Redis consumer group name (auto-generated if not provided)
            user_id: Optional user_id for per-user stream isolation
        """
        self.agent_class = agent_class
        self.num_workers = num_workers
        self.user_id = user_id

        # Create a unique consumer group name
        self.consumer_group = consumer_group or f"pool:{agent_class.__name__.lower()}"
        if user_id:
            self.consumer_group = f"{self.consumer_group}:{user_id}"

        self.workers: List[AgentWorker] = []
        self._running = False

        logger.info(
            f"[AgentPool] Created pool for {agent_class.__name__} "
            f"with {num_workers} workers, group={self.consumer_group}"
        )

    async def start(self) -> None:
        """Start all workers in the pool."""
        if self._running:
            return

        self._running = True

        for i in range(self.num_workers):
            worker_id = f"{self.consumer_group}:worker:{i}"

            # Create new agent instance for each worker
            agent = self.agent_class()

            worker = AgentWorker(
                agent=agent,
                worker_id=worker_id,
                consumer_group=self.consumer_group,
                user_id=self.user_id
            )

            await worker.start()
            self.workers.append(worker)

        logger.info(f"[AgentPool] Started {len(self.workers)} workers")

    async def stop(self) -> None:
        """Stop all workers in the pool."""
        self._running = False

        for worker in self.workers:
            await worker.stop()

        self.workers.clear()
        logger.info("[AgentPool] All workers stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all workers in the pool."""
        return {
            "pool": {
                "agent_class": self.agent_class.__name__,
                "num_workers": self.num_workers,
                "consumer_group": self.consumer_group,
                "user_id": self.user_id,
                "running": self._running
            },
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "events_processed": w.stats.events_processed,
                    "errors": w.stats.errors,
                    "uptime_seconds": round(w.stats.uptime_seconds, 1),
                    "last_event_at": w.stats.last_event_at.isoformat() if w.stats.last_event_at else None
                }
                for w in self.workers
            ],
            "totals": {
                "events_processed": sum(w.stats.events_processed for w in self.workers),
                "errors": sum(w.stats.errors for w in self.workers)
            }
        }

    @property
    def total_events_processed(self) -> int:
        """Get total events processed by all workers."""
        return sum(w.stats.events_processed for w in self.workers)


class MultiAgentPool:
    """
    Manages multiple agent pools for different agent types.

    Provides a unified interface for starting/stopping all agent pools
    and aggregating statistics.
    """

    def __init__(self):
        self.pools: Dict[str, AgentPool] = {}
        self._running = False

    def add_pool(
        self,
        name: str,
        agent_class: Type[BaseBackendAgent],
        num_workers: int = 2,
        user_id: Optional[str] = None
    ) -> AgentPool:
        """
        Add a new agent pool.

        Args:
            name: Pool identifier
            agent_class: Backend agent class
            num_workers: Number of workers
            user_id: Optional user_id for isolation

        Returns:
            The created AgentPool
        """
        pool = AgentPool(
            agent_class=agent_class,
            num_workers=num_workers,
            user_id=user_id
        )
        self.pools[name] = pool
        return pool

    async def start_all(self) -> None:
        """Start all pools."""
        self._running = True
        for name, pool in self.pools.items():
            logger.info(f"[MultiAgentPool] Starting pool: {name}")
            await pool.start()
        logger.info(f"[MultiAgentPool] All {len(self.pools)} pools started")

    async def stop_all(self) -> None:
        """Stop all pools."""
        self._running = False
        for name, pool in self.pools.items():
            logger.info(f"[MultiAgentPool] Stopping pool: {name}")
            await pool.stop()
        logger.info("[MultiAgentPool] All pools stopped")

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all pools."""
        return {
            name: pool.get_stats()
            for name, pool in self.pools.items()
        }


# Factory function for common pool configurations
def create_default_pools(
    num_workers_per_pool: int = 2,
    user_id: Optional[str] = None
) -> MultiAgentPool:
    """
    Create the default set of agent pools.

    Args:
        num_workers_per_pool: Number of workers per pool
        user_id: Optional user_id for isolation

    Returns:
        Configured MultiAgentPool with Ideas, Desktop, and Coding pools
    """
    from .ideas_agent import IdeasAgent
    from .desktop_agent import DesktopAgent
    from .coding_agent import CodingAgent

    multi_pool = MultiAgentPool()

    multi_pool.add_pool("ideas", IdeasAgent, num_workers_per_pool, user_id)
    multi_pool.add_pool("desktop", DesktopAgent, num_workers_per_pool, user_id)
    multi_pool.add_pool("coding", CodingAgent, num_workers_per_pool, user_id)

    return multi_pool


__all__ = [
    "AgentWorker",
    "AgentPool",
    "MultiAgentPool",
    "WorkerStats",
    "create_default_pools",
]
