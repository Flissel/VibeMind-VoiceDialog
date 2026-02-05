"""Test Bug 21 fix: Action verb detection for short commands."""

import asyncio
import sys
sys.path.insert(0, '.')

from swarm.agents.collector_agent import CollectorAgent, CollectorConfig


async def test_action_verb_detection():
    """Test that commands starting with action verbs skip accumulation."""
    print('=== Test Bug 21: Action Verb Detection ===')
    print()

    config = CollectorConfig()
    agent = CollectorAgent(config)

    test_cases = [
        # Short commands with action verbs (should NOT accumulate)
        ('geh rein', False),
        ('zeig alle', False),
        ('liste bubbles', False),
        ('erstelle test', False),
        ('loesche das', False),
        ('navigiere home', False),
        ('zurueck', False),
        ('back', False),
        ('show all', False),
        ('delete this', False),
        ('alle bubbles', False),

        # Short commands without action verbs (SHOULD accumulate)
        ('die ideen', True),
        ('nein warte', True),
        ('aeh...', True),
        ('hmm okay', True),

        # Medium length commands with action verbs (should NOT accumulate)
        ('geh in den test space', False),
        ('zeige mir die ideen', False),
        ('erstelle eine neue bubble', False),

        # Very long commands (should never accumulate)
        ('erstelle eine neue bubble mit dem namen marketing kampagne strategie', False),
    ]

    passed = 0
    failed = 0

    for text, expected in test_cases:
        result = await agent.should_accumulate(text)
        status = '[PASS]' if result == expected else '[FAIL]'
        if result == expected:
            passed += 1
        else:
            failed += 1
        display_text = text[:40] + '...' if len(text) > 40 else text
        print(f'{status} "{display_text}" -> accumulate={result} (expected: {expected})')

    print()
    print(f'Results: {passed} passed, {failed} failed')
    return failed == 0


if __name__ == '__main__':
    success = asyncio.run(test_action_verb_detection())
    sys.exit(0 if success else 1)
