"""
Quick Test Script for Multi-Agent Voice System

This script tests each component individually to verify the setup.
Run this before attempting to use the full system.
"""

import os
import sys
from dotenv import load_dotenv

def test_section(title):
    """Print a test section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")

def check_env_var(var_name, required=True):
    """Check if an environment variable is set"""
    value = os.getenv(var_name)
    if value:
        # Mask API keys for security
        if "KEY" in var_name or "API" in var_name:
            display_value = value[:8] + "..." if len(value) > 8 else "***"
        else:
            display_value = value
        print(f"  OK {var_name}: {display_value}")
        return True
    else:
        if required:
            print(f"  X {var_name}: NOT SET (required)")
        else:
            print(f"  ! {var_name}: NOT SET (optional)")
        return not required

def main():
    """Run all tests"""

    print("\n" + "=" * 70)
    print("  Multi-Agent Voice System - Setup Verification")
    print("=" * 70)

    # Load environment
    load_dotenv()

    all_passed = True

    # Test 1: Environment Variables
    test_section("1. Environment Variables")

    required_vars = [
        "ELEVENLABS_API_KEY",
        "SUPERMEMORY_API_KEY",
        "AGENT_CONVERSATIONAL_MEMORY",
        "AGENT_PROJECT_MANAGER",
        "AGENT_DESKTOP_WORKER",
        "AGENT_PROJECT_WRITER",
    ]

    optional_vars = [
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "DESKTOP_AUTOMATION_HOST",
        "DESKTOP_AUTOMATION_PORT"
    ]

    for var in required_vars:
        if not check_env_var(var, required=True):
            all_passed = False

    for var in optional_vars:
        check_env_var(var, required=False)

    if not all_passed:
        print("\n  X Some required environment variables are missing!")
        print("     Please check your .env file and add the missing values.")
        print("     See MULTI_AGENT_SETUP.md for instructions.\n")
        return False

    # Test 2: Agent Configuration
    test_section("2. Agent Configuration")

    try:
        from agent_config import get_agent_registry

        registry = get_agent_registry()
        agents = registry.list_agents()

        print(f"  OK Found {len(agents)} agents:")
        for agent_name in agents:
            agent = registry.get_agent(agent_name)
            print(f"    - {agent.name}")
            print(f"      Voice: {agent.voice_id}")
            print(f"      Can handoff to: {', '.join(agent.can_handoff_to)}")

        entry_agent = registry.get_entry_agent()
        print(f"\n  OK Entry agent: {entry_agent.name}")

    except Exception as e:
        print(f"  X Agent configuration error: {e}")
        all_passed = False

    # Test 3: Supermemory Connection
    test_section("3. Supermemory Connection")

    try:
        from memory.supermemory_client import SupermemoryClient

        client = SupermemoryClient()
        print(f"  OK Supermemory client initialized")
        print(f"    API URL: {client.base_url}")

        # Try a test operation
        try:
            import uuid
            test_session = str(uuid.uuid4())

            result = client.store_user_preference(
                session_id=test_session,
                preference_key="test_key",
                preference_value="test_value"
            )
            print(f"  OK Test memory stored successfully")

        except Exception as e:
            print(f"  ! Supermemory API test failed: {e}")
            print(f"    (This may be normal if you haven't verified your API key yet)")

    except Exception as e:
        print(f"  X Supermemory client error: {e}")
        all_passed = False

    # Test 4: Desktop Client
    test_section("4. Desktop Automation Client")

    try:
        from desktop.desktop_client import DesktopClient

        client = DesktopClient()
        print(f"  OK Desktop client initialized")
        print(f"    Platform: {client.system}")
        print(f"    Server: {client.host}:{client.port}")
        print(f"    Note: This is a stub - connect to your actual automation API")

    except Exception as e:
        print(f"  X Desktop client error: {e}")
        all_passed = False

    # Test 5: Handoff Tool
    test_section("5. Handoff Tool")

    try:
        from tools.handoff_tool import HandoffTool

        # Mock conversation manager
        class MockManager:
            class Agent:
                name = "ConversationalMemory"
            current_agent = Agent()

        tool = HandoffTool(MockManager())
        schema = tool.get_schema()

        print(f"  OK Handoff tool initialized")
        print(f"    Tool name: {schema['function']['name']}")
        print(f"    Required parameters: {schema['function']['parameters']['required']}")
        print(f"    Target agents: {schema['function']['parameters']['properties']['target_agent']['enum']}")

    except Exception as e:
        print(f"  X Handoff tool error: {e}")
        all_passed = False

    # Final Summary
    print("\n" + "=" * 70)
    print("  Test Summary")
    print("=" * 70 + "\n")

    if all_passed:
        print("  OK All tests passed!")
        print("\n  Next steps:")
        print("    1. Verify your 4 agents are created in ElevenLabs dashboard")
        print("    2. Configure the handoff_to_agent client tool for each agent")
        print("    3. Test Supermemory API connection (verify API key)")
        print("    4. Run the full system when ready")
        print("\n  See MULTI_AGENT_SETUP.md for detailed instructions.\n")
        return True
    else:
        print("  X Some tests failed!")
        print("\n  Please fix the errors above before proceeding.")
        print("  See MULTI_AGENT_SETUP.md for troubleshooting.\n")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
