"""
Test User Agents Tool Calling

Tests that Rachel, Antoni, and Adam correctly call their tools
when given natural language input.

Usage:
    python test_user_agents.py
    python test_user_agents.py --agent rachel
    python test_user_agents.py --verbose
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from swarm.ollama_client import get_ollama_client
from swarm.event_buffer import InputEvent
from swarm.user_agents import (
    create_rachel_agent,
    create_adam_agent,
    create_antoni_agent,
)

logger = logging.getLogger(__name__)


# Test cases for each agent
RACHEL_TESTS = [
    {
        "input": "list bubbles",
        "expected_tool": "list_bubbles",
        "description": "Direct English command",
    },
    {
        "input": "welche spaces hab ich?",
        "expected_tool": "list_bubbles",
        "description": "German question about spaces",
    },
    {
        "input": "zeig mir alle bubbles",
        "expected_tool": "list_bubbles",
        "description": "German show all bubbles",
    },
    {
        "input": "erstelle einen space namens Test",
        "expected_tool": "create_bubble",
        "description": "Create bubble in German",
    },
    {
        "input": "geh in den debug space",
        "expected_tool": "enter_bubble",
        "description": "Enter bubble in German",
    },
    {
        "input": "welche ideen hab ich?",
        "expected_tool": "list_ideas",
        "description": "List ideas in German",
    },
]

ADAM_TESTS = [
    {
        "input": "öffne chrome",
        "expected_tool": "open_app",
        "description": "Open app in German",
    },
    {
        "input": "mach einen screenshot",
        "expected_tool": "take_screenshot",
        "description": "Screenshot in German",
    },
    {
        "input": "scroll runter",
        "expected_tool": "scroll_screen",
        "description": "Scroll in German",
    },
    {
        "input": "zeig mir meine tasks",
        "expected_tool": "get_task_list",
        "description": "List tasks in German",
    },
]

ANTONI_TESTS = [
    {
        "input": "erstelle eine python funktion für fibonacci",
        "expected_tool": "generate_code",
        "description": "Generate code in German",
    },
    {
        "input": "zeig mir meine projekte",
        "expected_tool": "list_generated_projects",
        "description": "List projects in German",
    },
    {
        "input": "starte preview",
        "expected_tool": "start_preview",
        "description": "Start preview in German",
    },
]


class ToolCallTracker:
    """Tracks which tools were called during a test."""

    def __init__(self):
        self.called_tools = []
        self.tool_args = {}

    def reset(self):
        self.called_tools = []
        self.tool_args = {}

    def record_call(self, tool_name: str, args: dict = None):
        self.called_tools.append(tool_name)
        if args:
            self.tool_args[tool_name] = args


async def test_agent(agent, tests: list, agent_name: str, verbose: bool = False):
    """Test an agent with a list of test cases."""
    print(f"\n{'='*60}")
    print(f"Testing {agent_name}")
    print(f"{'='*60}")

    passed = 0
    failed = 0

    for i, test in enumerate(tests, 1):
        input_text = test["input"]
        expected_tool = test["expected_tool"]
        description = test["description"]

        print(f"\n[Test {i}] {description}")
        print(f"  Input: \"{input_text}\"")
        print(f"  Expected tool: {expected_tool}")

        try:
            # Create input event
            event = InputEvent(
                text=input_text,
                timestamp=0,
                target_space=None,
            )

            # Process input
            if verbose:
                print(f"  Processing...")

            response = await agent.process_input(event)

            # Check response for tool execution indicators
            response_lower = response.lower()

            # Heuristic: Check if the response indicates tool was called
            # This is imperfect but gives us some signal
            tool_called = False

            # Check for common tool result patterns
            if expected_tool == "list_bubbles":
                tool_called = any(x in response_lower for x in [
                    "space", "bubble", "keine", "du hast", "folgende", "hier sind",
                    "aktuell", "vorhanden", "leer", "★"
                ])
            elif expected_tool == "create_bubble":
                tool_called = any(x in response_lower for x in [
                    "erstellt", "created", "neu", "angelegt"
                ])
            elif expected_tool == "enter_bubble":
                tool_called = any(x in response_lower for x in [
                    "betreten", "entered", "gewechselt", "jetzt in", "befindest"
                ])
            elif expected_tool == "list_ideas":
                tool_called = any(x in response_lower for x in [
                    "idee", "idea", "keine", "hier sind", "folgende", "notiz"
                ])
            elif expected_tool == "open_app":
                tool_called = any(x in response_lower for x in [
                    "geöffnet", "opened", "gestartet", "launching"
                ])
            elif expected_tool == "take_screenshot":
                tool_called = any(x in response_lower for x in [
                    "screenshot", "aufgenommen", "gespeichert", "captured"
                ])
            elif expected_tool == "scroll_screen":
                tool_called = any(x in response_lower for x in [
                    "scroll", "gescrollt", "bewegt"
                ])
            elif expected_tool == "get_task_list":
                tool_called = any(x in response_lower for x in [
                    "task", "aufgabe", "keine", "hier sind", "folgende"
                ])
            elif expected_tool == "generate_code":
                tool_called = any(x in response_lower for x in [
                    "code", "generier", "erstell", "funktion", "welche sprache", "framework"
                ])
            elif expected_tool == "list_generated_projects":
                tool_called = any(x in response_lower for x in [
                    "projekt", "project", "keine", "hier sind", "folgende"
                ])
            elif expected_tool == "start_preview":
                tool_called = any(x in response_lower for x in [
                    "preview", "vorschau", "gestartet", "welches"
                ])

            # Also check if the response is NOT just a conversational deflection
            is_deflection = any(x in response_lower for x in [
                "was möchtest", "wie kann ich", "was genau", "kannst du",
                "mehr details", "verstehe nicht"
            ])

            if tool_called and not is_deflection:
                print(f"  ✓ PASSED - Tool appears to have been called")
                print(f"  Response: {response[:100]}...")
                passed += 1
            else:
                print(f"  ✗ FAILED - Tool may not have been called")
                print(f"  Response: {response[:200]}...")
                failed += 1

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1
            if verbose:
                import traceback
                traceback.print_exc()

    print(f"\n{agent_name} Results: {passed}/{passed+failed} passed")
    return passed, failed


async def run_tests(agent_filter: str = None, verbose: bool = False):
    """Run all agent tests."""
    print("="*60)
    print("VibeMind User Agent Tool Calling Tests")
    print("="*60)

    # Initialize Ollama client
    print("\nInitializing Ollama client...")
    ollama = get_ollama_client()
    model_client = ollama.client
    print(f"Using model: {ollama.model}")

    total_passed = 0
    total_failed = 0

    # Test Rachel
    if agent_filter is None or agent_filter == "rachel":
        rachel = create_rachel_agent(model_client)
        passed, failed = await test_agent(rachel, RACHEL_TESTS, "Rachel (Ideas Space)", verbose)
        total_passed += passed
        total_failed += failed

    # Test Adam
    if agent_filter is None or agent_filter == "adam":
        adam = create_adam_agent(model_client)
        passed, failed = await test_agent(adam, ADAM_TESTS, "Adam (Desktop Space)", verbose)
        total_passed += passed
        total_failed += failed

    # Test Antoni
    if agent_filter is None or agent_filter == "antoni":
        antoni = create_antoni_agent(model_client)
        passed, failed = await test_agent(antoni, ANTONI_TESTS, "Antoni (Coding Space)", verbose)
        total_passed += passed
        total_failed += failed

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total: {total_passed}/{total_passed+total_failed} tests passed")

    if total_failed == 0:
        print("\n✓ All tests passed!")
    else:
        print(f"\n✗ {total_failed} tests failed")

    return total_failed == 0


async def interactive_test(agent_name: str = "rachel"):
    """Interactive testing mode for a single agent."""
    print("="*60)
    print(f"Interactive Test Mode - {agent_name.capitalize()}")
    print("="*60)
    print("Type messages to test tool calling. Type 'quit' to exit.\n")

    # Initialize
    ollama = get_ollama_client()
    model_client = ollama.client
    print(f"Using model: {ollama.model}\n")

    # Create agent
    if agent_name == "rachel":
        agent = create_rachel_agent(model_client)
    elif agent_name == "adam":
        agent = create_adam_agent(model_client)
    elif agent_name == "antoni":
        agent = create_antoni_agent(model_client)
    else:
        print(f"Unknown agent: {agent_name}")
        return

    while True:
        try:
            user_input = input(f"[{agent_name}] You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit"):
                break

            event = InputEvent(
                text=user_input,
                timestamp=0,
                target_space=None,
            )

            print("Processing...")
            response = await agent.process_input(event)
            print(f"[{agent_name.capitalize()}]: {response}\n")

        except KeyboardInterrupt:
            break
        except EOFError:
            break

    print("Goodbye!")


def main():
    parser = argparse.ArgumentParser(
        description="Test User Agent Tool Calling"
    )
    parser.add_argument(
        "--agent",
        choices=["rachel", "adam", "antoni"],
        help="Test only a specific agent",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Interactive testing mode",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.interactive:
        asyncio.run(interactive_test(args.agent or "rachel"))
    else:
        success = asyncio.run(run_tests(args.agent, args.verbose))
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
