"""
Setup ElevenLabs Agents for Multi-Agent Voice System

This script creates 4 specialized agents with distinct voices:
1. Conversational Memory Assistant (Rachel - Professional female)
2. Project Manager (Alice - Calm British female)
3. Desktop Worker (Adam - Confident male)
4. Project Writer (Antoni - Creative male)

Run this script once to create all agents, then add the agent IDs to .env
"""

import os
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_agents():
    """Create all 4 ElevenLabs agents"""

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY not found in .env")
        return

    client = ElevenLabs(api_key=api_key)

    # Agent configurations
    agents_config = [
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
Use the handoff_to_agent tool when you need to delegate to a specialist."""
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

Always be organized, clear, and brief. Understand the task before delegating."""
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
Always confirm actions before executing potentially destructive operations."""
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
Always explain what you're creating and why."""
        }
    ]

    created_agents = []

    print("=" * 60)
    print("Creating ElevenLabs Agents for Multi-Agent Voice System")
    print("=" * 60)
    print()

    for i, config in enumerate(agents_config, 1):
        print(f"{i}. Creating: {config['name']}")
        print(f"   Voice ID: {config['voice_id']}")

        try:
            # Note: This uses the API directly since MCP tools have issues
            # You may need to create agents manually via the ElevenLabs dashboard
            # and then add their IDs to .env

            # For now, print configuration for manual creation
            print(f"   → Please create this agent manually in the ElevenLabs dashboard")
            print(f"     Name: {config['name']}")
            print(f"     Voice: {config['voice_id']}")
            print(f"     First Message: {config['first_message']}")
            print(f"     System Prompt: (see config above)")
            print()

            created_agents.append({
                "name": config['name'],
                "voice_id": config['voice_id'],
                "manual_creation_required": True
            })

        except Exception as e:
            print(f"   ✗ Error: {e}")
            print()

    print("=" * 60)
    print("Agent Creation Summary")
    print("=" * 60)
    print()
    print("Due to ElevenLabs SDK limitations, please create these agents manually:")
    print()
    print("1. Go to: https://elevenlabs.io/app/conversational-ai")
    print("2. Click 'Create Agent' for each agent below")
    print("3. Configure each with the details shown above")
    print("4. Copy each agent ID and add to .env file")
    print()
    print("Add these lines to your .env file:")
    print()
    print("# Multi-Agent Voice System Agent IDs")
    print("AGENT_CONVERSATIONAL_MEMORY=<your_agent_id_1>")
    print("AGENT_PROJECT_MANAGER=<your_agent_id_2>")
    print("AGENT_DESKTOP_WORKER=<your_agent_id_3>")
    print("AGENT_PROJECT_WRITER=<your_agent_id_4>")
    print()

    return created_agents


if __name__ == "__main__":
    create_agents()
