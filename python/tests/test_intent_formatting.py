#!/usr/bin/env python3
"""
Test script for Intent Classifier structured formatting recognition.
"""

import asyncio
import logging
from swarm.orchestrator.intent_classifier import get_intent_classifier

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_formatting_intents():
    """Test recognition of formatting intents."""

    print("=" * 60)
    print("TESTING INTENT CLASSIFIER - STRUCTURED FORMATTING")
    print("=" * 60)

    classifier = get_intent_classifier()

    # Test cases for structured formatting
    test_cases = [
        {
            "input": "Formatiere die Ideen in Aktionslisten",
            "expected_event": "idea.format",
            "expected_format": "action_list"
        },
        {
            "input": "Erstelle eine Tabelle mit Vorteilen und Nachteilen",
            "expected_event": "idea.format",
            "expected_format": "pros_cons_table"
        },
        {
            "input": "Konvertiere die Notizen in technische Spezifikationen",
            "expected_event": "idea.format",
            "expected_format": "technical_specs"
        },
        {
            "input": "Organisiere alle Ideen hierarchisch",
            "expected_event": "idea.structure",
            "expected_operation": "complex_structure"
        },
        {
            "input": "Erstelle eine Übersicht aller Konzepte",
            "expected_event": "idea.structure",
            "expected_operation": "complex_structure"
        }
    ]

    print(f"\nTeste {len(test_cases)} Formatierungsanfragen:")
    print()

    for i, test_case in enumerate(test_cases, 1):
        print(f"--- Test {i}: {test_case['input']} ---")

        try:
            result = await classifier.classify(test_case['input'])

            event_type = result.get('event_type', 'unknown')
            payload = result.get('payload', {})

            # Check if classification matches expectation
            success = event_type == test_case['expected_event']

            if test_case['expected_event'] == 'idea.format':
                format_type = payload.get('format_type') or payload.get('target_format')
                success = success and format_type == test_case['expected_format']
                print(f"Event: {event_type} | Format: {format_type} | Expected: {test_case['expected_format']}")
            elif test_case['expected_event'] == 'idea.structure':
                operation = payload.get('operation')
                success = success and operation == test_case['expected_operation']
                print(f"Event: {event_type} | Operation: {operation} | Expected: {test_case['expected_operation']}")

            status = "[SUCCESS]" if success else "[FAILED]"
            print(f"Status: {status}")

            if not success:
                print(f"Expected: {test_case['expected_event']}")
                print(f"Got: {event_type}")
                print(f"Payload: {payload}")

        except Exception as e:
            print(f"[ERROR] Exception: {e}")

        print("-" * 50)

    print("\nIntent Classifier Testing abgeschlossen!")

if __name__ == "__main__":
    asyncio.run(test_formatting_intents())