"""
Test the actual start_exploration tool function.
"""
import sys
import os
import asyncio

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8')

# Add python folder to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_start_exploration():
    """Test calling the start_exploration tool directly."""
    print("=" * 70)
    print("TESTING start_exploration TOOL")
    print("=" * 70)

    # Import the tool
    print("\n1. Importing start_exploration...")
    try:
        from swarm.tools.exploration_tools import start_exploration
        print("   ✓ Imported successfully")
    except ImportError as e:
        print(f"   ✗ Import failed: {e}")
        return

    # Check function signature
    print("\n2. Checking function signature...")
    import inspect
    sig = inspect.signature(start_exploration)
    print(f"   Parameters: {sig}")
    for name, param in sig.parameters.items():
        default = param.default if param.default != inspect.Parameter.empty else "required"
        print(f"     - {name}: {default}")

    # Get a bubble to explore from
    print("\n3. Getting a bubble to explore...")
    from data import IdeasRepository
    repo = IdeasRepository()
    ideas = repo.list(limit=10)
    bubbles = [i for i in ideas if not i.parent_id]

    if not bubbles:
        print("   ✗ No bubbles found, cannot test")
        return

    test_bubble = bubbles[0]
    print(f"   Using bubble: {test_bubble.title} (id: {test_bubble.id})")

    # Try to call start_exploration
    print("\n4. Calling start_exploration...")
    print(f"   Parameters:")
    print(f"     - bubble_id: {test_bubble.id}")
    print(f"     - depth: 2")
    print(f"     - mode: 'auto'")
    print(f"     - context: None")
    print()

    try:
        result = await start_exploration(
            bubble_id=test_bubble.id,
            depth=2,
            mode="auto",
            context=None
        )
        print("   ✓ Tool executed!")
        print(f"\n   Result:")
        if isinstance(result, dict):
            for key, value in result.items():
                if isinstance(value, str) and len(value) > 100:
                    value = value[:100] + "..."
                print(f"     {key}: {value}")
        else:
            print(f"     {result}")

    except Exception as e:
        print(f"   ✗ Execution error: {e}")
        import traceback
        traceback.print_exc()

    # Also test get_exploration_status
    print("\n5. Testing get_exploration_status...")
    try:
        from swarm.tools.exploration_tools import get_exploration_status
        status = await get_exploration_status()
        print("   ✓ Status retrieved!")
        if isinstance(status, dict):
            for key, value in status.items():
                print(f"     {key}: {value}")
        else:
            print(f"     {status}")
    except Exception as e:
        print(f"   ✗ Status error: {e}")


async def test_intent_to_tool_flow():
    """Test the intent classification → tool execution flow."""
    print("\n" + "=" * 70)
    print("TESTING INTENT → TOOL FLOW")
    print("=" * 70)

    # Test intent classification
    print("\n1. Testing intent classification...")
    try:
        from swarm.orchestrator.intent_classifier import IntentClassifier
        classifier = IntentClassifier()

        test_inputs = [
            "Finde tiefere Verbindungen",
            "Finde Verbindungen interaktiv",
            "Erkunde Richtung Marketing",
            "Stopp Exploration",
            "Ja behalten",
            "Nein ablehnen",
        ]

        for text in test_inputs:
            # Note: This would normally call the LLM, which we can't do in a quick test
            # So we'll just show what SHOULD happen
            print(f"\n   '{text}'")

            # Check which exploration intents exist
            from swarm.orchestrator.intent_classifier import CLASSIFIER_PROMPT_TEMPLATE
            exploration_keywords = {
                "tiefere Verbindungen": "idea.explore.start",
                "interaktiv": "idea.explore.start (mode=interactive)",
                "Erkunde Richtung": "idea.explore.direction",
                "Stopp Exploration": "idea.explore.stop",
                "behalten": "idea.explore.accept",
                "ablehnen": "idea.explore.reject",
            }

            for kw, intent in exploration_keywords.items():
                if kw.lower() in text.lower():
                    print(f"   → Expected intent: {intent}")
                    break

    except Exception as e:
        print(f"   ✗ Classification test failed: {e}")

    # Check IdeasAgent mapping
    print("\n2. Checking IdeasAgent tool mapping...")
    try:
        from swarm.backend_agents.ideas_agent import IdeasAgent
        agent = IdeasAgent()

        exploration_events = [
            "idea.explore.start",
            "idea.explore.stop",
            "idea.explore.accept",
            "idea.explore.reject",
            "idea.explore.depth",
        ]

        for evt in exploration_events:
            if evt in agent.EVENT_TO_TOOL:
                tool = agent.EVENT_TO_TOOL[evt]
                print(f"   ✓ {evt} → {tool}")
            else:
                print(f"   ✗ {evt} → NOT MAPPED (needs integration)")

    except Exception as e:
        print(f"   ✗ Agent check failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_start_exploration())
    asyncio.run(test_intent_to_tool_flow())
