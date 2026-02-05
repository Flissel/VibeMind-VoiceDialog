#!/usr/bin/env python
"""
Test script for the Intent Evaluation Framework (Phase 17).

Tests:
1. Intent Taxonomy
2. Synthetic Conversation Generator
3. Evaluation Runner (batch tests)
4. Real-Time Evaluator
"""

import asyncio
import sys
import os

# Add python directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_taxonomy():
    """Test intent taxonomy."""
    print("\n=== Testing Intent Taxonomy ===")

    from swarm.evaluation.intent_taxonomy import (
        IntentCategory,
        INTENT_TAXONOMY,
        get_category,
        get_intents_by_category,
        get_category_stats,
    )

    # Check categories exist
    assert len(IntentCategory) == 10, f"Expected 10 categories, got {len(IntentCategory)}"
    print(f"[OK] {len(IntentCategory)} categories defined")

    # Check intents are mapped
    assert len(INTENT_TAXONOMY) >= 35, f"Expected at least 35 intents, got {len(INTENT_TAXONOMY)}"
    print(f"[OK] {len(INTENT_TAXONOMY)} intents mapped")

    # Test get_category
    cat = get_category("bubble.create")
    assert cat == IntentCategory.CREATE, f"Expected CREATE, got {cat}"
    print("[OK] get_category() works")

    # Test get_intents_by_category
    query_intents = get_intents_by_category(IntentCategory.QUERY)
    assert len(query_intents) >= 5, f"Expected at least 5 QUERY intents, got {len(query_intents)}"
    print(f"[OK] {len(query_intents)} QUERY intents")

    # Test stats
    stats = get_category_stats()
    assert sum(stats.values()) == len(INTENT_TAXONOMY)
    print("[OK] Category stats correct")

    print("=== Taxonomy Tests PASSED ===")


def test_conversation_generator():
    """Test synthetic conversation generator."""
    print("\n=== Testing Conversation Generator ===")

    from swarm.evaluation.conversation_generator import (
        SyntheticUtterance,
        UTTERANCE_TEMPLATES,
        get_all_utterances,
        get_utterances_by_intent,
        get_utterances_by_category,
        get_stats,
    )
    from swarm.evaluation.intent_taxonomy import IntentCategory

    # Check utterances exist
    all_utts = get_all_utterances()
    assert len(all_utts) >= 50, f"Expected at least 50 utterances, got {len(all_utts)}"
    print(f"[OK] {len(all_utts)} total utterances")

    # Check by intent
    bubble_create_utts = get_utterances_by_intent("bubble.create")
    assert len(bubble_create_utts) >= 3, f"Expected at least 3 bubble.create utterances"
    print(f"[OK] {len(bubble_create_utts)} bubble.create utterances")

    # Check by category
    generate_utts = get_utterances_by_category(IntentCategory.GENERATE)
    assert len(generate_utts) >= 10, f"Expected at least 10 GENERATE utterances"
    print(f"[OK] {len(generate_utts)} GENERATE utterances")

    # Check stats
    stats = get_stats()
    assert stats["total"] == len(all_utts)
    assert stats["intents_covered"] >= 20
    print(f"[OK] Stats: {stats['intents_covered']} intents covered")

    # Check utterance structure
    utt = all_utts[0]
    assert hasattr(utt, "text"), "Utterance missing text"
    assert hasattr(utt, "expected_intent"), "Utterance missing expected_intent"
    assert hasattr(utt, "expected_payload"), "Utterance missing expected_payload"
    print("[OK] Utterance structure valid")

    print("=== Conversation Generator Tests PASSED ===")


def test_realtime_evaluator():
    """Test real-time evaluator."""
    print("\n=== Testing Real-Time Evaluator ===")

    from swarm.evaluation.realtime_evaluator import (
        RealtimeEvaluator,
        LiveClassification,
        get_realtime_evaluator,
    )

    # Create evaluator (without DB)
    evaluator = RealtimeEvaluator(repo=None)

    # Test on_classification
    log_id = evaluator.on_classification(
        session_id="test_session",
        user_input="Erstelle einen Space namens Test",
        result={
            "event_type": "bubble.create",
            "payload": {"title": "Test"},
            "confidence": 0.9
        }
    )
    assert evaluator.get_last_classification() is not None
    print("[OK] on_classification() works")

    # Test on_feedback (correct)
    response = evaluator.on_feedback("correct")
    assert "Danke" in response
    print("[OK] on_feedback(correct) works")

    # Test another classification
    evaluator.on_classification(
        session_id="test_session",
        user_input="Zeig alle Ideen",
        result={"event_type": "idea.list", "payload": {}}
    )

    # Test on_feedback (incorrect)
    response = evaluator.on_feedback("incorrect")
    assert "Korrektur" in response or "stattdessen" in response
    print("[OK] on_feedback(incorrect) works")

    # Test clarification
    response = evaluator.on_clarification("Ich wollte eine Idee erstellen")
    assert "Verstanden" in response
    print("[OK] on_clarification() works")

    # Test stats
    stats = evaluator.get_session_stats()
    assert stats["total"] >= 2
    print(f"[OK] Session stats: {stats}")

    # Test voice format
    voice_text = evaluator.format_stats_for_voice()
    assert len(voice_text) > 0
    print(f"[OK] Voice format: '{voice_text[:50]}...'")

    print("=== Real-Time Evaluator Tests PASSED ===")


async def test_evaluation_runner_mock():
    """Test evaluation runner with mock classifier."""
    print("\n=== Testing Evaluation Runner (Mock) ===")

    from swarm.evaluation.evaluation_runner import EvaluationRunner, EvaluationResult
    from swarm.evaluation.conversation_generator import SyntheticUtterance
    from swarm.evaluation.intent_taxonomy import IntentCategory

    # Create mock classifier
    class MockClassifier:
        async def classify(self, text):
            # Simple mock: return bubble.create for any "erstelle"
            if "erstelle" in text.lower() or "neuer" in text.lower():
                return {"event_type": "bubble.create", "payload": {"title": "Test"}}
            elif "zeig" in text.lower() or "liste" in text.lower():
                return {"event_type": "bubble.list", "payload": {}}
            elif "erweitere" in text.lower() or "generiere" in text.lower():
                return {"event_type": "idea.expand", "payload": {}}
            else:
                return {"event_type": "conversation.unknown", "payload": {}}

    runner = EvaluationRunner(classifier=MockClassifier())

    # Create test utterances
    test_utterances = [
        SyntheticUtterance(
            "Erstelle einen Space namens Marketing",
            "bubble.create",
            {"title": "Marketing"},
            IntentCategory.CREATE,
            "easy",
            ["direct"]
        ),
        SyntheticUtterance(
            "Zeig mir alle Spaces",
            "bubble.list",
            {},
            IntentCategory.QUERY,
            "easy",
            ["direct"]
        ),
        SyntheticUtterance(
            "Erweitere die Ideen",
            "idea.expand",
            {},
            IntentCategory.GENERATE,
            "easy",
            ["direct"]
        ),
    ]

    # Run evaluation
    report = await runner.run_all(test_utterances, name="Mock Test")

    print(f"[OK] Ran {report.total_tests} tests")
    print(f"[OK] Accuracy: {report.accuracy * 100:.1f}%")
    print(f"[OK] Correct: {report.correct}, Incorrect: {report.incorrect}")

    # Check report structure
    assert report.total_tests == 3
    assert hasattr(report, "per_category_accuracy")
    assert hasattr(report, "per_difficulty_accuracy")
    assert hasattr(report, "confusion_matrix")
    print("[OK] Report structure valid")

    # Test markdown output
    md = report.to_markdown()
    assert "# Intent Evaluation Report" in md
    assert "Accuracy" in md
    print("[OK] Markdown report generated")

    print("=== Evaluation Runner Tests PASSED ===")


def test_dashboard():
    """Test dashboard functions."""
    print("\n=== Testing Dashboard ===")

    from swarm.evaluation.dashboard import (
        format_stats_for_voice,
        print_utterance_stats,
    )

    # Test voice format (without DB)
    voice_text = format_stats_for_voice()
    assert len(voice_text) > 0
    print(f"[OK] Voice format: '{voice_text[:50]}...'")

    # Test utterance stats
    print_utterance_stats()
    print("[OK] Utterance stats printed")

    print("=== Dashboard Tests PASSED ===")


def main():
    """Run all tests."""
    print("=" * 60)
    print("   VibeMind Intent Evaluation Framework - Test Suite")
    print("=" * 60)

    try:
        test_taxonomy()
        test_conversation_generator()
        test_realtime_evaluator()
        asyncio.run(test_evaluation_runner_mock())
        test_dashboard()

        print("\n" + "=" * 60)
        print("   ALL TESTS PASSED!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n[FAILED] {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
