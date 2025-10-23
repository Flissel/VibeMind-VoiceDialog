"""
Test script for the multi-agent system
Demonstrates handoffs between agents
"""

import asyncio
from agent_orchestrator import get_orchestrator


async def test_agents():
    """Test the agent system"""
    print("=" * 60)
    print("VOICE DIALOG MULTI-AGENT SYSTEM - TEST")
    print("=" * 60)
    print()

    # Initialize orchestrator
    print("Initializing agent system...")
    orchestrator = await get_orchestrator()  # No API key for demo mode
    print()

    # Test cases
    test_inputs = [
        "Hello! What can you help me with?",
        "Take a screenshot of my screen",
        "Search for information about Python async programming",
        "Generate a function to calculate fibonacci numbers",
    ]

    print("Running test cases...")
    print()

    for i, test_input in enumerate(test_inputs, 1):
        print(f"\n{'=' * 60}")
        print(f"Test {i}: {test_input}")
        print('-' * 60)

        # Process input
        response = await orchestrator.process_user_input(test_input)

        print(response)
        print()

        # Wait a bit between tests
        await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

    # Shutdown
    await orchestrator.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(test_agents())
    except KeyboardInterrupt:
        print("\n[EXIT] Test interrupted")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
