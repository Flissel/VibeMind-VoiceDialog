"""Test Bug 20 fix: Multi-step command detection."""

import sys
sys.path.insert(0, '.')

def test_multistep_heuristic():
    """Test the _looks_like_multi_step() heuristic."""
    print('=== Test 1: _looks_like_multi_step() Heuristic ===')
    print()

    from swarm.orchestrator.intent_orchestrator import IntentOrchestrator
    orch = IntentOrchestrator()

    test_cases = [
        # German multi-step (should detect)
        ('Geh in Space Test und erstelle eine Idee', True),
        ('Navigiere in den Space Verbesserung der Conversion AI und erstelle dort eine Notiz', True),
        ('Lösche den Space Test dann erstelle einen neuen', True),
        ('Zeige mir die Projekte und danach erstelle ein neues', True),

        # English multi-step (should detect)
        ('Navigate to Marketing and create a note', True),
        ('Go to Ideas space and add a new idea', True),
        ('First show me the projects, then create a new one', True),

        # Single actions (should NOT detect)
        ('Alle Bubbles auflisten', False),
        ('Lösche den Space Test', False),
        ('Erstelle eine neue Idee', False),
        ('Navigate to Marketing', False),
        ('Show me the projects', False),

        # Incomplete/fragments (should NOT detect)
        ('äh die ideen...', False),
        ('nein warte', False),
    ]

    passed = 0
    failed = 0

    for text, expected in test_cases:
        result = orch._looks_like_multi_step(text)
        status = '[PASS]' if result == expected else '[FAIL]'
        if result == expected:
            passed += 1
        else:
            failed += 1
        display_text = text[:50] + '...' if len(text) > 50 else text
        print(f'{status} "{display_text}" -> {result} (expected: {expected})')

    print()
    print(f'Results: {passed} passed, {failed} failed')
    return failed == 0


if __name__ == '__main__':
    success = test_multistep_heuristic()
    sys.exit(0 if success else 1)
