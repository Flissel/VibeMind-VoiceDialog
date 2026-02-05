"""
Intent→Tool Test Case Definitions

Complete test cases for ALL 72 intent types in VibeMind.
Each test case defines:
- intent_type: Expected classification result
- user_input: German voice input to classify
- expected_params: Parameters that should be extracted
- expected_tool: Tool function that should execute
- validation_event: UI event that should be emitted (optional)
- validation_keywords: Keywords expected in result (optional)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class IntentToolTestCase:
    """Single intent→tool test case."""
    intent_type: str
    user_input: str
    expected_params: Dict[str, Any]
    expected_tool: str
    validation_event: Optional[str] = None
    validation_keywords: List[str] = field(default_factory=list)
    category: str = ""
    difficulty: str = "easy"  # easy, medium, hard


# =============================================================================
# BUBBLE.* TEST CASES (11 intents)
# =============================================================================

BUBBLE_TEST_CASES = [
    IntentToolTestCase(
        intent_type="bubble.list",
        user_input="Zeig mir meine Spaces",
        expected_params={},
        expected_tool="list_bubbles",
        validation_keywords=["Space", "Bubble", "keine"],
        category="bubble",
    ),
    IntentToolTestCase(
        intent_type="bubble.list",
        user_input="Liste alle Bubbles auf",
        expected_params={},
        expected_tool="list_bubbles",
        validation_keywords=["Space", "Bubble"],
        category="bubble",
        difficulty="easy",
    ),
    IntentToolTestCase(
        intent_type="bubble.create",
        user_input="Erstelle einen Space für Marketing",
        expected_params={"title": "Marketing"},
        expected_tool="create_bubble",
        validation_event="node_added",
        category="bubble",
    ),
    IntentToolTestCase(
        intent_type="bubble.create",
        user_input="Neuer Space Projektplanung",
        expected_params={"title": "Projektplanung"},
        expected_tool="create_bubble",
        validation_event="node_added",
        category="bubble",
        difficulty="medium",
    ),
    IntentToolTestCase(
        intent_type="bubble.enter",
        user_input="Geh in den Marketing Space",
        expected_params={"bubble_name": "Marketing"},
        expected_tool="enter_bubble",
        validation_event="space_changed",
        category="bubble",
    ),
    IntentToolTestCase(
        intent_type="bubble.enter",
        user_input="Öffne Projektplanung",
        expected_params={"bubble_name": "Projektplanung"},
        expected_tool="enter_bubble",
        validation_event="space_changed",
        category="bubble",
        difficulty="medium",
    ),
    IntentToolTestCase(
        intent_type="bubble.exit",
        user_input="Zurück zum Multiverse",
        expected_params={},
        expected_tool="exit_bubble",
        validation_event="space_changed",
        category="bubble",
    ),
    IntentToolTestCase(
        intent_type="bubble.exit",
        user_input="Geh raus aus dem Space",
        expected_params={},
        expected_tool="exit_bubble",
        validation_event="space_changed",
        category="bubble",
    ),
    IntentToolTestCase(
        intent_type="bubble.delete",
        user_input="Lösche den Marketing Space",
        expected_params={"bubble_name": "Marketing"},
        expected_tool="delete_bubble",
        validation_event="node_deleted",
        category="bubble",
    ),
    IntentToolTestCase(
        intent_type="bubble.delete_all_except",
        user_input="Lösche alle Spaces außer Marketing",
        expected_params={"except_name": "Marketing"},
        expected_tool="delete_all_bubbles_except",
        category="bubble",
        difficulty="hard",
    ),
    IntentToolTestCase(
        intent_type="bubble.stats",
        user_input="Zeig mir die Statistiken der Bubble",
        expected_params={},
        expected_tool="get_bubble_stats",
        validation_keywords=["Ideen", "Nodes"],
        category="bubble",
    ),
    IntentToolTestCase(
        intent_type="bubble.update",
        user_input="Benenne den Space um zu Sales",
        expected_params={"new_title": "Sales"},
        expected_tool="update_bubble",
        validation_event="node_updated",
        category="bubble",
    ),
    IntentToolTestCase(
        intent_type="bubble.current",
        user_input="Wo bin ich gerade?",
        expected_params={},
        expected_tool="get_current_space",
        validation_keywords=["Multiverse", "Space", "inside"],
        category="bubble",
    ),
]


# =============================================================================
# IDEA.* TEST CASES - CRUD (10 intents)
# =============================================================================

IDEA_CRUD_TEST_CASES = [
    IntentToolTestCase(
        intent_type="idea.create",
        user_input="Notiere: API Design Konzept",
        expected_params={"title": "API Design Konzept"},
        expected_tool="create_idea",
        validation_event="node_added",
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.create",
        user_input="Neue Idee für Datenbankstruktur",
        expected_params={"title": "Datenbankstruktur"},
        expected_tool="create_idea",
        validation_event="node_added",
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.list",
        user_input="Zeig mir alle Ideen",
        expected_params={},
        expected_tool="list_ideas",
        validation_keywords=["Idee", "Node"],
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.list",
        user_input="Was habe ich notiert?",
        expected_params={},
        expected_tool="list_ideas",
        category="idea",
        difficulty="medium",
    ),
    IntentToolTestCase(
        intent_type="idea.find",
        user_input="Finde die Idee API Design",
        expected_params={"query": "API Design"},
        expected_tool="find_idea",
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.find",
        user_input="Suche nach Datenbankstruktur",
        expected_params={"query": "Datenbankstruktur"},
        expected_tool="find_idea",
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.delete",
        user_input="Lösche die Idee API Design",
        expected_params={"idea_name": "API Design"},
        expected_tool="delete_idea",
        validation_event="node_deleted",
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.update",
        user_input="Update API Design mit REST Endpoints",
        expected_params={"idea_name": "API Design", "topic": "REST Endpoints", "mode": "generate"},
        expected_tool="update_idea",
        validation_event="node_updated",
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.update",
        user_input="Schreib in die Idee: Das ist der neue Inhalt",
        expected_params={"new_content": "Das ist der neue Inhalt", "mode": "literal"},
        expected_tool="update_idea",
        validation_event="node_updated",
        category="idea",
        difficulty="hard",
    ),
    IntentToolTestCase(
        intent_type="idea.count",
        user_input="Wie viele Ideen habe ich?",
        expected_params={},
        expected_tool="count_ideas",
        validation_keywords=["Ideen", "0", "1", "2"],
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.expand",
        user_input="Erweitere die Ideen",
        expected_params={},
        expected_tool="expand_ideas",
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.move",
        user_input="Verschiebe die Idee nach rechts",
        expected_params={"direction": "right"},
        expected_tool="move_idea",
        category="idea",
        difficulty="medium",
    ),
]


# =============================================================================
# IDEA.* TEST CASES - CONNECTIONS (4 intents)
# =============================================================================

IDEA_CONNECTION_TEST_CASES = [
    IntentToolTestCase(
        intent_type="idea.connect",
        user_input="Verbinde API Design mit Datenbankstruktur",
        expected_params={"idea1": "API Design", "idea2": "Datenbankstruktur"},
        expected_tool="connect_ideas",
        validation_event="edge_created",
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.link_to_root",
        user_input="Verknüpfe das mit dem Root",
        expected_params={},
        expected_tool="link_idea_to_root",
        validation_event="edge_created",
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.auto_link",
        user_input="Verlinke die Ideen automatisch",
        expected_params={},
        expected_tool="auto_link_ideas",
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.auto_link",
        user_input="Verbinde alle Ideen sinnvoll",
        expected_params={},
        expected_tool="auto_link_ideas",
        category="idea",
        difficulty="medium",
    ),
    IntentToolTestCase(
        intent_type="idea.analyze_links",
        user_input="Analysiere die Verbindungen",
        expected_params={},
        expected_tool="analyze_and_suggest_links",
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.classify",
        user_input="Klassifiziere die Idee",
        expected_params={},
        expected_tool="classify_idea",
        category="idea",
    ),
    IntentToolTestCase(
        intent_type="idea.classify",
        user_input="Send das ans Backend zur Analyse",
        expected_params={},
        expected_tool="classify_idea",
        category="idea",
        difficulty="medium",
    ),
]


# =============================================================================
# IDEA.* TEST CASES - FORMATTING (12 intents)
# =============================================================================

IDEA_FORMAT_TEST_CASES = [
    IntentToolTestCase(
        intent_type="idea.summarize",
        user_input="Fasse die Idee zusammen",
        expected_params={},
        expected_tool="summarize_idea",
        category="idea_format",
    ),
    IntentToolTestCase(
        intent_type="idea.whitepaper",
        user_input="Erstelle ein Whitepaper",
        expected_params={},
        expected_tool="generate_white_paper",
        category="idea_format",
    ),
    IntentToolTestCase(
        intent_type="idea.format_table",
        user_input="Formatiere das als Tabelle",
        expected_params={},
        expected_tool="format_idea_table",
        validation_event="node_structured_update",
        category="idea_format",
    ),
    IntentToolTestCase(
        intent_type="idea.format_note",
        user_input="Formatiere das als Notiz",
        expected_params={},
        expected_tool="format_idea_note",
        validation_event="node_structured_update",
        category="idea_format",
    ),
    IntentToolTestCase(
        intent_type="idea.format_action_list",
        user_input="Mach daraus eine Aktionsliste",
        expected_params={},
        expected_tool="format_idea_action_list",
        validation_event="node_structured_update",
        category="idea_format",
    ),
    IntentToolTestCase(
        intent_type="idea.format_pros_cons",
        user_input="Erstelle eine Pro-Contra Liste",
        expected_params={},
        expected_tool="format_idea_pros_cons",
        validation_event="node_structured_update",
        category="idea_format",
    ),
    IntentToolTestCase(
        intent_type="idea.format_hierarchy",
        user_input="Zeig das hierarchisch an",
        expected_params={},
        expected_tool="format_idea_hierarchy",
        validation_event="node_structured_update",
        category="idea_format",
    ),
    IntentToolTestCase(
        intent_type="idea.format_specs",
        user_input="Formatiere das als Spezifikation",
        expected_params={},
        expected_tool="format_idea_specs",
        validation_event="node_structured_update",
        category="idea_format",
    ),
    IntentToolTestCase(
        intent_type="idea.convert_format",
        user_input="Konvertiere zu Markdown",
        expected_params={"target_format": "markdown"},
        expected_tool="convert_format",
        category="idea_format",
    ),
    IntentToolTestCase(
        intent_type="idea.list_formats",
        user_input="Welche Formate gibt es?",
        expected_params={},
        expected_tool="list_available_formats",
        category="idea_format",
    ),
    IntentToolTestCase(
        intent_type="idea.current_space",
        user_input="In welchem Space bin ich?",
        expected_params={},
        expected_tool="get_current_space",
        category="idea",
    ),
]


# =============================================================================
# SYSTEM.* TEST CASES (6 intents)
# =============================================================================

SYSTEM_TEST_CASES = [
    IntentToolTestCase(
        intent_type="system.status",
        user_input="Zeig mir den Systemstatus",
        expected_params={},
        expected_tool="get_system_status",
        validation_keywords=["System", "Operationen", "Fehler"],
        category="system",
    ),
    IntentToolTestCase(
        intent_type="system.active_tasks",
        user_input="Welche Tasks laufen gerade?",
        expected_params={},
        expected_tool="list_active_tasks",
        category="system",
    ),
    IntentToolTestCase(
        intent_type="system.queue_status",
        user_input="Wie ist der Queue Status?",
        expected_params={},
        expected_tool="get_queue_status",
        category="system",
    ),
    IntentToolTestCase(
        intent_type="system.recent_completions",
        user_input="Zeig die letzten abgeschlossenen Aufgaben",
        expected_params={},
        expected_tool="get_recent_completions",
        category="system",
    ),
    IntentToolTestCase(
        intent_type="system.check_stuck",
        user_input="Gibt es hängende Operationen?",
        expected_params={},
        expected_tool="check_stuck_operations",
        category="system",
    ),
]


# =============================================================================
# TASK.* TEST CASES (4 intents)
# =============================================================================

TASK_TEST_CASES = [
    IntentToolTestCase(
        intent_type="task.list_today",
        user_input="Was steht heute an?",
        expected_params={},
        expected_tool="get_tasks_today",
        category="task",
    ),
    IntentToolTestCase(
        intent_type="task.recent",
        user_input="Zeig mir die letzten Aufgaben",
        expected_params={},
        expected_tool="get_recent_tasks",
        category="task",
    ),
    IntentToolTestCase(
        intent_type="task.search",
        user_input="Suche nach Task Marketing",
        expected_params={"query": "Marketing"},
        expected_tool="search_task_history",
        category="task",
    ),
    IntentToolTestCase(
        intent_type="task.stats",
        user_input="Zeig mir die Task Statistiken",
        expected_params={},
        expected_tool="get_task_stats",
        category="task",
    ),
]


# =============================================================================
# CONVERSATION.* TEST CASES (2 intents - voice handled, no tool)
# =============================================================================

CONVERSATION_TEST_CASES = [
    IntentToolTestCase(
        intent_type="conversation.greeting",
        user_input="Hallo Rachel",
        expected_params={},
        expected_tool="",  # No tool, handled by voice agent
        category="conversation",
    ),
    IntentToolTestCase(
        intent_type="conversation.help",
        user_input="Was kannst du alles?",
        expected_params={},
        expected_tool="",  # No tool, handled by voice agent
        category="conversation",
    ),
]


# =============================================================================
# NATURAL SPEECH VARIANTS (harder classification)
# =============================================================================

NATURAL_SPEECH_TEST_CASES = [
    # Incomplete sentences
    IntentToolTestCase(
        intent_type="idea.list",
        user_input="äh die ideen... zeigen oder so",
        expected_params={},
        expected_tool="list_ideas",
        category="natural",
        difficulty="hard",
    ),
    # Filler words
    IntentToolTestCase(
        intent_type="bubble.create",
        user_input="also ähm erstell mal so einen Space für äh Marketing",
        expected_params={"title": "Marketing"},
        expected_tool="create_bubble",
        category="natural",
        difficulty="hard",
    ),
    # Mixed German-English
    IntentToolTestCase(
        intent_type="idea.create",
        user_input="Create eine neue Idee für das Backend Design",
        expected_params={"title": "Backend Design"},
        expected_tool="create_idea",
        category="natural",
        difficulty="hard",
    ),
    # Informal speech
    IntentToolTestCase(
        intent_type="bubble.enter",
        user_input="geh mal in marketing rein",
        expected_params={"bubble_name": "Marketing"},
        expected_tool="enter_bubble",
        category="natural",
        difficulty="hard",
    ),
    # ASR-like transcription errors
    IntentToolTestCase(
        intent_type="idea.connect",
        user_input="verbinde api desain mit datenbank struktur",
        expected_params={"idea1": "api desain", "idea2": "datenbank struktur"},
        expected_tool="connect_ideas",
        category="natural",
        difficulty="hard",
    ),
]


# =============================================================================
# ALL TEST CASES COMBINED
# =============================================================================

ALL_TEST_CASES: List[IntentToolTestCase] = (
    BUBBLE_TEST_CASES +
    IDEA_CRUD_TEST_CASES +
    IDEA_CONNECTION_TEST_CASES +
    IDEA_FORMAT_TEST_CASES +
    SYSTEM_TEST_CASES +
    TASK_TEST_CASES +
    CONVERSATION_TEST_CASES +
    NATURAL_SPEECH_TEST_CASES
)

# Group by category for reporting
TEST_CASES_BY_CATEGORY = {
    "bubble": BUBBLE_TEST_CASES,
    "idea": IDEA_CRUD_TEST_CASES + IDEA_CONNECTION_TEST_CASES,
    "idea_format": IDEA_FORMAT_TEST_CASES,
    "system": SYSTEM_TEST_CASES,
    "task": TASK_TEST_CASES,
    "conversation": CONVERSATION_TEST_CASES,
    "natural": NATURAL_SPEECH_TEST_CASES,
}

# Get intent types that have test coverage
COVERED_INTENTS = set(tc.intent_type for tc in ALL_TEST_CASES)

# Statistics
def get_coverage_stats():
    """Get test coverage statistics."""
    by_intent = {}
    for tc in ALL_TEST_CASES:
        if tc.intent_type not in by_intent:
            by_intent[tc.intent_type] = 0
        by_intent[tc.intent_type] += 1

    by_difficulty = {"easy": 0, "medium": 0, "hard": 0}
    for tc in ALL_TEST_CASES:
        by_difficulty[tc.difficulty] += 1

    return {
        "total_tests": len(ALL_TEST_CASES),
        "unique_intents": len(by_intent),
        "tests_per_intent": by_intent,
        "by_difficulty": by_difficulty,
        "by_category": {k: len(v) for k, v in TEST_CASES_BY_CATEGORY.items()},
    }


if __name__ == "__main__":
    stats = get_coverage_stats()
    print(f"Total test cases: {stats['total_tests']}")
    print(f"Unique intents covered: {stats['unique_intents']}")
    print(f"\nBy category:")
    for cat, count in stats['by_category'].items():
        print(f"  {cat}: {count}")
    print(f"\nBy difficulty:")
    for diff, count in stats['by_difficulty'].items():
        print(f"  {diff}: {count}")
