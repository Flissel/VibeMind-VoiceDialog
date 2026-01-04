#!/usr/bin/env python
"""
VibeMind Hand Tracking WebSocket Server

Streams hand gesture data to clients (like Electron's multiverse.js) via WebSocket.
Requires MediaPipe and webcam for real hand detection.

SIMPLIFIED: Only SWIPE_LEFT and SWIPE_RIGHT gestures for space navigation.

Usage:
    python hand_tracking_server.py
    python hand_tracking_server.py --camera 1  # Use different camera

Port: 8766 (default)
"""

import asyncio
import json
import sys
import time
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import WebSocket and hand detection
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    logger.error("websockets not installed. Run: pip install websockets")
    sys.exit(1)

# Add parent directory to path for hand detection import
sys.path.insert(0, str(Path(__file__).parent))

try:
    from spaces.desktop_automation.hand_motion import (
        get_hand_detector, HandMotionDetector, GestureType, HAS_OPENCV, HAS_MEDIAPIPE,
    )
    HAS_HAND_DETECTION = HAS_OPENCV and HAS_MEDIAPIPE
except ImportError as e:
    HAS_HAND_DETECTION = False
    logger.error(f"Hand detection not available: {e}")
    logger.error("Install with: pip install opencv-python mediapipe")
    sys.exit(1)

if not HAS_HAND_DETECTION:
    logger.error("OpenCV and MediaPipe are required for hand tracking!")
    logger.error("Install with: pip install opencv-python mediapipe")
    sys.exit(1)


class HandTrackingServer:
    """
    WebSocket server that streams hand tracking data using MediaPipe.

    SIMPLIFIED: Only detects SWIPE_LEFT and SWIPE_RIGHT for space navigation.

    Clients connect to ws://localhost:8766 and receive:
    {
        "gesture": "SWIPE_LEFT" | "SWIPE_RIGHT" | "NONE",
        "position": {"x": 0.0-1.0, "y": 0.0-1.0},
        "hand_position": {"x": 0.0-1.0, "y": 0.0-1.0}
    }
    """

    # Swipe detection thresholds
    SWIPE_THRESHOLD = 0.15  # Minimum x-movement to trigger swipe
    SWIPE_COOLDOWN = 1.5    # Seconds between swipes

    def __init__(self, port: int = 8766, camera_index: int = 0):
        self.port = port
        self.camera_index = camera_index
        self.clients = set()
        self.detector = None
        self.current_gesture = "NONE"
        self.current_position = {"x": 0.5, "y": 0.5}
        self.previous_position = {"x": 0.5, "y": 0.5}
        self.running = False
        
        # Swipe detection state
        self.last_swipe_time = 0
        self.swipe_start_x = None

    async def start_detection(self) -> bool:
        """Start hand detection with webcam."""
        self.detector = get_hand_detector()
        
        # Check dependencies
        ok, msg = self.detector.check_dependencies()
        if not ok:
            logger.error(f"Dependencies check failed: {msg}")
            return False
            
        # Setup callbacks
        self.detector.on_gesture_detected = self._on_gesture
        self.detector.on_hand_position_changed = self._on_position
        
        # Start detection
        success = await self.detector.start(self.camera_index)
        if success:
            logger.info(f"Hand detection started with camera {self.camera_index}")
        else:
            logger.error(f"Failed to start webcam (camera index: {self.camera_index})")
            return False
        return True
        
    def _on_gesture(self, detected_hand):
        """Callback when gesture detected (from real detection)."""
        # We track position for swipe detection
        pass
        
    def _on_position(self, position):
        """Callback when hand position changes."""
        self.previous_position = self.current_position.copy()
        self.current_position = position
        
        # Detect swipe based on position change
        self._detect_swipe()
        
    def _detect_swipe(self):
        """Detect swipe gesture from hand movement."""
        current_time = time.time()
        
        # Check cooldown
        if current_time - self.last_swipe_time < self.SWIPE_COOLDOWN:
            return
            
        # Track swipe start
        if self.swipe_start_x is None:
            self.swipe_start_x = self.current_position["x"]
            return
            
        # Calculate horizontal movement
        dx = self.current_position["x"] - self.swipe_start_x
        
        # Check if movement exceeds threshold
        if abs(dx) >= self.SWIPE_THRESHOLD:
            if dx > 0:
                self.current_gesture = "SWIPE_RIGHT"
                logger.info("🔄 Detected: SWIPE_RIGHT (→)")
            else:
                self.current_gesture = "SWIPE_LEFT"
                logger.info("🔄 Detected: SWIPE_LEFT (←)")
                
            # Reset for next swipe
            self.last_swipe_time = current_time
            self.swipe_start_x = None
            
            # Broadcast the gesture
            asyncio.create_task(self._broadcast_state())
            
            # Reset gesture after a brief moment
            asyncio.create_task(self._reset_gesture_after_delay())
            
    async def _reset_gesture_after_delay(self):
        """Reset gesture to NONE after brief delay."""
        await asyncio.sleep(0.5)
        self.current_gesture = "NONE"
    
    async def _broadcast_state(self):
        """Send current state to all clients."""
        if not self.clients:
            return
            
        data = json.dumps({
            "gesture": self.current_gesture,
            "position": self.current_position,
            "hand_position": self.current_position
        })
        
        # Send to all clients
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(data)
            except:
                disconnected.add(client)
                
        # Clean up disconnected clients
        self.clients -= disconnected
        
    async def websocket_handler(self, websocket, path=None):
        """Handle WebSocket connections."""
        logger.info(f"Client connected: {websocket.remote_address}")
        self.clients.add(websocket)
        
        # Send initial state
        try:
            await websocket.send(json.dumps({
                "gesture": self.current_gesture,
                "position": self.current_position,
                "hand_position": self.current_position,
                "connected": True
            }))
        except:
            pass
        
        try:
            async for message in websocket:
                # Parse incoming messages (for manual testing)
                try:
                    data = json.loads(message)
                    logger.info(f"Received: {data}")
                    
                    # Handle manual gesture commands for testing
                    if data.get("command") == "swipe_left":
                        self.current_gesture = "SWIPE_LEFT"
                        await self._broadcast_state()
                        await self._reset_gesture_after_delay()
                    elif data.get("command") == "swipe_right":
                        self.current_gesture = "SWIPE_RIGHT"
                        await self._broadcast_state()
                        await self._reset_gesture_after_delay()
                except:
                    pass
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            logger.info("Client disconnected")
            
    async def run(self):
        """Run the WebSocket server."""
        self.running = True
        
        # Start hand detection
        if not await self.start_detection():
            logger.error("Failed to start hand detection. Exiting.")
            return
        
        print("\n" + "=" * 60)
        print("VIBEMIND HAND TRACKING SERVER")
        print("=" * 60)
        print(f"WebSocket: ws://localhost:{self.port}")
        print(f"Camera: {self.camera_index}")
        print()
        print("Gestures for Space-Navigation:")
        print("  SWIPE_LEFT  (←)  - navigate to left space")
        print("  SWIPE_RIGHT (→)  - navigate to right space")
        print("=" * 60)
        print("\nPress Ctrl+C to stop\n")
        
        # Start periodic position broadcast
        asyncio.create_task(self._periodic_broadcast())
        
        # Start WebSocket server
        async with websockets.serve(self.websocket_handler, "localhost", self.port):
            await asyncio.Future()  # Run forever
            
    async def _periodic_broadcast(self):
        """Periodically broadcast hand position."""
        while self.running:
            if self.clients:
                await self._broadcast_state()
            await asyncio.sleep(0.1)  # 10Hz updates
            
    async def stop(self):
        """Stop the server."""
        self.running = False
        if self.detector:
            await self.detector.stop()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Hand Tracking WebSocket Server (Swipe-Only)")
    parser.add_argument("--port", "-p", type=int, default=8766, help="Port (default: 8766)")
    parser.add_argument("--camera", "-c", type=int, default=0, help="Camera index (default: 0)")
    args = parser.parse_args()
    
    server = HandTrackingServer(port=args.port, camera_index=args.camera)
    
    try:
        await server.run()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())