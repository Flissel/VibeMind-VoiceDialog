"""Test terminal reasoning output with colors."""

import asyncio
import sys
sys.path.insert(0, '.')

from swarm.reasoning.reasoning_logger import get_reasoning_logger


async def test():
    print("=== Testing Terminal Reasoning Output ===")
    print()

    rl = get_reasoning_logger()
    ctx = rl.start_job('test-123', user_input='Erstelle eine Bubble')

    # Simulate a full execution flow
    await rl.log_intent_reasoning('test-123', 'bubble.create', 0.95, 'User will Bubble erstellen')
    await rl.log_dependency_reasoning('test-123', [{'event_type': 'bubble.create'}], 'Single step')
    await rl.log_tool_start('test-123', 'create_bubble', {'title': 'Marketing'})
    await rl.log_tool_complete('test-123', 'create_bubble', 'OK', latency_ms=245)
    await rl.log_result_reasoning('test-123', 'Bubble Marketing erstellt', 'Ich habe die Bubble erstellt.')

    rl.end_job('test-123')

    print()
    print("=== Test Complete ===")


if __name__ == '__main__':
    asyncio.run(test())
