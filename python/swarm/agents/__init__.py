"""
Swarm Agents Package

Enhancement pipeline agents for voice input pre-processing.
Domain-specific agents are in spaces/.
"""

# Enhancement pipeline (optional, feature-flagged in orchestrator)
# - collector_agent.py: Accumulates fragmented speech
# - intent_enhancer.py: Fixes ASR errors, normalizes dialects
# - execution_validator.py: Validates results, triggers learning feedback
