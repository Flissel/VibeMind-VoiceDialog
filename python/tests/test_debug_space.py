"""Test advanced features on Debug information space."""
import asyncio
import sys

# Test 1: RAG Classifier
async def test_rag_classifier():
    print("\n" + "="*60)
    print("TEST 1: RAG Classifier")
    print("="*60)

    from swarm.orchestrator.rag_intent_classifier import get_rag_intent_classifier
    rag = get_rag_intent_classifier()

    test_inputs = [
        "Erstelle ein Whitepaper",
        "Fasse alle Ideen zusammen",
        "Analysiere welche Ideen zusammengehören",
        "Verlinke die Ideen sinnvoll",
        "Formatiere die Idee als Tabelle",
    ]

    for input_text in test_inputs:
        result = await rag.classify(input_text)
        print(f"\n'{input_text}'")
        print(f"  -> {result.event_type} ({result.confidence*100:.0f}%)")
        if result.payload:
            print(f"  -> Params: {result.payload}")


# Test 2: Event Router
def test_event_router():
    print("\n" + "="*60)
    print("TEST 2: Event Router")
    print("="*60)

    from swarm.event_team.event_router import get_event_router
    router = get_event_router()

    events = ['idea.whitepaper', 'idea.summarize', 'idea.expand',
              'idea.analyze_links', 'idea.format_table', 'bubble.update']

    all_ok = True
    for event in events:
        stream = router.get_stream(event)
        ok = stream == 'events:tasks:ideas'
        status = 'OK' if ok else 'WRONG!'
        print(f"  {event}: {stream} [{status}]")
        if not ok:
            all_ok = False

    return all_ok


# Test 3: Tool Execution (sync mode)
def test_tools_directly():
    print("\n" + "="*60)
    print("TEST 3: Direct Tool Execution (Sync Mode)")
    print("="*60)

    # First, set the current bubble to Debug information
    from tools.bubble_tools import enter_bubble, _current_bubble_db_id

    result = enter_bubble({"bubble_name": "Debug information"})
    print(f"\nEnter bubble: {result[:80]}...")

    # Test summarize
    print("\n--- Testing summarize_idea ---")
    try:
        from tools.summary_tools import summarize_idea
        result = summarize_idea({"idea_name": None, "style": "concise"})
        print(f"Result: {result[:200]}..." if len(result) > 200 else f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test analyze_links
    print("\n--- Testing analyze_and_suggest_links ---")
    try:
        from tools.idea_tools import analyze_and_suggest_links
        result = analyze_and_suggest_links({})
        print(f"Result: {result[:300]}..." if len(result) > 300 else f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


async def main():
    print("Testing Advanced Features on Debug Information Space")
    print("="*60)

    # Test 1: RAG Classifier
    await test_rag_classifier()

    # Test 2: Event Router
    router_ok = test_event_router()

    # Test 3: Tools (only if router is OK)
    if router_ok:
        test_tools_directly()
    else:
        print("\nSkipping tool tests - event router not configured correctly!")

    print("\n" + "="*60)
    print("TESTS COMPLETE")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
