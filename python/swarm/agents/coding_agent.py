"""
Coding Agent for VibeMind Swarm

Handles code generation and project management.
This is the primary agent for the Coding Space.
"""

import logging
from typing import List, Callable, Optional

logger = logging.getLogger(__name__)

# System message for the Coding Agent
CODING_SYSTEM_MESSAGE = """You are the Coding Agent for VibeMind. Your role is to help users:

1. **Generate Code**: Create code projects based on descriptions
2. **Manage Projects**: List, preview, and manage generated projects
3. **Track Progress**: Monitor code generation status

**Available Tools:**
- generate_code: Start code generation for a project
- get_generation_status: Check progress of code generation
- list_generated_projects: List all generated projects
- start_preview / stop_preview: Control project previews

**Workflow:**
1. User describes what they want to build
2. You call generate_code with the description
3. Monitor progress with get_generation_status
4. Offer to start preview when ready

**Handoff Guidelines:**
- Hand off to shuttle_agent when task is complete or for non-coding requests
- Hand off to user for clarification or final confirmation

Be helpful and explain what you're building. Confirm when tasks complete."""


def generate_code(description: str, tech_stack: str = "") -> str:
    """
    Generate code for a project.

    Args:
        description: What to build
        tech_stack: Optional technology preference

    Returns:
        Generation status
    """
    try:
        from tools.coding_tools import generate_code as _generate
        return _generate({"description": description, "tech_stack": tech_stack})
    except ImportError:
        return "Coding tools not available. Coding Engine required."


def get_generation_status(project_id: str = "") -> str:
    """
    Check code generation progress.

    Args:
        project_id: Optional specific project ID

    Returns:
        Status message
    """
    try:
        from tools.coding_tools import get_generation_status as _status
        return _status({"project_id": project_id})
    except ImportError:
        return "Coding tools not available."


def list_generated_projects() -> str:
    """
    List all generated projects.

    Returns:
        Project list
    """
    try:
        from tools.coding_tools import list_generated_projects as _list
        return _list({})
    except ImportError:
        return "Coding tools not available."


def start_preview(project_id: str) -> str:
    """
    Start project preview.

    Args:
        project_id: Project to preview

    Returns:
        Preview URL or status
    """
    try:
        from tools.coding_tools import start_preview as _start
        return _start({"project_id": project_id})
    except ImportError:
        return "Coding tools not available."


def stop_preview(project_id: str) -> str:
    """
    Stop project preview.

    Args:
        project_id: Project to stop

    Returns:
        Confirmation
    """
    try:
        from tools.coding_tools import stop_preview as _stop
        return _stop({"project_id": project_id})
    except ImportError:
        return "Coding tools not available."


# Collect coding tools
CODING_TOOLS = [
    generate_code,
    get_generation_status,
    list_generated_projects,
    start_preview,
    stop_preview,
]


def create_coding_agent(model_client, handoff_targets: List[str] = None):
    """
    Create the Coding Agent for code generation.

    Args:
        model_client: The LLM client (Ollama or OpenAI-compatible)
        handoff_targets: List of agent names this agent can hand off to

    Returns:
        AssistantAgent instance
    """
    from autogen_agentchat.agents import AssistantAgent

    # Default handoff targets
    if handoff_targets is None:
        handoff_targets = ["shuttle_agent", "user"]

    agent = AssistantAgent(
        name="coding_agent",
        model_client=model_client,
        tools=CODING_TOOLS,
        handoffs=handoff_targets,
        system_message=CODING_SYSTEM_MESSAGE,
    )

    logger.info(f"Created Coding Agent with {len(CODING_TOOLS)} tools, handoffs: {handoff_targets}")
    return agent


def get_coding_tools() -> List[Callable]:
    """Get all tools for Coding Agent."""
    return CODING_TOOLS


__all__ = [
    "create_coding_agent",
    "get_coding_tools",
    "CODING_SYSTEM_MESSAGE",
    "CODING_TOOLS",
]
