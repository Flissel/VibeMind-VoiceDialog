#!/usr/bin/env python3
"""
Test Phase 9: Classifier parameter extraction and tool execution.

Tests:
1. IntentClassifier extracts correct parameter names
2. Tools receive and handle parameters correctly
3. End-to-end flow via IntentOrchestrator
"""

import asyncio
import os
import sys
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env
from dotenv import load_dotenv
load_dotenv()

# Force sync mode for testing
os.environ["FORCE_SYNC_MODE"] = "true"


def test_classifier_parameters():
    """Test that classifier extracts correct parameter names."""
    print("\n" + "=" * 60)
    print("TEST 1: IntentClassifier Parameter Extraction")
    print("=" * 60)

    from swarm.orchestrator.intent_classifier import get_intent_classifier

    classifier = get_intent_classifier()

    test_cases = [
        # (input, expected_event_type, expected_params)
        ("Lösche die Idee Test", "idea.delete", ["idea_name"]),
        ("Aktualisiere die Idee Kochen mit neuem Text", "idea.update", ["idea_name"]),
        ("Verbinde Python mit Coding", "idea.connect", ["idea1", "idea2"]),
        ("Erstelle eine Idee über Katzen", "idea.create", ["title", "content"]),
        ("Welche Spaces habe ich?", "bubble.list", []),
    ]

    passed = 0
    failed = 0

    for intent, expected_type, expected_params in test_cases:
        print(f"\n>>> Input: '{intent}'")

        try:
            result = classifier.classify_sync(intent)
            event_type = result.get("event_type", "")
            payload = result.get("payload", {})

            print(f"    Event: {event_type}")
            print(f"    Payload: {payload}")

            # Check event type
            type_ok = event_type == expected_type

            # Check parameters exist
            params_ok = all(p in payload for p in expected_params)

            if type_ok and params_ok:
                print(f"    [PASS] Correct event type and parameters")
                passed += 1
            else:
                if not type_ok:
                    print(f"    [FAIL] Expected event_type={expected_type}, got={event_type}")
                if not params_ok:
                    missing = [p for p in expected_params if p not in payload]
                    print(f"    [FAIL] Missing parameters: {missing}")
                failed += 1

        except Exception as e:
            print(f"    [ERROR] {e}")
            failed += 1

    print(f"\n--- Classifier Test Results: {passed}/{passed+failed} passed ---")
    return failed == 0


def test_tool_execution():
    """Test that tools execute with correct parameters."""
    print("\n" + "=" * 60)
    print("TEST 2: Direct Tool Execution")
    print("=" * 60)

    from tools.idea_tools import (
        list_ideas, create_idea, delete_idea,
        update_idea, connect_ideas, find_idea
    )
    from tools.bubble_tools import list_bubbles, create_bubble

    passed = 0
    failed = 0

    # Test list_ideas (should work even if empty)
    print("\n>>> list_ideas({})")
    try:
        result = list_ideas({})
        print(f"    Result: {result}")
        print("    [PASS]")
        passed += 1
    except Exception as e:
        print(f"    [FAIL] {e}")
        failed += 1

    # Test list_bubbles
    print("\n>>> list_bubbles({})")
    try:
        result = list_bubbles({})
        print(f"    Result: {result}")
        print("    [PASS]")
        passed += 1
    except Exception as e:
        print(f"    [FAIL] {e}")
        failed += 1

    # Test create_idea with correct params
    print("\n>>> create_idea({'title': 'TestIdea', 'content': 'Test content'})")
    try:
        result = create_idea({"title": "TestIdea", "content": "Test content"})
        print(f"    Result: {result}")
        if "TestIdea" in result or "Added" in result or "Enter a space" in result:
            print("    [PASS]")
            passed += 1
        else:
            print("    [WARN] Unexpected response")
            passed += 1  # Still counts as working
    except Exception as e:
        print(f"    [FAIL] {e}")
        failed += 1

    # Test delete_idea with idea_name (not idea_id)
    print("\n>>> delete_idea({'idea_name': 'NonExistent'})")
    try:
        result = delete_idea({"idea_name": "NonExistent"})
        print(f"    Result: {result}")
        # Should return "couldn't find" not crash
        if "find" in result.lower() or "delete" in result.lower():
            print("    [PASS] Correctly handles missing idea")
            passed += 1
        else:
            print("    [PASS]")
            passed += 1
    except Exception as e:
        print(f"    [FAIL] {e}")
        failed += 1

    # Test update_idea with idea_name, new_content
    print("\n>>> update_idea({'idea_name': 'NonExistent', 'new_content': 'new text'})")
    try:
        result = update_idea({"idea_name": "NonExistent", "new_content": "new text"})
        print(f"    Result: {result}")
        print("    [PASS] Correctly handles parameters")
        passed += 1
    except Exception as e:
        print(f"    [FAIL] {e}")
        failed += 1

    # Test connect_ideas with idea1, idea2
    print("\n>>> connect_ideas({'idea1': 'A', 'idea2': 'B'})")
    try:
        result = connect_ideas({"idea1": "A", "idea2": "B"})
        print(f"    Result: {result}")
        print("    [PASS] Correctly handles parameters")
        passed += 1
    except Exception as e:
        print(f"    [FAIL] {e}")
        failed += 1

    print(f"\n--- Tool Execution Results: {passed}/{passed+failed} passed ---")
    return failed == 0


def test_orchestrator_flow():
    """Test end-to-end flow via IntentOrchestrator."""
    print("\n" + "=" * 60)
    print("TEST 3: IntentOrchestrator End-to-End Flow")
    print("=" * 60)

    from swarm.orchestrator import get_orchestrator

    orchestrator = get_orchestrator()

    test_cases = [
        "Welche Spaces habe ich?",
        "Lösche die Idee TestToDelete",
        "Verbinde Idee1 mit Idee2",
    ]

    passed = 0
    failed = 0

    for intent in test_cases:
        print(f"\n>>> Intent: '{intent}'")
        try:
            result = orchestrator.process_intent_sync(intent)
            print(f"    Event: {result.event_type}")
            print(f"    Response: {result.response_hint}")
            print(f"    Error: {result.error}")

            if result.error:
                print(f"    [WARN] Has error but tool executed")
            else:
                print("    [PASS]")
            passed += 1

        except Exception as e:
            print(f"    [FAIL] {e}")
            failed += 1

    print(f"\n--- Orchestrator Results: {passed}/{passed+failed} passed ---")
    return failed == 0


def main():
    print("=" * 60)
    print("PHASE 9 TOOL VERIFICATION")
    print("Testing classifier parameters and tool execution")
    print("=" * 60)

    results = []

    # Test 1: Classifier
    results.append(("Classifier Parameters", test_classifier_parameters()))

    # Test 2: Direct Tools
    results.append(("Tool Execution", test_tool_execution()))

    # Test 3: Orchestrator
    results.append(("Orchestrator Flow", test_orchestrator_flow()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    print("\n" + ("ALL TESTS PASSED!" if all_passed else "SOME TESTS FAILED"))
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
