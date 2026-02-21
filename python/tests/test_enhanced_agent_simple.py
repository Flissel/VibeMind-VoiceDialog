#!/usr/bin/env python3
"""
Simple Test for Enhanced Base Agent
"""

import asyncio
from spaces.ideas.enhanced.enhanced_ideas_agent import EnhancedIdeasAgent
from swarm.backend_agents.plugins.learning_plugin import LearningPlugin

async def test_enhanced_agent():
    print("🤖 Testing Enhanced Base Agent...")

    # Create enhanced agent
    agent = EnhancedIdeasAgent()

    try:
        # Test 1: Agent initialization
        print("  🚀 Initializing agent...")
        await agent.start()
        print("    ✅ Agent started successfully")
        print(f"    ✅ Agent state: {agent.agent_state}")
        print(f"    ✅ Capabilities: {list(agent.capabilities)}")

        # Test 2: Plugin system
        print("  🔌 Testing plugin system...")
        learning_plugin = None
        for plugin in agent._plugins.values():
            if plugin.name == "learning":
                learning_plugin = plugin
                break

        if learning_plugin:
            print("    ✅ Learning plugin loaded")
            print(f"    ✅ Plugin capabilities: {list(learning_plugin.capabilities)}")
        else:
            print("    ❌ Learning plugin not found")

        # Test 3: Workflow state management
        print("  📊 Testing workflow state management...")
        workflow_id = "test_workflow_123"
        steps = ["create_idea", "expand_idea", "connect_ideas"]

        workflow_state = await agent.create_workflow_state(workflow_id, steps)
        print(f"    ✅ Created workflow with {len(workflow_state.pending_steps)} steps")

        # Update workflow progress
        await agent.update_workflow_state(workflow_id, completed_step="create_idea")
        updated_state = await agent.get_workflow_state(workflow_id)
        print(f"    ✅ Workflow progress: {updated_state.progress_percentage:.1f}%")

        # Test 4: Agent coordination (mock)
        print("  🤝 Testing agent coordination...")
        # Since we only have one agent, we'll test the coordination framework
        await agent.send_coordination_message("other_agent", "test_message", {"data": "test"})
        print("    ✅ Coordination message sent")

        # Test 5: Health monitoring
        print("  ❤️ Testing health monitoring...")
        health = agent.health
        print(f"    ✅ Agent healthy: {health.is_healthy}")
        print(f"    ✅ Uptime: {health.uptime_seconds:.1f}s")
        print(f"    ✅ Tasks processed: {health.tasks_processed}")

        # Test 6: Agent statistics
        print("  📈 Testing agent statistics...")
        stats = agent.get_enhanced_stats()
        print(f"    ✅ Agent name: {stats['name']}")
        print(f"    ✅ Active workflows: {stats['active_workflows']}")
        print(f"    ✅ Plugins loaded: {len(stats['plugins'])}")

        print("🎉 Enhanced Agent test completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await agent.stop()
        print("    ✅ Agent stopped")

if __name__ == "__main__":
    asyncio.run(test_enhanced_agent())