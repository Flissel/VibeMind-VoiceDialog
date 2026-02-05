"""
Quick evaluation of enhancement pipeline on problem patterns.
Bypasses Supermemory to avoid delays.
"""
import asyncio
import os

os.environ['FORCE_SYNC_MODE'] = 'true'
os.environ['USE_ENHANCEMENT_PIPELINE'] = 'true'
os.environ['USE_RAG_CLASSIFIER'] = 'true'
# Note: Supermemory is optional - classifier falls back to local rules if unavailable

# Focused tests on previously failing patterns
TEST_CASES = [
    # CORRECTION TESTS (previously 20%)
    {"id": "COR_01", "input": "erstelle... nein warte lösche den space", "expected": "bubble.delete", "pattern": "correction"},
    {"id": "COR_02", "input": "zeig die ideen... ach nee die spaces", "expected": "bubble.list", "pattern": "correction"},
    {"id": "COR_03", "input": "loesche... moment warte erstelle idee", "expected": "idea.create", "pattern": "correction"},
    {"id": "COR_04", "input": "verbinde... nee warte liste erstmal alles", "expected": "idea.list", "pattern": "correction"},
    {"id": "COR_05", "input": "whitepaper... nein doch zusammenfassung", "expected": "idea.summarize", "pattern": "correction"},
    {"id": "COR_06", "input": "geh rein... andersrum erstmal zeigen", "expected": "idea.list", "pattern": "correction"},
    {"id": "COR_07", "input": "formatieren... stopp erst verlinken", "expected": "idea.auto_link", "pattern": "correction"},
    {"id": "COR_08", "input": "mach weg... halt mach erstmal neu", "expected": "idea.create", "pattern": "correction"},
    {"id": "COR_09", "input": "speichern... nee warte analysieren", "expected": "idea.analyze_links", "pattern": "correction"},
    {"id": "COR_10", "input": "stats zeigen... nee erst reingehn", "expected": "bubble.enter", "pattern": "correction"},

    # INFORMAL TESTS (previously 50%)
    {"id": "INF_01", "input": "zeig mal", "expected": "idea.list", "pattern": "informal"},
    {"id": "INF_02", "input": "mach weg", "expected": "idea.delete", "pattern": "informal"},
    {"id": "INF_03", "input": "wo bin ich", "expected": "idea.current_space", "pattern": "informal"},
    {"id": "INF_04", "input": "was ist", "expected": "idea.current_space", "pattern": "informal"},
    {"id": "INF_05", "input": "reinhauen", "expected": "idea.create", "pattern": "informal"},
    {"id": "INF_06", "input": "rein damit", "expected": "idea.create", "pattern": "informal"},
    {"id": "INF_07", "input": "zeig", "expected": "idea.list", "pattern": "informal"},
    {"id": "INF_08", "input": "zeig erstmal", "expected": "idea.list", "pattern": "informal"},

    # ASR ERROR TESTS
    {"id": "ASR_01", "input": "zeig mir meine idden", "expected": "idea.list", "pattern": "asr"},
    {"id": "ASR_02", "input": "erstele einen neuen speiss", "expected": "bubble.create", "pattern": "asr"},
    {"id": "ASR_03", "input": "loesch die bubbl", "expected": "idea.delete", "pattern": "asr"},
    {"id": "ASR_04", "input": "formatiren als tabelen", "expected": "idea.format_table", "pattern": "asr"},
    {"id": "ASR_05", "input": "erstelle whitepapier", "expected": "idea.whitepaper", "pattern": "asr"},

    # DIALECT TESTS
    {"id": "DIA_01", "input": "schaug amoi de ideen an", "expected": "idea.list", "pattern": "dialect"},
    {"id": "DIA_02", "input": "mach dat weg", "expected": "idea.delete", "pattern": "dialect"},
    {"id": "DIA_03", "input": "geh ma do nei", "expected": "bubble.enter", "pattern": "dialect"},
    {"id": "DIA_04", "input": "pack da wat rein", "expected": "idea.create", "pattern": "dialect"},
    {"id": "DIA_05", "input": "zamfassn", "expected": "idea.summarize", "pattern": "dialect"},

    # CONTEXTUAL TESTS
    {"id": "CTX_01", "input": "das da löschen", "expected": "idea.delete", "pattern": "contextual"},
    {"id": "CTX_02", "input": "die sache von vorhin zeigen", "expected": "idea.find", "pattern": "contextual"},
]


async def run_evaluation():
    from swarm.orchestrator.rag_intent_classifier import get_rag_intent_classifier
    from swarm.agents.intent_enhancer import get_intent_enhancer, reset_intent_enhancer

    # Initialize
    reset_intent_enhancer()
    enhancer = get_intent_enhancer()
    classifier = get_rag_intent_classifier()

    print("=" * 60)
    print("QUICK ENHANCEMENT PIPELINE EVALUATION")
    print("=" * 60)
    print(f"Enhancement rules: {len(enhancer.rules.rules)}")
    print()

    results = {"passed": 0, "failed": 0, "by_pattern": {}}

    for test in TEST_CASES:
        input_text = test["input"]
        expected = test["expected"]
        pattern = test["pattern"]

        if pattern not in results["by_pattern"]:
            results["by_pattern"][pattern] = {"passed": 0, "failed": 0}

        # Enhance
        enhanced = await enhancer.enhance(input_text, {})
        enhanced_text = enhanced.normalized_text

        # Classify
        result = await classifier.classify(enhanced_text, bubble_context=None)

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

        enhancement_info = ""
        if enhanced.was_enhanced:
            enhancement_info = f" [enhanced: {enhanced.rules_applied}]"

        print(f'{status} {test["id"]}: "{input_text[:40]}..."{enhancement_info}')
        if enhanced_text != input_text:
            print(f'      Enhanced: "{enhanced_text[:50]}"')
        print(f'      Expected: {expected}, Got: {actual} ({confidence:.0%})')
        print()

    # Summary
    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    total = results["passed"] + results["failed"]
    overall_pct = 100 * results["passed"] / total if total > 0 else 0
    print(f"Total: {results['passed']}/{total} ({overall_pct:.0f}%)")
    print()
    print("By Pattern:")
    for pattern, stats in sorted(results["by_pattern"].items()):
        t = stats["passed"] + stats["failed"]
        pct = 100 * stats["passed"] / t if t > 0 else 0
        threshold = 90 if pattern in ["correction", "informal"] else 80
        status = "[OK]" if pct >= threshold else "[FAIL]"
        print(f"  {status} {pattern}: {stats['passed']}/{t} ({pct:.0f}%) [target: {threshold}%]")

    print()
    print("=" * 60)
    correction_pct = results["by_pattern"].get("correction", {})
    informal_pct = results["by_pattern"].get("informal", {})
    c_rate = 100 * correction_pct.get("passed", 0) / max(1, correction_pct.get("passed", 0) + correction_pct.get("failed", 0))
    i_rate = 100 * informal_pct.get("passed", 0) / max(1, informal_pct.get("passed", 0) + informal_pct.get("failed", 0))

    if c_rate >= 90 and i_rate >= 90:
        print("VERDICT: Enhancement pipeline WORKING!")
    elif c_rate >= 60 and i_rate >= 60:
        print("VERDICT: Enhancement pipeline IMPROVING (needs tuning)")
    else:
        print("VERDICT: Enhancement pipeline needs more work")

    return results


if __name__ == "__main__":
    asyncio.run(run_evaluation())
