"""
Execution Layer - Scalable Task Execution Infrastructure

Phase 16: Advanced Execution Layer with Workflow Planning, Resource Management,
and Parallel Processing for complex multi-step operations.

Features:
- Workflow Planning with dependency graphs
- Resource-aware task scheduling
- Parallel execution with concurrency control
- Execution monitoring and performance tracking
- Error recovery and circuit breaker patterns
- Scalable worker pool management
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple, Callable
from enum import Enum
from collections import defaultdict, deque
import heapq
import threading
import statistics

from swarm.workers.base_worker import BaseWorker, WorkerConfig, WorkerProgress
from swarm.event_buffer import TaskInfo, TaskStatus

logger = logging.getLogger(__name__)


class ExecutionState(Enum):
    """States for execution layer components."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResourceType(Enum):
    """Types of resources that can be managed."""
    CPU = "cpu"
    MEMORY = "memory"
    NETWORK = "network"
    STORAGE = "storage"
    GPU = "gpu"


@dataclass
class ResourceRequirements:
    """Resource requirements for a task."""
    cpu_cores: float = 1.0
    memory_mb: float = 128.0
    network_bandwidth: float = 0.0  # Mbps
    storage_mb: float = 10.0
    gpu_memory_mb: float = 0.0

    @property
    def total_resources(self) -> Dict[ResourceType, float]:
        """Get all resource requirements as a dict."""
        return {
            ResourceType.CPU: self.cpu_cores,
            ResourceType.MEMORY: self.memory_mb,
            ResourceType.NETWORK: self.network_bandwidth,
            ResourceType.STORAGE: self.storage_mb,
            ResourceType.GPU: self.gpu_memory_mb,
        }


@dataclass
class WorkflowStep:
    """A step in a workflow with dependencies."""
    step_id: str
    task_type: str
    payload: Dict[str, Any]
    dependencies: Set[str] = field(default_factory=set)
    resource_requirements: ResourceRequirements = field(default_factory=ResourceRequirements)
    priority: int = 1  # 1=low, 5=high
    timeout_seconds: float = 300.0
    retry_count: int = 3

    @property
    def is_ready(self) -> bool:
        """Check if all dependencies are satisfied."""
        return len(self.dependencies) == 0


@dataclass
class WorkflowPlan:
    """Complete workflow execution plan."""
    workflow_id: str
    steps: Dict[str, WorkflowStep]
    execution_order: List[str] = field(default_factory=list)
    estimated_duration: float = 0.0
    total_resources: ResourceRequirements = field(default_factory=ResourceRequirements)

    def get_ready_steps(self, completed_steps: Set[str]) -> List[WorkflowStep]:
        """Get steps that are ready to execute."""
        ready = []
        for step in self.steps.values():
            if step.step_id not in completed_steps and step.is_ready:
                ready.append(step)
        return ready

    def mark_dependency_satisfied(self, completed_step_id: str) -> None:
        """Mark a dependency as satisfied for all dependent steps."""
        for step in self.steps.values():
            step.dependencies.discard(completed_step_id)


@dataclass
class ExecutionMetrics:
    """Performance metrics for execution tracking."""
    workflow_id: str
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_execution_time: float = 0.0
    total_execution_time: float = 0.0
    resource_utilization: Dict[ResourceType, float] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_tasks == 0:
            return 0.0
        return self.completed_tasks / self.total_tasks

    @property
    def is_complete(self) -> bool:
        """Check if execution is complete."""
        return self.completed_tasks + self.failed_tasks >= self.total_tasks


class ResourceManager:
    """
    Manages system resources for task scheduling.

    Tracks available resources and prevents over-subscription.
    """

    def __init__(self, total_resources: Dict[ResourceType, float]):
        self.total_resources = total_resources.copy()
        self.available_resources = total_resources.copy()
        self.allocated_resources: Dict[str, Dict[ResourceType, float]] = {}
        self._lock = threading.Lock()

    def allocate_resources(self, task_id: str, requirements: ResourceRequirements) -> bool:
        """
        Try to allocate resources for a task.

        Args:
            task_id: Unique task identifier
            requirements: Resource requirements

        Returns:
            True if allocation successful
        """
        with self._lock:
            needed = requirements.total_resources

            # Check if all resources are available
            for resource_type, amount in needed.items():
                if self.available_resources.get(resource_type, 0) < amount:
                    return False

            # Allocate resources
            for resource_type, amount in needed.items():
                self.available_resources[resource_type] -= amount

            self.allocated_resources[task_id] = needed
            logger.debug(f"Allocated resources for task {task_id}: {needed}")
            return True

    def release_resources(self, task_id: str) -> None:
        """
        Release resources allocated to a task.

        Args:
            task_id: Task identifier
        """
        with self._lock:
            if task_id in self.allocated_resources:
                allocated = self.allocated_resources[task_id]
                for resource_type, amount in allocated.items():
                    self.available_resources[resource_type] += amount
                del self.allocated_resources[task_id]
                logger.debug(f"Released resources for task {task_id}")

    def get_utilization(self) -> Dict[ResourceType, float]:
        """Get current resource utilization percentages."""
        utilization = {}
        for resource_type, total in self.total_resources.items():
            used = total - self.available_resources.get(resource_type, total)
            utilization[resource_type] = (used / total) * 100 if total > 0 else 0
        return utilization


class WorkflowPlanner:
    """
    Plans workflow execution with dependency resolution and optimization.
    """

    def __init__(self):
        self.plans: Dict[str, WorkflowPlan] = {}

    def create_plan(
        self,
        workflow_id: str,
        steps: List[WorkflowStep],
        optimize: bool = True
    ) -> WorkflowPlan:
        """
        Create an optimized execution plan for a workflow.

        Args:
            workflow_id: Unique workflow identifier
            steps: List of workflow steps
            optimize: Whether to optimize execution order

        Returns:
            Optimized workflow plan
        """
        plan = WorkflowPlan(workflow_id=workflow_id, steps={step.step_id: step for step in steps})

        if optimize:
            plan.execution_order = self._optimize_execution_order(steps)
        else:
            plan.execution_order = [step.step_id for step in steps]

        # Calculate total resources and estimated duration
        plan.total_resources = self._calculate_total_resources(steps)
        plan.estimated_duration = self._estimate_duration(steps)

        self.plans[workflow_id] = plan
        logger.info(f"Created workflow plan {workflow_id} with {len(steps)} steps")
        return plan

    def _optimize_execution_order(self, steps: List[WorkflowStep]) -> List[str]:
        """
        Optimize execution order using topological sort with priority weighting.
        """
        # Build dependency graph
        graph = defaultdict(list)
        in_degree = defaultdict(int)

        step_dict = {step.step_id: step for step in steps}

        for step in steps:
            in_degree[step.step_id] = len(step.dependencies)
            for dep in step.dependencies:
                graph[dep].append(step.step_id)

        # Priority queue for topological sort (higher priority first)
        queue = []
        for step_id, degree in in_degree.items():
            if degree == 0:
                step = step_dict[step_id]
                # Use negative priority for max-heap behavior
                heapq.heappush(queue, (-step.priority, step_id))

        order = []
        while queue:
            _, step_id = heapq.heappop(queue)
            order.append(step_id)

            for dependent in graph[step_id]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    dep_step = step_dict[dependent]
                    heapq.heappush(queue, (-dep_step.priority, dependent))

        # Check for cycles
        if len(order) != len(steps):
            logger.warning("Workflow contains cycles, using original order")
            return [step.step_id for step in steps]

        return order

    def _calculate_total_resources(self, steps: List[WorkflowStep]) -> ResourceRequirements:
        """Calculate total resource requirements for all steps."""
        total = ResourceRequirements()
        for step in steps:
            total.cpu_cores = max(total.cpu_cores, step.resource_requirements.cpu_cores)
            total.memory_mb += step.resource_requirements.memory_mb
            total.network_bandwidth = max(total.network_bandwidth, step.resource_requirements.network_bandwidth)
            total.storage_mb += step.resource_requirements.storage_mb
            total.gpu_memory_mb = max(total.gpu_memory_mb, step.resource_requirements.gpu_memory_mb)
        return total

    def _estimate_duration(self, steps: List[WorkflowStep]) -> float:
        """Estimate total workflow duration based on step timeouts."""
        # Simple estimation: sum of all timeouts (assuming parallel execution where possible)
        # In reality, this would consider the critical path
        return sum(step.timeout_seconds for step in steps) * 0.7  # 70% efficiency factor


class ExecutionEngine:
    """
    Core execution engine with parallel processing and resource management.
    """

    def __init__(
        self,
        workers: List[BaseWorker],
        resource_manager: Optional[ResourceManager] = None,
        max_concurrent_tasks: int = 10
    ):
        self.workers = {worker.name: worker for worker in workers}
        self.resource_manager = resource_manager or ResourceManager({
            ResourceType.CPU: 8.0,  # 8 CPU cores
            ResourceType.MEMORY: 8192.0,  # 8GB RAM
            ResourceType.NETWORK: 100.0,  # 100 Mbps
            ResourceType.STORAGE: 102400.0,  # 100GB
            ResourceType.GPU: 0.0  # No GPU
        })

        self.max_concurrent_tasks = max_concurrent_tasks
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.workflow_planner = WorkflowPlanner()

        # Metrics and monitoring
        self.metrics: Dict[str, ExecutionMetrics] = {}
        self.execution_history: List[ExecutionMetrics] = []

        # Circuit breaker for error handling
        self.failure_count = 0
        self.last_failure_time = 0
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 60.0  # seconds

        self._running = False
        self._shutdown_event = asyncio.Event()

        logger.info(f"ExecutionEngine initialized with {len(workers)} workers")

    async def execute_workflow(
        self,
        workflow_id: str,
        steps: List[WorkflowStep],
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> ExecutionMetrics:
        """
        Execute a complete workflow with dependency management.

        Args:
            workflow_id: Unique workflow identifier
            steps: List of workflow steps to execute
            progress_callback: Optional progress callback

        Returns:
            Execution metrics
        """
        # Create execution plan
        plan = self.workflow_planner.create_plan(workflow_id, steps)

        # Initialize metrics
        metrics = ExecutionMetrics(
            workflow_id=workflow_id,
            total_tasks=len(steps)
        )
        self.metrics[workflow_id] = metrics

        logger.info(f"Starting workflow execution: {workflow_id} ({len(steps)} steps)")

        try:
            # Execute workflow
            await self._execute_workflow_plan(plan, metrics, progress_callback)

            metrics.end_time = time.time()
            metrics.total_execution_time = metrics.end_time - metrics.start_time

            if metrics.failed_tasks == 0:
                logger.info(f"Workflow {workflow_id} completed successfully")
            else:
                logger.warning(f"Workflow {workflow_id} completed with {metrics.failed_tasks} failures")

        except Exception as e:
            logger.error(f"Workflow {workflow_id} failed: {e}")
            metrics.end_time = time.time()
            metrics.total_execution_time = metrics.end_time - metrics.start_time

        # Store in history
        self.execution_history.append(metrics)

        return metrics

    async def _execute_workflow_plan(
        self,
        plan: WorkflowPlan,
        metrics: ExecutionMetrics,
        progress_callback: Optional[Callable[[str, float, str], None]]
    ) -> None:
        """Execute a workflow plan with parallel processing."""
        completed_steps: Set[str] = set()
        pending_tasks: Dict[str, asyncio.Task] = {}

        while len(completed_steps) < len(plan.steps):
            # Check circuit breaker
            if self._is_circuit_breaker_open():
                raise Exception("Circuit breaker is open due to excessive failures")

            # Get ready steps
            ready_steps = plan.get_ready_steps(completed_steps)

            # Limit concurrent tasks
            available_slots = self.max_concurrent_tasks - len(pending_tasks)
            steps_to_start = ready_steps[:available_slots]

            # Start new tasks
            for step in steps_to_start:
                if self._can_allocate_resources(step):
                    task = asyncio.create_task(self._execute_step(step, metrics))
                    pending_tasks[step.step_id] = task
                    logger.debug(f"Started execution of step {step.step_id}")

            # Wait for at least one task to complete
            if pending_tasks:
                done, pending = await asyncio.wait(
                    pending_tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Process completed tasks
                for task in done:
                    step_id = None
                    for sid, t in pending_tasks.items():
                        if t == task:
                            step_id = sid
                            break

                    if step_id:
                        del pending_tasks[step_id]
                        completed_steps.add(step_id)
                        plan.mark_dependency_satisfied(step_id)

                        # Update progress
                        progress = (len(completed_steps) / len(plan.steps)) * 100
                        if progress_callback:
                            progress_callback(plan.workflow_id, progress, f"Completed step {step_id}")

            else:
                # No tasks running and no ready steps - possible deadlock
                logger.error("Workflow deadlock detected - no ready steps and no running tasks")
                break

        # Wait for all remaining tasks
        if pending_tasks:
            await asyncio.gather(*pending_tasks.values(), return_exceptions=True)

    def _can_allocate_resources(self, step: WorkflowStep) -> bool:
        """Check if resources can be allocated for a step."""
        if not self.resource_manager:
            return True
        return self.resource_manager.allocate_resources(step.step_id, step.resource_requirements)

    async def _execute_step(self, step: WorkflowStep, metrics: ExecutionMetrics) -> None:
        """Execute a single workflow step."""
        start_time = time.time()

        try:
            # Find appropriate worker
            worker = self._find_worker_for_task(step.task_type)
            if not worker:
                raise Exception(f"No worker available for task type: {step.task_type}")

            # Create task info
            task_info = TaskInfo(
                task_id=step.step_id,
                task_type=step.task_type,
                payload=step.payload,
                status=TaskStatus.PENDING
            )

            # Execute task
            result = await asyncio.wait_for(
                worker.execute_task(task_info),
                timeout=step.timeout_seconds
            )

            # Success
            metrics.completed_tasks += 1
            execution_time = time.time() - start_time
            metrics.total_execution_time += execution_time

            logger.info(f"Step {step.step_id} completed in {execution_time:.2f}s")

        except Exception as e:
            # Failure
            metrics.failed_tasks += 1
            self._record_failure()
            logger.error(f"Step {step.step_id} failed: {e}")

        finally:
            # Always release resources
            if self.resource_manager:
                self.resource_manager.release_resources(step.step_id)

    def _find_worker_for_task(self, task_type: str) -> Optional[BaseWorker]:
        """Find an appropriate worker for a task type."""
        # Simple mapping - could be enhanced with worker capabilities
        worker_mapping = {
            "bubble.create": "bubble_worker",
            "bubble.list": "bubble_worker",
            "idea.create": "ideas_worker",
            "idea.list": "ideas_worker",
            "code.generate": "coding_worker",
            "desktop.task": "desktop_worker",
        }

        worker_name = worker_mapping.get(task_type)
        return self.workers.get(worker_name)

    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self.failure_count < self.circuit_breaker_threshold:
            return False

        # Check if timeout has passed
        if time.time() - self.last_failure_time > self.circuit_breaker_timeout:
            self.failure_count = 0  # Reset
            return False

        return True

    def _record_failure(self) -> None:
        """Record a failure for circuit breaker."""
        self.failure_count += 1
        self.last_failure_time = time.time()

    def get_workflow_status(self, workflow_id: str) -> Optional[ExecutionMetrics]:
        """Get status of a workflow execution."""
        return self.metrics.get(workflow_id)

    def get_resource_utilization(self) -> Dict[ResourceType, float]:
        """Get current resource utilization."""
        return self.resource_manager.get_utilization() if self.resource_manager else {}

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get overall execution statistics."""
        if not self.execution_history:
            return {}

        completion_times = [m.total_execution_time for m in self.execution_history if m.end_time]
        success_rates = [m.success_rate for m in self.execution_history]

        return {
            "total_workflows": len(self.execution_history),
            "avg_completion_time": statistics.mean(completion_times) if completion_times else 0,
            "avg_success_rate": statistics.mean(success_rates) if success_rates else 0,
            "total_tasks_executed": sum(m.total_tasks for m in self.execution_history),
            "total_tasks_completed": sum(m.completed_tasks for m in self.execution_history),
        }


# Global execution engine instance
_execution_engine: Optional[ExecutionEngine] = None


def get_execution_engine(workers: Optional[List[BaseWorker]] = None) -> ExecutionEngine:
    """Get or create the global execution engine instance."""
    global _execution_engine
    if _execution_engine is None and workers:
        _execution_engine = ExecutionEngine(workers)
    return _execution_engine


__all__ = [
    "ExecutionEngine",
    "WorkflowPlanner",
    "ResourceManager",
    "WorkflowStep",
    "WorkflowPlan",
    "ExecutionMetrics",
    "ResourceRequirements",
    "ResourceType",
    "ExecutionState",
    "get_execution_engine",
]