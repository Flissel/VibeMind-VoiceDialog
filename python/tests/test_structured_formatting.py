#!/usr/bin/env python3
"""
Test script for structured formatting tools.

Tests the LLM-based formatting functionality with different content types.
"""

import asyncio
import json
import logging
from tools.structured_formatting_tools import (
    format_idea_content,
    validate_format_schema,
    get_supported_formats,
    format_content_preview
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_formatting():
    """Test different formatting scenarios."""

    print("=" * 60)
    print("TESTING STRUCTURED FORMATTING TOOLS")
    print("=" * 60)

    # Test data
    test_cases = [
        {
            "title": "VibeMind Projektplanung",
            "content": "Ich moechte ein neues Projekt starten. Erstelle eine Bubble fuer 'KI-Chatbot', fuege Ideen fuer Features hinzu, verlinke sie sinnvoll und generiere eine Uebersicht aller Konzepte. Dann analysiere die Vor- und Nachteile der KI-Integration.",
            "format_type": "action_list",
            "description": "VibeMind-spezifische Actions"
        },
        {
            "title": "KI-Integration Analyse",
            "content": "Die Integration von KI-Modellen bringt viele Vorteile aber auch Herausforderungen. Einerseits können komplexe Aufgaben automatisiert werden, andererseits steigen die Kosten und es gibt Datenschutzbedenken. Die Genauigkeit ist hoch aber es gibt Black-Box-Probleme. Skalierbarkeit ist gut aber es braucht viel Rechenpower.",
            "format_type": "pros_cons_table",
            "description": "Vor-/Nachteile Analyse"
        },
        {
            "title": "Systemarchitektur",
            "content": "Das System besteht aus Frontend, Backend und Datenbank. Das Frontend kommuniziert mit dem Backend über REST-API. Das Backend verarbeitet Geschäftslogik und greift auf die Datenbank zu. Es gibt auch einen Cache-Layer für Performance. Sicherheit wird durch Authentifizierung und Autorisierung gewährleistet.",
            "format_type": "technical_specs",
            "description": "Technische Spezifikationen"
        }
    ]

    print(f"\nUnterstützte Formate: {get_supported_formats()}")
    print()

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test {i}: {test_case['description']} ---")
        print(f"Titel: {test_case['title']}")
        print(f"Format: {test_case['format_type']}")
        print(f"Content: {test_case['content'][:100]}...")
        print()

        try:
            # Format content
            print("[INFO] Formatiere Content...")
            result = await format_idea_content(
                test_case['content'],
                test_case['format_type'],
                test_case['title']
            )

            if result['success']:
                print("[SUCCESS] Formatierung erfolgreich!")

                # Show preview
                preview = format_content_preview(
                    result['content'],
                    test_case['format_type']
                )
                print(f"[PREVIEW] {preview}")

                # Show structured content (truncated)
                content_str = json.dumps(result['content'], indent=2, ensure_ascii=False)
                if len(content_str) > 500:
                    content_str = content_str[:500] + "\n... (truncated)"
                print(f"\n[JSON] Strukturiertes JSON:\n{content_str}")

            else:
                print(f"[ERROR] Formatierung fehlgeschlagen: {result['error']}")

        except Exception as e:
            print(f"[EXCEPTION] Fehler: {e}")

        print("-" * 50)

def test_validation():
    """Test schema validation."""
    print("\n" + "=" * 60)
    print("TESTING SCHEMA VALIDATION")
    print("=" * 60)

    # Valid action list
    valid_action_list = {
        "type": "action_list",
        "title": "Test Liste",
        "items": [
            {"task": "Erste Aufgabe", "status": "pending"},
            {"task": "Zweite Aufgabe", "status": "completed"}
        ]
    }

    # Invalid action list (missing task)
    invalid_action_list = {
        "type": "action_list",
        "items": [
            {"status": "pending"}  # Missing task
        ]
    }

    test_cases = [
        ("Valid action_list", valid_action_list, "action_list"),
        ("Invalid action_list", invalid_action_list, "action_list"),
    ]

    for name, content, format_type in test_cases:
        print(f"\n--- {name} ---")
        is_valid, error = validate_format_schema(content, format_type)
        status = "[VALID]" if is_valid else f"[INVALID] {error}"
        print(status)

async def main():
    """Run all tests."""
    print(">>> Starting Structured Formatting Tests...")

    # Test validation first (doesn't need LLM)
    test_validation()

    # Test formatting (needs LLM API)
    await test_formatting()

    print("\n>>> Tests abgeschlossen!")

if __name__ == "__main__":
    asyncio.run(main())