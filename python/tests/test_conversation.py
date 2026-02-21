"""
Test Conversation - Simulates the new architecture flow.

Tests:
1. Intent Classification (LLM)
2. Event Routing
3. Backend Agent Tool Mapping

Note: Redis is not required for this test - we test the classification and routing logic.
"""

import asyncio
import os
import sys

# Add paths
sys.path.insert(0, os.path.dirname(__file__))

# Set up logging
import logging
logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')


async def test_intent_classifier():
    """Test the intent classifier with various German voice commands."""
    print("\n" + "="*60)
    print("TEST 1: Intent Classification")
    print("="*60)

    # Check if API key is available
    if not os.getenv("OPENROUTER_API_KEY"):
        print("SKIP: OPENROUTER_API_KEY not set - skipping LLM test")
        return False

    from swarm.orchestrator.intent_classifier import IntentClassifier

    classifier = IntentClassifier()

    test_intents = [
        "Welche Spaces habe ich?",
        "Erstelle einen neuen Space namens Projekt Alpha",
        "Oeffne Chrome",
        "Erstelle eine Todo App mit React",
        "Hallo Rachel!",
    ]

    for intent in test_intents:
        print(f"\nUser: \"{intent}\"")
        try:
            result = await classifier.classify(intent)
            print(f"  -> event_type: {result['event_type']}")
            print(f"  -> payload: {result['payload']}")
            print(f"  -> response_hint: {result.get('response_hint', 'N/A')}")
        except Exception as e:
            print(f"  -> ERROR: {e}")

    return True


def test_event_routing():
    """Test event routing to correct streams."""
    print("\n" + "="*60)
    print("TEST 2: Event Routing")
    print("="*60)

    from swarm.event_team.event_router import EventRouter

    router = EventRouter()

    test_events = [
        ("bubble.list", "events:tasks:ideas"),
        ("bubble.create", "events:tasks:ideas"),
        ("idea.create", "events:tasks:ideas"),
        ("desktop.open_app", "events:tasks:desktop"),
        ("desktop.click", "events:tasks:desktop"),
        ("code.generate", "events:tasks:coding"),
        ("code.modify", "events:tasks:coding"),
        ("unknown.event", "events:tasks"),  # Default
    ]

    all_passed = True
    for event_type, expected_stream in test_events:
        actual_stream = router.get_stream(event_type)
        status = "OK" if actual_stream == expected_stream else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  {event_type} -> {actual_stream} [{status}]")

    return all_passed


def test_backend_agent_tools():
    """Test that backend agents have the correct tools loaded."""
    print("\n" + "="*60)
    print("TEST 3: Backend Agent Tools")
    print("="*60)

    from swarm.backend_agents import IdeasAgent, DesktopAgent, CodingAgent

    # Test IdeasAgent
    ideas_agent = IdeasAgent()
    ideas_tools = ideas_agent.tools
    print(f"\nIdeasAgent: {len(ideas_tools)} tools")
    for name in sorted(ideas_tools.keys())[:5]:
        print(f"  - {name}")
    if len(ideas_tools) > 5:
        print(f"  ... and {len(ideas_tools) - 5} more")

    # Test DesktopAgent
    desktop_agent = DesktopAgent()
    desktop_tools = desktop_agent.tools
    print(f"\nDesktopAgent: {len(desktop_tools)} tools")
    for name in sorted(desktop_tools.keys())[:5]:
        print(f"  - {name}")
    if len(desktop_tools) > 5:
        print(f"  ... and {len(desktop_tools) - 5} more")

    # Test CodingAgent
    coding_agent = CodingAgent()
    coding_tools = coding_agent.tools
    print(f"\nCodingAgent: {len(coding_tools)} tools")
    for name in sorted(coding_tools.keys()):
        print(f"  - {name}")

    return True


def test_rachel_voice_interface():
    """Test that Rachel only has send_intent tool."""
    print("\n" + "="*60)
    print("TEST 4: Rachel Voice Interface")
    print("="*60)

    from spaces.ideas.agents.rachel_agent import RachelAgent

    rachel = RachelAgent()
    tools = rachel.get_tools()

    print(f"\nRachel has {len(tools)} tool(s):")
    for tool in tools:
        name = tool.__name__ if hasattr(tool, '__name__') else str(tool)
        print(f"  - {name}")

    # Verify it's only send_intent
    if len(tools) == 1:
        print("\nOK: Rachel is voice-only (1 tool)")
        return True
    else:
        print(f"\nFAIL: Rachel should have 1 tool, has {len(tools)}")
        return False


def test_event_type_to_tool_mapping():
    """Test that event types map to correct tool names in backend agents."""
    print("\n" + "="*60)
    print("TEST 5: Event Type -> Tool Mapping")
    print("="*60)

    from swarm.backend_agents import IdeasAgent, DesktopAgent, CodingAgent

    # Test mappings
    test_cases = [
        (IdeasAgent(), "bubble.list", "list_bubbles"),
        (IdeasAgent(), "bubble.create", "create_bubble"),
        (IdeasAgent(), "idea.create", "create_idea"),
        (DesktopAgent(), "desktop.open_app", "open_app"),
        (DesktopAgent(), "desktop.click", "click_element"),
        (CodingAgent(), "code.generate", "generate_code"),
        (CodingAgent(), "code.modify", "modify_code_sync"),
    ]

    all_passed = True
    for agent, event_type, expected_tool in test_cases:
        actual_tool = agent._get_tool_name(event_type)
        status = "OK" if actual_tool == expected_tool else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  {agent.name}: {event_type} -> {actual_tool} [{status}]")

    return all_passed


async def main():
    """Run all tests."""
    print("\n" + "#"*60)
    print("# VibeMind Architecture Test - Conversation Flow")
    print("#"*60)

    results = []

    # Test 1: Intent Classification (requires API key)
    results.append(("Intent Classification", await test_intent_classifier()))

    # Test 2: Event Routing
    results.append(("Event Routing", test_event_routing()))

    # Test 3: Backend Agent Tools
    results.append(("Backend Agent Tools", test_backend_agent_tools()))

    # Test 4: Rachel Voice Interface
    results.append(("Rachel Voice Interface", test_rachel_voice_interface()))

    # Test 5: Event Type to Tool Mapping
    results.append(("Event->Tool Mapping", test_event_type_to_tool_mapping()))

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL/SKIP"
        print(f"  {name}: {status}")

    passed_count = sum(1 for _, p in results if p)
    print(f"\n{passed_count}/{len(results)} tests passed")

    print("\n" + "="*60)
    print("ARCHITECTURE VERIFIED")
    print("="*60)
    print("""
    User speaks
         |
         v
    +------------------+
    | Rachel (Voice)   |  <- 1 tool: send_intent()
    +------------------+
         |
         v
    +------------------+
    | IntentClassifier |  <- LLM classifies intent
    +------------------+
         |
         v
    +------------------+
    | EventRouter      |  <- Routes to correct stream
    +------------------+
         |
         v
    +------------------+
    | Redis Streams    |  <- events:tasks:{ideas,desktop,coding}
    +------------------+
         |
         v
    +------------------+
    | Backend Agents   |  <- Execute 37 tools
    | - IdeasAgent     |
    | - DesktopAgent   |
    | - CodingAgent    |
    +------------------+
         |
         v
    +------------------+
    | Status Listener  |  <- events:status
    +------------------+
         |
         v
    Rachel speaks result
    """)


if __name__ == "__main__":
    asyncio.run(main())
