"""
Analysis Package - Multi-Agent Intent Analysis for VibeMind

Phase 13+: Parallel intent analysis through multiple specialized agents.

Components:
- IntentAnalysisTeam: Coordinates parallel hypothesis generation
- ReasoningAgent: Multi-step reasoning for complex intents
- ContextAgent: User context and history analysis
- SemanticAgent: NLP analysis with audio metadata integration
- UserContext: User profile and session state
"""

from swarm.analysis.user_context import (
    UserContext,
    UserContextBuilder,
)
from swarm.analysis.intent_analysis_team import (
    IntentHypothesis,
    IntentAnalysisTeam,
    get_intent_analysis_team,
)
from swarm.analysis.semantic_agent import (
    SemanticAgent,
    get_semantic_agent,
)

__all__ = [
    # User Context
    "UserContext",
    "UserContextBuilder",
    # Analysis Team
    "IntentHypothesis",
    "IntentAnalysisTeam",
    "get_intent_analysis_team",
    # Semantic Agent
    "SemanticAgent",
    "get_semantic_agent",
]
