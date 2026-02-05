"""
Test Tool Execution - Verifies that backend agent tools actually execute.

This test directly calls tools without Redis to verify they work.
"""

import os
import sys

# Add paths
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("TEST: Direct Tool Execution (ohne Redis)")
print("=" * 60)


def test_bubble_tools():
    """Test bubble tools directly."""
    print("\n--- Bubble Tools ---")

    from swarm.tools.adapted_bubble_tools import BUBBLE_TOOLS

    # Find list_bubbles
    list_bubbles = next((t for t in BUBBLE_TOOLS if t.__name__ == "list_bubbles"), None)
    if list_bubbles:
        try:
            result = list_bubbles()
            print(f"list_bubbles(): {result}")
            return True
        except Exception as e:
            print(f"list_bubbles() ERROR: {e}")
            return False
    else:
        print("list_bubbles not found!")
        return False


def test_idea_tools():
    """Test idea tools directly."""
    print("\n--- Idea Tools ---")

    from swarm.tools.adapted_idea_tools import IDEA_TOOLS

    # Find list_ideas
    list_ideas = next((t for t in IDEA_TOOLS if t.__name__ == "list_ideas"), None)
    if list_ideas:
        try:
            result = list_ideas()
            print(f"list_ideas(): {result}")
            return True
        except Exception as e:
            print(f"list_ideas() ERROR: {e}")
            return False
    else:
        print("list_ideas not found!")
        return False


def test_coding_tools():
    """Test coding tools directly."""
    print("\n--- Coding Tools ---")

    from swarm.tools.adapted_coding_tools import CODING_TOOLS

    # Find list_generated_projects
    list_projects = next((t for t in CODING_TOOLS if t.__name__ == "list_generated_projects"), None)
    if list_projects:
        try:
            result = list_projects()
            print(f"list_generated_projects(): {result}")
            return True
        except Exception as e:
            print(f"list_generated_projects() ERROR: {e}")
            return False
    else:
        print("list_generated_projects not found!")
        return False


def test_backend_agent_tool_execution():
    """Test that backend agents can execute their tools."""
    print("\n--- Backend Agent Tool Execution ---")

    from swarm.backend_agents import IdeasAgent, CodingAgent

    # Test IdeasAgent
    ideas_agent = IdeasAgent()
    print(f"\nIdeasAgent has {len(ideas_agent.tools)} tools")

    # Try to execute list_bubbles via agent
    tool = ideas_agent.tools.get("list_bubbles")
    if tool:
        try:
            result = tool()
            print(f"  IdeasAgent.tools['list_bubbles'](): {result[:100]}...")
            return True
        except Exception as e:
            print(f"  IdeasAgent.tools['list_bubbles']() ERROR: {e}")
            return False
    else:
        print("  list_bubbles not in IdeasAgent.tools")
        return False


if __name__ == "__main__":
    results = []

    results.append(("Bubble Tools", test_bubble_tools()))
    results.append(("Idea Tools", test_idea_tools()))
    results.append(("Coding Tools", test_coding_tools()))
    results.append(("Backend Agent Execution", test_backend_agent_tool_execution()))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    passed_count = sum(1 for _, p in results if p)
    print(f"\n{passed_count}/{len(results)} tool execution tests passed")
