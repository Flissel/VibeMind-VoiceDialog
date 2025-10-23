"""Test visual feedback through DesktopAgent"""
import asyncio
from agent_orchestrator import AgentOrchestrator
from tools.moire_service import MoireTrackerService

async def test_visual_feedback():
    print("\n=== Testing Visual Feedback via DesktopAgent ===\n")

    # Start MoireTracker service
    service = MoireTrackerService()
    service.start()

    orchestrator = AgentOrchestrator(api_key=None)
    await orchestrator.initialize()

    desktop_agent = orchestrator.desktop_agent

    if not desktop_agent.moire_connected:
        print("[FAIL] Desktop agent not connected to MoireTracker")
        return

    print("[OK] Desktop agent connected\n")

    # Test 1: Enable visual feedback
    print("1. Enabling visual feedback...")
    await desktop_agent.set_visual_feedback(True)
    print("   >>> Overlay should be VISIBLE - check your screen <<<")
    await asyncio.sleep(3)

    # Test 2: Disable visual feedback
    print("\n2. Disabling visual feedback...")
    await desktop_agent.set_visual_feedback(False)
    print("   >>> Overlay should be HIDDEN - check your screen <<<")
    await asyncio.sleep(2)

    # Test 3: Enable again
    print("\n3. Enabling visual feedback again...")
    await desktop_agent.set_visual_feedback(True)
    print("   >>> Overlay should be VISIBLE again - check your screen <<<")
    await asyncio.sleep(3)

    # Cleanup
    print("\n4. Cleaning up...")
    await desktop_agent.set_visual_feedback(False)

    await orchestrator.shutdown()
    service.stop()

    print("\n=== Test Complete ===")
    print("Visual feedback system is working correctly!")

if __name__ == "__main__":
    asyncio.run(test_visual_feedback())
