"""
Test correction rule fixes - verify EASY and MEDIUM patterns are working
"""
import asyncio
import os

os.environ['FORCE_SYNC_MODE'] = 'true'
os.environ['USE_ENHANCEMENT_PIPELINE'] = 'true'
os.environ['USE_RAG_CLASSIFIER'] = 'true'


# Sample of correction tests to verify fix
TEST_CASES = [
    # Correction tests - these were failing at 20%
    {'input': 'erstelle... nein warte lösche den space', 'expected': 'bubble.delete', 'pattern': 'correction'},
    {'input': 'zeig die ideen... ach nee die spaces', 'expected': 'bubble.list', 'pattern': 'correction'},
    {'input': 'erstele... nein warte loesche', 'expected': 'idea.delete', 'pattern': 'correction'},
    {'input': 'mach weg... doch zeig erstmal', 'expected': 'idea.list', 'pattern': 'correction'},
    {'input': 'loesche... moment... erstelle idee', 'expected': 'idea.create', 'pattern': 'correction'},

    # Informal tests - were at 50%
    {'input': 'zeig mal', 'expected': 'idea.list', 'pattern': 'informal'},
    {'input': 'mach weg', 'expected': 'idea.delete', 'pattern': 'informal'},
    {'input': 'wo bin ich', 'expected': 'idea.current_space', 'pattern': 'informal'},

    # ASR tests
    {'input': 'zeig mir meine idden', 'expected': 'idea.list', 'pattern': 'asr'},
    {'input': 'erstele einen neuen speiss', 'expected': 'bubble.create', 'pattern': 'asr'},

    # Dialect tests
    {'input': 'schaug amoi de ideen an', 'expected': 'idea.list', 'pattern': 'dialect'},
    {'input': 'mach dat weg', 'expected': 'idea.delete', 'pattern': 'dialect'},
]


async def run_tests():
    from swarm.orchestrator.rag_intent_classifier import get_rag_intent_classifier
    from swarm.agents.intent_enhancer import get_intent_enhancer, reset_intent_enhancer

    # Reset and get fresh enhancer
    reset_intent_enhancer()
    enhancer = get_intent_enhancer()
    classifier = get_rag_intent_classifier()

    print(f'Enhancement rules loaded: {len(enhancer.rules.rules)}')
    print()

    results = {'passed': 0, 'failed': 0, 'by_pattern': {}}

    for test in TEST_CASES:
        input_text = test['input']
        expected = test['expected']
        pattern = test['pattern']

        if pattern not in results['by_pattern']:
            results['by_pattern'][pattern] = {'passed': 0, 'failed': 0}

        # Enhance the input
        enhanced = await enhancer.enhance(input_text, {})
        enhanced_text = enhanced.normalized_text

        # Classify
        result = await classifier.classify(enhanced_text, bubble_context=None)

        actual = result.event_type if result else 'None'
        confidence = result.confidence if result else 0
        passed = actual == expected

        if passed:
            results['passed'] += 1
            results['by_pattern'][pattern]['passed'] += 1
            status = '[OK]'
        else:
            results['failed'] += 1
            results['by_pattern'][pattern]['failed'] += 1
            status = '[FAIL]'

        enhancement_info = ''
        if enhanced.was_enhanced:
            enhancement_info = f' [enhanced: {enhanced.rules_applied}]'

        print(f'{status} [{pattern}] "{input_text}"{enhancement_info}')
        if enhanced_text != input_text:
            print(f'      Enhanced: "{enhanced_text}"')
        print(f'      Expected: {expected}, Got: {actual} ({confidence:.0%})')
        print()

    print('='*60)
    print('RESULTS')
    print('='*60)
    total = results['passed'] + results['failed']
    print(f'Total: {results["passed"]}/{total} ({100*results["passed"]/total:.0f}%)')
    print()
    for pattern, stats in results['by_pattern'].items():
        t = stats['passed'] + stats['failed']
        pct = 100 * stats['passed'] / t if t > 0 else 0
        print(f'  {pattern}: {stats["passed"]}/{t} ({pct:.0f}%)')


if __name__ == "__main__":
    asyncio.run(run_tests())
