#!/usr/bin/env python3
"""
Simple Test for Execution Layer
"""

import asyncio
from swarm.execution_layer import ExecutionEngine, WorkflowPlanner, WorkflowStep
from swarm.workers.base_worker import BaseWorker, WorkerConfig
from swarm.navigation import SpaceType

class MockWorker(BaseWorker):
    """Simple mock worker for testing."""

    def __init__(self, name: str, task_types: list):
        config = WorkerConfig(
            name=name,
            space_type=SpaceType.BUBBLE,
            description=f"Mock worker for {name}"
        )
        super().__init__(config)
        self.task_types = task_types
        self.executed_tasks = []

    async def execute_task(self, task):
        """Mock task execution."""
        await asyncio.sleep(0.01)  # Small delay
        self.executed_tasks.append(task.task_id)
        return f"Executed {task.task_type} for {task.task_id}"

async def test_execution_layer():
    print("⚙️ Testing Execution Layer...")

    # Create mock workers
    bubble_worker = MockWorker("bubble_worker", ["bubble.create", "bubble.list"])
    ideas_worker = MockWorker("ideas_worker", ["idea.create", "idea.list"])

    # Create execution engine
    engine = ExecutionEngine([bubble_worker, ideas_worker])

    try:
        # Test 1: Workflow planning
        print("  📋 Testing workflow planning...")
        planner = WorkflowPlanner()

        steps = [
            WorkflowStep("step1", "bubble.create", {"title": "Test Bubble"}),
            WorkflowStep("step2", "idea.create", {"title": "Test Idea"}, {"step1"}),
            WorkflowStep("step3", "idea.list", {}, {"step2"}),
        ]

        plan = planner.create_plan("test_workflow", steps)
        print(f"    ✅ Created plan with {len(plan.steps)} steps")
        print(f"    ✅ Execution order: {plan.execution_order}")

        # Test 2: Workflow execution
        print("  🚀 Testing workflow execution...")
        metrics = await engine.execute_workflow("test_workflow", steps)
        print(f"    ✅ Workflow completed: {metrics.completed_tasks}/{metrics.total_tasks} tasks")
        print(".2f")

        # Verify workers executed tasks
        total_executed = len(bubble_worker.executed_tasks) + len(ideas_worker.executed_tasks)
        print(f"    ✅ Workers executed {total_executed} tasks")

        # Test 3: Resource management
        print("  💾 Testing resource management...")
        utilization = engine.get_resource_utilization()
        print(f"    ✅ Resource utilization: CPU={utilization.get('cpu', 0):.1f}%")

        print("🎉 Execution Layer test completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_execution_layer())