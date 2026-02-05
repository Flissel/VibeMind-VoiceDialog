"""Debug contextual rule application."""
import asyncio
import os
os.environ['FORCE_SYNC_MODE'] = 'true'
os.environ['USE_ENHANCEMENT_PIPELINE'] = 'true'

from swarm.agents.intent_enhancer import get_intent_enhancer, reset_intent_enhancer

async def test():
    reset_intent_enhancer()
    enhancer = get_intent_enhancer()

    # Debug contextual rule
    input_text = 'die sache von vorhin zeigen'
    result = await enhancer.enhance(input_text, {})

    print(f'Input: "{input_text}"')
    print(f'Enhanced: "{result.normalized_text}"')
    print(f'Rules applied: {result.rules_applied}')
    print(f'Was enhanced: {result.was_enhanced}')

    # Check ctx_002 rule
    for rule in enhancer.rules.rules.values():
        if rule.id == 'ctx_002':
            print(f'\nRule ctx_002:')
            print(f'  Pattern: "{rule.pattern}"')
            print(f'  Replacement: "{rule.replacement}"')
            print(f'  Active: {rule.active}')
            print(f'  Category: {rule.category}')

            # Test if pattern matches
            import re
            matches = rule.pattern in input_text.lower()
            print(f'  Pattern in input: {matches}')

asyncio.run(test())
