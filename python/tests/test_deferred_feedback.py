"""
Test Deferred Feedback - Verifies the async feedback flow.

Tests:
1. NotificationQueue: Add and retrieve notifications
2. Rachel: Check queue before processing
3. StatusListener: Push to queue on task completion
4. End-to-end: Simulate async task completion and deferred feedback
"""

import asyncio
import os
import sys

# Add paths
sys.path.insert(0, os.path.dirname(__file__))

# Set up logging
import logging
logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')


def test_notification_queue():
    """Test NotificationQueue basic operations."""
    print("\n" + "=" * 60)
    print("TEST 1: NotificationQueue")
    print("=" * 60)

    from swarm.orchestrator.notification_queue import NotificationQueue

    queue = NotificationQueue()

    # Test add
    queue.add_notification(
        job_id="job-123",
        event_type="bubble.create",
        result="Space 'Projekt Alpha' wurde erstellt"
    )
    queue.add_notification(
        job_id="job-456",
        event_type="code.generate",
        result="Todo App generiert, Preview bereit"
    )

    print(f"  Pending count: {queue.count()}")
    assert queue.count() == 2, "Should have 2 notifications"

    # Test has_pending
    assert queue.has_pending() == True, "Should have pending"

    # Test get_and_clear
    notifications = queue.get_and_clear()
    print(f"  Retrieved: {len(notifications)} notifications")
    assert len(notifications) == 2, "Should retrieve 2"

    # Test queue is now empty
    assert queue.count() == 0, "Queue should be empty after get_and_clear"
    assert queue.has_pending() == False, "Should have no pending"

    print("  OK: NotificationQueue works correctly")
    return True


def test_notification_formatting():
    """Test notification context formatting."""
    print("\n" + "=" * 60)
    print("TEST 2: Notification Formatting")
    print("=" * 60)

    from swarm.orchestrator.notification_queue import NotificationQueue

    queue = NotificationQueue()
    queue.add_notification("job-1", "bubble.create", "Space erstellt")
    queue.add_notification("job-2", "code.generate", "App generiert")

    # Test format_for_context
    context = queue.format_for_context()
    print(f"  Context: {context[:100]}...")

    assert "Bubble Create" in context, "Should contain readable event type"
    assert "Space erstellt" in context, "Should contain result"

    print("  OK: Formatting works correctly")
    return True


def test_rachel_notification_check():
    """Test that Rachel checks NotificationQueue."""
    print("\n" + "=" * 60)
    print("TEST 3: Rachel Notification Check")
    print("=" * 60)

    from swarm.orchestrator.notification_queue import NotificationQueue
    from swarm.user_agents.rachel import RachelAgent

    # Create queue with pending notification
    queue = NotificationQueue()
    queue.add_notification("job-123", "bubble.list", "Du hast 5 Spaces")

    # Create Rachel with queue
    rachel = RachelAgent(notification_queue=queue)

    # Verify Rachel has the queue
    assert rachel.notification_queue is not None, "Rachel should have queue"
    assert rachel.notification_queue.has_pending(), "Queue should have pending"

    print("  Rachel has NotificationQueue: OK")
    print(f"  Pending notifications: {rachel.notification_queue.count()}")

    # Test format_notifications
    notifications = queue.get_and_clear()
    formatted = rachel._format_notifications(notifications)
    print(f"  Formatted: {formatted}")

    assert "Bubble List" in formatted, "Should format event type"

    print("  OK: Rachel notification check works")
    return True


def test_status_listener_queue():
    """Test that StatusListener pushes to NotificationQueue."""
    print("\n" + "=" * 60)
    print("TEST 4: StatusListener -> NotificationQueue")
    print("=" * 60)

    from swarm.orchestrator.notification_queue import NotificationQueue
    from swarm.listeners.status_listener import StatusListener

    queue = NotificationQueue()
    listener = StatusListener(notification_queue=queue)

    # Simulate task completion
    listener._queue_notification(
        job_id="job-789",
        event_type="idea.create",
        result="Idee gespeichert"
    )

    print(f"  Queue count after status: {queue.count()}")
    assert queue.count() == 1, "Should have 1 notification"

    notifications = queue.get_and_clear()
    assert notifications[0].event_type == "idea.create"
    assert "gespeichert" in notifications[0].result

    print("  OK: StatusListener pushes to queue correctly")
    return True


async def test_end_to_end_flow():
    """Test complete async feedback flow."""
    print("\n" + "=" * 60)
    print("TEST 5: End-to-End Async Flow")
    print("=" * 60)

    from swarm.orchestrator.notification_queue import NotificationQueue
    from swarm.listeners.status_listener import StatusListener
    from swarm.user_agents.rachel import RachelAgent
    from swarm.event_buffer import InputEvent

    # 1. Create shared queue
    queue = NotificationQueue()
    print("  1. Created shared NotificationQueue")

    # 2. Create StatusListener
    listener = StatusListener(notification_queue=queue)
    print("  2. Created StatusListener with queue")

    # 3. Create Rachel
    rachel = RachelAgent(notification_queue=queue)
    print("  3. Created Rachel with queue")

    # 4. Simulate: User sends request, gets response_hint
    print("\n  --- Simulating async task ---")
    print("  User: 'Erstelle einen Space namens Test'")
    print("  Rachel: 'Ich erstelle den Space...' (response_hint)")

    # 5. Backend completes task, pushes to queue
    listener._queue_notification(
        job_id="job-async-1",
        event_type="bubble.create",
        result="Space 'Test' wurde erfolgreich erstellt"
    )
    print("  Backend: Task completed -> notification queued")

    # 6. User says something else, Rachel checks queue
    print("\n  --- Next user input ---")
    print("  User: 'Hallo'")

    # Check that queue has pending
    assert queue.has_pending(), "Queue should have pending notification"
    print(f"  Queue has pending: {queue.count()} notification(s)")

    # Get and format notifications (like Rachel would do)
    notifications = queue.get_and_clear()
    context = rachel._format_notifications(notifications)
    print(f"  Context injected: [{context}]")

    # Verify the notification was retrieved
    assert len(notifications) == 1
    assert notifications[0].event_type == "bubble.create"
    assert "Test" in notifications[0].result

    print("\n  OK: End-to-end async flow works correctly!")
    return True


async def main():
    """Run all tests."""
    print("\n" + "#" * 60)
    print("# VibeMind Phase 2 - Deferred Feedback Test")
    print("#" * 60)

    results = []

    # Test 1: NotificationQueue
    results.append(("NotificationQueue", test_notification_queue()))

    # Test 2: Formatting
    results.append(("Notification Formatting", test_notification_formatting()))

    # Test 3: Rachel check
    results.append(("Rachel Notification Check", test_rachel_notification_check()))

    # Test 4: StatusListener
    results.append(("StatusListener -> Queue", test_status_listener_queue()))

    # Test 5: End-to-end
    results.append(("End-to-End Flow", await test_end_to_end_flow()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    passed_count = sum(1 for _, p in results if p)
    print(f"\n{passed_count}/{len(results)} tests passed")

    print("\n" + "=" * 60)
    print("DEFERRED FEEDBACK ARCHITECTURE")
    print("=" * 60)
    print("""
    User: "Erstelle Code fuer eine App"
         |
         v
    Rachel.send_intent() -> Orchestrator -> Redis
         |
         v
    Rachel: "Ich starte die Generierung..."
         |
         v
    [CodingAgent arbeitet im Hintergrund]
         |
         v
    CodingAgent fertig -> StatusListener
         |
         v
    StatusListener -> NotificationQueue
         |
         v
    User sagt irgendwas
         |
         v
    Rachel.process_input() checks NotificationQueue
         |
         v
    Rachel: "Uebrigens, die App ist fertig! [result]"
    """)


if __name__ == "__main__":
    asyncio.run(main())
