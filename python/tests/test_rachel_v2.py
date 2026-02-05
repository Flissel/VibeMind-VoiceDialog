"""Test Rachel V2 activation and send_intent functionality."""

import os
import sys
sys.path.insert(0, '.')

# Enable V2 mode BEFORE importing
os.environ["RACHEL_V2"] = "true"


def test_v2_imports():
    """Test that V2 imports work correctly."""
    print("=== Test Rachel V2 Imports ===")
    print()

    from agents.rachel import (
        AGENT_CONFIG,
        get_tools,
        get_tool_definitions,
        SYSTEM_PROMPT,
        FIRST_MESSAGE
    )

    print(f"Agent: {AGENT_CONFIG['name']}")
    print(f"Tools: {list(get_tools().keys())}")
    print(f"Tool definitions: {len(get_tool_definitions())}")
    print(f"System prompt starts with: {SYSTEM_PROMPT[:50]}...")
    print(f"First message: {FIRST_MESSAGE}")
    print()

    # Verify only send_intent tool
    tools = get_tools()
    assert "send_intent" in tools, "send_intent must be in tools"
    assert len(tools) == 1, f"Expected 1 tool, got {len(tools)}"

    tool_defs = get_tool_definitions()
    assert len(tool_defs) == 1, f"Expected 1 tool definition, got {len(tool_defs)}"
    assert tool_defs[0]["name"] == "send_intent", "Tool definition must be send_intent"

    print("[PASS] V2 imports correct")
    return True


def test_send_intent():
    """Test send_intent function execution."""
    print()
    print("=== Test send_intent Execution ===")
    print()

    from agents.rachel.tools_v2 import send_intent

    # Test with a simple command
    test_cases = [
        {"user_request": "Liste alle Bubbles auf"},
        {"user_request": "Erstelle eine Bubble namens Test"},
        {"user_request": ""},  # Empty request
    ]

    for params in test_cases:
        print(f"Input: {params}")
        result = send_intent(params)
        print(f"Result: {result[:100]}...")
        print()

    print("[PASS] send_intent executed")
    return True


if __name__ == "__main__":
    print("Testing Rachel V2 Mode")
    print("=" * 50)
    print()

    success = True
    success = test_v2_imports() and success

    # Only test send_intent if imports work
    if success:
        success = test_send_intent() and success

    print()
    print("=" * 50)
    if success:
        print("All tests passed!")
    else:
        print("Some tests failed!")
        sys.exit(1)
