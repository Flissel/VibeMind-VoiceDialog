"""
MCP Tools Adapter - Desktop Automation Tools for Claude Worker

Adapts MCP Docker tools and local automation tools for use by the Claude worker.
Provides a unified interface for:
- Handoff tools (click, type, scroll, press_key)
- Moire OCR tools (scan, find_element, get_ui_context)
- Browser tools (navigate, click, type) via MCP Docker

Usage:
    from workers.mcp_tools_adapter import get_tool, execute_tool, AVAILABLE_TOOLS
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, Awaitable

logger = logging.getLogger(__name__)

# Import local automation tools
try:
    from tools.handoff_tools import (
        mcp_click,
        mcp_type,
        mcp_scroll,
        mcp_press_key,
        mcp_read_screen,
        mcp_validate,
        mcp_get_focus,
        HAS_PYAUTOGUI,
        HAS_OCR
    )
    HAS_HANDOFF_TOOLS = True
except ImportError as e:
    logger.warning(f"Handoff tools not available: {e}")
    HAS_HANDOFF_TOOLS = False
    HAS_PYAUTOGUI = False
    HAS_OCR = False

# Import Moire OCR tools
try:
    from tools.moire_tools import (
        moire_scan,
        moire_find_element,
        moire_get_ui_context,
        HAS_WEBSOCKETS
    )
    HAS_MOIRE_TOOLS = True
except ImportError as e:
    logger.warning(f"Moire tools not available: {e}")
    HAS_MOIRE_TOOLS = False
    HAS_WEBSOCKETS = False


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

# Tools available to the Claude worker
TOOL_DEFINITIONS = {
    # Desktop automation - clicks
    "click": {
        "name": "click",
        "description": "Click at screen coordinates. Use after finding element with scan_desktop or find_element.",
        "parameters": {
            "x": {"type": "integer", "required": True, "description": "X coordinate"},
            "y": {"type": "integer", "required": True, "description": "Y coordinate"},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
            "double_click": {"type": "boolean", "default": False}
        }
    },

    # Desktop automation - typing
    "type_text": {
        "name": "type_text",
        "description": "Type text at current cursor position. Click on input field first.",
        "parameters": {
            "text": {"type": "string", "required": True, "description": "Text to type"},
            "use_clipboard": {"type": "boolean", "default": False, "description": "Use clipboard for unicode"}
        }
    },

    # Desktop automation - scrolling
    "scroll": {
        "name": "scroll",
        "description": "Scroll up or down at current position or specified location.",
        "parameters": {
            "direction": {"type": "string", "enum": ["up", "down"], "required": True},
            "amount": {"type": "integer", "default": 3, "description": "Scroll clicks"},
            "x": {"type": "integer", "description": "Optional X coordinate"},
            "y": {"type": "integer", "description": "Optional Y coordinate"}
        }
    },

    # Desktop automation - keys
    "press_key": {
        "name": "press_key",
        "description": "Press a key or key combination. Examples: 'enter', 'ctrl+c', 'win+r'",
        "parameters": {
            "key": {"type": "string", "required": True, "description": "Key or combination"}
        }
    },

    # OCR - Moire scan (preferred)
    "scan_desktop": {
        "name": "scan_desktop",
        "description": "Scan the entire desktop with OCR. Returns all visible text and UI elements with positions. Use this first to understand what's on screen.",
        "parameters": {
            "timeout": {"type": "number", "default": 30.0, "description": "Timeout in seconds"}
        }
    },

    # OCR - Find element
    "find_element": {
        "name": "find_element",
        "description": "Find a specific UI element by its text. Returns click coordinates if found.",
        "parameters": {
            "text": {"type": "string", "required": True, "description": "Text to search for"},
            "timeout": {"type": "number", "default": 10.0}
        }
    },

    # OCR - Get UI context
    "get_ui_context": {
        "name": "get_ui_context",
        "description": "Get complete UI context organized by category (buttons, menus, inputs, etc.).",
        "parameters": {
            "timeout": {"type": "number", "default": 10.0}
        }
    },

    # OCR - Read screen (fallback)
    "read_screen": {
        "name": "read_screen",
        "description": "Capture screenshot and extract text using local OCR (pytesseract). Use when Moire is unavailable.",
        "parameters": {
            "region": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"}
                },
                "description": "Optional region to capture"
            }
        }
    },

    # Get focused window
    "get_focus": {
        "name": "get_focus",
        "description": "Get information about the currently focused window.",
        "parameters": {}
    },

    # Wait
    "wait": {
        "name": "wait",
        "description": "Wait for specified duration. Use between actions for UI to update.",
        "parameters": {
            "seconds": {"type": "number", "required": True, "description": "Seconds to wait"}
        }
    }
}


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

async def _click(x: int, y: int, button: str = "left", double_click: bool = False) -> Dict[str, Any]:
    """Execute click at coordinates."""
    if not HAS_HANDOFF_TOOLS:
        return {"success": False, "error": "Handoff tools not available"}
    return await mcp_click(x, y, button, double_click)


async def _type_text(text: str, use_clipboard: bool = False) -> Dict[str, Any]:
    """Type text at cursor."""
    if not HAS_HANDOFF_TOOLS:
        return {"success": False, "error": "Handoff tools not available"}
    return await mcp_type(text, use_clipboard=use_clipboard)


async def _scroll(direction: str, amount: int = 3, x: int = None, y: int = None) -> Dict[str, Any]:
    """Scroll up or down."""
    if not HAS_HANDOFF_TOOLS:
        return {"success": False, "error": "Handoff tools not available"}
    return await mcp_scroll(direction, amount, x, y)


async def _press_key(key: str) -> Dict[str, Any]:
    """Press a key or combination."""
    if not HAS_HANDOFF_TOOLS:
        return {"success": False, "error": "Handoff tools not available"}
    return await mcp_press_key(key)


async def _scan_desktop(timeout: float = 30.0) -> Dict[str, Any]:
    """Scan desktop with OCR - prefer Moire, fallback to local."""
    if HAS_MOIRE_TOOLS:
        result = await moire_scan(timeout=timeout)
        if result.get("success"):
            return result

    # Fallback to local OCR
    if HAS_OCR:
        return await mcp_read_screen()

    return {"success": False, "error": "No OCR tools available (Moire or pytesseract)"}


async def _find_element(text: str, timeout: float = 10.0) -> Dict[str, Any]:
    """Find element by text - prefer Moire, fallback to local."""
    if HAS_MOIRE_TOOLS:
        result = await moire_find_element(text, timeout=timeout)
        if result.get("success"):
            return result

    # Fallback to local OCR
    if HAS_OCR:
        return await mcp_validate(text, timeout=timeout)

    return {"success": False, "error": "No OCR tools available"}


async def _get_ui_context(timeout: float = 10.0) -> Dict[str, Any]:
    """Get UI context from Moire."""
    if HAS_MOIRE_TOOLS:
        return await moire_get_ui_context(timeout=timeout)
    return {"success": False, "error": "Moire OCR not available"}


async def _read_screen(region: Dict[str, int] = None) -> Dict[str, Any]:
    """Read screen with local OCR."""
    if not HAS_OCR:
        return {"success": False, "error": "Local OCR (pytesseract) not available"}
    return await mcp_read_screen(region)


async def _get_focus() -> Dict[str, Any]:
    """Get focused window info."""
    if not HAS_HANDOFF_TOOLS:
        return {"success": False, "error": "Handoff tools not available"}
    return await mcp_get_focus()


async def _wait(seconds: float) -> Dict[str, Any]:
    """Wait for specified duration."""
    await asyncio.sleep(seconds)
    return {"success": True, "waited_seconds": seconds}


# Tool function mapping
TOOL_FUNCTIONS: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {
    "click": _click,
    "type_text": _type_text,
    "scroll": _scroll,
    "press_key": _press_key,
    "scan_desktop": _scan_desktop,
    "find_element": _find_element,
    "get_ui_context": _get_ui_context,
    "read_screen": _read_screen,
    "get_focus": _get_focus,
    "wait": _wait
}


# =============================================================================
# PUBLIC API
# =============================================================================

def get_available_tools() -> Dict[str, Dict[str, Any]]:
    """Get all available tool definitions."""
    return TOOL_DEFINITIONS.copy()


def get_tool_names() -> list:
    """Get list of available tool names."""
    return list(TOOL_DEFINITIONS.keys())


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    """Get a specific tool definition."""
    return TOOL_DEFINITIONS.get(name)


async def execute_tool(name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Execute a tool by name with parameters.

    Args:
        name: Tool name
        params: Tool parameters

    Returns:
        Tool execution result
    """
    if name not in TOOL_FUNCTIONS:
        return {"success": False, "error": f"Unknown tool: {name}"}

    func = TOOL_FUNCTIONS[name]
    params = params or {}

    try:
        result = await func(**params)
        return result
    except TypeError as e:
        return {"success": False, "error": f"Invalid parameters for {name}: {e}"}
    except Exception as e:
        logger.error(f"Tool {name} execution error: {e}")
        return {"success": False, "error": str(e)}


def get_tools_for_llm() -> list:
    """
    Get tool definitions formatted for LLM function calling.

    Returns:
        List of tool definitions in OpenAI function format
    """
    tools = []
    for name, definition in TOOL_DEFINITIONS.items():
        params = definition.get("parameters", {})

        # Build properties and required list
        properties = {}
        required = []

        for param_name, param_def in params.items():
            prop = {"type": param_def.get("type", "string")}
            if "description" in param_def:
                prop["description"] = param_def["description"]
            if "enum" in param_def:
                prop["enum"] = param_def["enum"]
            if "default" in param_def:
                prop["default"] = param_def["default"]
            if "properties" in param_def:
                prop["properties"] = param_def["properties"]

            properties[param_name] = prop

            if param_def.get("required"):
                required.append(param_name)

        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": definition["description"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        })

    return tools


def get_status() -> Dict[str, Any]:
    """Get adapter status and tool availability."""
    return {
        "handoff_tools": HAS_HANDOFF_TOOLS,
        "pyautogui": HAS_PYAUTOGUI,
        "local_ocr": HAS_OCR,
        "moire_tools": HAS_MOIRE_TOOLS,
        "moire_websockets": HAS_WEBSOCKETS,
        "available_tools": list(TOOL_FUNCTIONS.keys()),
        "total_tools": len(TOOL_FUNCTIONS)
    }


# =============================================================================
# TEST
# =============================================================================

async def test_adapter():
    """Test the MCP tools adapter."""
    print("MCP Tools Adapter Status:")
    status = get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")

    print("\nAvailable Tools:")
    for name, definition in TOOL_DEFINITIONS.items():
        print(f"  - {name}: {definition['description'][:50]}...")

    print("\nTool Definitions for LLM:")
    tools = get_tools_for_llm()
    print(f"  {len(tools)} tools defined")

    # Test wait tool
    print("\nTesting 'wait' tool...")
    result = await execute_tool("wait", {"seconds": 0.1})
    print(f"  Result: {result}")

    # Test get_focus
    print("\nTesting 'get_focus' tool...")
    result = await execute_tool("get_focus", {})
    print(f"  Result: {result}")


if __name__ == "__main__":
    asyncio.run(test_adapter())
