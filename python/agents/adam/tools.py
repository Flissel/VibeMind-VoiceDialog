"""
Adam Agent Tools

Adam seeds desktop tasks to the Claude worker for execution.
He has only one tool: seed_task.
"""

from typing import Dict, Any, List, Callable

# Import tools from worker_queue
from tools.worker_queue import seed_task as _seed_task, get_worker_report as _get_worker_report


def seed_task(params: Dict[str, Any]) -> str:
    """
    Send a desktop task to the Claude worker for execution.

    The Claude worker will execute this task step by step using MCP tools.
    Use get_worker_report() to check progress.

    Args (via params):
        description: What to do (e.g., "Open Chrome and search for Python docs")
        priority: "low", "normal", "high", or "urgent" (default: "normal")

    Returns:
        str: Confirmation with task_id
    """
    description = params.get("description", "").strip()
    priority = params.get("priority", "normal")

    if not description:
        return "What would you like me to do? Please describe the task."

    result = _seed_task(description, priority)

    if result.get("success"):
        return f"Got it. Working on: {description[:50]}..."
    else:
        return f"Error: {result.get('error', 'Unknown error')}"


def get_worker_report(params: Dict[str, Any]) -> str:  # noqa: ARG001
    """
    Get the latest progress report from the Claude worker.

    Use this when the user asks "what's happening?" or wants a status update.

    Returns:
        str: Progress summary from the worker
    """
    del params  # unused, required for tool interface
    result = _get_worker_report()

    if result.get("message"):
        return result["message"]

    # Format the report nicely
    summary = result.get("summary", "Working...")
    steps = result.get("steps_completed", 0)
    is_final = result.get("is_final", False)

    if is_final:
        return f"Done! {summary}"
    else:
        return f"Step {steps}: {summary}"


# =============================================================================
# TOOL DEFINITIONS for ElevenLabs
# =============================================================================

def get_tool_definitions() -> List[Dict[str, Any]]:
    """Tool definitions for ElevenLabs."""
    return [
        {
            "type": "function",
            "function": {
                "name": "seed_task",
                "description": "Send a desktop task to the worker. Examples: 'Open Chrome', 'Click the Start button', 'Type hello world'. The worker executes it step by step.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "What to do. Be specific."
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "normal", "high", "urgent"],
                            "description": "Task priority (default: normal)"
                        }
                    },
                    "required": ["description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_worker_report",
                "description": "Get progress update from the worker. Use when user asks 'what's happening?' or 'status?'",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
    ]


def get_tools() -> Dict[str, Callable]:
    """All tool functions for Client-Tools registration."""
    return {
        "seed_task": seed_task,
        "get_worker_report": get_worker_report,
    }


def register_tools(client_tools) -> None:
    """Register Adam's tools with ClientTools manager."""
    for tool_name, tool_func in get_tools().items():
        client_tools.register(tool_name, tool_func)
        print(f"  [Adam] Registered: {tool_name}")
