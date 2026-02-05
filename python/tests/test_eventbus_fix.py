"""
Test script for EventBus fix and debugging system
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_event_bus():
    """Test EventBus event loop handling."""
    print("=" * 60)
    print("Test 1: EventBus Event Loop Handling")
    print("=" * 60)

    async def _test():
        from swarm.event_bus import get_event_bus, force_reset_event_bus

        # Reset first
        force_reset_event_bus()

        bus = get_event_bus()
        print(f"Redis URL: {bus.redis_url}")

        try:
            r = await bus._get_redis()
            pong = await r.ping()
            print(f"Redis ping: {pong}")
            print(f"Event loop tracked: {bus._redis_loop is not None}")

            # Test reconnect detection
            current_loop = asyncio.get_running_loop()
            print(f"Loop match: {bus._redis_loop == current_loop}")

            await bus.close()
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False

    try:
        result = asyncio.run(_test())
        if result:
            print("[PASS] EventBus test")
        else:
            print("[FAIL] EventBus test")
        return result
    except Exception as e:
        print(f"[FAIL] EventBus test: {e}")
        return False


def test_agent_execution_logger():
    """Test AgentExecutionLogger."""
    print()
    print("=" * 60)
    print("Test 2: AgentExecutionLogger")
    print("=" * 60)

    try:
        from swarm.debugging import get_agent_execution_logger

        logger = get_agent_execution_logger()
        print(f"Logs dir: {logger.logs_dir}")

        # Test logging
        logger.log_event_received(
            agent_name="TestAgent",
            job_id="test-123",
            event_type="test.event",
            payload={"test": "data"}
        )

        logger.log_tool_started(
            agent_name="TestAgent",
            job_id="test-123",
            original_event="test.event",
            tool_name="test_tool",
            params={"param1": "value1"}
        )

        logger.log_tool_completed(
            agent_name="TestAgent",
            job_id="test-123",
            original_event="test.event",
            tool_name="test_tool",
            result="Success!"
        )

        # Check logs
        logs = logger.get_recent_logs(limit=10)
        print(f"Recent logs count: {len(logs)}")

        print("[PASS] AgentExecutionLogger test")
        return True
    except Exception as e:
        print(f"[FAIL] AgentExecutionLogger test: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_post_session_analyzer():
    """Test PostSessionAnalyzer."""
    print()
    print("=" * 60)
    print("Test 3: PostSessionAnalyzer")
    print("=" * 60)

    try:
        from swarm.debugging import SessionData, run_all_detectors
        from datetime import datetime, timedelta

        # Create mock session data
        session_data = SessionData(
            session_id="test-session",
            start_time=datetime.utcnow() - timedelta(minutes=5),
            end_time=datetime.utcnow(),
            messages=[
                {"role": "user", "content": "Verlinke die Ideen"},
                {"role": "assistant", "content": "Ich gehe in den Space..."},
                {"role": "user", "content": "Nein, verlinke sie!"},
            ],
            intent_logs=[],
            tool_logs=[],
            agent_execution_logs=[
                {"event_type": "error", "agent_name": "IdeasAgent", "tool_name": "list_ideas", "error": "Test error"}
            ],
            errors=["Test error"],
        )

        # Run detectors
        issues = run_all_detectors(session_data)
        print(f"Issues detected: {len(issues)}")
        for issue in issues:
            print(f"  - {issue.title} ({issue.severity.value})")

        print("[PASS] PostSessionAnalyzer test")
        return True
    except Exception as e:
        print(f"[FAIL] PostSessionAnalyzer test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    results = []

    results.append(("EventBus", test_event_bus()))
    results.append(("AgentExecutionLogger", test_agent_execution_logger()))
    results.append(("PostSessionAnalyzer", test_post_session_analyzer()))

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    passed = 0
    for name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status}: {name}")
        if success:
            passed += 1

    print(f"\nPassed: {passed}/{len(results)} tests")
    return passed == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
