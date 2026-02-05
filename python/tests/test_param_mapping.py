"""
Autonomous Test: Parameter Mapping in Backend Agents

Tests that PARAM_MAPPING correctly normalizes classifier output
to match tool expected parameters.

Run: python test_param_mapping.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))


def test_ideas_agent_param_mapping():
    """Test IdeasAgent PARAM_MAPPING normalization."""
    print("\n" + "="*60)
    print("TEST: IdeasAgent PARAM_MAPPING")
    print("="*60)

    from swarm.backend_agents.ideas_agent import IdeasAgent

    agent = IdeasAgent()

    test_cases = [
        # (event_type, classifier_params, expected_normalized)
        (
            "bubble.create",
            {"bubble_name": "Marketing"},
            {"title": "Marketing"},
        ),
        (
            "bubble.create",
            {"name": "Sales"},
            {"title": "Sales"},
        ),
        (
            "bubble.create",
            {"space": "Development"},
            {"title": "Development"},
        ),
        (
            "bubble.enter",
            {"title": "Marketing"},
            {"bubble_name": "Marketing"},
        ),
        (
            "bubble.enter",
            {"space_name": "Sales"},
            {"bubble_name": "Sales"},
        ),
        (
            "idea.create",
            {"idea_description": "This is the content", "title": "My Idea"},
            {"content": "This is the content", "title": "My Idea"},
        ),
        (
            "idea.create",
            {"name": "New Idea", "description": "Some description"},
            {"title": "New Idea", "content": "Some description"},
        ),
        (
            "idea.create",
            {"idea_name": "Test", "idea_description": "Test content"},
            {"title": "Test", "content": "Test content"},
        ),
        (
            "idea.find",
            {"text": "search term"},
            {"query": "search term"},
        ),
        (
            "idea.find",
            {"search": "another term"},
            {"query": "another term"},
        ),
        (
            "idea.connect",
            {"source": "Idea A", "target": "Idea B"},
            {"idea1": "Idea A", "idea2": "Idea B"},
        ),
        (
            "idea.connect",
            {"from_idea": "First", "to_idea": "Second"},
            {"idea1": "First", "idea2": "Second"},
        ),
        (
            "idea.update",
            {"title": "Old Name", "description": "New content"},
            {"idea_name": "Old Name", "new_content": "New content"},
        ),
    ]

    passed = 0
    failed = 0

    for event_type, input_params, expected in test_cases:
        result = agent._normalize_params(event_type, input_params)

        if result == expected:
            print(f"  [PASS] {event_type}: {input_params} -> {result}")
            passed += 1
        else:
            print(f"  [FAIL] {event_type}: {input_params}")
            print(f"         Expected: {expected}")
            print(f"         Got:      {result}")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def test_transcript_extraction():
    """Test fallback parameter extraction from transcript."""
    print("\n" + "="*60)
    print("TEST: Transcript Parameter Extraction")
    print("="*60)

    from swarm.backend_agents.ideas_agent import IdeasAgent

    agent = IdeasAgent()

    test_cases = [
        # (event_type, transcript, expected_extracted)
        (
            "bubble.enter",
            "Navigiere in den Space Langzeitspeicher",
            {"bubble_name": "Langzeitspeicher"},
        ),
        (
            "bubble.enter",
            "Gehe in den Space Debug Information",
            {"bubble_name": "Debug Information"},
        ),
        (
            "bubble.enter",
            "Navigiere zu Marketing",
            {"bubble_name": "Marketing"},
        ),
        (
            "idea.create",
            "Erstelle eine Idee Neue Funktion",
            {"title": "Neue Funktion"},
        ),
        (
            "idea.find",
            "Suche nach Marketing Strategie",
            {"query": "Marketing Strategie"},
        ),
        (
            "idea.connect",
            "Verbinde Marketing mit Sales",
            {"idea1": "Marketing", "idea2": "Sales"},
        ),
    ]

    passed = 0
    failed = 0

    for event_type, transcript, expected in test_cases:
        result = agent._extract_params_from_transcript(event_type, transcript)

        # Check if extracted params match expected (subset matching)
        match = True
        for key, value in expected.items():
            if key not in result:
                match = False
                break
            # Fuzzy match for extracted values (may have extra whitespace)
            if expected[key].lower() not in result[key].lower():
                match = False
                break

        if match:
            print(f"  [PASS] {event_type}: '{transcript[:40]}...'")
            print(f"         Extracted: {result}")
            passed += 1
        else:
            print(f"  [FAIL] {event_type}: '{transcript[:40]}...'")
            print(f"         Expected: {expected}")
            print(f"         Got:      {result}")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def test_tool_signatures():
    """Verify adapted tools have correct signatures."""
    print("\n" + "="*60)
    print("TEST: Adapted Tool Signatures")
    print("="*60)

    import inspect
    from swarm.tools.adapted_idea_tools import (
        create_idea, list_ideas, find_idea, update_idea,
        delete_idea, connect_ideas, auto_link_ideas
    )
    from swarm.tools.adapted_bubble_tools import (
        create_bubble, list_bubbles, enter_bubble, exit_bubble,
        delete_bubble
    )

    tools_to_check = [
        ("create_idea", create_idea, ["title", "content", "type"]),
        ("list_ideas", list_ideas, []),
        ("find_idea", find_idea, ["query"]),
        ("update_idea", update_idea, ["idea_name", "new_content", "new_title"]),
        ("delete_idea", delete_idea, ["idea_name"]),
        ("connect_ideas", connect_ideas, ["idea1", "idea2"]),
        ("auto_link_ideas", auto_link_ideas, ["threshold", "max_links"]),
        ("create_bubble", create_bubble, ["title"]),
        ("list_bubbles", list_bubbles, []),
        ("enter_bubble", enter_bubble, ["bubble_name"]),
        ("exit_bubble", exit_bubble, []),
        ("delete_bubble", delete_bubble, ["bubble_name"]),
    ]

    passed = 0
    failed = 0

    for name, func, expected_params in tools_to_check:
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        # Check all expected params exist
        missing = [p for p in expected_params if p not in params]

        if not missing:
            print(f"  [PASS] {name}({', '.join(params)})")
            passed += 1
        else:
            print(f"  [FAIL] {name}: missing params: {missing}")
            print(f"         Has: {params}")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all tests and generate evaluation report."""
    print("\n" + "#"*60)
    print("# AUTONOMOUS TEST: Parameter Mapping & Normalization")
    print("#"*60)

    results = {}

    # Run tests
    results["PARAM_MAPPING"] = test_ideas_agent_param_mapping()
    results["Transcript Extraction"] = test_transcript_extraction()
    results["Tool Signatures"] = test_tool_signatures()

    # Generate evaluation report
    print("\n" + "="*60)
    print("EVALUATION REPORT")
    print("="*60)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    total = len(results)

    print(f"\n  Total Tests: {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")

    print("\n  Details:")
    for name, result in results.items():
        status = "[PASS]" if result is True else "[FAIL]"
        print(f"    {status} {name}")

    print("\n" + "="*60)

    if failed == 0:
        print("  OVERALL: SUCCESS - All tests passed!")
        print("="*60)
        return 0
    else:
        print(f"  OVERALL: FAILED - {failed} test(s) failed")
        print("="*60)
        return 1


if __name__ == "__main__":
    exit(main())
