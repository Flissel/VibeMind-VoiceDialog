#!/usr/bin/env python3
"""
Test script for AnalysisTeam-Centered Orchestrator Architecture (Phase 14)

Tests the new architecture where IntentAnalysisTeam is the core analysis engine,
with ToolOrchestrator and Legacy classifier as parallel extensions.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from swarm.orchestrator.intent_orchestrator import get_orchestrator
from swarm.event_team import TaskContext


async def test_core_analysis():
    """Test core analysis with IntentAnalysisTeam."""
    print("=== Testing Core Analysis (IntentAnalysisTeam) ===")

    orchestrator = get_orchestrator()

    # Test with a simple intent
    intent_text = "Erstelle eine neue Idee namens 'Test Projekt'"
    context = TaskContext(user_id="test_user", session_id="test_session")

    try:
        result = await orchestrator.process_intent(intent_text, context)

        print(f"✅ Core Analysis Result:")
        print(f"  Event Type: {result.event_type}")
        print(f"  Job ID: {result.job_id}")
        print(f"  Response: {result.response_hint}")
        print(f"  Conversational: {result.is_conversational}")

        return result.event_type != "error"

    except Exception as e:
        print(f"❌ Core Analysis Failed: {e}")
        return False


async def test_parallel_extensions():
    """Test parallel extension processing."""
    print("\n=== Testing Parallel Extensions ===")

    # Force disable core analysis to test extensions
    os.environ["USE_INTENT_ANALYSIS"] = "false"

    orchestrator = get_orchestrator()

    intent_text = "Liste alle meine Spaces auf"
    context = TaskContext(user_id="test_user", session_id="test_session")

    try:
        result = await orchestrator.process_intent(intent_text, context)

        print(f"✅ Extension Result:")
        print(f"  Event Type: {result.event_type}")
        print(f"  Job ID: {result.job_id}")
        print(f"  Response: {result.response_hint}")
        print(f"  Conversational: {result.is_conversational}")

        return result.event_type != "error"

    except Exception as e:
        print(f"❌ Extension Test Failed: {e}")
        return False
    finally:
        # Reset environment
        if "USE_INTENT_ANALYSIS" in os.environ:
            del os.environ["USE_INTENT_ANALYSIS"]


async def test_fallback_processing():
    """Test fallback processing when everything fails."""
    print("\n=== Testing Fallback Processing ===")

    # Disable all components to force fallback
    os.environ["USE_INTENT_ANALYSIS"] = "false"
    os.environ["USE_TOOL_ORCHESTRATOR"] = "false"

    orchestrator = get_orchestrator()

    intent_text = "Eine komplett unbekannte Anfrage xyz123"
    context = TaskContext(user_id="test_user", session_id="test_session")

    try:
        result = await orchestrator.process_intent(intent_text, context)

        print(f"✅ Fallback Result:")
        print(f"  Event Type: {result.event_type}")
        print(f"  Response: {result.response_hint}")
        print(f"  Conversational: {result.is_conversational}")

        # Fallback should always return conversation.unknown
        return result.event_type == "conversation.unknown"

    except Exception as e:
        print(f"❌ Fallback Test Failed: {e}")
        return False
    finally:
        # Reset environment
        for key in ["USE_INTENT_ANALYSIS", "USE_TOOL_ORCHESTRATOR"]:
            if key in os.environ:
                del os.environ[key]


async def test_full_pipeline():
    """Test the complete pipeline with all components enabled."""
    print("\n=== Testing Full Pipeline ===")

    # Enable all components
    os.environ["USE_INTENT_ANALYSIS"] = "true"
    os.environ["USE_TOOL_ORCHESTRATOR"] = "true"

    orchestrator = get_orchestrator()

    test_cases = [
        "Hallo, wie geht es dir?",
        "Erstelle eine neue Bubble namens 'Test Space'",
        "Liste meine Ideen auf"
    ]

    results = []

    for intent_text in test_cases:
        print(f"\nTesting: '{intent_text}'")
        context = TaskContext(user_id="test_user", session_id="test_session")

        try:
            result = await orchestrator.process_intent(intent_text, context)
            print(f"  Result: {result.event_type} - {result.response_hint[:50]}...")

            success = result.event_type != "error"
            results.append(success)

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results.append(False)

    # Reset environment
    for key in ["USE_INTENT_ANALYSIS", "USE_TOOL_ORCHESTRATOR"]:
        if key in os.environ:
            del os.environ[key]

    return all(results)


async def main():
    """Run all tests."""
    print("🚀 Testing AnalysisTeam-Centered Orchestrator Architecture")
    print("=" * 60)

    # Check available components
    orchestrator = get_orchestrator()
    print("Available Components:")
    print(f"  IntentAnalysisTeam: {'✅' if orchestrator._use_intent_analysis else '❌'}")
    print(f"  ToolOrchestrator: {'✅' if orchestrator._use_tool_orchestrator else '❌'}")
    print(f"  Legacy Classifier: {'✅' if orchestrator.classifier else '❌'}")
    print()

    # Run tests
    test_results = []

    # Test 1: Core Analysis
    test_results.append(await test_core_analysis())

    # Test 2: Parallel Extensions
    test_results.append(await test_parallel_extensions())

    # Test 3: Fallback Processing
    test_results.append(await test_fallback_processing())

    # Test 4: Full Pipeline
    test_results.append(await test_full_pipeline())

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    print(f"  Core Analysis: {'✅ PASS' if test_results[0] else '❌ FAIL'}")
    print(f"  Extensions: {'✅ PASS' if test_results[1] else '❌ FAIL'}")
    print(f"  Fallback: {'✅ PASS' if test_results[2] else '❌ FAIL'}")
    print(f"  Full Pipeline: {'✅ PASS' if test_results[3] else '❌ FAIL'}")

    passed = sum(test_results)
    total = len(test_results)

    print(f"\n🎯 Overall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! AnalysisTeam-Centered Architecture is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the implementation.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)