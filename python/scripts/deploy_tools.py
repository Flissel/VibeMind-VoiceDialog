#!/usr/bin/env python3
"""
Deploy Tools to ElevenLabs Conversational AI

Creates client tools via the API and links them to agents.
Uses credentials from .env file.
"""

import os
import sys
import json
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE = "https://api.elevenlabs.io/v1/convai"


def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent / ".env"

    if env_path.exists():
        with open(env_path, 'r') as f:
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


def get_agent_id(name: str) -> str:
    """Get agent ID from environment."""
    env_var = f"AGENT_{name.upper()}"
    agent_id = os.getenv(env_var)
    if not agent_id:
        raise ValueError(f"{env_var} not set in .env")
    return agent_id


# ============================================================================
# API FUNCTIONS
# ============================================================================

def create_tool(api_key: str, tool_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a tool via the ElevenLabs API.

    POST /v1/convai/tools
    """
    url = f"{API_BASE}/tools"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {"tool_config": tool_config}

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        print(f"Error creating tool: {response.status_code}")
        print(response.text)
        response.raise_for_status()

    return response.json()


def list_tools(api_key: str) -> List[Dict[str, Any]]:
    """
    List all tools.

    GET /v1/convai/tools
    """
    url = f"{API_BASE}/tools"
    headers = {"xi-api-key": api_key}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json().get("tools", [])


def delete_tool(api_key: str, tool_id: str) -> bool:
    """
    Delete a tool.

    DELETE /v1/convai/tools/{tool_id}
    """
    url = f"{API_BASE}/tools/{tool_id}"
    headers = {"xi-api-key": api_key}

    response = requests.delete(url, headers=headers)
    if response.status_code != 200:
        print(f"    Delete failed: {response.status_code} - {response.text[:100]}", flush=True)
    return response.status_code == 200


def get_agent(api_key: str, agent_id: str) -> Dict[str, Any]:
    """
    Get agent configuration.

    GET /v1/convai/agents/{agent_id}
    """
    url = f"{API_BASE}/agents/{agent_id}"
    headers = {"xi-api-key": api_key}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()


def update_agent_tools(api_key: str, agent_id: str, tool_ids: List[str]) -> Dict[str, Any]:
    """
    Update agent to link tools.

    PATCH /v1/convai/agents/{agent_id}
    """
    url = f"{API_BASE}/agents/{agent_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }

    # Get current agent config to preserve existing tool_ids
    current = get_agent(api_key, agent_id)
    current_tool_ids = []

    try:
        current_tool_ids = current.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tool_ids", [])
    except (KeyError, TypeError):
        pass

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

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code != 200:
        print(f"Error updating agent: {response.status_code}")
        print(response.text)
        response.raise_for_status()

    return response.json()


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

IDEA_TOOLS = [
    {
        "type": "client",
        "name": "list_ideas",
        "description": "List all NOTES and IDEAS INSIDE the current bubble/space. NOT for listing spaces - use list_bubbles for that. Use when user says: show my notes, what ideas do I have here, list content in this space.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "create_idea",
        "description": "Create a new idea/note INSIDE the current bubble. Use when user wants to add, create, or save an idea, note, or thought.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title for the idea"
                },
                "content": {
                    "type": "string",
                    "description": "Full content or description"
                },
                "type": {
                    "type": "string",
                    "description": "Type: idea, note, link, or image (default: idea)"
                }
            },
            "required": ["title"]
        }
    },
    {
        "type": "client",
        "name": "add_image",
        "description": "Add an image to the current bubble/space. Use when user wants to add, save, or attach an image or picture via URL.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the image (http:// or https://)"
                },
                "title": {
                    "type": "string",
                    "description": "Caption or title for the image"
                }
            },
            "required": ["url"]
        }
    },
    {
        "type": "client",
        "name": "find_idea",
        "description": "Search for ideas matching a query. Use when user wants to find, search, or look for something.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search text"
                }
            },
            "required": ["query"]
        }
    },
    {
        "type": "client",
        "name": "update_idea",
        "description": "Update an existing idea. Use when user wants to change, edit, or modify an idea.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "idea_name": {
                    "type": "string",
                    "description": "Name of idea to update"
                },
                "new_content": {
                    "type": "string",
                    "description": "New content"
                },
                "new_title": {
                    "type": "string",
                    "description": "New title"
                }
            },
            "required": ["idea_name"]
        }
    },
    {
        "type": "client",
        "name": "connect_ideas",
        "description": "Link two ideas together. Use when user wants to connect, link, or relate ideas.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "idea1": {
                    "type": "string",
                    "description": "First idea name"
                },
                "idea2": {
                    "type": "string",
                    "description": "Second idea name"
                }
            },
            "required": ["idea1", "idea2"]
        }
    },
    {
        "type": "client",
        "name": "delete_idea",
        "description": "Delete an idea. Use when user wants to remove, delete, or get rid of an idea.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "idea_name": {
                    "type": "string",
                    "description": "Name of idea to delete"
                }
            },
            "required": ["idea_name"]
        }
    },
    {
        "type": "client",
        "name": "get_current_space",
        "description": "Get information about current location. Use when user asks where they are or what space this is.",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
]

MEMORY_TOOLS = [
    {
        "type": "client",
        "name": "make_memories",
        "description": "Background memory consolidation. Called during conversation pauses when user speaks briefly. Analyzes recent conversation to extract insights. Returns empty - NO voice response.",
        "expects_response": False,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "recent_audio_duration": {
                    "type": "number",
                    "description": "How long the user spoke in seconds"
                },
                "trigger_reason": {
                    "type": "string",
                    "description": "Why triggered: pause, short_utterance, or silence"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "recall_about_user",
        "description": "Recall stored insights about the user. Use when user asks what you remember about them or what you've talked about.",
        "expects_response": True,
        "response_timeout_secs": 20,
        "parameters": {
            "type": "object",
            "properties": {
                "insight_type": {
                    "type": "string",
                    "description": "Optional filter: preference, goal, topic, or emotion"
                }
            }
        }
    }
]

BUBBLE_TOOLS = [
    {
        "type": "client",
        "name": "list_bubbles",
        "description": "List all SPACES/BUBBLES in the multiverse. NOT for listing ideas - use list_ideas for content inside a bubble. Use when user says: show my spaces, what bubbles do I have, list all my idea spaces.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "create_bubble",
        "description": "Create a new bubble/space in the multiverse. A bubble is a CONTAINER for ideas. Use when user wants to create a new space, bubble, or area to organize ideas.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Name for the new space"
                },
                "description": {
                    "type": "string",
                    "description": "Optional description"
                }
            },
            "required": ["title"]
        }
    },
    {
        "type": "client",
        "name": "get_bubble_stats",
        "description": "Get statistics about a bubble including note count, connections, and score. Use when user asks how developed an idea is or what's in a space.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "bubble_name": {
                    "type": "string",
                    "description": "Name of bubble to check (uses current if not specified)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "score_bubble",
        "description": "Calculate and update bubble score based on content richness. Use when user wants to evaluate or score an idea space.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "bubble_name": {
                    "type": "string",
                    "description": "Name of bubble to score (uses current if not specified)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "promote_bubble",
        "description": "Promote a bubble/idea to a project. Use when user wants to turn an idea into a project or promote a space.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "bubble_name": {
                    "type": "string",
                    "description": "Name of bubble to promote (uses current if not specified)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "delete_bubble",
        "description": "Delete a bubble/space and all its contents. Use when user wants to remove or delete a space.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "bubble_name": {
                    "type": "string",
                    "description": "Name of bubble to delete"
                }
            },
            "required": ["bubble_name"]
        }
    },
    {
        "type": "client",
        "name": "enter_bubble",
        "description": "Enter a bubble/space to work inside it. Use when user wants to go into a space, enter a bubble, or focus on a specific area.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "bubble_name": {
                    "type": "string",
                    "description": "Name of bubble to enter"
                }
            },
            "required": ["bubble_name"]
        }
    },
    {
        "type": "client",
        "name": "exit_bubble",
        "description": "Exit the current bubble and return to the multiverse view. Use when user wants to leave, exit, or go back from the current space.",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "evaluate_bubble_evolution",
        "description": "Use AI to evaluate how evolved/complete a bubble's ideas are. Scores on completeness, structure, actionability, and depth. Returns recommendations for improvement. Use when user asks: how evolved is this idea, evaluate this bubble, give me AI analysis of this space.",
        "expects_response": True,
        "response_timeout_secs": 30,
        "parameters": {
            "type": "object",
            "properties": {
                "bubble_name": {
                    "type": "string",
                    "description": "Name of bubble to evaluate (uses current if not specified)"
                }
            }
        }
    }
]

SUMMARY_TOOLS = [
    {
        "type": "client",
        "name": "summarize_idea",
        "description": "Create an AI-powered summary of an idea/bubble using GPT and Gemini. Use when user says: summarize this idea, create a summary, give me an overview of this space.",
        "expects_response": True,
        "response_timeout_secs": 60,
        "parameters": {
            "type": "object",
            "properties": {
                "idea_name": {
                    "type": "string",
                    "description": "Name of the idea/bubble to summarize (uses current if not specified)"
                },
                "style": {
                    "type": "string",
                    "description": "Summary style: concise, detailed, or actionable (default: concise)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "list_summaries",
        "description": "List all ideas that have AI summaries. Use when user asks what summaries exist or wants to see summarized ideas.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "get_summary",
        "description": "Read the existing summary of an idea. Use when user wants to hear a summary or asks what the summary says.",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "idea_name": {
                    "type": "string",
                    "description": "Name of the idea (uses current if not specified)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "generate_white_paper",
        "description": "Generate a structured White Paper document from linked ideas using graph traversal. Traverses connected notes and creates a hierarchical document. Use when user says: generate white paper, create project overview, make a document from linked ideas, create report from this topic.",
        "expects_response": True,
        "response_timeout_secs": 120,
        "parameters": {
            "type": "object",
            "properties": {
                "start_node": {
                    "type": "string",
                    "description": "Name of the starting idea/note to traverse from (required)"
                },
                "task": {
                    "type": "string",
                    "description": "What kind of document to create - e.g. project overview, technical spec, summary report (default: project overview)"
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum traversal depth - how many connections to follow (default: 5)"
                }
            },
            "required": ["start_node"]
        }
    },
    {
        "type": "client",
        "name": "generate_project_structure",
        "description": "Convert whitepaper and notes into a structured project specification with requirements, features, and phases. Creates canvas nodes for each feature. Use when user says: generate project structure, extract requirements, turn this into a project spec.",
        "expects_response": True,
        "response_timeout_secs": 45,
        "parameters": {
            "type": "object",
            "properties": {
                "bubble_name": {
                    "type": "string",
                    "description": "Name of bubble to structure (uses current if not specified)"
                },
                "create_nodes": {
                    "type": "boolean",
                    "description": "Create canvas nodes for each feature (default: true)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "generate_feature_docs",
        "description": "Generate detailed markdown documentation for each feature with user stories, acceptance criteria, and technical notes. Creates connected documents on canvas. Use when user says: generate feature docs, document all features, create feature specifications.",
        "expects_response": True,
        "response_timeout_secs": 60,
        "parameters": {
            "type": "object",
            "properties": {
                "bubble_name": {
                    "type": "string",
                    "description": "Name of bubble to document (uses current if not specified)"
                },
                "include_requirements": {
                    "type": "boolean",
                    "description": "Include linked requirements in docs (default: true)"
                },
                "connect_features": {
                    "type": "boolean",
                    "description": "Create edges between related features (default: true)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "submit_to_req_orchestrator",
        "description": "Submit bubble requirements to req-orchestrator for quality validation. Evaluates requirements against 9 criteria (clarity, testability, etc.) and returns scores. Optionally exports as markdown files. Use when user says: validate my requirements, submit to arch team, check requirement quality, export validated features.",
        "expects_response": True,
        "response_timeout_secs": 120,
        "parameters": {
            "type": "object",
            "properties": {
                "bubble_name": {
                    "type": "string",
                    "description": "Name of bubble to validate (uses current if not specified)"
                },
                "output_dir": {
                    "type": "string",
                    "description": "Directory to export markdown files (optional)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "get_requirement_clarifications",
        "description": "Get pending clarification questions for requirements that failed validation. Shows questions from req-orchestrator that need user input. Use when user says: what clarifications are needed, show requirement questions, what needs clarification.",
        "expects_response": True,
        "response_timeout_secs": 30,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
]

SUPERMEMORY_TOOLS = [
    {
        "type": "client",
        "name": "search_memory",
        "description": "Search SuperMemory for relevant context. Use semantic search to find memories from past conversations. Use when user asks: Was weisst du noch ueber...?, Erinnere dich an..., Was haben wir ueber ... besprochen?, Suche nach Informationen ueber...",
        "expects_response": True,
        "response_timeout_secs": 15,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in memory"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 5)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "type": "client",
        "name": "store_to_supermemory",
        "description": "Store important information in SuperMemory for later recall. Use to remember facts, preferences, or context that should persist. Use when user says: Merke dir dass..., Speichere dass..., Erinnere dich dass ich..., Notiere fuer spaeter...",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The information to store"
                },
                "category": {
                    "type": "string",
                    "description": "Category: preference, fact, project, or note (default: note)"
                }
            },
            "required": ["content"]
        }
    },
    {
        "type": "client",
        "name": "recall_conversation",
        "description": "Recall conversation history from current session. Use when user asks: Was haben wir bisher besprochen?, Zusammenfassung unseres Gespraechs, Worueber haben wir geredet?",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "clear_session_memory",
        "description": "Start a fresh session with new context. Use when user says: Vergiss diese Session, Starte neue Session, Reset Kontext.",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
]


# ============================================================================
# DEPLOYMENT FUNCTIONS
# ============================================================================

def deploy_tools(api_key: str, tools: List[Dict], agent_id: str, tool_set_name: str) -> List[str]:
    """
    Deploy a set of tools and link them to an agent.

    Returns list of created tool IDs.
    """
    print(f"\n{'='*60}")
    print(f"Deploying {tool_set_name} to agent {agent_id}")
    print('='*60)

    created_ids = []

    for tool_config in tools:
        tool_name = tool_config["name"]
        print(f"\n  Creating tool: {tool_name}...")

        try:
            result = create_tool(api_key, tool_config)
            tool_id = result.get("id") or result.get("tool_id")

            if tool_id:
                created_ids.append(tool_id)
                print(f"    Created: {tool_id}")
            else:
                print(f"    Warning: No tool ID in response")
                print(f"    Response: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"    Error: {e}")

    if created_ids:
        print(f"\n  Linking {len(created_ids)} tools to agent...")
        try:
            update_agent_tools(api_key, agent_id, created_ids)
            print(f"    Linked successfully!")
        except Exception as e:
            print(f"    Error linking tools: {e}")

    return created_ids


def list_existing_tools(api_key: str):
    """List all existing tools."""
    print("\nExisting tools:")
    print("-" * 40)

    tools = list_tools(api_key)
    for tool in tools:
        tool_id = tool.get("id") or tool.get("tool_id")
        config = tool.get("tool_config", {})
        name = config.get("name", "Unknown")
        tool_type = config.get("type", "Unknown")
        print(f"  - {name} ({tool_type}): {tool_id}")

    return tools


def cleanup_duplicate_tools(api_key: str, tool_names: List[str]):
    """Remove duplicate tools by name, keeping only the newest."""
    print("\nChecking for duplicate tools...")

    tools = list_tools(api_key)

    # Group by name
    by_name = {}
    for tool in tools:
        config = tool.get("tool_config", {})
        name = config.get("name")
        if name in tool_names:
            if name not in by_name:
                by_name[name] = []
            by_name[name].append(tool)

    # Delete all but the newest for each name
    deleted = 0
    for name, tool_list in by_name.items():
        if len(tool_list) > 1:
            # Sort by ID (newer IDs are usually longer/later)
            tool_list.sort(key=lambda t: t.get("id", ""), reverse=True)
            # Keep first (newest), delete rest
            for old_tool in tool_list[1:]:
                tool_id = old_tool.get("id")
                if tool_id:
                    print(f"  Deleting duplicate: {name} ({tool_id})")
                    delete_tool(api_key, tool_id)
                    deleted += 1

    if deleted:
        print(f"  Removed {deleted} duplicate tools")
    else:
        print("  No duplicates found")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    load_env()

    try:
        api_key = get_api_key()
        # Use AGENT_MULTIVERSE (Rachel) as the target agent
        agent_id = os.getenv("AGENT_MULTIVERSE") or os.getenv("AGENT_RACHEL")
        if not agent_id:
            agent_id = get_agent_id("CONVERSATIONAL_MEMORY")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("ElevenLabs Tool Deployment")
    print("=" * 60)
    print(f"API Key: {api_key[:10]}...")
    print(f"Target Agent: Rachel (Multiverse)")
    print(f"Agent ID: {agent_id}")

    # List existing tools
    list_existing_tools(api_key)

    # Get tool names for duplicate check
    idea_names = [t["name"] for t in IDEA_TOOLS]
    memory_names = [t["name"] for t in MEMORY_TOOLS]
    bubble_names = [t["name"] for t in BUBBLE_TOOLS]
    summary_names = [t["name"] for t in SUMMARY_TOOLS]
    supermemory_names = [t["name"] for t in SUPERMEMORY_TOOLS]

    # Clean up any existing duplicates
    cleanup_duplicate_tools(api_key, idea_names + memory_names + bubble_names + summary_names + supermemory_names)

    # Deploy idea tools
    idea_ids = deploy_tools(api_key, IDEA_TOOLS, agent_id, "Idea Tools")

    # Deploy memory tools
    memory_ids = deploy_tools(api_key, MEMORY_TOOLS, agent_id, "Memory Tools")

    # Deploy bubble tools
    bubble_ids = deploy_tools(api_key, BUBBLE_TOOLS, agent_id, "Bubble Tools")

    # Deploy summary tools
    summary_ids = deploy_tools(api_key, SUMMARY_TOOLS, agent_id, "Summary Tools")

    # Deploy SuperMemory tools
    supermemory_ids = deploy_tools(api_key, SUPERMEMORY_TOOLS, agent_id, "SuperMemory Tools")

    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print(f"Idea Tools: {len(idea_ids)} created")
    print(f"Memory Tools: {len(memory_ids)} created")
    print(f"Bubble Tools: {len(bubble_ids)} created")
    print(f"Summary Tools: {len(summary_ids)} created")
    print(f"SuperMemory Tools: {len(supermemory_ids)} created")
    print(f"Total: {len(idea_ids) + len(memory_ids) + len(bubble_ids) + len(summary_ids) + len(supermemory_ids)} tools")

    if idea_ids or memory_ids or bubble_ids or summary_ids or supermemory_ids:
        print("\nCreated Tool IDs:")
        for tid in idea_ids + memory_ids + bubble_ids + summary_ids + supermemory_ids:
            print(f"  - {tid}")


if __name__ == "__main__":
    main()
