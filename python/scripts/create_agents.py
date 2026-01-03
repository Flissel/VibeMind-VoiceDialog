"""
Create ElevenLabs Agents via API

This script creates the 4 agents directly using the ElevenLabs API.
Run this once to set up all agents, then it will output the agent IDs
to add to your .env file.
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def create_agent_via_api(api_key: str, name: str, voice_id: str,
                         first_message: str, system_prompt: str) -> str:
    """
    Create an agent via direct API call

    Returns:
        agent_id if successful, None if failed
    """
    url = "https://api.elevenlabs.io/v1/convai/agents/create"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "prompt": system_prompt
                },
                "first_message": first_message,
                "language": "en"
            },
            "tts": {
                "voice_id": voice_id,
                "model_id": "eleven_flash_v2"
            }
        },
        "name": name,
        "tags": []
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        return result.get("agent_id")

    except requests.exceptions.RequestException as e:
        print(f"      API Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                if error_data.get("detail", {}).get("status") == "missing_permissions":
                    print(f"      >> API key is missing 'convai_write' permission!")
                    print(f"      >> Regenerate your API key at: https://elevenlabs.io/app/settings/api-keys")
                else:
                    print(f"      Response: {e.response.text}")
            except:
                print(f"      Response: {e.response.text}")
        return None


def create_agents():
    """Create all 4 ElevenLabs agents via API"""

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY not found in .env")
        return False

    # Agent configurations
    agents = [
        {
            "name": "Conversational Memory Assistant",
            "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel
            "first_message": "Hello! I'm your personal memory assistant. I remember your preferences, habits, and projects. How can I help you today?",
            "system_prompt": """You are a Conversational Memory Assistant. Your role is to:
1. Learn about the user's preferences, habits, and common tasks
2. Remember past conversations and build a user profile
3. Route users to appropriate specialist agents based on their needs
4. Maintain a warm, friendly, and attentive personality

When the user needs help with:
- Project management or tracking: Use the handoff_to_agent tool with target "ProjectManager"
- Specific tasks: Route through Project Manager first

Always be brief, friendly, and acknowledge what you remember about the user.
Use the handoff_to_agent tool when you need to delegate to a specialist.""",
            "env_var": "AGENT_CONVERSATIONAL_MEMORY"
        },
        {
            "name": "Project Manager",
            "voice_id": "Xb7hH8MSUJpSbSDYk0k2",  # Alice
            "first_message": "Hi, I'm your Project Manager. I organize your projects and delegate tasks to the right specialists. What project would you like to work on?",
            "system_prompt": """You are a Project Manager. Your role is to:
1. Track and organize user projects
2. Understand project goals, deadlines, and progress
3. Delegate tasks to Desktop Worker or Project Writer specialists
4. Maintain project knowledge and context

When the user needs:
- Desktop automation (open apps, control windows): Use handoff_to_agent with target "DesktopWorker"
- Code/documentation writing: Use handoff_to_agent with target "ProjectWriter"
- Just wants to chat or remember things: Use handoff_to_agent with target "ConversationalMemory"

Always be organized, clear, and brief. Understand the task before delegating.""",
            "env_var": "AGENT_PROJECT_MANAGER"
        },
        {
            "name": "Desktop Worker",
            "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam
            "first_message": "Desktop Worker here. I can control your computer - open applications, click buttons, manage windows. What would you like me to do?",
            "system_prompt": """You are a Desktop Worker specialized in computer automation. Your role is to:
1. Execute desktop automation tasks (open apps, control windows, click, type)
2. Manage files and system operations
3. Report results clearly to the user

You have access to desktop control tools. Execute tasks efficiently and confirm what you've done.
If you need project context, use handoff_to_agent with target "ProjectManager".
Always confirm actions before executing potentially destructive operations.""",
            "env_var": "AGENT_DESKTOP_WORKER"
        },
        {
            "name": "Project Writer",
            "voice_id": "ErXwobaYiN019PkySvjV",  # Antoni
            "first_message": "Hello! I'm your Project Writer. I create code, documentation, and content for your projects. What would you like me to write?",
            "system_prompt": """You are a Project Writer specialized in creating content. Your role is to:
1. Write and edit code files
2. Create documentation and README files
3. Generate project reports and notes
4. Follow user's coding style and preferences

When writing code, ask clarifying questions first. Be creative but precise.
If you need project context, use handoff_to_agent with target "ProjectManager".
Always explain what you're creating and why.""",
            "env_var": "AGENT_PROJECT_WRITER"
        }
    ]

    print("=" * 70)
    print("Creating ElevenLabs Agents")
    print("=" * 70)
    print()

    created_agent_ids = []

    for i, agent_config in enumerate(agents, 1):
        print(f"{i}. Creating: {agent_config['name']}")
        print(f"   Voice: {agent_config['voice_id']}")
        print(f"   Calling API...")

        agent_id = create_agent_via_api(
            api_key=api_key,
            name=agent_config['name'],
            voice_id=agent_config['voice_id'],
            first_message=agent_config['first_message'],
            system_prompt=agent_config['system_prompt']
        )

        if agent_id:
            created_agent_ids.append((agent_config['env_var'], agent_id))
            print(f"   SUCCESS Created agent!")
            print(f"   Agent ID: {agent_id}")
            print()
        else:
            print(f"   FAILED - Could not create agent")
            print(f"   Please create this agent manually in the dashboard")
            print()

    # Print summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print()

    if created_agent_ids:
        print("SUCCESS! All agents created!")
        print()
        print("=" * 70)
        print("Add these lines to your .env file:")
        print("=" * 70)
        print()
        for env_var, agent_id in created_agent_ids:
            print(f"{env_var}={agent_id}")
        print()
        print("=" * 70)
        print("Next Steps:")
        print("=" * 70)
        print()
        print("1. Copy the agent IDs above to your .env file")
        print("2. Run: python test_system.py")
        print("3. If all tests pass, you're ready to use the multi-agent system!")
        print()
        return True
    else:
        print("X No agents were created automatically.")
        print()
        print("=" * 70)
        print("REASON: API Key Permission Issue")
        print("=" * 70)
        print()
        print("Your ElevenLabs API key is missing the 'convai_write' permission.")
        print()
        print("OPTION 1: Regenerate API Key with Permissions")
        print("--------------------------------------------------")
        print("1. Go to: https://elevenlabs.io/app/settings/api-keys")
        print("2. Delete your current API key")
        print("3. Create a new API key with 'Conversational AI Write' permission enabled")
        print("4. Update ELEVENLABS_API_KEY in your .env file")
        print("5. Run this script again: python create_agents.py")
        print()
        print("OPTION 2: Manual Agent Creation (Dashboard)")
        print("--------------------------------------------------")
        print("1. Go to: https://elevenlabs.io/app/conversational-ai")
        print("2. Click 'Create Agent' 4 times (one for each agent)")
        print("3. Use the configurations from MULTI_AGENT_SETUP.md")
        print("4. Copy each agent ID and add to your .env file")
        print()
        print("For detailed step-by-step instructions, see: MULTI_AGENT_SETUP.md")
        print()
        return False


if __name__ == "__main__":
    success = create_agents()
    sys.exit(0 if success else 1)
