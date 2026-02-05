#!/usr/bin/env python3
"""
Test script for Enhanced Reasoning with Semantic Analysis (Phase 15)

Tests the new multi-modal reasoning capabilities of the SemanticAgent.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from swarm.analysis.semantic_agent import get_semantic_agent
from swarm.analysis.intent_analysis_team import IntentHypothesis
from swarm.analysis.user_context import UserContext
from swarm.elevenlabs_input import ElevenLabsInput


async def test_multi_modal_confidence():
    """Test multi-modal confidence calculation."""
    print("=== Testing Multi-Modal Confidence Calculation ===")

    agent = get_semantic_agent()

    # Test cases with different input combinations
    test_cases = [
        {
            "name": "High confidence text + ElevenLabs",
            "text": "Erstelle eine neue Idee für mein Projekt",
            "elevenlabs": ElevenLabsInput(
                transcript_confidence=0.95,
                intent_detected="create_idea",
                intent_confidence=0.9,
                detected_language="de"
            ),
            "expected_min": 0.7
        },
        {
            "name": "Low confidence text only",
            "text": "x",
            "elevenlabs": None,
            "expected_min": 0.2
        },
        {
            "name": "Medium confidence with context",
            "text": "Zeig mir meine Ideen",
            "elevenlabs": ElevenLabsInput(
                transcript_confidence=0.7,
                detected_language="de"
            ),
            "expected_min": 0.5
        }
    ]

    for test_case in test_cases:
        context = UserContext(user_id="test_user", session_id="test_session")

        confidence = agent._calculate_multi_modal_confidence(
            test_case["text"],
            context,
            test_case["elevenlabs"]
        )

        print(f"✅ {test_case['name']}: {confidence:.2f} (expected min: {test_case['expected_min']})")

        assert confidence >= test_case["expected_min"], f"Confidence too low: {confidence}"
        assert confidence <= 0.95, f"Confidence too high: {confidence}"

    print("✅ Multi-modal confidence calculation working correctly")


async def test_context_aware_reasoning():
    """Test context-aware reasoning capabilities."""
    print("\n=== Testing Context-Aware Reasoning ===")

    agent = get_semantic_agent()

    # Test with recent creation context
    context = UserContext(
        user_id="test_user",
        session_id="test_session",
        current_space="Projekt Alpha",
        recent_actions=[
            {"type": "idea.create", "timestamp": "2024-01-01"},
            {"type": "idea.create", "timestamp": "2024-01-02"}
        ]
    )

    user_input = "Erstelle noch eine Idee"
    base_confidence = 0.6

    hypotheses = agent._context_aware_analysis(user_input, context, base_confidence)

    print(f"✅ Generated {len(hypotheses)} context-aware hypotheses")

    # Should find creation hypothesis boosted by recent activity
    creation_hypotheses = [h for h in hypotheses if h.event_type == "idea.create"]
    assert len(creation_hypotheses) > 0, "Should generate creation hypothesis from context"

    boosted_hypothesis = creation_hypotheses[0]
    print(f"✅ Creation hypothesis confidence: {boosted_hypothesis.confidence:.2f} (should be > 0.6)")

    assert boosted_hypothesis.confidence > base_confidence, "Confidence should be boosted by context"


async def test_enhanced_hypothesis_merging():
    """Test enhanced hypothesis merging with semantic clustering."""
    print("\n=== Testing Enhanced Hypothesis Merging ===")

    agent = get_semantic_agent()

    # Create multiple similar hypotheses
    hypotheses = [
        IntentHypothesis(
            event_type="idea.create",
            payload={},
            confidence=0.7,
            reasoning="Text pattern match",
            source="text_pattern"
        ),
        IntentHypothesis(
            event_type="idea.create",
            payload={},
            confidence=0.6,
            reasoning="ElevenLabs intent",
            source="elevenlabs"
        ),
        IntentHypothesis(
            event_type="bubble.create",
            payload={},
            confidence=0.5,
            reasoning="Context pattern",
            source="context"
        ),
        IntentHypothesis(
            event_type="conversation.greeting",
            payload={},
            confidence=0.8,
            reasoning="Greeting pattern",
            source="conversation"
        )
    ]

    context = UserContext(user_id="test_user")
    merged = agent._enhanced_hypothesis_merging(hypotheses, context)

    print(f"✅ Merged {len(hypotheses)} hypotheses into {len(merged)}")

    # Should have merged similar creation hypotheses
    creation_hypotheses = [h for h in merged if "create" in h.event_type]
    if creation_hypotheses:
        merged_creation = creation_hypotheses[0]
        print(f"✅ Merged creation hypothesis confidence: {merged_creation.confidence:.2f}")
        assert "merge" in merged_creation.source, "Should indicate merged source"

    # Should preserve greeting (different cluster)
    greeting_hypotheses = [h for h in merged if h.event_type == "conversation.greeting"]
    assert len(greeting_hypotheses) > 0, "Should preserve greeting hypothesis"


async def test_pattern_based_reasoning():
    """Test pattern-based reasoning with regex matching."""
    print("\n=== Testing Pattern-Based Reasoning ===")

    agent = get_semantic_agent()

    test_cases = [
        {
            "input": "Erstelle eine neue Idee",
            "expected_event": "idea.create",
            "description": "German creation pattern"
        },
        {
            "input": "Zeig mir alle Ideen",
            "expected_event": "idea.list",
            "description": "German information pattern"
        },
        {
            "input": "Lösche diese Idee",
            "expected_event": "idea.delete",
            "description": "German deletion pattern"
        }
    ]

    context = UserContext(user_id="test_user")
    base_confidence = 0.6

    for test_case in test_cases:
        hypotheses = agent._pattern_based_reasoning(test_case["input"], context, base_confidence)

        matching_hypotheses = [h for h in hypotheses if h.event_type == test_case["expected_event"]]

        print(f"✅ {test_case['description']}: {len(matching_hypotheses)} matching hypotheses")

        if matching_hypotheses:
            best_match = max(matching_hypotheses, key=lambda h: h.confidence)
            print(f"   Confidence: {best_match.confidence:.2f}, Source: {best_match.source}")
            assert best_match.confidence > 0.4, f"Confidence too low: {best_match.confidence}"


async def test_full_enhanced_analysis():
    """Test the complete enhanced analysis pipeline."""
    print("\n=== Testing Full Enhanced Analysis Pipeline ===")

    agent = get_semantic_agent()

    # Rich test case with all modalities
    user_input = "Ich will eine neue Idee für mein Projekt erstellen"
    context = UserContext(
        user_id="test_user",
        session_id="test_session",
        current_space="Projekt Alpha",
        recent_actions=[{"type": "idea.create"}]
    )
    elevenlabs_input = ElevenLabsInput(
        transcript_confidence=0.9,
        intent_detected="create_idea",
        intent_confidence=0.85,
        detected_language="de"
    )

    hypotheses = await agent.analyze(user_input, context, elevenlabs_input)

    print(f"✅ Full pipeline generated {len(hypotheses)} hypotheses")

    # Should have high-confidence creation hypothesis
    creation_hypotheses = [h for h in hypotheses if h.event_type == "idea.create"]
    assert len(creation_hypotheses) > 0, "Should generate creation hypothesis"

    best_hypothesis = max(creation_hypotheses, key=lambda h: h.confidence)
    print(f"✅ Best hypothesis: {best_hypothesis.event_type} "
          f"(confidence: {best_hypothesis.confidence:.2f})")
    print(f"   Source: {best_hypothesis.source}")
    print(f"   Reasoning: {best_hypothesis.reasoning}")

    assert best_hypothesis.confidence > 0.7, f"Confidence should be high: {best_hypothesis.confidence}"


async def main():
    """Run all enhanced reasoning tests."""
    print("🚀 Testing Enhanced Reasoning with Semantic Analysis (Phase 15)")
    print("=" * 70)

    try:
        await test_multi_modal_confidence()
        await test_context_aware_reasoning()
        await test_enhanced_hypothesis_merging()
        await test_pattern_based_reasoning()
        await test_full_enhanced_analysis()

        print("\n" + "=" * 70)
        print("🎉 All Enhanced Reasoning tests passed!")
        print("✅ Multi-modal confidence calculation")
        print("✅ Context-aware reasoning")
        print("✅ Enhanced hypothesis merging")
        print("✅ Pattern-based reasoning")
        print("✅ Full analysis pipeline")
        print("\nThe Enhanced Semantic Analysis is working correctly.")

        return 0

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)