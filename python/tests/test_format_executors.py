"""Test that format executors are loaded correctly."""
import sys
sys.path.insert(0, '.')

from swarm.orchestrator.intent_orchestrator import IntentOrchestrator

print("Testing format executor loading...")
print()

orch = IntentOrchestrator()

# Check format executors
format_intents = [k for k in orch._tool_executors.keys() if 'format' in k]
print(f'Format executors loaded: {len(format_intents)}')
for intent in sorted(format_intents):
    print(f'  - {intent}')

print()
# Test a format call
print("Testing idea.format_table executor...")
result = orch._tool_executors.get("idea.format_table")
print(f"  Executor exists: {result is not None}")

if result:
    print("  Executor function:", result.__name__)
