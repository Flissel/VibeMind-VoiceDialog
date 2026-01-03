#!/usr/bin/env python3
"""
Deploy Adam's Tools to ElevenLabs (Clean Slate)

Deploys exactly 9 tools for Adam (Desktop Agent):
- 3 Moire OCR tools (primary)
- 4 Desktop action tools
- 1 Transfer tool
- 1 Legacy scan tool

This script REPLACES all existing tools (clean slate approach).
"""

import os
import sys
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env from parent directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
AGENT_ADAM = os.getenv("ADAM_AGENT_ID") or os.getenv("AGENT_ADAM")

BASE_URL = "https://api.elevenlabs.io/v1"

# Output log
log_file = Path(__file__).parent / "deploy_moire_tools.log"
log_lines = []

def log(msg):
    print(msg)
    log_lines.append(msg)

def save_log():
    log_file.write_text("\n".join(log_lines), encoding='utf-8')


# =====================================================================
# ADAM'S COMPLETE TOOL SET (9 tools, English)
# =====================================================================

ADAM_TOOLS = [
    # Transfer tool
    {
        "type": "client",
        "name": "transfer_to_alice",
        "description": "Transfer conversation back to Alice (coordinator). Use when task is complete or you need help.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },

    # Moire OCR tools (primary)
    {
        "type": "client",
        "name": "moire_scan",
        "description": "Scan desktop with OCR via MoireServer. Returns all visible text and UI elements. Use this FIRST to see what's on screen.",
        "parameters": {
            "type": "object",
            "properties": {
                "timeout": {
                    "type": "number",
                    "description": "Max wait time in seconds (default: 30)"
                }
            },
            "required": []
        }
    },
    {
        "type": "client",
        "name": "moire_find_element",
        "description": "Find a UI element by text using OCR. Returns clickable coordinates (x, y). Use to locate buttons, links, icons before clicking.",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Text to search for on screen (e.g., 'Start', 'Chrome', 'Settings')"
                }
            },
            "required": ["description"]
        }
    },
    {
        "type": "client",
        "name": "moire_get_ui_context",
        "description": "Get complete UI context with all elements organized by category (buttons, text, icons, inputs).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },

    # Desktop action tools
    {
        "type": "client",
        "name": "click_element",
        "description": "Click on a UI element at specific coordinates. Use after moire_find_element to click on found elements.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {
                    "type": "number",
                    "description": "X coordinate to click"
                },
                "y": {
                    "type": "number",
                    "description": "Y coordinate to click"
                }
            },
            "required": ["x", "y"]
        }
    },
    {
        "type": "client",
        "name": "type_text",
        "description": "Type text using keyboard. Use after clicking on an input field.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to type"
                }
            },
            "required": ["text"]
        }
    },
    {
        "type": "client",
        "name": "open_application",
        "description": "Open an application by name (e.g., Chrome, VSCode, Notepad, Explorer).",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Application name to open"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "type": "client",
        "name": "get_window_info",
        "description": "Get information about the currently active window (title, size, position).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },

    # Legacy tool (kept for compatibility)
    {
        "type": "client",
        "name": "scan_desktop",
        "description": "Basic desktop scan (legacy). Prefer moire_scan for better OCR results.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


# =====================================================================
# API FUNCTIONS
# =====================================================================

def update_agent_tools(agent_id: str, tools: list) -> dict:
    """Update agent with tools via PATCH (REPLACES all existing tools)."""
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tools": tools
                }
            }
        }
    }

    log(f"Sending payload with {len(tools)} tools (REPLACE mode)...")

    response = requests.patch(
        f"{BASE_URL}/convai/agents/{agent_id}",
        headers=headers,
        json=payload
    )

    log(f"Response status: {response.status_code}")

    if response.status_code != 200:
        raise Exception(f"Failed to update agent: {response.status_code} - {response.text}")
    return response.json()


def get_agent_config(agent_id: str) -> dict:
    """Get current agent configuration."""
    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    response = requests.get(
        f"{BASE_URL}/convai/agents/{agent_id}",
        headers=headers
    )

    if response.status_code != 200:
        raise Exception(f"Failed to get agent: {response.status_code} - {response.text}")
    return response.json()


def deploy_adam_tools():
    """Deploy all 9 tools to Adam (REPLACES existing tools)."""
    if not ELEVENLABS_API_KEY:
        log("ERROR: ELEVENLABS_API_KEY not set")
        return False

    if not AGENT_ADAM:
        log("ERROR: ADAM_AGENT_ID or AGENT_ADAM not set")
        return False

    log(f"{'='*60}")
    log("Deploying Adam's Tools (Clean Slate)")
    log(f"{'='*60}")
    log(f"Agent ID: {AGENT_ADAM}")

    # Show current state
    try:
        current_config = get_agent_config(AGENT_ADAM)
        current_tools = current_config.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tools", [])
        log(f"\nCurrent tools on agent: {len(current_tools)}")
    except Exception as e:
        log(f"Could not get current config: {e}")
        current_tools = []

    log(f"\nDeploying {len(ADAM_TOOLS)} tools (REPLACING all existing):")
    for tool in ADAM_TOOLS:
        log(f"   - {tool['name']}")

    try:
        # REPLACE all tools with our clean set
        result = update_agent_tools(AGENT_ADAM, ADAM_TOOLS)
        log("\nAPI call successful!")

        # Verify
        updated = get_agent_config(AGENT_ADAM)
        deployed_tools = updated.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tools", [])

        log(f"\n{'='*60}")
        log(f"VERIFIED: Adam now has {len(deployed_tools)} tools")
        log(f"{'='*60}")

        for t in deployed_tools:
            log(f"   [{t.get('type', 'unknown')}] {t.get('name')}")

        if len(deployed_tools) == len(ADAM_TOOLS):
            log(f"\nSUCCESS: Exactly {len(ADAM_TOOLS)} tools deployed!")
        else:
            log(f"\nWARNING: Expected {len(ADAM_TOOLS)}, got {len(deployed_tools)}")

        return True

    except Exception as e:
        log(f"\nDeployment failed: {e}")
        import traceback
        log(traceback.format_exc())
        return False


def main():
    """Main function."""
    success = deploy_adam_tools()
    save_log()
    return success


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
