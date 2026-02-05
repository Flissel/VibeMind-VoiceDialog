#!/usr/bin/env python3
"""
Test Sync Mode Tool Execution
Tests if tools work in sync mode (without Redis).
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

# Force sync mode
os.environ["FORCE_SYNC_MODE"] = "true"

def test_sync_orchestrator():
    """Test orchestrator in sync mode."""
    print("Testing orchestrator in sync mode...")

    try:
        from swarm.orchestrator.intent_orchestrator import get_orchestrator
        orchestrator = get_orchestrator()

        # Test simple commands
        test_commands = [
            "liste meine bubbles",
            "erstelle eine neue idee test",
            "liste ideen"
        ]

        for cmd in test_commands:
            print(f"\nTesting: '{cmd}'")
            result = orchestrator.process_intent_sync(cmd)
            print(f"  Result: {result.response_hint}")
            print(f"  Event: {result.event_type}")
            print(f"  Conversational: {result.is_conversational}")

        return True

    except Exception as e:
        print(f"Sync orchestrator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_complex_command():
    """Test complex command that should trigger multiple steps."""
    print("\nTesting complex command...")

    try:
        from swarm.orchestrator.intent_orchestrator import get_orchestrator
        orchestrator = get_orchestrator()

        # Test complex command
        cmd = "formatiere den aktuellen space so dass die ideen sinnvoll verlinkt werden"
        print(f"Testing complex: '{cmd}'")

        result = orchestrator.process_intent_sync(cmd)
        print(f"  Result: {result.response_hint}")
        print(f"  Event: {result.event_type}")
        print(f"  Conversational: {result.is_conversational}")

        return True

    except Exception as e:
        print(f"Complex command test failed: {e}")
        return False

def main():
    """Run sync mode tests."""
    print("=" * 60)
    print("SYNC MODE TOOL EXECUTION TESTS")
    print("=" * 60)

    tests = [
        ("Sync Orchestrator", test_sync_orchestrator),
        ("Complex Command", test_complex_command),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            result = test_func()
            if result:
                passed += 1
                print("  PASSED")
            else:
                print("  FAILED")
        except Exception as e:
            print(f"  CRASHED: {e}")

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed}/{total} tests passed")

    if passed == total:
        print("All sync mode tests PASSED!")
        return True
    else:
        print("Some sync mode tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)