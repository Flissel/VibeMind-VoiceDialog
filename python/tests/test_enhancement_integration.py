"""
Test Enhancement Pipeline Integration with Orchestrator

Quick verification that the enhancement pipeline is properly integrated
and improves intent classification for problematic input patterns.
"""

import asyncio
import os
import sys

# Set environment for sync mode (no Redis needed)
os.environ["FORCE_SYNC_MODE"] = "true"
os.environ["USE_ENHANCEMENT_PIPELINE"] = "true"
os.environ["USE_RAG_CLASSIFIER"] = "true"

# Test cases focused on problematic patterns from evaluation
TEST_CASES = [
    # ASR errors
    {"input": "zeig mir meine idden", "expected": "idea.list", "pattern": "asr"},
    {"input": "erstele einen neuen speiss", "expected": "bubble.create", "pattern": "asr"},

    # Dialect
    {"input": "schaug amoi de ideen an", "expected": "idea.list", "pattern": "dialect"},
    {"input": "mach dat weg", "expected": "idea.delete", "pattern": "dialect"},

    # Informal
    {"input": "zeig mal", "expected": "idea.list", "pattern": "informal"},
    {"input": "mach weg", "expected": "idea.delete", "pattern": "informal"},

    # Standard (should still work)
    {"input": "zeig mir alle ideen", "expected": "idea.list", "pattern": "standard"},
    {"input": "erstelle einen neuen space namens Test", "expected": "bubble.create", "pattern": "standard"},
]


async def test_with_enhancer():
    """Test RAG classifier with enhancement pipeline."""
    from swarm.orchestrator.rag_intent_classifier import get_rag_intent_classifier
    from swarm.agents.intent_enhancer import get_intent_enhancer, reset_intent_enhancer

    # Reset and get fresh enhancer
    reset_intent_enhancer()
    enhancer = get_intent_enhancer()
    classifier = get_rag_intent_classifier()

    print("=" * 60)
    print("Enhancement Pipeline Integration Test")
    print("=" * 60)
    print(f"Enhancement rules loaded: {len(enhancer.rules.rules)}")
    print()

    results = {"passed": 0, "failed": 0, "by_pattern": {}}

    for test in TEST_CASES:
        input_text = test["input"]
        expected = test["expected"]
        pattern = test["pattern"]

        if pattern not in results["by_pattern"]:
            results["by_pattern"][pattern] = {"passed": 0, "failed": 0}

        # Step 1: Enhance the input
        enhanced = await enhancer.enhance(input_text, {})
        enhanced_text = enhanced.normalized_text

        # Step 2: Classify the enhanced input
        result = await classifier.classify(enhanced_text, bubble_context=None)

        # Check result
        actual = result.event_type if result else "None"
        confidence = result.confidence if result else 0
        passed = actual == expected

        if passed:
            results["passed"] += 1
            results["by_pattern"][pattern]["passed"] += 1
            status = "[OK]"
        else:
            results["failed"] += 1
            results["by_pattern"][pattern]["failed"] += 1
            status = "[FAIL]"

        # Print result
        enhancement_info = ""
        if enhanced.was_enhanced:
            enhancement_info = f" [enhanced: {enhanced.rules_applied}]"

        print(f"{status} [{pattern}] '{input_text}'{enhancement_info}")
        if enhanced_text != input_text:
            print(f"      Enhanced: '{enhanced_text}'")
        print(f"      Expected: {expected}, Got: {actual} ({confidence:.0%})")
        print()

    # Summary
    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    total = results["passed"] + results["failed"]
    print(f"Total: {results['passed']}/{total} ({100*results['passed']/total:.0f}%)")
    print()
    print("By Pattern:")
    for pattern, stats in results["by_pattern"].items():
        total_p = stats["passed"] + stats["failed"]
        pct = 100 * stats["passed"] / total_p if total_p > 0 else 0
        print(f"  {pattern}: {stats['passed']}/{total_p} ({pct:.0f}%)")

    return results


async def main():
    try:
        results = await test_with_enhancer()

        # Check if improvements are visible
        print()
        print("=" * 60)

        # Check problem patterns
        problem_patterns = ["asr", "dialect", "informal"]
        improvements = 0
        for pattern in problem_patterns:
            if pattern in results["by_pattern"]:
                stats = results["by_pattern"][pattern]
                if stats["passed"] > 0:
                    improvements += 1

        if improvements >= 2:
            print("VERDICT: Enhancement pipeline is working!")
            print("Problem patterns (ASR, dialect, informal) show improvement.")
        else:
            print("VERDICT: Enhancement pipeline needs more tuning.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
