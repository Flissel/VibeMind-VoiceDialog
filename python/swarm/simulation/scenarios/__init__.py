"""
Predefined Test Scenarios for Agent Simulation.

Provides ready-to-use scenarios for testing various aspects of the VibeMind system.
"""

from swarm.simulation.scenario_runner import ConversationTurn, SimulationScenario


# =============================================================================
# SCENARIO 1: Feature Design (Multi-Step)
# =============================================================================

FEATURE_DESIGN_SCENARIO = SimulationScenario(
    name="Feature Design",
    description="User designs a complete feature with multiple steps: create bubble, add ideas, connect them",
    tags=["multi-step", "integration", "core-flow"],
    turns=[
        ConversationTurn(
            user_input="Erstelle eine neue Bubble namens Marketing Kampagne",
            expected_intent="bubble.create",
        ),
        ConversationTurn(
            user_input="Geh in die Bubble Marketing Kampagne",
            expected_intent="bubble.enter",
            context_checks=["current_bubble == 'Marketing Kampagne'"],
        ),
        ConversationTurn(
            user_input="Erstelle eine Idee: Social Media Strategie",
            expected_intent="idea.create",
        ),
        ConversationTurn(
            user_input="Noch eine Idee: Content Kalender",
            expected_intent="idea.create",
        ),
        ConversationTurn(
            user_input="Verbinde Social Media Strategie mit Content Kalender",
            expected_intent="idea.connect",
        ),
        ConversationTurn(
            user_input="Welche Ideen hab ich jetzt?",
            expected_intent="idea.list",
        ),
        ConversationTurn(
            user_input="Erweitere die Ideen",
            expected_intent="idea.expand",
        ),
    ],
)


# =============================================================================
# SCENARIO 2: Context Awareness (Short-term)
# =============================================================================

CONTEXT_AWARENESS_SCENARIO = SimulationScenario(
    name="Context Awareness",
    description="Tests Rachel's ability to remember recent actions",
    tags=["context", "memory"],
    turns=[
        ConversationTurn(
            user_input="Erstelle eine Bubble namens Test Kontext",
            expected_intent="bubble.create",
        ),
        ConversationTurn(
            user_input="Geh in Test Kontext",
            expected_intent="bubble.enter",
        ),
        ConversationTurn(
            user_input="Erstelle eine Idee: Erste Testidee",
            expected_intent="idea.create",
        ),
        ConversationTurn(
            user_input="Welche Bubbles habe ich?",
            expected_intent="bubble.list",
            context_checks=["rachel_knows_about('Test Kontext')"],
        ),
    ],
)


# =============================================================================
# SCENARIO 3: Error Recovery
# =============================================================================

ERROR_RECOVERY_SCENARIO = SimulationScenario(
    name="Error Recovery",
    description="Tests system behavior when requesting non-existent entities",
    tags=["error-handling", "robustness"],
    turns=[
        ConversationTurn(
            user_input="Geh in Bubble XYZ123NonExistent",
            expected_intent="bubble.enter",
            expected_error=True,
        ),
        ConversationTurn(
            user_input="Welche Bubbles gibt es?",
            expected_intent="bubble.list",
        ),
        ConversationTurn(
            user_input="Verbinde Idee ABC mit Idee DEF",
            expected_intent="idea.connect",
            expected_error=True,
        ),
    ],
)


# =============================================================================
# SCENARIO 4: Navigation Flow
# =============================================================================

NAVIGATION_SCENARIO = SimulationScenario(
    name="Navigation Flow",
    description="Tests navigation between bubbles and spaces",
    tags=["navigation", "core-flow"],
    turns=[
        ConversationTurn(
            user_input="Erstelle Bubble Navigation Test",
            expected_intent="bubble.create",
        ),
        ConversationTurn(
            user_input="Geh rein",
            expected_intent="bubble.enter",
        ),
        ConversationTurn(
            user_input="Zurueck",
            expected_intent="bubble.exit",
        ),
        ConversationTurn(
            user_input="Welche Bubbles habe ich?",
            expected_intent="bubble.list",
        ),
    ],
)


# =============================================================================
# SCENARIO 5: Quick Commands
# =============================================================================

QUICK_COMMANDS_SCENARIO = SimulationScenario(
    name="Quick Commands",
    description="Tests rapid single-turn commands",
    tags=["quick", "single-turn"],
    turns=[
        ConversationTurn(
            user_input="Welche Bubbles habe ich?",
            expected_intent="bubble.list",
        ),
        ConversationTurn(
            user_input="Zeig alle Ideen",
            expected_intent="idea.list",
        ),
        ConversationTurn(
            user_input="Hallo Rachel",
            expected_intent="conversation.greeting",
        ),
        ConversationTurn(
            user_input="Was kannst du?",
            expected_intent="conversation.help",
        ),
    ],
)


# =============================================================================
# SCENARIO 6: Idea Management
# =============================================================================

IDEA_MANAGEMENT_SCENARIO = SimulationScenario(
    name="Idea Management",
    description="Tests creating, finding, and modifying ideas",
    tags=["ideas", "crud"],
    turns=[
        ConversationTurn(
            user_input="Erstelle Bubble Ideen Test",
            expected_intent="bubble.create",
        ),
        ConversationTurn(
            user_input="Geh in Ideen Test",
            expected_intent="bubble.enter",
        ),
        ConversationTurn(
            user_input="Neue Idee: Brainstorming Session",
            expected_intent="idea.create",
        ),
        ConversationTurn(
            user_input="Notiere: Wichtige Deadline naechste Woche",
            expected_intent="idea.create",
        ),
        ConversationTurn(
            user_input="Zeig alle Ideen",
            expected_intent="idea.list",
        ),
        ConversationTurn(
            user_input="Suche nach Deadline",
            expected_intent="idea.find",
        ),
    ],
)


# =============================================================================
# SCENARIO 7: Fuzzy Matching
# =============================================================================

FUZZY_MATCHING_SCENARIO = SimulationScenario(
    name="Fuzzy Matching",
    description="Tests fuzzy matching for bubble and idea names",
    tags=["fuzzy", "robustness"],
    turns=[
        ConversationTurn(
            user_input="Erstelle Bubble Projekt Management",
            expected_intent="bubble.create",
        ),
        ConversationTurn(
            user_input="Geh in Projekt",  # Partial match
            expected_intent="bubble.enter",
        ),
        ConversationTurn(
            user_input="Neue Idee: Team Meeting planen",
            expected_intent="idea.create",
        ),
        ConversationTurn(
            user_input="Suche Meeting",  # Partial match
            expected_intent="idea.find",
        ),
    ],
)


# =============================================================================
# ALL SCENARIOS
# =============================================================================

ALL_SCENARIOS = [
    FEATURE_DESIGN_SCENARIO,
    CONTEXT_AWARENESS_SCENARIO,
    ERROR_RECOVERY_SCENARIO,
    NAVIGATION_SCENARIO,
    QUICK_COMMANDS_SCENARIO,
    IDEA_MANAGEMENT_SCENARIO,
    FUZZY_MATCHING_SCENARIO,
]

# Quick test scenarios (faster execution)
QUICK_SCENARIOS = [
    QUICK_COMMANDS_SCENARIO,
    NAVIGATION_SCENARIO,
]

# Core scenarios for essential testing
CORE_SCENARIOS = [
    FEATURE_DESIGN_SCENARIO,
    NAVIGATION_SCENARIO,
    IDEA_MANAGEMENT_SCENARIO,
]


def get_scenario_by_name(name: str) -> SimulationScenario:
    """Get a scenario by name (case-insensitive)."""
    name_lower = name.lower()
    for scenario in ALL_SCENARIOS:
        if scenario.name.lower() == name_lower:
            return scenario
    raise ValueError(f"Scenario not found: {name}")


def get_scenarios_by_tag(tag: str) -> list:
    """Get all scenarios with a specific tag."""
    tag_lower = tag.lower()
    return [s for s in ALL_SCENARIOS if tag_lower in [t.lower() for t in s.tags]]


__all__ = [
    "ALL_SCENARIOS",
    "QUICK_SCENARIOS",
    "CORE_SCENARIOS",
    "FEATURE_DESIGN_SCENARIO",
    "CONTEXT_AWARENESS_SCENARIO",
    "ERROR_RECOVERY_SCENARIO",
    "NAVIGATION_SCENARIO",
    "QUICK_COMMANDS_SCENARIO",
    "IDEA_MANAGEMENT_SCENARIO",
    "FUZZY_MATCHING_SCENARIO",
    "get_scenario_by_name",
    "get_scenarios_by_tag",
]
