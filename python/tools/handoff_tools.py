"""
Handoff MCP Tools for VibeMind Voice Dialog

Direct desktop automation tools using pyautogui - same functionality as the
Handoff MCP server but integrated directly into the VibeMind tool system.

Tools:
- mcp_click - Click at coordinates or find element and click
- mcp_type - Type text at cursor position
- mcp_scroll - Scroll up/down
- mcp_press_key - Press keyboard key or hotkey
- mcp_read_screen - OCR screen capture using pytesseract
- mcp_validate - Find UI element location by description
- mcp_get_focus - Get currently focused window
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Import pyautogui for desktop automation
try:
    import pyautogui
    pyautogui.PAUSE = 0.1
    pyautogui.FAILSAFE = True
    HAS_PYAUTOGUI = True
except ImportError:
    logger.warning("pyautogui not available. Install with: pip install pyautogui")
    HAS_PYAUTOGUI = False

# Import pytesseract for OCR
try:
    import pytesseract
    from PIL import Image, ImageGrab
    HAS_OCR = True
except ImportError:
    logger.warning("pytesseract/PIL not available for OCR")
    HAS_OCR = False


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

async def mcp_click(x: int, y: int, button: str = "left", double_click: bool = False) -> Dict[str, Any]:
    """
    Click at the specified coordinates.

    Args:
        x: X coordinate on screen
        y: Y coordinate on screen
        button: Mouse button ('left', 'right', 'middle')
        double_click: Whether to double-click

    Returns:
        Dict with success status and details
    """
    logger.debug("mcp_click called with x=%s y=%s button=%s", x, y, button)
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui not installed"}

    try:
        start = time.time()

        if double_click:
            pyautogui.doubleClick(x, y, button=button)
            action = "double_click"
        else:
            pyautogui.click(x, y, button=button)
            action = "click"

        duration_ms = (time.time() - start) * 1000

        return {
            "success": True,
            "action": action,
            "x": x,
            "y": y,
            "button": button,
            "duration_ms": round(duration_ms, 1)
        }
    except Exception as e:
        logger.error(f"mcp_click failed: {e}")
        return {"success": False, "error": str(e)}


async def mcp_type(text: str, interval: float = 0.02, use_clipboard: bool = False) -> Dict[str, Any]:
    """
    Type text at the current cursor position.

    Args:
        text: Text to type
        interval: Interval between keystrokes (seconds)
        use_clipboard: If True, use clipboard paste for faster input (handles unicode)

    Returns:
        Dict with success status
    """
    logger.debug("mcp_type called with text_length=%s use_clipboard=%s", len(text), use_clipboard)
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui not installed"}

    try:
        start = time.time()

        if use_clipboard:
            # Use clipboard for faster typing and unicode support
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)
        else:
            # Direct typing (ASCII only for pyautogui.write)
            try:
                pyautogui.write(text, interval=interval)
            except Exception:
                # Fallback to clipboard for non-ASCII
                import pyperclip
                pyperclip.copy(text)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.1)

        duration_ms = (time.time() - start) * 1000

        return {
            "success": True,
            "action": "type",
            "text_length": len(text),
            "duration_ms": round(duration_ms, 1)
        }
    except Exception as e:
        logger.error(f"mcp_type failed: {e}")
        return {"success": False, "error": str(e)}


async def mcp_scroll(direction: str, amount: int = 3, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
    """
    Scroll the mouse wheel.

    Args:
        direction: 'up' or 'down'
        amount: Number of scroll clicks
        x: Optional X coordinate to scroll at
        y: Optional Y coordinate to scroll at

    Returns:
        Dict with success status
    """
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui not installed"}

    try:
        start = time.time()

        # Move to position if specified
        if x is not None and y is not None:
            pyautogui.moveTo(x, y)
            time.sleep(0.05)

        # Convert direction to scroll clicks
        clicks = abs(amount) if amount else 3
        if direction.lower() == "down":
            clicks = -clicks

        pyautogui.scroll(clicks)

        duration_ms = (time.time() - start) * 1000

        return {
            "success": True,
            "action": "scroll",
            "direction": direction,
            "amount": abs(clicks),
            "duration_ms": round(duration_ms, 1)
        }
    except Exception as e:
        logger.error(f"mcp_scroll failed: {e}")
        return {"success": False, "error": str(e)}


async def mcp_press_key(key: str) -> Dict[str, Any]:
    """
    Press a key or key combination.

    Args:
        key: Key to press. Examples:
             - Single keys: 'enter', 'tab', 'escape', 'space', 'win'
             - Combinations: 'ctrl+c', 'ctrl+v', 'alt+tab', 'win+r'

    Returns:
        Dict with success status
    """
    logger.debug("mcp_press_key called with key=%s", key)
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui not installed"}

    try:
        start = time.time()

        # Handle key combinations
        if '+' in key:
            keys = [k.strip().lower() for k in key.split('+')]
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(key.lower())

        duration_ms = (time.time() - start) * 1000

        return {
            "success": True,
            "action": "press_key",
            "key": key,
            "duration_ms": round(duration_ms, 1)
        }
    except Exception as e:
        logger.error(f"mcp_press_key failed: {e}")
        return {"success": False, "error": str(e)}


async def mcp_read_screen(region: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """
    Capture screenshot and extract text using OCR.

    Args:
        region: Optional region to capture {x, y, width, height}

    Returns:
        Dict with extracted text and success status
    """
    logger.debug("mcp_read_screen called with region=%s", region)
    if not HAS_OCR:
        return {"success": False, "error": "pytesseract/PIL not installed"}

    try:
        start = time.time()

        # Capture screenshot
        if region:
            bbox = (region['x'], region['y'],
                    region['x'] + region['width'],
                    region['y'] + region['height'])
            screenshot = ImageGrab.grab(bbox=bbox)
        else:
            screenshot = ImageGrab.grab()

        # Run OCR
        text = pytesseract.image_to_string(screenshot)

        # Also get structured data
        data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)

        # Extract text blocks with positions
        blocks = []
        for i, txt in enumerate(data['text']):
            if txt.strip():
                blocks.append({
                    "text": txt,
                    "x": data['left'][i],
                    "y": data['top'][i],
                    "width": data['width'][i],
                    "height": data['height'][i],
                    "confidence": data['conf'][i]
                })

        duration_ms = (time.time() - start) * 1000

        return {
            "success": True,
            "text": text.strip(),
            "blocks": blocks,
            "block_count": len(blocks),
            "duration_ms": round(duration_ms, 1)
        }
    except Exception as e:
        logger.error(f"mcp_read_screen failed: {e}")
        return {"success": False, "error": str(e)}


async def mcp_validate(target: str, timeout: float = 10.0) -> Dict[str, Any]:
    """
    Find a UI element on screen by its description/text.

    Uses OCR to locate the element and returns its coordinates.
    For better accuracy, connect to MoireServer using moire_tools.

    Args:
        target: Text to search for on screen
        timeout: Maximum time to search (seconds)

    Returns:
        Dict with element location if found
    """
    logger.debug("mcp_validate called with target=%s", target)
    if not HAS_OCR:
        return {"success": False, "error": "pytesseract/PIL not installed"}

    try:
        start = time.time()

        # Capture and OCR
        screenshot = ImageGrab.grab()
        data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)

        target_lower = target.lower()
        best_match = None
        best_confidence = 0

        # Search for matching text
        for i, txt in enumerate(data['text']):
            if txt.strip() and target_lower in txt.lower():
                conf = data['conf'][i]
                if conf > best_confidence:
                    best_confidence = conf
                    x = data['left'][i]
                    y = data['top'][i]
                    w = data['width'][i]
                    h = data['height'][i]
                    best_match = {
                        "text": txt,
                        "x": x + w // 2,  # Center X
                        "y": y + h // 2,  # Center Y
                        "bounds": {"x": x, "y": y, "width": w, "height": h},
                        "confidence": conf
                    }

        duration_ms = (time.time() - start) * 1000

        if best_match:
            return {
                "success": True,
                "found": True,
                "target": target,
                "element": best_match,
                "x": best_match["x"],
                "y": best_match["y"],
                "confidence": best_match["confidence"],
                "duration_ms": round(duration_ms, 1)
            }
        else:
            return {
                "success": True,
                "found": False,
                "target": target,
                "message": f"Element '{target}' not found on screen",
                "duration_ms": round(duration_ms, 1)
            }
    except Exception as e:
        logger.error(f"mcp_validate failed: {e}")
        return {"success": False, "error": str(e)}


async def mcp_get_focus() -> Dict[str, Any]:
    """
    Get information about the currently focused window.

    Returns:
        Dict with window title and handle
    """
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui not installed"}

    try:
        import subprocess

        # Use PowerShell to get active window info on Windows
        result = subprocess.run(
            ['powershell', '-Command',
             'Add-Type -AssemblyName System.Windows.Forms; '
             '[System.Windows.Forms.Form]::ActiveForm.Text; '
             '(Get-Process | Where-Object {$_.MainWindowHandle -eq '
             '(Add-Type -MemberDefinition \'[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();\' '
             '-Name Win32 -PassThru)::GetForegroundWindow()}).MainWindowTitle'],
            capture_output=True,
            text=True
        )

        # Alternative simpler approach
        result2 = subprocess.run(
            ['powershell', '-Command',
             '(Get-Process | Where-Object {$_.MainWindowHandle -ne 0} | '
             'Sort-Object CPU -Descending | Select-Object -First 1).MainWindowTitle'],
            capture_output=True,
            text=True
        )

        title = result.stdout.strip() or result2.stdout.strip() or "Unknown"

        return {
            "success": True,
            "window_title": title,
            "has_focus": bool(title and title != "Unknown")
        }
    except Exception as e:
        logger.error(f"mcp_get_focus failed: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

HANDOFF_TOOLS = [
    {
        "name": "mcp_click",
        "description": "Click at screen coordinates. Use mcp_validate first to find element locations.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate"},
                "y": {"type": "integer", "description": "Y coordinate"},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "double_click": {"type": "boolean", "default": False}
            },
            "required": ["x", "y"]
        }
    },
    {
        "name": "mcp_type",
        "description": "Type text at current cursor position. For non-ASCII characters, set use_clipboard=true.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to type"},
                "use_clipboard": {"type": "boolean", "default": False, "description": "Use clipboard paste for unicode"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "mcp_scroll",
        "description": "Scroll the mouse wheel up or down.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"]},
                "amount": {"type": "integer", "default": 3, "description": "Scroll clicks"},
                "x": {"type": "integer", "description": "Optional X coordinate"},
                "y": {"type": "integer", "description": "Optional Y coordinate"}
            },
            "required": ["direction"]
        }
    },
    {
        "name": "mcp_press_key",
        "description": "Press a key or key combination. Examples: 'enter', 'ctrl+c', 'win+r', 'alt+tab'",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key or combo like 'enter' or 'ctrl+s'"}
            },
            "required": ["key"]
        }
    },
    {
        "name": "mcp_read_screen",
        "description": "Capture screenshot and extract text using OCR. Returns all visible text on screen.",
        "parameters": {
            "type": "object",
            "properties": {
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
            },
            "required": []
        }
    },
    {
        "name": "mcp_validate",
        "description": "Find a UI element on screen by text. Returns coordinates for clicking.",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Text to search for on screen"}
            },
            "required": ["target"]
        }
    },
    {
        "name": "mcp_get_focus",
        "description": "Get the currently focused window title.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


# =============================================================================
# REGISTRATION FOR VIBEMIND
# =============================================================================

def register_handoff_tools(tools_manager) -> None:
    """
    Register Handoff MCP tools with the ClientToolsManager.

    Args:
        tools_manager: ClientToolsManager instance
    """
    print("Registering Handoff MCP tools...")

    # Create wrapper functions that handle async execution
    def create_wrapper(async_func):
        def wrapper(params):
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, async_func(**params))
                        return future.result()
                else:
                    return asyncio.run(async_func(**params))
            except Exception as e:
                return {"success": False, "error": str(e)}
        return wrapper

    # Register each tool
    tools_manager.register_with_observer("mcp_click", create_wrapper(
        lambda x, y, button="left", double_click=False: mcp_click(x, y, button, double_click)
    ))
    print("  - mcp_click")

    tools_manager.register_with_observer("mcp_type", create_wrapper(
        lambda text, use_clipboard=False, interval=0.02: mcp_type(text, interval, use_clipboard)
    ))
    print("  - mcp_type")

    tools_manager.register_with_observer("mcp_scroll", create_wrapper(
        lambda direction, amount=3, x=None, y=None: mcp_scroll(direction, amount, x, y)
    ))
    print("  - mcp_scroll")

    tools_manager.register_with_observer("mcp_press_key", create_wrapper(
        lambda key: mcp_press_key(key)
    ))
    print("  - mcp_press_key")

    tools_manager.register_with_observer("mcp_read_screen", create_wrapper(
        lambda region=None: mcp_read_screen(region)
    ))
    print("  - mcp_read_screen")

    tools_manager.register_with_observer("mcp_validate", create_wrapper(
        lambda target, timeout=10.0: mcp_validate(target, timeout)
    ))
    print("  - mcp_validate")

    tools_manager.register_with_observer("mcp_get_focus", create_wrapper(
        lambda: mcp_get_focus()
    ))
    print("  - mcp_get_focus")

    print(f"Handoff MCP tools registered ({len(HANDOFF_TOOLS)} tools)")


# =============================================================================
# TEST
# =============================================================================

async def test_handoff_tools():
    """Test the handoff tools."""
    print("Testing Handoff MCP Tools...")
    print(f"  pyautogui available: {HAS_PYAUTOGUI}")
    print(f"  OCR available: {HAS_OCR}")

    # Test get focus
    result = await mcp_get_focus()
    print(f"\nmcp_get_focus: {result}")

    # Test read screen (if OCR available)
    if HAS_OCR:
        result = await mcp_read_screen()
        print(f"\nmcp_read_screen: found {result.get('block_count', 0)} text blocks")
        if result.get('text'):
            print(f"  Sample text: {result['text'][:100]}...")

    # Test validate
    if HAS_OCR:
        result = await mcp_validate("Start")
        print(f"\nmcp_validate('Start'): {result}")

    print("\nHandoff tools test completed")


if __name__ == "__main__":
    asyncio.run(test_handoff_tools())
