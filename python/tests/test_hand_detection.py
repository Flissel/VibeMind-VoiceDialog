#!/usr/bin/env python
"""
Test Hand Detection with MediaPipe

Testet die Hand-Erkennung mit Webcam-Visualisierung.

Installation:
    pip install mediapipe opencv-python

Usage:
    python test_hand_detection.py
    
    Drücke 'q' zum Beenden.
"""

import sys
from pathlib import Path

# Füge python/ zum Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import cv2

from spaces.desktop_automation.hand_motion import (
    get_hand_detector,
    HandMotionDetector,
    GestureType,
    HAS_OPENCV,
    HAS_MEDIAPIPE,
)


class HandDetectionDemo:
    """Demo für Hand-Erkennung mit Visualisierung."""
    
    def __init__(self):
        self.detector = get_hand_detector()
        self.current_gesture = GestureType.NONE
        self.current_position = {"x": 0.5, "y": 0.5}
        self.frame_count = 0
        self.running = False
        self._current_frame = None
    
    def _on_gesture(self, detected_hand):
        """Callback für erkannte Gesten."""
        self.current_gesture = detected_hand.gesture
        self.frame_count += 1
    
    def _on_position(self, position):
        """Callback für Hand-Position."""
        self.current_position = position
    
    def _on_frame(self, frame):
        """Callback für verarbeitete Frames."""
        self._current_frame = frame
    
    async def run(self, camera_index: int = 0):
        """
        Starte die Demo.
        
        Args:
            camera_index: Kamera-Index (0 = Standard)
        """
        print("\n" + "=" * 60)
        print("HAND DETECTION DEMO")
        print("=" * 60)
        print(f"OpenCV verfügbar: {HAS_OPENCV}")
        print(f"MediaPipe verfügbar: {HAS_MEDIAPIPE}")
        print("=" * 60)
        
        # Prüfe Abhängigkeiten
        ok, msg = self.detector.check_dependencies()
        if not ok:
            print(f"\nERROR: {msg}")
            print("\nInstalliere mit:")
            print("  pip install mediapipe opencv-python")
            return
        
        # Callbacks setzen
        self.detector.on_gesture_detected = self._on_gesture
        self.detector.on_hand_position_changed = self._on_position
        self.detector.on_frame_processed = self._on_frame
        
        # Starte Erkennung
        print(f"\nStarte Webcam (Index: {camera_index})...")
        success = await self.detector.start(camera_index)
        
        if not success:
            print("ERROR: Konnte Kamera nicht öffnen!")
            return
        
        self.running = True
        print("\n[INFO] Hand vor die Kamera halten")
        print("[INFO] Drücke 'q' zum Beenden\n")
        
        # Visualisierungs-Loop
        try:
            while self.running:
                if self._current_frame is not None:
                    # Info auf Frame zeichnen
                    frame = self._current_frame.copy()
                    
                    # Geste anzeigen
                    gesture_text = f"Geste: {self.current_gesture.value.upper()}"
                    cv2.putText(
                        frame, gesture_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
                    )
                    
                    # Position anzeigen
                    pos_text = f"Pos: X={self.current_position['x']:.2f} Y={self.current_position['y']:.2f}"
                    cv2.putText(
                        frame, pos_text, (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2
                    )
                    
                    # Frame-Counter
                    cv2.putText(
                        frame, f"Frames: {self.frame_count}", (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1
                    )
                    
                    # Gesten-Feedback (farbiger Kreis)
                    gesture_colors = {
                        GestureType.NONE: (100, 100, 100),
                        GestureType.OPEN_HAND: (0, 255, 0),
                        GestureType.CLOSED_FIST: (0, 0, 255),
                        GestureType.POINTING: (255, 255, 0),
                        GestureType.SPREAD_FINGERS: (255, 0, 255),
                        GestureType.PINCH: (0, 255, 255),
                    }
                    color = gesture_colors.get(self.current_gesture, (100, 100, 100))
                    cv2.circle(frame, (frame.shape[1] - 50, 50), 30, color, -1)
                    
                    # Frame anzeigen
                    cv2.imshow("VibeMind Hand Detection", frame)
                
                # Key-Check
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n[INFO] Beenden...")
                    self.running = False
                    break
                
                await asyncio.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n[INFO] Unterbrochen")
        finally:
            await self.detector.stop()
            cv2.destroyAllWindows()
            
            print("\n" + "=" * 60)
            print(f"Gesamt verarbeitete Frames: {self.frame_count}")
            print("=" * 60)


async def main():
    """Hauptfunktion."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Hand Detection Demo")
    parser.add_argument(
        "--camera", "-c", type=int, default=0,
        help="Kamera-Index (default: 0)"
    )
    args = parser.parse_args()
    
    demo = HandDetectionDemo()
    await demo.run(camera_index=args.camera)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()