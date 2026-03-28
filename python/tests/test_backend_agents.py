#!/usr/bin/env python3
"""
Test script to check if backend agents start correctly.
"""

import asyncio
import sys
import os

# Add current directory and python subdirectory to path
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

async def test_backend_agents():
    """Test if backend agents can be created and started."""
    try:
        print("Testing backend agents...")

        # Test imports
        print("1. Testing imports...")
        from swarm.backend_agents import get_ideas_agent, get_desktop_agent, get_coding_agent
        print("   [OK] Imports successful")

        # Test agent creation
        print("2. Testing agent creation...")
        ideas_agent = get_ideas_agent()
        desktop_agent = get_desktop_agent()
        coding_agent = get_coding_agent()
        print("   [OK] Agents created")

        # Test agent start
        print("3. Testing agent start...")
        await ideas_agent.start()
        await desktop_agent.start()
        await coding_agent.start()
        print("   [OK] Agents started")

        # Test event bus
        print("4. Testing event bus...")
        from swarm.event_bus import get_event_bus
        event_bus = get_event_bus()
        await event_bus.start_listeners()
        print("   [OK] Event bus started")

        print("\n[SUCCESS] All backend agents working correctly!")

        # Cleanup
        await ideas_agent.stop()
        await desktop_agent.stop()
        await coding_agent.stop()
        await event_bus.close()

    except Exception as e:
        print(f"\n[ERROR] Backend agents failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_backend_agents())