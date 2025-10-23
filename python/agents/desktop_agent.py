"""
Desktop Agent - Handles screen capture, OCR, and window management
Enhanced with MoireTracker for advanced desktop element detection
"""

import asyncio
from typing import List, Dict, Any, Optional
import pyautogui
from PIL import Image
import io
import sys
sys.path.append('..')  # Allow importing from tools
from tools.moire_client import MoireTrackerClient


class DesktopAgent:
    """
    Agent for desktop interaction tasks:
    - Screenshot capture
    - OCR text recognition
    - Window management
    - Desktop element detection (398 icons via MoireTracker)
    - High-precision mouse tracking
    """

    def __init__(self, name: str = "DesktopAgent"):
        """
        Initialize the Desktop Agent

        Args:
            name: Agent name
        """
        self.name = name

        # Try to connect to MoireTracker
        self.moire = MoireTrackerClient()
        self.moire_connected = self.moire.connect()

        if self.moire_connected:
            print(f"[{self.name}] [OK] Connected to MoireTracker (enhanced mode)")
        else:
            print(f"[{self.name}] [WARN] MoireTracker not available (basic mode)")

        self.system_message = """You are a Desktop Agent specialized in:
- Taking screenshots (full screen or specific regions)
- Performing OCR (Optical Character Recognition) on screen content
- Managing windows and applications
- Visual analysis of screen content
- Detecting and locating desktop icons and applications (398 elements)
- High-precision mouse position tracking

You have access to tools for capturing and analyzing screen content.
Always be precise and clear about what you're capturing or analyzing."""

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of tools this agent can use

        Returns:
            List of tool definitions
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "take_screenshot",
                    "description": "Capture a screenshot of the entire screen or a specific region",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "region": {
                                "type": "string",
                                "description": "Region to capture: 'full', 'window', or coordinates like '100,100,800,600'"
                            },
                            "save_path": {
                                "type": "string",
                                "description": "Optional path to save the screenshot"
                            }
                        },
                        "required": ["region"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "perform_ocr",
                    "description": "Extract text from a screenshot or image using OCR",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_path": {
                                "type": "string",
                                "description": "Path to image file, or 'screen' for current screen"
                            },
                            "region": {
                                "type": "string",
                                "description": "Optional region to OCR: '100,100,800,600'"
                            }
                        },
                        "required": ["image_path"]
                    }
                }
            }
        ]

        # Add MoireTracker-enhanced tools if connected
        if self.moire_connected:
            tools.extend([
                {
                    "type": "function",
                    "function": {
                        "name": "scan_desktop_elements",
                        "description": "Scan all desktop icons and applications (398 elements detected via MoireTracker)",
                        "parameters": {"type": "object", "properties": {}}
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "find_desktop_element",
                        "description": "Find a specific desktop icon or application by name",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Element name to search for (case-insensitive)"
                                },
                                "exact_match": {
                                    "type": "boolean",
                                    "description": "Require exact name match (default: False)"
                                }
                            },
                            "required": ["name"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_mouse_info",
                        "description": "Get current mouse position with high precision",
                        "parameters": {"type": "object", "properties": {}}
                    }
                }
            ])

        return tools

    async def take_screenshot(self, region: str = "full", save_path: Optional[str] = None) -> str:
        """
        Take a screenshot

        Args:
            region: Region to capture
            save_path: Optional path to save

        Returns:
            Status message
        """
        try:
            if region == "full":
                screenshot = pyautogui.screenshot()
            else:
                # Parse region coordinates if provided
                # For now, just take full screenshot
                screenshot = pyautogui.screenshot()

            if save_path:
                screenshot.save(save_path)
                return f"[OK] Screenshot saved to {save_path}"
            else:
                # Save to temp location
                temp_path = "temp_screenshot.png"
                screenshot.save(temp_path)
                return f"[OK] Screenshot captured: {temp_path}"

        except Exception as e:
            return f"[FAIL] Screenshot failed: {str(e)}"

    async def perform_ocr(self, image_path: str, region: Optional[str] = None) -> str:
        """
        Perform OCR on an image

        Args:
            image_path: Path to image or 'screen'
            region: Optional region to OCR

        Returns:
            Extracted text
        """
        try:
            # Note: This is a placeholder
            # Real implementation would use pytesseract or similar
            return "[OCR] Text extraction not yet implemented. Would extract text from: " + image_path
        except Exception as e:
            return f"[FAIL] OCR failed: {str(e)}"

    async def scan_desktop_elements(self) -> List[Dict[str, Any]]:
        """
        Scan all desktop icons/elements using MoireTracker

        Returns:
            List of element dictionaries with name, position, type, etc.
        """
        if not self.moire_connected:
            return []

        try:
            elements = self.moire.scan_desktop()
            return [
                {
                    "id": elem.id,
                    "name": elem.text,
                    "app": elem.app_name,
                    "position": (elem.x, elem.y),
                    "size": (elem.width, elem.height),
                    "type": elem.type_name,
                    "clickable": elem.clickable,
                    "confidence": elem.confidence
                }
                for elem in elements
            ]
        except Exception as e:
            print(f"[{self.name}] Scan failed: {e}")
            return []

    async def find_desktop_element(self, name: str, exact_match: bool = False) -> Optional[Dict[str, Any]]:
        """
        Find specific desktop element by name

        Args:
            name: Element name to search for
            exact_match: Require exact name match

        Returns:
            Element dictionary if found, None otherwise
        """
        if not self.moire_connected:
            return None

        try:
            elem = self.moire.find_element(name, exact_match=exact_match)
            if elem:
                return {
                    "id": elem.id,
                    "name": elem.text,
                    "app": elem.app_name,
                    "position": (elem.x, elem.y),
                    "size": (elem.width, elem.height),
                    "type": elem.type_name,
                    "clickable": elem.clickable,
                    "confidence": elem.confidence
                }
            return None
        except Exception as e:
            print(f"[{self.name}] Find failed: {e}")
            return None

    async def get_mouse_info(self) -> Dict[str, Any]:
        """
        Get current mouse position with high precision

        Returns:
            Dictionary with mouse position info
        """
        if self.moire_connected:
            try:
                pos = self.moire.get_mouse_position()
                if pos:
                    return {
                        "x": pos.x,
                        "y": pos.y,
                        "confidence": pos.confidence,
                        "timestamp": pos.timestamp_ms
                    }
            except Exception as e:
                print(f"[{self.name}] Mouse tracking failed: {e}")

        # Fallback to basic pyautogui
        x, y = pyautogui.position()
        return {
            "x": float(x),
            "y": float(y),
            "confidence": 1.0,
            "timestamp": 0
        }

    async def set_visual_feedback(self, enabled: bool) -> bool:
        """
        Control moiré overlay visibility for visual feedback

        Args:
            enabled: True to show overlay, False to hide

        Returns:
            True if successful
        """
        if not self.moire_connected:
            return False

        try:
            if enabled:
                return self.moire.set_active()
            else:
                return self.moire.set_standby()
        except Exception as e:
            print(f"[{self.name}] Visual feedback control failed: {e}")
            return False

    async def process_task(self, task: str, context: Optional[str] = None) -> str:
        """
        Process a delegated task with visual feedback

        Args:
            task: The task to perform
            context: Additional context

        Returns:
            Task result
        """
        # Show moiré overlay (visual feedback) when working
        if self.moire_connected:
            self.moire.set_active()

        result_parts = [f"[{self.name}] Processing: {task}"]

        task_lower = task.lower()

        try:
            # Desktop element commands (MoireTracker enhanced)
            if any(word in task_lower for word in ["desktop", "what's on", "list", "scan", "applications", "icons"]):
                elements = await self.scan_desktop_elements()
                if elements:
                    result_parts.append(f"\nFound {len(elements)} desktop elements:")
                    # Show first 10
                    for i, elem in enumerate(elements[:10]):
                        result_parts.append(f"  {i+1}. {elem['name']} ({elem['app']}) at {elem['position']}")
                    if len(elements) > 10:
                        result_parts.append(f"  ... and {len(elements) - 10} more")
                else:
                    result_parts.append("No desktop elements found")

            elif any(word in task_lower for word in ["find", "where is", "locate"]):
                # Extract search term (simple heuristic)
                words = task_lower.split()
                search_term = None
                for i, word in enumerate(words):
                    if word in ["find", "locate", "where"] and i + 1 < len(words):
                        search_term = " ".join(words[i+1:])
                        break

                if search_term:
                    elem = await self.find_desktop_element(search_term, exact_match=False)
                    if elem:
                        result_parts.append(f"\nFound '{elem['name']}' at position {elem['position']}")
                        result_parts.append(f"  App: {elem['app']}")
                        result_parts.append(f"  Confidence: {elem['confidence']:.2f}")
                    else:
                        result_parts.append(f"\nCould not find '{search_term}' on desktop")
                else:
                    result_parts.append("Please specify what to find")

            elif any(word in task_lower for word in ["mouse", "cursor", "pointer"]):
                mouse_info = await self.get_mouse_info()
                result_parts.append(f"\nMouse position: ({mouse_info['x']:.1f}, {mouse_info['y']:.1f})")
                result_parts.append(f"Confidence: {mouse_info['confidence']:.2f}")

            # Original commands
            elif "screenshot" in task_lower or "capture" in task_lower:
                result = await self.take_screenshot()
                result_parts.append(result)

            elif "ocr" in task_lower or "text" in task_lower:
                result = await self.perform_ocr("screen")
                result_parts.append(result)

            else:
                result_parts.append("\nAvailable commands:")
                result_parts.append("  - 'What's on my desktop?' (scan all icons)")
                result_parts.append("  - 'Find Chrome' (locate specific app)")
                result_parts.append("  - 'Where is my mouse?' (mouse position)")
                result_parts.append("  - 'Take screenshot'")
                result_parts.append("  - 'Perform OCR'")

        finally:
            # Hide overlay when done
            if self.moire_connected:
                self.moire.set_standby()

        return "\n".join(result_parts)
