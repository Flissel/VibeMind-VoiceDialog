"""
Hello World Client Tools for Testing Agent Communication

These simple tools help verify that:
1. ElevenLabs agents can call client tools successfully
2. Agent transfers are working correctly
3. Desktop Worker and Project Writer agents execute tasks

Each agent writes a unique message to demonstrate which agent handled the request.
"""

import os
from datetime import datetime
from pathlib import Path


def write_hello_desktop() -> str:
    """
    Desktop Worker's hello world tool.

    Writes "Hello world from Desktop Worker Agent" to a timestamped file.

    Returns:
        str: Success message with filename
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"hello_desktop_{timestamp}.txt"
    filepath = Path(filename)

    message = f"Hello world from Desktop Worker Agent\nTimestamp: {datetime.now().isoformat()}\n"

    try:
        with open(filepath, "w") as f:
            f.write(message)

        return f"Success! Desktop Worker wrote file: {filepath.absolute()}"

    except Exception as e:
        return f"Error writing file: {str(e)}"


def write_hello_writer() -> str:
    """
    Project Writer's hello world tool.

    Writes "Hello world from Project Writer Agent" to a timestamped file.

    Returns:
        str: Success message with filename
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"hello_writer_{timestamp}.txt"
    filepath = Path(filename)

    message = f"Hello world from Project Writer Agent\nTimestamp: {datetime.now().isoformat()}\n"

    try:
        with open(filepath, "w") as f:
            f.write(message)

        return f"Success! Project Writer wrote file: {filepath.absolute()}"

    except Exception as e:
        return f"Error writing file: {str(e)}"


def write_hello_combined(agent_name: str, custom_message: str = "") -> str:
    """
    Generic hello world tool that any agent can use.

    Args:
        agent_name: Name of the agent calling this tool
        custom_message: Optional custom message to append

    Returns:
        str: Success message with filename
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"hello_{agent_name.lower().replace(' ', '_')}_{timestamp}.txt"
    filepath = Path(filename)

    message = f"Hello world from {agent_name} Agent\n"
    message += f"Timestamp: {datetime.now().isoformat()}\n"

    if custom_message:
        message += f"\nCustom message: {custom_message}\n"

    try:
        with open(filepath, "w") as f:
            f.write(message)

        return f"Success! {agent_name} wrote file: {filepath.absolute()}"

    except Exception as e:
        return f"Error writing file: {str(e)}"


# Export all tool functions
__all__ = [
    "write_hello_desktop",
    "write_hello_writer",
    "write_hello_combined"
]
