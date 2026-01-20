"""
Enhanced Base Backend Agent - Advanced Agent Framework

Phase 17: Backend Agent Evolution with enhanced capabilities:
- Event-driven communication with pub/sub patterns
- State management for complex workflows
- Plugin architecture for extensibility
- Agent coordination and collaboration
- Health monitoring and self-healing
- Advanced error recovery and resilience
"""

import asyncio
import logging
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Callable, Optional, Set, TYPE_CHECKING
from enum import Enum
import json
import statistics

from swarm.backend_agents.base_agent import BaseBackendAgent
from swarm.event_bus import SwarmEvent

if TYPE_CHECKING:
    from swarm.execution_layer import ExecutionEngine

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Enhanced agent states for complex workflows."""
    INITIALIZING = "initializing"
    IDLE = "idle"
    PROCESSING = "processing"
    COLLABORATING = "collaborating"
    WAITING = "waiting"
    RECOVERING = "recovering"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class AgentCapability(Enum):
    """Agent capabilities for coordination."""
    TASK_EXECUTION = "task_execution"
    DATA_PROCESSING = "data_processing"
    COORDINATION = "coordination"
    MONITORING = "monitoring"
    COMMUNICATION = "communication"
    LEARNING = "learning"
    RECOVERY = "recovery"


@dataclass
class AgentHealth:
    """Health metrics for agent monitoring."""
    agent_name: str
    state: AgentState
    uptime_seconds: float = 0.0
    tasks_processed: int = 0
    tasks_failed: int = 0
    avg_response_time: float = 0.0
    memory_usage_mb: float = 0.0
    error_rate: float = 0.0
    last_health_check: float = field(default_factory=time.time)
    capabilities: Set[AgentCapability] = field(default_factory=set)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.tasks_processed + self.tasks_failed
        return self.tasks_processed / total if total > 0 else 0.0

    @property
    def is_healthy(self) -> bool:
        """Check if agent is healthy."""
        return (
            self.error_rate < 0.1 and  # < 10% error rate
            self.avg_response_time < 30.0 and  # < 30s avg response
            time.time() - self.last_health_check < 60.0  # Recent health check
        )


@dataclass
class WorkflowState:
    """State management for complex workflows."""
    workflow_id: str
    current_step: str
    completed_steps: Set[str] = field(default_factory=set)
    pending_steps: Set[str] = field(default_factory=set)
    failed_steps: Set[str] = field(default_factory=set)
    shared_data: Dict[str, Any] = field(default_factory=dict)
    collaborators: Set[str] = field(default_factory=set)  # Other agents involved
    start_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)

    @property
    def is_complete(self) -> bool:
        """Check if workflow is complete."""
        return len(self.pending_steps) == 0 and len(self.failed_steps) == 0

    @property
    def progress_percentage(self) -> float:
        """Calculate workflow progress."""
        total_steps = len(self.completed_steps) + len(self.pending_steps) + len(self.failed_steps)
        if total_steps == 0:
            return 100.0
        return (len(self.completed_steps) / total_steps) * 100.0


class AgentPlugin(ABC):
    """Plugin interface for extending agent capabilities."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> Set[AgentCapability]:
        """Capabilities provided by this plugin."""
        pass

    @abstractmethod
    async def initialize(self, agent: 'EnhancedBaseAgent') -> None:
        """Initialize plugin with agent reference."""
        pass

    @abstractmethod
    async def execute(self, task_type: str, payload: Dict[str, Any]) -> Any:
        """Execute plugin-specific task."""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup plugin resources."""
        pass


class EnhancedBaseAgent(BaseBackendAgent):
    """
    Enhanced Backend Agent with advanced capabilities.

    Phase 17 Features:
    - State management for complex workflows
    - Event-driven communication patterns
    - Plugin architecture for extensibility
    - Agent coordination and collaboration
    - Health monitoring and self-healing
    - Advanced error recovery
    """

    def __init__(self):
        super().__init__()

        # Enhanced state management
        self._agent_state = AgentState.INITIALIZING
        self._health = AgentHealth(agent_name=self.name)
        self._capabilities: Set[AgentCapability] = set()

        # Workflow state management
        self._active_workflows: Dict[str, WorkflowState] = {}
        self._workflow_lock = asyncio.Lock()

        # Plugin system
        self._plugins: Dict[str, AgentPlugin] = {}
        self._plugin_lock = asyncio.Lock()

        # Agent coordination
        self._collaborators: Dict[str, 'EnhancedBaseAgent'] = {}
        self._coordination_channels: Dict[str, asyncio.Queue] = {}

        # Advanced monitoring
        self._response_times: List[float] = []
        self._health_check_interval = 30.0  # seconds
        self._health_monitor_task: Optional[asyncio.Task] = None

        # Event-driven communication
        self._event_subscriptions: Dict[str, Callable] = {}
        self._event_history: List[SwarmEvent] = []

        # Learning and adaptation
        self._performance_history: Dict[str, List[float]] = {}
        self._adaptation_rules: Dict[str, Callable] = {}

    @property
    def agent_state(self) -> AgentState:
        """Current agent state."""
        return self._agent_state

    @property
    def health(self) -> AgentHealth:
        """Current health status."""
        return self._health

    @property
    def capabilities(self) -> Set[AgentCapability]:
        """Agent capabilities."""
        return self._capabilities.copy()

    async def start(self):
        """Enhanced start with health monitoring and plugin initialization."""
        if self._running:
            logger.warning(f"{self.name} already running")
            return

        # Initialize plugins
        await self._initialize_plugins()

        # Start health monitoring
        self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())

        # Update state
        self._agent_state = AgentState.IDLE
        self._health.state = AgentState.IDLE
        self._health.last_health_check = time.time()

        # Start base functionality
        await super().start()

        logger.info(f"Enhanced {self.name} started with {len(self._plugins)} plugins")

    async def stop(self):
        """Enhanced stop with cleanup."""
        self._agent_state = AgentState.SHUTDOWN

        # Stop health monitoring
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass

        # Cleanup plugins
        await self._cleanup_plugins()

        # Cleanup workflows
        async with self._workflow_lock:
            self._active_workflows.clear()

        # Stop base functionality
        await super().stop()

    # =========================================================================
    # PLUGIN ARCHITECTURE
    # =========================================================================

    async def register_plugin(self, plugin: AgentPlugin) -> None:
        """Register a plugin with this agent."""
        async with self._plugin_lock:
            if plugin.name in self._plugins:
                logger.warning(f"Plugin {plugin.name} already registered")
                return

            await plugin.initialize(self)
            self._plugins[plugin.name] = plugin
            self._capabilities.update(plugin.capabilities)

            logger.info(f"Registered plugin {plugin.name} with capabilities: {plugin.capabilities}")

    async def unregister_plugin(self, plugin_name: str) -> None:
        """Unregister a plugin."""
        async with self._plugin_lock:
            if plugin_name not in self._plugins:
                return

            plugin = self._plugins[plugin_name]
            await plugin.cleanup()
            self._capabilities.difference_update(plugin.capabilities)
            del self._plugins[plugin_name]

            logger.info(f"Unregistered plugin {plugin_name}")

    async def execute_with_plugins(
        self,
        task_type: str,
        payload: Dict[str, Any]
    ) -> Any:
        """Execute task using available plugins."""
        # Try plugins first
        for plugin in self._plugins.values():
            if any(cap in plugin.capabilities for cap in [AgentCapability.TASK_EXECUTION]):
                try:
                    result = await plugin.execute(task_type, payload)
                    if result is not None:
                        return result
                except Exception as e:
                    logger.warning(f"Plugin {plugin.name} failed for {task_type}: {e}")

        # Fall back to base implementation
        return await self._execute_base_task(task_type, payload)

    async def _initialize_plugins(self) -> None:
        """Initialize all registered plugins."""
        # This will be overridden by subclasses to register specific plugins
        pass

    async def _cleanup_plugins(self) -> None:
        """Cleanup all plugins."""
        for plugin in self._plugins.values():
            try:
                await plugin.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up plugin {plugin.name}: {e}")

    # =========================================================================
    # WORKFLOW STATE MANAGEMENT
    # =========================================================================

    async def create_workflow_state(self, workflow_id: str, steps: List[str]) -> WorkflowState:
        """Create new workflow state."""
        async with self._workflow_lock:
            state = WorkflowState(
                workflow_id=workflow_id,
                current_step=steps[0] if steps else "",
                pending_steps=set(steps),
                completed_steps=set()
            )
            self._active_workflows[workflow_id] = state
            return state

    async def update_workflow_state(
        self,
        workflow_id: str,
        completed_step: Optional[str] = None,
        failed_step: Optional[str] = None,
        shared_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update workflow state."""
        async with self._workflow_lock:
            if workflow_id not in self._active_workflows:
                return

            state = self._active_workflows[workflow_id]
            state.last_update = time.time()

            if completed_step:
                state.completed_steps.add(completed_step)
                state.pending_steps.discard(completed_step)
                state.current_step = completed_step

            if failed_step:
                state.failed_steps.add(failed_step)
                state.pending_steps.discard(failed_step)

            if shared_data:
                state.shared_data.update(shared_data)

    async def get_workflow_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """Get workflow state."""
        async with self._workflow_lock:
            return self._active_workflows.get(workflow_id)

    # =========================================================================
    # AGENT COORDINATION
    # =========================================================================

    async def collaborate_with_agent(
        self,
        agent_name: str,
        workflow_id: str,
        message: Dict[str, Any]
    ) -> None:
        """Send collaboration message to another agent."""
        event = SwarmEvent(
            stream=f"agent.{agent_name}",
            event_type="collaboration.request",
            payload={
                "from_agent": self.name,
                "workflow_id": workflow_id,
                "message": message,
                "timestamp": time.time()
            }
        )
        await self.bus.publish(event)

    async def register_collaborator(self, agent: 'EnhancedBaseAgent') -> None:
        """Register another agent for collaboration."""
        self._collaborators[agent.name] = agent
        self._coordination_channels[agent.name] = asyncio.Queue()

    async def send_coordination_message(
        self,
        target_agent: str,
        message_type: str,
        payload: Dict[str, Any]
    ) -> None:
        """Send coordination message to specific agent."""
        if target_agent in self._coordination_channels:
            await self._coordination_channels[target_agent].put({
                "type": message_type,
                "payload": payload,
                "from": self.name,
                "timestamp": time.time()
            })

    async def receive_coordination_messages(self) -> None:
        """Process incoming coordination messages."""
        for agent_name, channel in self._coordination_channels.items():
            try:
                while not channel.empty():
                    message = channel.get_nowait()
                    await self._handle_coordination_message(agent_name, message)
            except asyncio.QueueEmpty:
                continue

    async def _handle_coordination_message(self, from_agent: str, message: Dict[str, Any]) -> None:
        """Handle incoming coordination message."""
        message_type = message.get("type", "")
        payload = message.get("payload", {})

        if message_type == "workflow_update":
            await self._handle_workflow_update(from_agent, payload)
        elif message_type == "resource_request":
            await self._handle_resource_request(from_agent, payload)
        elif message_type == "health_check":
            await self._handle_health_check(from_agent, payload)

    async def _handle_workflow_update(self, from_agent: str, payload: Dict[str, Any]) -> None:
        """Handle workflow update from collaborating agent."""
        workflow_id = payload.get("workflow_id")
        if workflow_id:
            await self.update_workflow_state(
                workflow_id,
                completed_step=payload.get("completed_step"),
                shared_data=payload.get("shared_data")
            )

    async def _handle_resource_request(self, from_agent: str, payload: Dict[str, Any]) -> None:
        """Handle resource request from collaborating agent."""
        # Implementation depends on resource management system
        pass

    async def _handle_health_check(self, from_agent: str, payload: Dict[str, Any]) -> None:
        """Handle health check from collaborating agent."""
        # Respond with own health status
        response = {
            "agent": self.name,
            "healthy": self._health.is_healthy,
            "state": self._agent_state.value,
            "capabilities": [cap.value for cap in self._capabilities]
        }
        await self.send_coordination_message(from_agent, "health_response", response)

    # =========================================================================
    # EVENT-DRIVEN COMMUNICATION
    # =========================================================================

    async def subscribe_to_events(self, event_pattern: str, handler: Callable) -> None:
        """Subscribe to specific event patterns."""
        self._event_subscriptions[event_pattern] = handler
        await self.bus.subscribe_pattern(event_pattern, self._handle_subscribed_event)

    async def publish_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        target_agents: Optional[List[str]] = None
    ) -> None:
        """Publish event with optional targeting."""
        event = SwarmEvent(
            stream=self.stream,
            event_type=event_type,
            payload={
                **payload,
                "from_agent": self.name,
                "target_agents": target_agents,
                "timestamp": time.time()
            }
        )

        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > 1000:  # Limit history
            self._event_history = self._event_history[-500:]

        await self.bus.publish(event)

    async def _handle_subscribed_event(self, event: SwarmEvent) -> None:
        """Handle subscribed events."""
        for pattern, handler in self._event_subscriptions.items():
            if self._matches_pattern(event.event_type, pattern):
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler for {pattern}: {e}")

    def _matches_pattern(self, event_type: str, pattern: str) -> bool:
        """Simple pattern matching for event types."""
        # Support wildcards like "workflow.*" or "agent.health.*"
        if "*" in pattern:
            import fnmatch
            return fnmatch.fnmatch(event_type, pattern)
        return event_type == pattern

    # =========================================================================
    # HEALTH MONITORING & SELF-HEALING
    # =========================================================================

    async def _health_monitor_loop(self) -> None:
        """Continuous health monitoring."""
        while self._running:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._perform_health_check()
                await self._perform_self_healing()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    async def _perform_health_check(self) -> None:
        """Perform comprehensive health check."""
        start_time = time.time()

        # Update basic metrics
        self._health.uptime_seconds = time.time() - getattr(self, '_start_time', time.time())
        self._health.memory_usage_mb = self._get_memory_usage()
        self._health.error_rate = 1.0 - self._health.success_rate
        self._health.last_health_check = time.time()

        # Calculate average response time
        if self._response_times:
            self._health.avg_response_time = statistics.mean(self._response_times[-100:])  # Last 100

        # Check plugin health
        plugin_health = await self._check_plugin_health()
        if not plugin_health:
            self._agent_state = AgentState.ERROR

        # Update state based on health
        if self._health.is_healthy:
            if self._agent_state == AgentState.ERROR:
                self._agent_state = AgentState.RECOVERING
                await self._perform_self_healing()
            elif self._agent_state == AgentState.RECOVERING:
                self._agent_state = AgentState.IDLE
        else:
            self._agent_state = AgentState.ERROR

        self._health.state = self._agent_state

    async def _check_plugin_health(self) -> bool:
        """Check health of all plugins."""
        for plugin in self._plugins.values():
            try:
                # Plugin-specific health check (if implemented)
                if hasattr(plugin, 'health_check'):
                    healthy = await plugin.health_check()
                    if not healthy:
                        return False
            except Exception as e:
                logger.warning(f"Plugin {plugin.name} health check failed: {e}")
                return False
        return True

    async def _perform_self_healing(self) -> None:
        """Perform self-healing actions."""
        if self._agent_state != AgentState.ERROR:
            return

        logger.info(f"Performing self-healing for {self.name}")

        # Restart unhealthy plugins
        for plugin_name, plugin in list(self._plugins.items()):
            try:
                if hasattr(plugin, 'health_check'):
                    healthy = await plugin.health_check()
                    if not healthy:
                        logger.info(f"Restarting plugin {plugin_name}")
                        await plugin.cleanup()
                        await plugin.initialize(self)
            except Exception as e:
                logger.error(f"Failed to restart plugin {plugin_name}: {e}")

        # Clear error state if health improved
        await self._perform_health_check()
        if self._health.is_healthy:
            self._agent_state = AgentState.IDLE
            logger.info(f"Self-healing successful for {self.name}")

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0

    # =========================================================================
    # ENHANCED EVENT HANDLING
    # =========================================================================

    async def _handle_event(self, event: SwarmEvent):
        """Enhanced event handling with coordination."""
        start_time = time.time()

        try:
            self._agent_state = AgentState.PROCESSING
            self._health.tasks_processed += 1

            # Handle coordination messages
            if event.event_type.startswith("collaboration."):
                await self._handle_collaboration_event(event)
                return

            # Handle workflow events
            if "workflow" in event.event_type:
                await self._handle_workflow_event(event)
                return

            # Process regular events
            await super()._handle_event(event)

        except Exception as e:
            self._health.tasks_failed += 1
            raise
        finally:
            # Record response time
            response_time = time.time() - start_time
            self._response_times.append(response_time)
            if len(self._response_times) > 1000:  # Limit history
                self._response_times = self._response_times[-500:]

            self._agent_state = AgentState.IDLE

    async def _handle_collaboration_event(self, event: SwarmEvent) -> None:
        """Handle collaboration events from other agents."""
        self._agent_state = AgentState.COLLABORATING

        payload = event.payload
        from_agent = payload.get("from_agent", "unknown")

        # Route to appropriate handler
        if event.event_type == "collaboration.request":
            await self._handle_collaboration_request(from_agent, payload)
        elif event.event_type == "collaboration.response":
            await self._handle_collaboration_response(from_agent, payload)

    async def _handle_workflow_event(self, event: SwarmEvent) -> None:
        """Handle workflow-related events."""
        payload = event.payload
        workflow_id = payload.get("workflow_id")

        if workflow_id:
            await self.update_workflow_state(
                workflow_id,
                completed_step=payload.get("completed_step"),
                failed_step=payload.get("failed_step"),
                shared_data=payload.get("shared_data")
            )

    async def _handle_collaboration_request(self, from_agent: str, payload: Dict[str, Any]) -> None:
        """Handle collaboration request."""
        # Default implementation - can be overridden
        logger.info(f"Collaboration request from {from_agent}: {payload}")

    async def _handle_collaboration_response(self, from_agent: str, payload: Dict[str, Any]) -> None:
        """Handle collaboration response."""
        # Default implementation - can be overridden
        logger.info(f"Collaboration response from {from_agent}: {payload}")

    # =========================================================================
    # LEARNING AND ADAPTATION
    # =========================================================================

    def record_performance(self, task_type: str, response_time: float, success: bool) -> None:
        """Record performance metrics for learning."""
        if task_type not in self._performance_history:
            self._performance_history[task_type] = []

        self._performance_history[task_type].append(response_time if success else response_time * 2)

        # Keep only recent history
        if len(self._performance_history[task_type]) > 100:
            self._performance_history[task_type] = self._performance_history[task_type][-50:]

    def get_performance_insights(self, task_type: str) -> Dict[str, float]:
        """Get performance insights for task type."""
        if task_type not in self._performance_history:
            return {}

        times = self._performance_history[task_type]
        return {
            "avg_response_time": statistics.mean(times),
            "median_response_time": statistics.median(times),
            "min_response_time": min(times),
            "max_response_time": max(times),
            "success_rate": len([t for t in times if t < 10.0]) / len(times)  # Rough success estimate
        }

    async def _execute_base_task(self, task_type: str, payload: Dict[str, Any]) -> Any:
        """Base task execution - to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _execute_base_task")

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_agent_stats(self) -> Dict[str, Any]:
        """Get comprehensive agent statistics."""
        return {
            "name": self.name,
            "state": self._agent_state.value,
            "health": {
                "healthy": self._health.is_healthy,
                "uptime": self._health.uptime_seconds,
                "tasks_processed": self._health.tasks_processed,
                "success_rate": self._health.success_rate,
                "avg_response_time": self._health.avg_response_time,
                "error_rate": self._health.error_rate
            },
            "capabilities": [cap.value for cap in self._capabilities],
            "active_workflows": len(self._active_workflows),
            "plugins": list(self._plugins.keys()),
            "collaborators": list(self._collaborators.keys())
        }


__all__ = [
    "EnhancedBaseAgent",
    "AgentState",
    "AgentCapability",
    "AgentHealth",
    "WorkflowState",
    "AgentPlugin"
]