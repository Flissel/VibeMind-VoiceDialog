"""
VibeMind Three.js Multiverse Server

Serves the Three.js glass bubble visualization and provides WebSocket
communication for bidirectional Python-JavaScript interaction.

Usage:
    python threejs_multiverse_server.py

Opens browser automatically to http://localhost:8080
"""

import asyncio
import json
import webbrowser
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Callable, Set
import logging

# HTTP server
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

# WebSocket server
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("Warning: websockets not installed. Run: pip install websockets")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Bubble:
    """Represents a single bubble/universe in the multiverse."""
    id: int
    title: str
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    color: int = 0x4488ff  # Hex color
    radius: float = 0.7
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "position": self.position,
            "color": self.color,
            "radius": self.radius,
        }


# ============================================================================
# MULTIVERSE STATE
# ============================================================================

class MultiverseState:
    """Manages the state of all bubbles and connected clients."""

    def __init__(self):
        self.bubbles: Dict[int, Bubble] = {}
        self.next_id = 1
        self.clients: Set = set()
        self.on_bubble_selected: Optional[Callable[[int, str], None]] = None
        self.on_client_connected: Optional[Callable[[], None]] = None

    def add_bubble(self, title: str, position: Dict[str, float] = None,
                   color: int = 0x4488ff, radius: float = 0.7) -> Bubble:
        """Add a new bubble and notify all clients."""
        bubble = Bubble(
            id=self.next_id,
            title=title,
            position=position or {"x": 0, "y": 0, "z": 0},
            color=color,
            radius=radius
        )
        self.bubbles[bubble.id] = bubble
        self.next_id += 1

        # Notify clients
        asyncio.create_task(self.broadcast({
            "type": "add_bubble",
            "bubble": bubble.to_dict()
        }))

        return bubble

    def remove_bubble(self, id: int) -> bool:
        """Remove a bubble and notify all clients."""
        if id in self.bubbles:
            del self.bubbles[id]
            asyncio.create_task(self.broadcast({
                "type": "remove_bubble",
                "id": id
            }))
            return True
        return False

    def update_bubble(self, id: int, **kwargs) -> Optional[Bubble]:
        """Update bubble properties and notify clients."""
        if id not in self.bubbles:
            return None

        bubble = self.bubbles[id]
        for key, value in kwargs.items():
            if hasattr(bubble, key):
                setattr(bubble, key, value)

        # Send full update
        asyncio.create_task(self.broadcast({
            "type": "update_bubbles",
            "bubbles": [bubble.to_dict()]
        }))

        return bubble

    def get_all_bubbles(self) -> List[dict]:
        """Get all bubbles as dictionaries."""
        return [b.to_dict() for b in self.bubbles.values()]

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        if not self.clients:
            return

        data = json.dumps(message)
        await asyncio.gather(
            *[client.send(data) for client in self.clients],
            return_exceptions=True
        )

    async def handle_client_message(self, message: dict):
        """Handle incoming messages from Three.js client."""
        msg_type = message.get("type")

        if msg_type == "ready":
            logger.info("Client ready, sending initial state")
            # Send all bubbles to new client
            await self.broadcast({
                "type": "update_bubbles",
                "bubbles": self.get_all_bubbles()
            })
            if self.on_client_connected:
                self.on_client_connected()

        elif msg_type == "bubble_selected":
            bubble_id = message.get("id")
            title = message.get("title")
            logger.info(f"Bubble selected: {title} (id={bubble_id})")
            if self.on_bubble_selected:
                self.on_bubble_selected(bubble_id, title)


# Global state
state = MultiverseState()


# ============================================================================
# HTTP SERVER (serves static files)
# ============================================================================

class MultiverseHTTPHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler to serve from web directory."""

    def __init__(self, *args, **kwargs):
        # Set the directory to serve
        web_dir = Path(__file__).parent.parent / "web"
        super().__init__(*args, directory=str(web_dir), **kwargs)

    def log_message(self, format, *args):
        # Quieter logging
        pass


def run_http_server(port: int = 8080):
    """Run HTTP server in a background thread."""
    server = HTTPServer(("localhost", port), MultiverseHTTPHandler)
    logger.info(f"HTTP server running on http://localhost:{port}")
    server.serve_forever()


# ============================================================================
# WEBSOCKET SERVER
# ============================================================================

async def websocket_handler(websocket, path=None):
    """Handle WebSocket connections from Three.js client."""
    logger.info(f"Client connected: {websocket.remote_address}")
    state.clients.add(websocket)

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                await state.handle_client_message(data)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON: {message}")
    except websockets.ConnectionClosed:
        pass
    finally:
        state.clients.discard(websocket)
        logger.info("Client disconnected")


async def run_websocket_server(port: int = 8765):
    """Run WebSocket server."""
    if not HAS_WEBSOCKETS:
        logger.error("websockets library not installed!")
        return

    async with websockets.serve(websocket_handler, "localhost", port):
        logger.info(f"WebSocket server running on ws://localhost:{port}")
        await asyncio.Future()  # Run forever


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class MultiverseApp:
    """Main application coordinating servers and state."""

    def __init__(self, http_port: int = 8088, ws_port: int = 8765):
        self.http_port = http_port
        self.ws_port = ws_port
        self.state = state

        # Set up callbacks
        self.state.on_bubble_selected = self._on_bubble_selected
        self.state.on_client_connected = self._on_client_connected

    def _on_bubble_selected(self, id: int, title: str):
        """Called when user selects a bubble in the UI."""
        print(f"\n>>> Bubble Selected: {title} (id={id})")
        # Override this in your application

    def _on_client_connected(self):
        """Called when browser connects."""
        print(">>> Browser connected!")

    def add_bubble(self, title: str, x: float = 0, y: float = 0, z: float = 0,
                   color: int = 0x4488ff, radius: float = 0.7) -> Bubble:
        """Add a bubble to the multiverse."""
        return self.state.add_bubble(
            title=title,
            position={"x": x, "y": y, "z": z},
            color=color,
            radius=radius
        )

    def remove_bubble(self, id: int):
        """Remove a bubble by ID."""
        self.state.remove_bubble(id)

    def update_bubble(self, id: int, **kwargs):
        """Update a bubble's properties."""
        self.state.update_bubble(id, **kwargs)

    async def run(self, open_browser: bool = True):
        """Start all servers and run the application."""
        # Start HTTP server in background thread
        http_thread = threading.Thread(
            target=run_http_server,
            args=(self.http_port,),
            daemon=True
        )
        http_thread.start()

        # Open browser
        if open_browser:
            url = f"http://localhost:{self.http_port}/glass_bubbles.html"
            webbrowser.open(url)
            print(f"\n[*] Opening: {url}")

        # Run WebSocket server
        print("\n" + "=" * 60)
        print("VIBEMIND MULTIVERSE SERVER")
        print("=" * 60)
        print(f"HTTP:      http://localhost:{self.http_port}")
        print(f"WebSocket: ws://localhost:{self.ws_port}")
        print("=" * 60)
        print("\nPress Ctrl+C to stop\n")

        await run_websocket_server(self.ws_port)


# ============================================================================
# DEMO
# ============================================================================

async def demo():
    """Demo showing how to use the multiverse."""
    app = MultiverseApp()

    # Add some initial bubbles
    app.add_bubble("Universe Alpha", x=-2, y=0.5, z=0, color=0x4488ff, radius=0.8)
    app.add_bubble("Universe Beta", x=2, y=-0.5, z=-1, color=0xff4488, radius=0.7)
    app.add_bubble("Research Hub", x=0, y=1.5, z=1, color=0x44ff88, radius=0.6)
    app.add_bubble("Creative Space", x=-1, y=-1, z=2, color=0xffaa44, radius=0.75)
    app.add_bubble("Data Nexus", x=1.5, y=0, z=-2, color=0xaa44ff, radius=0.65)

    # Start the server
    await app.run(open_browser=True)


if __name__ == "__main__":
    try:
        asyncio.run(demo())
    except KeyboardInterrupt:
        print("\n\nShutting down...")
