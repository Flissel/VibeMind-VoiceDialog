#!/usr/bin/env python3
"""
Test script for format validator functionality.
"""

from tools.structured_formatting_tools import validate_format_schema

def test_basic_validation():
    """Test basic format validation."""

    # Test valid note
    valid_note = {
        "type": "note",
        "title": "Test Note",
        "text": "This is a test note."
    }

    is_valid, error = validate_format_schema(valid_note, "note")
    print(f"Note validation: {'PASS' if is_valid else f'FAIL: {error}'}")

    # Test invalid note (missing text)
    invalid_note = {
        "type": "note",
        "title": "Test Note"
    }

    is_valid, error = validate_format_schema(invalid_note, "note")
    print(f"Invalid note validation: {'PASS (correctly rejected)' if not is_valid else 'FAIL (incorrectly accepted)'}")

    # Test kanban
    valid_kanban = {
        "type": "kanban",
        "title": "Test Board",
        "columns": [
            {"name": "Backlog", "cards": [{"title": "Test Card"}]}
        ]
    }

    is_valid, error = validate_format_schema(valid_kanban, "kanban")
    print(f"Kanban validation: {'PASS' if is_valid else f'FAIL: {error}'}")

if __name__ == "__main__":
    print("Format Validator Test")
    print("=" * 20)
    test_basic_validation()
    print("Test completed!")