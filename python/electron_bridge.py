"""
Electron Bridge - Python subprocess wrapper for MoireTrackerClient

Receives commands from Electron (via stdin) and executes them using MoireTrackerClient.
Sends responses back to Electron (via stdout) as JSON.

Protocol:
---------
Request (from Electron):
{
    "request_id": 1,
    "command": "click_element",
    "params": {"name": "Chrome"}
}

Response (to Electron):
{
    "request_id": 1,
    "success": true,
    "data": {...},
    "error": null
}
"""

import sys
import json
import asyncio
import logging
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

# CRITICAL: Configure logging to stderr ONLY **BEFORE** importing voice_dialog modules
# stdout is reserved for JSON responses to Electron
# This MUST happen before any voice_dialog imports because logger.py writes to stdout
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(name)s - %(message)s',
    stream=sys.stderr,  # All logs go to stderr
    force=True  # Override any existing configuration
)

# Disable the voice_dialog logger module completely
import os
os.environ['DISABLE_LOGGER_INIT'] = '1'

# Now it's safe to import voice_dialog modules
from tools.moire_client import MoireTrackerClient
from tools.moire_service import MoireTrackerService

logger = logging.getLogger(__name__)


class ElectronBridge:
    """
    Bridge between Electron (TypeScript) and MoireTrackerClient (Python)
    """

    def __init__(self):
        self.client = None
        self.service = None
        self.running = True

    def send_response(self, request_id: int, success: bool, data=None, error=None):
        """
        Send JSON response to Electron via stdout

        CRITICAL: Only JSON responses go to stdout!
        All other output (logs, errors) MUST go to stderr
        """
        response = {
            "request_id": request_id,
            "success": success,
            "data": data or {},
            "error": error
        }

        # Write to stdout (Electron reads this)
        print(json.dumps(response), flush=True)

    async def handle_initialize(self, request_id: int, params: dict):
        """Initialize MoireTracker service and client"""
        try:
            logger.info("Initializing MoireTracker...")

            # Start MoireTracker service
            self.service = MoireTrackerService()
            if not self.service.start():
                raise Exception("Failed to start MoireTracker service")

            logger.info("MoireTracker service started successfully")

            # Create and connect client
            self.client = MoireTrackerClient()
            if not self.client.connect():
                raise Exception("Failed to connect to MoireTracker")

            logger.info("Connected to MoireTracker successfully")

            # Send success response
            self.send_response(request_id, True, {
                "message": "MoireTracker initialized successfully",
                "backend": self.client.ipc.get_backend_name()
            })

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            self.send_response(request_id, False, error=str(e))

    async def handle_scan_desktop(self, request_id: int, params: dict):
        """Scan desktop for all elements"""
        try:
            if not self.client or not self.client.is_connected():
                raise Exception("Not connected to MoireTracker")

            logger.info("Scanning desktop...")
            elements = self.client.scan_desktop()

            # Convert elements to dicts
            elements_data = [{
                "id": el.id,
                "type": el.type.name,
                "name": el.name,
                "x": el.x,
                "y": el.y,
                "width": el.width,
                "height": el.height,
                "clickable": el.clickable,
                "confidence": el.confidence
            } for el in elements]

            logger.info(f"Found {len(elements)} desktop elements")

            self.send_response(request_id, True, {
                "elements": elements_data,
                "count": len(elements)
            })

        except Exception as e:
            logger.error(f"Desktop scan failed: {e}")
            self.send_response(request_id, False, error=str(e))

    async def handle_find_element(self, request_id: int, params: dict):
        """Find element by name"""
        try:
            if not self.client or not self.client.is_connected():
                raise Exception("Not connected to MoireTracker")

            name = params.get("name")
            if not name:
                raise Exception("Element name not provided")

            logger.info(f"Finding element: {name}")
            element = self.client.find_element(name)

            if element:
                element_data = {
                    "id": element.id,
                    "type": element.type.name,
                    "name": element.name,
                    "x": element.x,
                    "y": element.y,
                    "width": element.width,
                    "height": element.height,
                    "clickable": element.clickable,
                    "confidence": element.confidence
                }
                logger.info(f"Found element: {element.name}")
                self.send_response(request_id, True, {"element": element_data})
            else:
                logger.warning(f"Element not found: {name}")
                self.send_response(request_id, True, {"element": None})

        except Exception as e:
            logger.error(f"Find element failed: {e}")
            self.send_response(request_id, False, error=str(e))

    async def handle_click_element(self, request_id: int, params: dict):
        """Click element by name"""
        try:
            if not self.client or not self.client.is_connected():
                raise Exception("Not connected to MoireTracker")

            name = params.get("name")
            if not name:
                raise Exception("Element name not provided")

            logger.info(f"Clicking element: {name}")
            success = self.client.click_element(name)

            if success:
                logger.info(f"Successfully clicked: {name}")
            else:
                logger.warning(f"Click failed: {name}")

            self.send_response(request_id, True, {
                "success": success,
                "element_name": name
            })

        except Exception as e:
            logger.error(f"Click element failed: {e}")
            self.send_response(request_id, False, error=str(e))

    async def handle_get_mouse_position(self, request_id: int, params: dict):
        """Get current mouse position"""
        try:
            if not self.client or not self.client.is_connected():
                raise Exception("Not connected to MoireTracker")

            logger.info("Getting mouse position...")
            mouse_pos = self.client.get_mouse_position()

            if mouse_pos:
                position_data = {
                    "x": mouse_pos.x,
                    "y": mouse_pos.y,
                    "confidence": mouse_pos.confidence,
                    "timestamp": mouse_pos.timestamp
                }
                logger.info(f"Mouse at ({mouse_pos.x:.2f}, {mouse_pos.y:.2f})")
                self.send_response(request_id, True, {"position": position_data})
            else:
                logger.warning("Failed to get mouse position")
                self.send_response(request_id, True, {"position": None})

        except Exception as e:
            logger.error(f"Get mouse position failed: {e}")
            self.send_response(request_id, False, error=str(e))

    async def handle_focus_window(self, request_id: int, params: dict):
        """Focus a window by title or process name"""
        try:
            if not self.client or not self.client.is_connected():
                raise Exception("Not connected to MoireTracker")

            identifier = params.get("identifier")
            by_title = params.get("by_title", True)

            if not identifier:
                raise Exception("Window identifier not provided")

            logger.info(f"Focusing window: {identifier}")
            success = self.client.focus_window(identifier, by_title)

            if success:
                logger.info(f"Successfully focused window: {identifier}")
            else:
                logger.warning(f"Focus window failed: {identifier}")

            self.send_response(request_id, True, {
                "success": success,
                "identifier": identifier
            })

        except Exception as e:
            logger.error(f"Focus window failed: {e}")
            self.send_response(request_id, False, error=str(e))

    async def handle_close_window(self, request_id: int, params: dict):
        """Close a window by title or process name"""
        try:
            if not self.client or not self.client.is_connected():
                raise Exception("Not connected to MoireTracker")

            identifier = params.get("identifier")
            by_title = params.get("by_title", True)
            force = params.get("force", False)

            if not identifier:
                raise Exception("Window identifier not provided")

            logger.info(f"Closing window: {identifier} (force={force})")
            success = self.client.close_window(identifier, by_title, force)

            if success:
                logger.info(f"Successfully closed window: {identifier}")
            else:
                logger.warning(f"Close window failed: {identifier}")

            self.send_response(request_id, True, {
                "success": success,
                "identifier": identifier
            })

        except Exception as e:
            logger.error(f"Close window failed: {e}")
            self.send_response(request_id, False, error=str(e))

    async def handle_resize_window(self, request_id: int, params: dict):
        """Resize and reposition a window"""
        try:
            if not self.client or not self.client.is_connected():
                raise Exception("Not connected to MoireTracker")

            identifier = params.get("identifier")
            by_title = params.get("by_title", True)
            x = params.get("x")
            y = params.get("y")
            width = params.get("width")
            height = params.get("height")

            if not identifier:
                raise Exception("Window identifier not provided")
            if None in (x, y, width, height):
                raise Exception("Window dimensions not fully specified")

            logger.info(f"Resizing window: {identifier} to ({x}, {y}, {width}x{height})")
            success = self.client.resize_window(identifier, x, y, width, height, by_title)

            if success:
                logger.info(f"Successfully resized window: {identifier}")
            else:
                logger.warning(f"Resize window failed: {identifier}")

            self.send_response(request_id, True, {
                "success": success,
                "identifier": identifier
            })

        except Exception as e:
            logger.error(f"Resize window failed: {e}")
            self.send_response(request_id, False, error=str(e))

    async def handle_get_active_window(self, request_id: int, params: dict):
        """Get information about the currently active window"""
        try:
            if not self.client or not self.client.is_connected():
                raise Exception("Not connected to MoireTracker")

            logger.info("Getting active window...")
            window = self.client.get_active_window()

            if window:
                window_data = {
                    "hwnd": window.hwnd,
                    "title": window.title,
                    "class_name": window.class_name,
                    "process_name": window.process_name,
                    "process_id": window.process_id,
                    "rect": {
                        "left": window.left,
                        "top": window.top,
                        "right": window.right,
                        "bottom": window.bottom
                    },
                    "is_visible": window.is_visible,
                    "is_minimized": window.is_minimized,
                    "is_maximized": window.is_maximized,
                    "z_order": window.z_order
                }
                logger.info(f"Active window: {window.title}")
                self.send_response(request_id, True, {"window": window_data})
            else:
                logger.warning("No active window")
                self.send_response(request_id, True, {"window": None})

        except Exception as e:
            logger.error(f"Get active window failed: {e}")
            self.send_response(request_id, False, error=str(e))

    async def handle_click_window(self, request_id: int, params: dict):
        """Click at a specific offset within a window"""
        try:
            if not self.client or not self.client.is_connected():
                raise Exception("Not connected to MoireTracker")

            identifier = params.get("identifier")
            by_title = params.get("by_title", True)
            x_offset = params.get("x_offset", 0)
            y_offset = params.get("y_offset", 0)

            if not identifier:
                raise Exception("Window identifier not provided")

            logger.info(f"Clicking window: {identifier} at offset ({x_offset}, {y_offset})")
            success = self.client.click_window(identifier, x_offset, y_offset, by_title)

            if success:
                logger.info(f"Successfully clicked window: {identifier}")
            else:
                logger.warning(f"Click window failed: {identifier}")

            self.send_response(request_id, True, {
                "success": success,
                "identifier": identifier
            })

        except Exception as e:
            logger.error(f"Click window failed: {e}")
            self.send_response(request_id, False, error=str(e))

    async def handle_shutdown(self, request_id: int, params: dict):
        """Shutdown MoireTracker and exit"""
        try:
            logger.info("Shutting down...")

            if self.client:
                self.client.disconnect()

            if self.service:
                self.service.stop()

            self.send_response(request_id, True, {"message": "Shutdown successful"})

            # Stop event loop
            self.running = False

        except Exception as e:
            logger.error(f"Shutdown failed: {e}")
            self.send_response(request_id, False, error=str(e))

    async def process_command(self, command_data: dict):
        """Process a single command from Electron"""
        request_id = command_data.get("request_id")
        command = command_data.get("command")
        params = command_data.get("params", {})

        logger.info(f"Processing command: {command} (ID: {request_id})")

        # Route to appropriate handler
        if command == "initialize":
            await self.handle_initialize(request_id, params)
        elif command == "scan_desktop":
            await self.handle_scan_desktop(request_id, params)
        elif command == "find_element":
            await self.handle_find_element(request_id, params)
        elif command == "click_element":
            await self.handle_click_element(request_id, params)
        elif command == "get_mouse_position":
            await self.handle_get_mouse_position(request_id, params)
        elif command == "focus_window":
            await self.handle_focus_window(request_id, params)
        elif command == "close_window":
            await self.handle_close_window(request_id, params)
        elif command == "resize_window":
            await self.handle_resize_window(request_id, params)
        elif command == "get_active_window":
            await self.handle_get_active_window(request_id, params)
        elif command == "click_window":
            await self.handle_click_window(request_id, params)
        elif command == "shutdown":
            await self.handle_shutdown(request_id, params)
        else:
            logger.error(f"Unknown command: {command}")
            self.send_response(request_id, False, error=f"Unknown command: {command}")

    async def run(self):
        """Main event loop - read commands from stdin"""
        logger.info("Electron Bridge started, waiting for commands...")

        # Send ready signal (JSON to stdout)
        print(json.dumps({"ready": True}), flush=True)

        while self.running:
            try:
                # Read command from stdin (blocking)
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )

                if not line:
                    # EOF reached
                    logger.info("Stdin closed, exiting...")
                    break

                # Parse command
                command_data = json.loads(line)
                await self.process_command(command_data)

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
            except Exception as e:
                logger.error(f"Error processing command: {e}")

        logger.info("Electron Bridge exiting")


async def main():
    """Entry point"""
    bridge = ElectronBridge()
    await bridge.run()


if __name__ == "__main__":
    asyncio.run(main())
