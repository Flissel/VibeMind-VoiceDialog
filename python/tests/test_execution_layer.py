#!/usr/bin/env python3
"""
Test script for Execution Layer - Scalable Task Execution Infrastructure

Tests the workflow planning, resource management, and parallel processing capabilities.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from swarm.execution_layer import (
    ExecutionEngine, WorkflowPlanner, ResourceManager,
    WorkflowStep, ResourceRequirements, ResourceType,
    get_execution_engine
)
from swarm.workers.base_worker import BaseWorker, WorkerConfig
from swarm.navigation import SpaceType


class MockWorker(BaseWorker):
    """Mock worker for testing."""

    def __init__(self, name: str, supported_task_types: list):
        config = WorkerConfig(
            name=name,
            space_type=SpaceType.BUBBLE,
            description=f"Mock worker for {name}"
        )
        super().__init__(config)
        self.supported_task_types = supported_task_types
        self.execution_count = 0

    async def execute_task(self, task):
        """Mock task execution."""
        self.execution_count += 1
        await asyncio.sleep(0.1)  # Simulate work

        if task.task_type in self.supported_task_types:
            return f"Executed {task.task_type} successfully"
        else:
            raise Exception(f"Unsupported task type: {task.task_type}")


async def test_workflow_planning():
    """Test workflow planning with dependencies."""
    print("=== Testing Workflow Planning ===")

    planner = WorkflowPlanner()

    # Create workflow steps with dependencies
    steps = [
        WorkflowStep(
            step_id="create_bubble",
            task_type="bubble.create",
            payload={"title": "Test Bubble"},
            priority=3
        ),
        WorkflowStep(
            step_id="create_idea",
            task_type="idea.create",
            payload={"title": "Test Idea"},
            dependencies={"create_bubble"},  # Depends on bubble creation
            priority=2
        ),
        WorkflowStep(
            step_id="list_ideas",
            task_type="idea.list",
            payload={},
            dependencies={"create_idea"},  # Depends on idea creation
            priority=1
        )
    ]

    plan = planner.create_plan("test_workflow", steps)

    print(f"✅ Created plan with {len(plan.steps)} steps")
    print(f"   Execution order: {plan.execution_order}")
    print(f"   Estimated duration: {plan.estimated_duration:.1f}s")

    # Verify dependency ordering
    create_bubble_idx = plan.execution_order.index("create_bubble")
    create_idea_idx = plan.execution_order.index("create_idea")
    list_ideas_idx = plan.execution_order.index("list_ideas")

    assert create_bubble_idx < create_idea_idx, "Bubble creation should come before idea creation"
    assert create_idea_idx < list_ideas_idx, "Idea creation should come before listing"

    print("✅ Dependency ordering is correct")


async def test_resource_management():
    """Test resource allocation and management."""
    print("\n=== Testing Resource Management ===")

    # Initialize resource manager with limited resources
    total_resources = {
        ResourceType.CPU: 4.0,
        ResourceType.MEMORY: 2048.0,
        ResourceType.STORAGE: 10240.0
    }
    manager = ResourceManager(total_resources)

    # Test resource allocation
    req1 = ResourceRequirements(cpu_cores=2.0, memory_mb=1024.0)
    success1 = manager.allocate_resources("task1", req1)
    assert success1, "First allocation should succeed"
    print("✅ First resource allocation successful")

    # Check utilization
    utilization = manager.get_utilization()
    assert utilization[ResourceType.CPU] == 50.0, "CPU utilization should be 50%"
    assert utilization[ResourceType.MEMORY] == 50.0, "Memory utilization should be 50%"
    print(f"✅ Resource utilization: CPU={utilization[ResourceType.CPU]}%, Memory={utilization[ResourceType.MEMORY]}%")

    # Try to allocate more than available
    req2 = ResourceRequirements(cpu_cores=3.0, memory_mb=1024.0)  # Only 2 CPU cores left
    success2 = manager.allocate_resources("task2", req2)
    assert not success2, "Second allocation should fail due to insufficient CPU"
    print("✅ Resource over-allocation correctly prevented")

    # Release resources
    manager.release_resources("task1")
    utilization_after = manager.get_utilization()
    assert utilization_after[ResourceType.CPU] == 0.0, "CPU utilization should be 0% after release"
    print("✅ Resource release successful")


async def test_parallel_execution():
    """Test parallel workflow execution."""
    print("\n=== Testing Parallel Execution ===")

    # Create mock workers
    bubble_worker = MockWorker("bubble_worker", ["bubble.create", "bubble.list"])
    ideas_worker = MockWorker("ideas_worker", ["idea.create", "idea.list"])

    # Create execution engine
    engine = ExecutionEngine([bubble_worker, ideas_worker], max_concurrent_tasks=3)

    # Create workflow with parallel steps
    steps = [
        WorkflowStep(
            step_id="create_bubble_1",
            task_type="bubble.create",
            payload={"title": "Bubble 1"}
        ),
        WorkflowStep(
            step_id="create_bubble_2",
            task_type="bubble.create",
            payload={"title": "Bubble 2"}
        ),
        WorkflowStep(
            step_id="create_idea",
            task_type="idea.create",
            payload={"title": "Test Idea"},
            dependencies={"create_bubble_1"}  # Depends on first bubble
        )
    ]

    # Execute workflow
    metrics = await engine.execute_workflow("parallel_test", steps)

    print(f"✅ Workflow completed: {metrics.completed_tasks}/{metrics.total_tasks} tasks")
    print(".2f")
    print(".1%")

    assert metrics.completed_tasks == 3, "All tasks should complete"
    assert metrics.failed_tasks == 0, "No tasks should fail"
    assert metrics.success_rate == 1.0, "Success rate should be 100%"

    print("✅ Parallel execution successful")


async def test_dependency_management():
    """Test complex dependency management."""
    print("\n=== Testing Dependency Management ===")

    planner = WorkflowPlanner()

    # Create complex dependency graph
    steps = [
        WorkflowStep(step_id="A", task_type="task.A", payload={}),
        WorkflowStep(step_id="B", task_type="task.B", payload={}, dependencies={"A"}),
        WorkflowStep(step_id="C", task_type="task.C", payload={}, dependencies={"A"}),
        WorkflowStep(step_id="D", task_type="task.D", payload={}, dependencies={"B", "C"}),
        WorkflowStep(step_id="E", task_type="task.E", payload={}, dependencies={"D"}),
    ]

    plan = planner.create_plan("dependency_test", steps)

    # Verify topological ordering
    indices = {step: i for i, step in enumerate(plan.execution_order)}

    assert indices["A"] < indices["B"], "A should come before B"
    assert indices["A"] < indices["C"], "A should come before C"
    assert indices["B"] < indices["D"], "B should come before D"
    assert indices["C"] < indices["D"], "C should come before D"
    assert indices["D"] < indices["E"], "D should come before E"

    print("✅ Complex dependency graph correctly resolved")
    print(f"   Execution order: {' -> '.join(plan.execution_order)}")


async def test_error_handling():
    """Test error handling and recovery."""
    print("\n=== Testing Error Handling ===")

    # Create worker that sometimes fails
    class FailingWorker(MockWorker):
        async def execute_task(self, task):
            if task.task_type == "failing.task":
                raise Exception("Simulated failure")
            return await super().execute_task(task)

    failing_worker = FailingWorker("failing_worker", ["failing.task", "success.task"])

    engine = ExecutionEngine([failing_worker])

    # Create workflow with failing task
    steps = [
        WorkflowStep(step_id="success_1", task_type="success.task", payload={}),
        WorkflowStep(step_id="failure", task_type="failing.task", payload={}),
        WorkflowStep(step_id="success_2", task_type="success.task", payload={}),
    ]

    metrics = await engine.execute_workflow("error_test", steps)

    print(f"✅ Error handling test: {metrics.completed_tasks} completed, {metrics.failed_tasks} failed")
    print(".1%")

    assert metrics.completed_tasks == 2, "Two tasks should succeed"
    assert metrics.failed_tasks == 1, "One task should fail"
    assert metrics.success_rate == 2/3, "Success rate should be 66.7%"

    print("✅ Error handling and recovery working correctly")


async def test_resource_utilization():
    """Test resource utilization monitoring."""
    print("\n=== Testing Resource Utilization ===")

    # Create resource manager
    manager = ResourceManager({
        ResourceType.CPU: 8.0,
        ResourceType.MEMORY: 4096.0
    })

    # Allocate some resources
    req1 = ResourceRequirements(cpu_cores=2.0, memory_mb=1024.0)
    req2 = ResourceRequirements(cpu_cores=4.0, memory_mb=2048.0)

    manager.allocate_resources("task1", req1)
    manager.allocate_resources("task2", req2)

    utilization = manager.get_utilization()

    expected_cpu = (2.0 + 4.0) / 8.0 * 100  # 75%
    expected_memory = (1024.0 + 2048.0) / 4096.0 * 100  # 75%

    assert abs(utilization[ResourceType.CPU] - expected_cpu) < 0.1, f"CPU utilization should be {expected_cpu}%"
    assert abs(utilization[ResourceType.MEMORY] - expected_memory) < 0.1, f"Memory utilization should be {expected_memory}%"

    print(f"✅ Resource utilization: CPU={utilization[ResourceType.CPU]:.1f}%, Memory={utilization[ResourceType.MEMORY]:.1f}%")

    # Release and check
    manager.release_resources("task1")
    utilization_after = manager.get_utilization()

    expected_cpu_after = 4.0 / 8.0 * 100  # 50%
    expected_memory_after = 2048.0 / 4096.0 * 100  # 50%

    assert abs(utilization_after[ResourceType.CPU] - expected_cpu_after) < 0.1, "CPU utilization should be 50% after release"
    print("✅ Resource release correctly reflected in utilization")


async def main():
    """Run all execution layer tests."""
    print("🚀 Testing Execution Layer - Scalable Task Execution Infrastructure")
    print("=" * 75)

    try:
        await test_workflow_planning()
        await test_resource_management()
        await test_parallel_execution()
        await test_dependency_management()
        await test_error_handling()
        await test_resource_utilization()

        print("\n" + "=" * 75)
        print("🎉 All Execution Layer tests passed!")
        print("✅ Workflow planning with dependency resolution")
        print("✅ Resource management and allocation")
        print("✅ Parallel execution with concurrency control")
        print("✅ Complex dependency graph handling")
        print("✅ Error handling and recovery")
        print("✅ Resource utilization monitoring")
        print("\nThe Execution Layer is ready for production use!")

        return 0

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)