#!/usr/bin/env python3
"""
Deploy Coding Tools to Antoni Agent

This script deploys client tools for code generation to the Antoni agent.
Antoni is the coding/writing specialist who can generate code via Hybrid Run.

Tools deployed:
- generate_code: Start code generation for a new project
- get_generation_status: Check the status of a generation job
- start_preview: Start VNC preview for a completed project
- stop_preview: Stop a running preview
- list_generated_projects: List all generated projects
- cancel_generation: Cancel a running generation job

Usage:
    python deploy_coding_tools.py
"""

import os
import sys
import json
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional

# ==============================================================================
# CONFIGURATION
# ==============================================================================

API_BASE = "https://api.elevenlabs.io/v1/convai"


def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent / ".env"

    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


def get_api_key() -> str:
    """Get ElevenLabs API key from environment."""
    key = os.getenv('ELEVENLABS_API_KEY')
    if not key:
        raise ValueError("ELEVENLABS_API_KEY not set in .env")
    return key


def get_antoni_agent_id() -> str:
    """Get Antoni agent ID from environment."""
    agent_id = os.getenv("AGENT_ANTONI") or os.getenv("AGENT_PROJECT_WRITER")
    if not agent_id:
        raise ValueError("AGENT_ANTONI or AGENT_PROJECT_WRITER not set in .env")
    return agent_id


# ==============================================================================
# API FUNCTIONS
# ==============================================================================

def api_request(method: str, endpoint: str, api_key: str, data: Dict = None) -> Optional[Dict]:
    """Make API request to ElevenLabs."""
    url = f"{API_BASE}/{endpoint}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    if method == "GET":
        response = requests.get(url, headers=headers)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=data)
    elif method == "PATCH":
        response = requests.patch(url, headers=headers, json=data)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unknown method: {method}")
    
    if response.status_code not in (200, 201, 204):
        print(f"  API Error: {response.status_code} - {response.text[:200]}")
        return None
    
    if response.status_code == 204:
        return {}
    
    try:
        return response.json()
    except:
        return {}


def get_agent(api_key: str, agent_id: str) -> Optional[Dict]:
    """Get agent configuration."""
    return api_request("GET", f"agents/{agent_id}", api_key)


def list_tools(api_key: str) -> List[Dict]:
    """List all tools."""
    result = api_request("GET", "tools", api_key)
    return result.get("tools", []) if result else []


def create_tool(api_key: str, tool_config: Dict) -> Optional[Dict]:
    """Create a new tool."""
    return api_request("POST", "tools", api_key, {"tool_config": tool_config})


def delete_tool(api_key: str, tool_id: str) -> bool:
    """Delete a tool."""
    result = api_request("DELETE", f"tools/{tool_id}", api_key)
    return result is not None


def update_agent_tools(api_key: str, agent_id: str, tool_ids: List[str]) -> bool:
    """Update agent to use specified tools."""
    agent = get_agent(api_key, agent_id)
    if not agent:
        return False
    
    prompt = agent.get("conversation_config", {}).get("agent", {}).get("prompt", {})
    current_tool_ids = prompt.get("tool_ids", [])
    
    # Merge new tools with existing (avoid duplicates)
    all_tool_ids = list(set(current_tool_ids + tool_ids))
    
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tool_ids": all_tool_ids
                }
            }
        }
    }
    
    result = api_request("PATCH", f"agents/{agent_id}", api_key, payload)
    return result is not None


def unlink_tools_from_agent(api_key: str, agent_id: str, tool_ids_to_remove: List[str]) -> bool:
    """Remove specific tool_ids from an agent."""
    agent = get_agent(api_key, agent_id)
    if not agent:
        return False
    
    prompt = agent.get("conversation_config", {}).get("agent", {}).get("prompt", {})
    current_tool_ids = prompt.get("tool_ids", [])
    
    # Remove specified tool IDs
    new_tool_ids = [tid for tid in current_tool_ids if tid not in tool_ids_to_remove]
    
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tool_ids": new_tool_ids
                }
            }
        }
    }
    
    result = api_request("PATCH", f"agents/{agent_id}", api_key, payload)
    return result is not None


# ==============================================================================
# CODING TOOL DEFINITIONS
# ==============================================================================

CODING_TOOLS = [
    {
        "type": "client",
        "name": "generate_code",
        "description": "Start code generation for a new project using Hybrid Run Coding Engine. Use when user says: create an app, generate code for, build me a website, make a project.",
        "expects_response": True,
        "response_timeout_secs": 30,
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Project title/name (required)"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed requirements and what the project should do"
                },
                "tech_stack": {
                    "type": "string",
                    "description": "Technology stack: react, vue, python-flask, nextjs, html-css-js (default: react)"
                },
                "requirements": {
                    "type": "string",
                    "description": "Comma-separated list of specific requirements"
                },
                "autonomous": {
                    "type": "boolean",
                    "description": "Run in full autonomous mode without interruptions (default: true)"
                }
            },
            "required": ["title"]
        }
    },
    {
        "type": "client",
        "name": "get_generation_status",
        "description": "Get the current status of a code generation job. Use when user asks: what's the status, is my project ready, show me the progress, how's the project doing.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job ID to check"
                },
                "project_name": {
                    "type": "string",
                    "description": "Project name to search for (alternative to job_id)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "start_preview",
        "description": "Start a VNC preview for a completed project. Use when user says: start preview, show me the preview, open the project, run it.",
        "expects_response": True,
        "response_timeout_secs": 20,
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job ID of the project"
                },
                "project_name": {
                    "type": "string",
                    "description": "Project name to search for (alternative to job_id)"
                },
                "resolution": {
                    "type": "string",
                    "description": "VNC resolution like 1280x720 (default: 1280x720)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "stop_preview",
        "description": "Stop a running VNC preview. Use when user says: stop preview, close the preview, end the preview.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job ID of the project"
                },
                "project_name": {
                    "type": "string",
                    "description": "Project name to search for (alternative to job_id)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "list_generated_projects",
        "description": "List all generated code projects. Use when user asks: show my projects, which projects do I have, list all generations.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "description": "Filter by status: pending, generating, converging, testing, completed, failed, previewing"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of projects to return (default: 10)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "cancel_generation",
        "description": "Cancel a running code generation job. Use when user says: cancel, stop the generation, abort job.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "The job ID to cancel (required)"
                }
            },
            "required": ["job_id"]
        }
    }
]


# ==============================================================================
# DEPLOYMENT FUNCTIONS
# ==============================================================================

def cleanup_existing_coding_tools(api_key: str, agent_id: str) -> int:
    """Remove existing coding tools before redeployment."""
    print("\n" + "="*60)
    print("PHASE 1: Cleaning up existing coding tools")
    print("="*60)
    
    tools = list_tools(api_key)
    coding_tool_names = [t["name"] for t in CODING_TOOLS]
    
    # Find all coding tool IDs
    coding_tool_ids = []
    for tool in tools:
        config = tool.get("tool_config", {})
        name = config.get("name", "")
        if name in coding_tool_names:
            tool_id = tool.get("id") or tool.get("tool_id")
            if tool_id:
                coding_tool_ids.append(tool_id)
                print(f"  Found: {name} ({tool_id})")
    
    if not coding_tool_ids:
        print("  No existing coding tools found")
        return 0
    
    # Unlink from agent first
    print(f"\n  Unlinking {len(coding_tool_ids)} tools from Antoni...")
    unlink_tools_from_agent(api_key, agent_id, coding_tool_ids)
    
    # Delete the tools
    print(f"\n  Deleting tools...")
    deleted = 0
    for tool in tools:
        config = tool.get("tool_config", {})
        name = config.get("name", "")
        if name in coding_tool_names:
            tool_id = tool.get("id") or tool.get("tool_id")
            if tool_id:
                print(f"    Deleting: {name} ({tool_id})")
                if delete_tool(api_key, tool_id):
                    deleted += 1
                    print(f"      ✓ Deleted")
                else:
                    print(f"      ✗ Failed to delete")
    
    print(f"\n  Deleted {deleted} existing coding tools")
    return deleted


def deploy_coding_tools(api_key: str, agent_id: str) -> List[str]:
    """Deploy all coding tools to Antoni agent."""
    print("\n" + "="*60)
    print("PHASE 2: Deploying coding tools to Antoni")
    print("="*60)
    
    created_ids = []
    
    for tool_config in CODING_TOOLS:
        tool_name = tool_config["name"]
        print(f"\n  Creating: {tool_name}...")
        
        result = create_tool(api_key, tool_config)
        if result:
            tool_id = result.get("id") or result.get("tool_id")
            if tool_id:
                created_ids.append(tool_id)
                print(f"    ✓ Created: {tool_id}")
            else:
                print(f"    ✗ No ID returned")
        else:
            print(f"    ✗ Failed to create")
    
    # Link tools to agent
    if created_ids:
        print(f"\n  Linking {len(created_ids)} tools to Antoni ({agent_id})...")
        if update_agent_tools(api_key, agent_id, created_ids):
            print(f"    ✓ Linked successfully")
        else:
            print(f"    ✗ Failed to link")
    
    return created_ids


def verify_deployment(api_key: str, agent_id: str) -> bool:
    """Verify that Antoni has all coding tools."""
    print("\n" + "="*60)
    print("PHASE 3: Verification")
    print("="*60)
    
    agent = get_agent(api_key, agent_id)
    if not agent:
        print("  ✗ Failed to fetch Antoni agent")
        return False
    
    prompt = agent.get("conversation_config", {}).get("agent", {}).get("prompt", {})
    tool_ids = prompt.get("tool_ids", [])
    
    # Get all tools to match IDs to names
    all_tools = list_tools(api_key)
    tool_names_by_id = {}
    for tool in all_tools:
        config = tool.get("tool_config", {})
        tid = tool.get("id") or tool.get("tool_id")
        name = config.get("name", "")
        if tid:
            tool_names_by_id[tid] = name
    
    # Check which coding tools are linked
    expected_names = set(t["name"] for t in CODING_TOOLS)
    found_names = set()
    
    for tid in tool_ids:
        name = tool_names_by_id.get(tid, "")
        if name in expected_names:
            found_names.add(name)
    
    print(f"\n  Antoni has {len(tool_ids)} total tools linked")
    print(f"  Expected coding tools: {len(expected_names)}")
    print(f"  Found coding tools: {len(found_names)}")
    
    if found_names == expected_names:
        print("\n  ✓ All coding tools verified!")
        for name in sorted(found_names):
            print(f"    - {name}")
        return True
    else:
        missing = expected_names - found_names
        print(f"\n  ⚠ Missing tools: {', '.join(missing)}")
        return False


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    """Main entry point."""
    load_env()
    
    try:
        api_key = get_api_key()
        agent_id = get_antoni_agent_id()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print("=" * 60)
    print("Coding Tools Deployment to Antoni Agent")
    print("=" * 60)
    print(f"\nAPI Key: {api_key[:10]}...")
    print(f"Antoni Agent ID: {agent_id}")
    
    print("\nTools to deploy:")
    for tool in CODING_TOOLS:
        print(f"  - {tool['name']}: {tool['description'][:60]}...")
    
    # Phase 1: Cleanup
    cleanup_existing_coding_tools(api_key, agent_id)
    
    # Phase 2: Deploy
    created_ids = deploy_coding_tools(api_key, agent_id)
    
    # Phase 3: Verify
    all_ok = verify_deployment(api_key, agent_id)
    
    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT SUMMARY")
    print("=" * 60)
    print(f"\nDeployed {len(created_ids)} coding tools to Antoni:")
    for tool in CODING_TOOLS:
        print(f"  - {tool['name']}")
    
    if all_ok:
        print("\n✓ All verifications passed!")
        print("\nUsage examples:")
        print('  User: "Erstelle eine Todo-App mit React"')
        print('  User: "Wie ist der Status von abc123?"')
        print('  User: "Starte die Preview"')
        print('  User: "Zeig mir meine Projekte"')
    else:
        print("\n⚠ Some verifications failed - check warnings above")
    
    print("=" * 60)


if __name__ == "__main__":
    main()