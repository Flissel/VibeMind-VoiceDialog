#!/usr/bin/env python3
"""
Deploy Transfer Tools to ElevenLabs Agents

This script deploys the transfer_to_agent system tools to all agents.
The transfer configuration enables hub-and-spoke conversation handoffs.

Transfer Flow:
    Alice (Hub) <-> Rachel (Bubbles)
    Alice (Hub) <-> Adam (Desktop)
    Alice (Hub) <-> Antoni (Coding)
    Rachel <-> Multiverse
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
BASE_URL = "https://api.elevenlabs.io/v1/convai/agents"

# Agent IDs from .env
AGENTS = {
    "Rachel": os.getenv("AGENT_CONVERSATIONAL_MEMORY"),
    "Alice": os.getenv("AGENT_PROJECT_MANAGER"),
    "Adam": os.getenv("AGENT_DESKTOP_WORKER"),
    "Antoni": os.getenv("AGENT_PROJECT_WRITER"),
    "Multiverse": os.getenv("AGENT_MULTIVERSE"),
}

# Transfer configurations for each agent
TRANSFER_CONFIGS = {
    # Rachel (Conversational Memory) - transfers to Alice or Multiverse
    "Rachel": {
        "type": "system",
        "name": "transfer_to_agent",
        "description": "Transfer to Project Manager for tasks or Multiverse for bubble navigation",
        "params": {
            "system_tool_type": "transfer_to_agent",
            "transfers": [
                {
                    "agent_id": AGENTS["Alice"],
                    "condition": "User requests any action, task, or project work",
                    "transfer_message": "",
                    "delay_ms": 0,
                    "enable_transferred_agent_first_message": True
                },
                {
                    "agent_id": AGENTS["Multiverse"],
                    "condition": "User wants to return to bubbles, navigate spaces, go back to multiverse, or exit conversation",
                    "transfer_message": "",
                    "delay_ms": 0,
                    "enable_transferred_agent_first_message": True
                }
            ],
            "voicemail_message": ""
        },
        "disable_interruptions": False
    },

    # Alice (Project Manager) - Hub agent, transfers to specialists
    "Alice": {
        "type": "system",
        "name": "transfer_to_agent",
        "description": "Transfer to specialist agents based on task type",
        "params": {
            "system_tool_type": "transfer_to_agent",
            "transfers": [
                {
                    "agent_id": AGENTS["Adam"],
                    "condition": "User needs desktop automation, file operations, window control, or system tasks",
                    "transfer_message": "",
                    "delay_ms": 0,
                    "enable_transferred_agent_first_message": True
                },
                {
                    "agent_id": AGENTS["Antoni"],
                    "condition": "User needs document creation, writing, editing, or content generation",
                    "transfer_message": "",
                    "delay_ms": 0,
                    "enable_transferred_agent_first_message": True
                },
                {
                    "agent_id": AGENTS["Rachel"],
                    "condition": "User wants to chat, needs clarification, or task is complete",
                    "transfer_message": "",
                    "delay_ms": 0,
                    "enable_transferred_agent_first_message": True
                }
            ],
            "voicemail_message": ""
        },
        "disable_interruptions": False
    },

    # Adam (Desktop Worker) - returns to Alice
    "Adam": {
        "type": "system",
        "name": "transfer_to_agent",
        "description": "Return to Project Manager after completing desktop task",
        "params": {
            "system_tool_type": "transfer_to_agent",
            "transfers": [
                {
                    "agent_id": AGENTS["Alice"],
                    "condition": "Task is complete or user needs different help",
                    "transfer_message": "",
                    "delay_ms": 0,
                    "enable_transferred_agent_first_message": True
                }
            ],
            "voicemail_message": ""
        },
        "disable_interruptions": False
    },

    # Antoni (Project Writer) - returns to Alice
    "Antoni": {
        "type": "system",
        "name": "transfer_to_agent",
        "description": "Return to Project Manager after completing writing task",
        "params": {
            "system_tool_type": "transfer_to_agent",
            "transfers": [
                {
                    "agent_id": AGENTS["Alice"],
                    "condition": "Writing task is complete or user needs different help",
                    "transfer_message": "",
                    "delay_ms": 0,
                    "enable_transferred_agent_first_message": True
                }
            ],
            "voicemail_message": ""
        },
        "disable_interruptions": False
    },

    # Multiverse - transfers to Rachel or Alice
    "Multiverse": {
        "type": "system",
        "name": "transfer_to_agent",
        "description": "Transfer to Rachel for conversation or Alice for tasks",
        "params": {
            "system_tool_type": "transfer_to_agent",
            "transfers": [
                {
                    "agent_id": AGENTS["Rachel"],
                    "condition": "User wants to chat, have a conversation, talk to Rachel, or just wants to talk",
                    "transfer_message": "",
                    "delay_ms": 0,
                    "enable_transferred_agent_first_message": True
                },
                {
                    "agent_id": AGENTS["Alice"],
                    "condition": "User needs task execution, project work, automation, or coordination",
                    "transfer_message": "",
                    "delay_ms": 0,
                    "enable_transferred_agent_first_message": True
                }
            ],
            "voicemail_message": ""
        },
        "disable_interruptions": False
    }
}


def get_agent_config(agent_id: str) -> dict:
    """Fetch current agent configuration."""
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }

    url = f"{BASE_URL}/{agent_id}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"  Error fetching config: {response.status_code} - {response.text}")
        return None


def update_agent_tools(agent_id: str, tools: list) -> bool:
    """Update agent with new tools configuration.

    Note: As of July 2025, ElevenLabs moved tools from agent.tools to agent.prompt.tools
    """
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }

    # First get current config
    current = get_agent_config(agent_id)
    if not current:
        return False

    # Get existing tools from NEW location (prompt.tools), filter out any existing transfer tools
    prompt = current.get("conversation_config", {}).get("agent", {}).get("prompt", {})
    existing_tools = prompt.get("tools", [])
    filtered_tools = [t for t in existing_tools if t.get("name") != "transfer_to_agent"]

    # Add new transfer tool
    updated_tools = filtered_tools + tools

    # Build update payload - NEW location: agent.prompt.tools
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tools": updated_tools
                }
            }
        }
    }

    url = f"{BASE_URL}/{agent_id}"
    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        return True
    else:
        print(f"  Error updating: {response.status_code} - {response.text}")
        return False


def deploy_transfers():
    """Deploy transfer tools to all agents."""
    print("=" * 60)
    print("Deploying Transfer Tools to ElevenLabs Agents")
    print("=" * 60)

    if not ELEVENLABS_API_KEY:
        print("ERROR: ELEVENLABS_API_KEY not found in .env")
        return False

    # Check all agent IDs are configured
    for name, agent_id in AGENTS.items():
        if not agent_id:
            print(f"ERROR: Agent ID for {name} not configured in .env")
            return False

    success_count = 0
    total = len(TRANSFER_CONFIGS)

    for agent_name, transfer_config in TRANSFER_CONFIGS.items():
        agent_id = AGENTS[agent_name]
        print(f"\n{agent_name} ({agent_id})")
        print("-" * 40)

        # Deploy the transfer tool
        print(f"  Deploying transfer tool...")
        if update_agent_tools(agent_id, [transfer_config]):
            print(f"  [OK] Transfer tool deployed")
            success_count += 1
        else:
            print(f"  [FAILED] Could not deploy transfer tool")

    print("\n" + "=" * 60)
    print(f"Deployed {success_count}/{total} transfer tools")

    if success_count == total:
        print("[SUCCESS] All transfer tools deployed!")
    else:
        print("[PARTIAL] Some deployments failed")

    print("=" * 60)
    return success_count == total


if __name__ == "__main__":
    deploy_transfers()
