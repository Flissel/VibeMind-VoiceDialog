"""
Light Planet WebSocket Server

Sendet Hand-Gesten und Position-Daten an die Three.js Light Planet Visualisierung.

Usage:
    python light_planet_server.py
    
    Dann öffne: http://localhost:8088/light_planet.html
"""

import asyncio
import json
import webbrowser
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Set, Callable
from http.server import HTTPServer, SimpleHTTPRequestHandler
import logging

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("Warning: websockets nicht installiert. Run: pip install websockets")

from .light_planet import get_light_planet, LightPlanetRenderer, HandGesture
from .hand_motion import get_hand_detector, HandMotionDetector, GestureType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LightPlanetServer:
    """
    WebSocket Server für die Light Planet Visualisierung.
    
    Verbindet Hand Motion Detection mit der Three.js Darstellung.
    """
    
    def __init__(self, http_port: int = 8088, ws_port: int = 8766):
        self.http_port = http_port
        self.ws_port = ws_port
        
        self.clients: Set = set()
        self.planet = get_light_planet()
        self.hand_detector = get_hand_detector()
        
        # Callbacks registrieren
        self.hand_detector.on_gesture_detected = self._on_gesture
        self.hand_detector.on_hand_position_changed = self._on_hand_position
        
        # Custom message handlers
        self.on_client_ready: Optional[Callable[[], None]] = None
    
    def _on_gesture(self, detected_hand):
        """Callback wenn eine Geste erkannt wird."""
        gesture_name = detected_hand.gesture.value
        logger.info(f"[LightPlanet] Geste erkannt: {gesture_name}")
        
        # An Planet-Renderer weiterleiten
        hand_gesture = HandGesture(
            gesture_type=gesture_name,
            position=detected_hand.landmarks.get_palm_center(),
            velocity=detected_hand.velocity,
            confidence=detected_hand.landmarks.confidence
        )
        self.planet.process_hand_gesture(hand_gesture)
        
        # An Three.js senden
        asyncio.create_task(self.broadcast({
            "type": "gesture",
            "gesture": gesture_name
        }))
    
    def _on_hand_position(self, position: Dict[str, float]):
        """Callback wenn sich die Hand-Position ändert."""
        # An Three.js senden
        asyncio.create_task(self.broadcast({
            "type": "hand_position",
            "x": position.get("x", 0.5),
            "y": position.get("y", 0.5),
            "z": position.get("z", 0.0)
        }))
    
    async def broadcast(self, message: Dict[str, Any]):
        """Sende Nachricht an alle verbundenen Clients."""
        if not self.clients:
            return
        
        data = json.dumps(message)
        await asyncio.gather(
            *[client.send(data) for client in self.clients],
            return_exceptions=True
        )
    
    async def handle_client(self, websocket, path=None):
        """Handle eine WebSocket-Verbindung."""
        logger.info(f"[LightPlanet] Client verbunden: {websocket.remote_address}")
        self.clients.add(websocket)
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(data, websocket)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON: {message}")
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            logger.info("[LightPlanet] Client disconnected")
    
    async def _handle_message(self, data: Dict[str, Any], websocket):
        """Verarbeite eingehende Nachrichten."""
        msg_type = data.get("type")
        
        if msg_type == "ready":
            logger.info(f"[LightPlanet] Client ready: {data.get('space', 'unknown')}")
            
            # Sende initiale Planet-Konfiguration
            await websocket.send(json.dumps({
                "type": "planet_config",
                **self.planet.get_three_js_config()
            }))
            
            if self.on_client_ready:
                self.on_client_ready()
        
        elif msg_type == "gesture_test":
            # Test-Gesten vom UI
            gesture = data.get("gesture", "none")
            self.simulate_gesture(gesture)
    
    def simulate_gesture(self, gesture_name: str, 
                        position: Optional[Dict[str, float]] = None):
        """
        Simuliere eine Geste (für Tests ohne Webcam).
        
        Args:
            gesture_name: Name der Geste (open, closed, pointing, spread, pinch)
            position: Optionale Position
        """
        gesture_map = {
            "open": GestureType.OPEN_HAND,
            "closed": GestureType.CLOSED_FIST,
            "pointing": GestureType.POINTING,
            "spread": GestureType.SPREAD_FINGERS,
            "pinch": GestureType.PINCH,
            "none": GestureType.NONE,
        }
        
        gesture_type = gesture_map.get(gesture_name, GestureType.NONE)
        self.hand_detector.simulate_gesture(gesture_type, position)
    
    async def start_websocket_server(self):
        """Starte den WebSocket Server."""
        if not HAS_WEBSOCKETS:
            logger.error("websockets not installed!")
            return
        
        async with websockets.serve(self.handle_client, "localhost", self.ws_port):
            logger.info(f"[LightPlanet] WebSocket server: ws://localhost:{self.ws_port}")
            await asyncio.Future()  # Laufe endlos
    
    def start_http_server(self):
        """Starte den HTTP Server für statische Dateien."""
        web_dir = Path(__file__).parent.parent.parent.parent / "web"
        
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(web_dir), **kwargs)
            
            def log_message(self, format, *args):
                pass  # Quiet logging
        
        server = HTTPServer(("localhost", self.http_port), Handler)
        logger.info(f"[LightPlanet] HTTP server: http://localhost:{self.http_port}")
        server.serve_forever()
    
    async def run(self, open_browser: bool = True):
        """
        Starte alle Server.
        
        Args:
            open_browser: Browser automatisch öffnen
        """
        # HTTP Server in Background Thread
        http_thread = threading.Thread(
            target=self.start_http_server,
            daemon=True
        )
        http_thread.start()
        
        # Planet Renderer starten
        await self.planet.start()
        
        # Browser öffnen
        if open_browser:
            url = f"http://localhost:{self.http_port}/light_planet.html"
            webbrowser.open(url)
            logger.info(f"[LightPlanet] Opening: {url}")
        
        # Info ausgeben
        print("\n" + "=" * 60)
        print("VIBEMIND LIGHT PLANET SERVER")
        print("=" * 60)
        print(f"HTTP:      http://localhost:{self.http_port}/light_planet.html")
        print(f"WebSocket: ws://localhost:{self.ws_port}")
        print("=" * 60)
        print("\nGesten-Buttons im Browser zum Testen verfügbar.")
        print("Drücke Ctrl+C zum Beenden.\n")
        
        # WebSocket Server starten
        await self.start_websocket_server()
    
    async def start_hand_detection(self, camera_index: int = 0):
        """
        Starte die Webcam Hand-Erkennung.
        
        Args:
            camera_index: Kamera-Index (0 = Standard-Webcam)
        """
        logger.info(f"[LightPlanet] Starte Hand Detection mit Kamera {camera_index}")
        await self.hand_detector.start(camera_index)
    
    async def stop(self):
        """Stoppe alle Server."""
        await self.planet.stop()
        await self.hand_detector.stop()
        logger.info("[LightPlanet] Server gestoppt")


# Globale Server-Instanz
_server: Optional[LightPlanetServer] = None


def get_server() -> LightPlanetServer:
    """Hole die globale Server-Instanz."""
    global _server
    if _server is None:
        _server = LightPlanetServer()
    return _server


async def main():
    """Hauptfunktion zum Starten des Servers."""
    server = get_server()
    await server.run(open_browser=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nServer wird beendet...")