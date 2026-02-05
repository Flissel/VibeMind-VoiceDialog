"""Test system monitoring functionality."""
import sys
sys.path.insert(0, '.')

import time


def test_monitor():
    """Test the system status monitor."""
    print("=== Testing System Status Monitor ===")
    print()

    from swarm.monitoring.system_status import get_status_monitor
    monitor = get_status_monitor()

    # Start some test operations
    print("Starting test operations...")

    op1 = monitor.start_operation("llm_call", "RAG classify: test input 1")
    op2 = monitor.start_operation("tool_exec", "bubble.list")

    # Simulate some work
    time.sleep(0.5)

    # Complete one
    monitor.complete_operation(op2, success=True)

    time.sleep(0.3)

    # Complete the other
    monitor.complete_operation(op1, success=True)

    # Add a failed one
    op3 = monitor.start_operation("llm_call", "RAG classify: failing test")
    time.sleep(0.2)
    monitor.complete_operation(op3, success=False, error="Test error")

    print()
    print("=== Status Summary ===")
    monitor.print_status_summary()

    print()
    print("=== Status Dict ===")
    import json
    status = monitor.get_status()
    print(json.dumps(status, indent=2, default=str))


def test_tools():
    """Test the status tools."""
    print()
    print("=== Testing Status Tools ===")
    print()

    from tools.system_status_tools import get_system_status, check_stuck_operations

    result = get_system_status()
    print("get_system_status():")
    print(result)
    print()

    result = check_stuck_operations()
    print("check_stuck_operations():")
    print(result)


def test_orchestrator_integration():
    """Test that monitoring is integrated into orchestrator."""
    print()
    print("=== Testing Orchestrator Integration ===")
    print()

    from swarm.orchestrator.intent_orchestrator import IntentOrchestrator

    orch = IntentOrchestrator()

    # Check system.status tool is registered
    if "system.status" in orch._tool_executors:
        print("[OK] system.status tool registered")
    else:
        print("[FAIL] system.status tool NOT registered")

    # Execute it
    executor = orch._tool_executors.get("system.status")
    if executor:
        result = executor({})
        print("system.status result:")
        print(result)


if __name__ == "__main__":
    test_monitor()
    test_tools()
    test_orchestrator_integration()
    print()
    print("=== All tests complete ===")
