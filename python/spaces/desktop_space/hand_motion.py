"""
Hand Motion Detection - MediaPipe Integration

Webcam-basierte Handerkennung für die Interaktion mit dem Desktop Automation Space.
Verwendet MediaPipe für die Handerkennung.

Installation:
    pip install mediapipe opencv-python

Konzept:
- Webcam-Stream wird analysiert
- Hand-Landmarks werden erkannt
- Gesten werden klassifiziert
- Position wird zum Light Planet Controller gesendet
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Tuple
from enum import Enum
import asyncio
import math
import logging

# MediaPipe und OpenCV (optional imports)
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False

logger = logging.getLogger(__name__)


class GestureType(Enum):
    """Erkennbare Hand-Gesten."""
    NONE = "none"
    OPEN_HAND = "open"  # Offene Hand
    CLOSED_FIST = "closed"  # Geschlossene Faust
    POINTING = "pointing"  # Zeigefinger ausgestreckt
    SPREAD_FINGERS = "spread"  # Alle Finger gespreizt
    PINCH = "pinch"  # Daumen und Zeigefinger zusammen
    GRAB = "grab"  # Greif-Geste
    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"
    SWIPE_UP = "swipe_up"
    SWIPE_DOWN = "swipe_down"


@dataclass
class HandLandmarks:
    """
    21 Hand-Landmarks wie von MediaPipe definiert.
    
    Landmark-IDs:
    0: WRIST
    1-4: THUMB (CMC, MCP, IP, TIP)
    5-8: INDEX (MCP, PIP, DIP, TIP)
    9-12: MIDDLE (MCP, PIP, DIP, TIP)
    13-16: RING (MCP, PIP, DIP, TIP)
    17-20: PINKY (MCP, PIP, DIP, TIP)
    """
    landmarks: List[Dict[str, float]] = field(default_factory=list)
    handedness: str = "Right"  # "Left" oder "Right"
    confidence: float = 0.0
    
    def get_landmark(self, index: int) -> Optional[Dict[str, float]]:
        """Hole Landmark nach Index."""
        if 0 <= index < len(self.landmarks):
            return self.landmarks[index]
        return None
    
    def get_palm_center(self) -> Dict[str, float]:
        """Berechne Zentrum der Handfläche."""
        if len(self.landmarks) < 13:
            return {"x": 0.5, "y": 0.5, "z": 0.0}
        
        # Durchschnitt der MCP-Punkte (5, 9, 13, 17) und Handgelenk (0)
        indices = [0, 5, 9, 13, 17]
        x = sum(self.landmarks[i]["x"] for i in indices) / len(indices)
        y = sum(self.landmarks[i]["y"] for i in indices) / len(indices)
        z = sum(self.landmarks[i].get("z", 0) for i in indices) / len(indices)
        
        return {"x": x, "y": y, "z": z}
    
    def get_finger_tip(self, finger: str) -> Optional[Dict[str, float]]:
        """
        Hole Fingerspitze.
        
        Args:
            finger: "thumb", "index", "middle", "ring", "pinky"
        """
        finger_tips = {
            "thumb": 4,
            "index": 8,
            "middle": 12,
            "ring": 16,
            "pinky": 20,
        }
        idx = finger_tips.get(finger.lower())
        return self.get_landmark(idx) if idx else None
    
    @classmethod
    def from_mediapipe(cls, hand_landmarks, handedness: str = "Right") -> "HandLandmarks":
        """
        Erstelle HandLandmarks aus MediaPipe-Ergebnis.
        
        Args:
            hand_landmarks: MediaPipe hand_landmarks Objekt
            handedness: "Left" oder "Right"
        """
        landmarks_list = []
        for lm in hand_landmarks.landmark:
            landmarks_list.append({
                "x": lm.x,
                "y": lm.y,
                "z": lm.z,
            })
        
        return cls(
            landmarks=landmarks_list,
            handedness=handedness,
            confidence=1.0  # MediaPipe gibt keine confidence pro Landmark
        )


@dataclass 
class DetectedHand:
    """Eine erkannte Hand mit allen Informationen."""
    landmarks: HandLandmarks
    gesture: GestureType = GestureType.NONE
    velocity: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    is_primary: bool = True  # Primäre Hand für Interaktion


class GestureRecognizer:
    """
    Erkennt Gesten aus Hand-Landmarks.
    
    Verwendet geometrische Heuristiken für zuverlässige Erkennung.
    """
    
    def __init__(self):
        self.previous_landmarks: Optional[HandLandmarks] = None
        self.gesture_history: List[GestureType] = []
        self.history_size = 5
        self.position_history: List[Dict[str, float]] = []
    
    def recognize(self, landmarks: HandLandmarks) -> GestureType:
        """
        Erkenne Geste aus Landmarks.
        
        Args:
            landmarks: Die Hand-Landmarks
            
        Returns:
            Erkannte Geste
        """
        if len(landmarks.landmarks) < 21:
            return GestureType.NONE
        
        # Finger-Zustände berechnen
        fingers_extended = self._get_extended_fingers(landmarks)
        num_extended = sum(fingers_extended.values())
        
        # Gesten klassifizieren
        gesture = GestureType.NONE
        
        if num_extended == 5:
            # Alle Finger gestreckt
            if self._are_fingers_spread(landmarks):
                gesture = GestureType.SPREAD_FINGERS
            else:
                gesture = GestureType.OPEN_HAND
                
        elif num_extended == 0:
            gesture = GestureType.CLOSED_FIST
            
        elif num_extended == 1 and fingers_extended.get("index", False):
            gesture = GestureType.POINTING
            
        elif self._is_pinching(landmarks):
            gesture = GestureType.PINCH
        
        # Swipe-Erkennung
        swipe = self._detect_swipe(landmarks)
        if swipe != GestureType.NONE:
            gesture = swipe
        
        # Historie aktualisieren
        self.previous_landmarks = landmarks
        self.gesture_history.append(gesture)
        if len(self.gesture_history) > self.history_size:
            self.gesture_history.pop(0)
        
        # Position-Historie für Swipe-Detection
        palm_pos = landmarks.get_palm_center()
        self.position_history.append(palm_pos)
        if len(self.position_history) > 10:
            self.position_history.pop(0)
        
        return gesture
    
    def _get_extended_fingers(self, landmarks: HandLandmarks) -> Dict[str, bool]:
        """Prüfe welche Finger ausgestreckt sind."""
        result = {
            "thumb": False,
            "index": False,
            "middle": False,
            "ring": False,
            "pinky": False,
        }
        
        # Finger-Tip und PIP Indices
        finger_data = {
            "thumb": (4, 2),    # Tip, IP
            "index": (8, 6),    # Tip, PIP
            "middle": (12, 10),
            "ring": (16, 14),
            "pinky": (20, 18),
        }
        
        wrist = landmarks.get_landmark(0)
        if not wrist:
            return result
        
        for finger, (tip_idx, pip_idx) in finger_data.items():
            tip = landmarks.get_landmark(tip_idx)
            pip = landmarks.get_landmark(pip_idx)
            
            if not tip or not pip:
                continue
            
            # Für Daumen: Spezialbehandlung (seitliche Bewegung)
            if finger == "thumb":
                # Daumen ist gestreckt wenn Tip weiter vom Handgelenk entfernt ist als MCP
                mcp = landmarks.get_landmark(2)
                if mcp:
                    tip_dist = abs(tip["x"] - wrist["x"])
                    mcp_dist = abs(mcp["x"] - wrist["x"])
                    result[finger] = tip_dist > mcp_dist
            else:
                # Andere Finger: Vergleiche Y-Koordinaten (Finger nach oben = kleineres Y)
                # In MediaPipe ist Y invertiert (0 oben, 1 unten)
                result[finger] = tip["y"] < pip["y"]
        
        return result
    
    def _are_fingers_spread(self, landmarks: HandLandmarks) -> bool:
        """Prüfe ob Finger gespreizt sind."""
        tips = [landmarks.get_finger_tip(f) for f in ["index", "middle", "ring", "pinky"]]
        tips = [t for t in tips if t is not None]
        
        if len(tips) < 4:
            return False
        
        # Berechne Abstände zwischen benachbarten Fingerspitzen
        total_dist = 0
        for i in range(len(tips) - 1):
            dist = math.sqrt(
                (tips[i]["x"] - tips[i+1]["x"])**2 +
                (tips[i]["y"] - tips[i+1]["y"])**2
            )
            total_dist += dist
        
        avg_dist = total_dist / (len(tips) - 1)
        return avg_dist > 0.06  # Threshold für "gespreizt"
    
    def _is_pinching(self, landmarks: HandLandmarks) -> bool:
        """Prüfe ob Daumen und Zeigefinger zusammen sind (Pinch)."""
        thumb_tip = landmarks.get_finger_tip("thumb")
        index_tip = landmarks.get_finger_tip("index")
        
        if not thumb_tip or not index_tip:
            return False
        
        dist = math.sqrt(
            (thumb_tip["x"] - index_tip["x"])**2 +
            (thumb_tip["y"] - index_tip["y"])**2
        )
        
        return dist < 0.05  # Sehr nah zusammen
    
    def _detect_swipe(self, landmarks: HandLandmarks) -> GestureType:
        """Erkenne Swipe-Gesten aus Positions-Historie."""
        if len(self.position_history) < 5:
            return GestureType.NONE
        
        # Berechne Bewegung über die letzten Frames
        start_pos = self.position_history[0]
        end_pos = self.position_history[-1]
        
        dx = end_pos["x"] - start_pos["x"]
        dy = end_pos["y"] - start_pos["y"]
        
        # Swipe-Threshold
        threshold = 0.15
        
        if abs(dx) > abs(dy):
            if dx > threshold:
                return GestureType.SWIPE_RIGHT
            elif dx < -threshold:
                return GestureType.SWIPE_LEFT
        else:
            if dy > threshold:
                return GestureType.SWIPE_DOWN
            elif dy < -threshold:
                return GestureType.SWIPE_UP
        
        return GestureType.NONE


class HandMotionDetector:
    """
    Hauptklasse für die Hand Motion Detection mit MediaPipe.
    
    Verarbeitet Webcam-Frames und erkennt Hand-Gesten in Echtzeit.
    """
    
    def __init__(self):
        self.is_running = False
        self.gesture_recognizer = GestureRecognizer()
        self.on_gesture_detected: Optional[Callable[[DetectedHand], None]] = None
        self.on_hand_position_changed: Optional[Callable[[Dict[str, float]], None]] = None
        self.on_frame_processed: Optional[Callable[[Any], None]] = None  # Für Debug-Visualisierung
        self._last_hand: Optional[DetectedHand] = None
        
        # MediaPipe Komponenten
        self._mp_hands = None
        self._mp_drawing = None
        self._capture = None
        self._detection_task = None
        
        # Frame-Rate Control
        self._target_fps = 30
        self._frame_interval = 1.0 / self._target_fps
        
        # Status
        self._has_required_libs = HAS_OPENCV and HAS_MEDIAPIPE
    
    def check_dependencies(self) -> Tuple[bool, str]:
        """
        Prüfe ob alle Abhängigkeiten installiert sind.
        
        Returns:
            (success, message)
        """
        if not HAS_OPENCV:
            return False, "OpenCV nicht installiert. Run: pip install opencv-python"
        if not HAS_MEDIAPIPE:
            return False, "MediaPipe nicht installiert. Run: pip install mediapipe"
        return True, "Alle Abhängigkeiten verfügbar"
    
    async def start(self, camera_index: int = 0) -> bool:
        """
        Starte die Hand-Erkennung.
        
        Args:
            camera_index: Index der Webcam (0 = Standard)
            
        Returns:
            True wenn erfolgreich gestartet
        """
        # Prüfe Abhängigkeiten
        ok, msg = self.check_dependencies()
        if not ok:
            logger.error(f"[HandMotion] {msg}")
            print(f"[HandMotion] ERROR: {msg}")
            return False
        
        logger.info(f"[HandMotion] Starte mit Kamera {camera_index}")
        
        # MediaPipe initialisieren
        self._mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self._mp_drawing = mp.solutions.drawing_utils
        
        # Webcam öffnen
        self._capture = cv2.VideoCapture(camera_index)
        if not self._capture.isOpened():
            logger.error(f"[HandMotion] Kamera {camera_index} konnte nicht geöffnet werden")
            return False
        
        # Kamera-Einstellungen
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._capture.set(cv2.CAP_PROP_FPS, self._target_fps)
        
        self.is_running = True
        
        # Starte Detection-Loop in separatem Task
        self._detection_task = asyncio.create_task(self._detection_loop())
        
        logger.info("[HandMotion] Erfolgreich gestartet")
        return True
    
    async def stop(self):
        """Stoppe die Hand-Erkennung."""
        self.is_running = False
        
        # Warte auf Task-Ende
        if self._detection_task:
            self._detection_task.cancel()
            try:
                await self._detection_task
            except asyncio.CancelledError:
                pass
        
        # Cleanup
        if self._capture:
            self._capture.release()
            self._capture = None
        
        if self._mp_hands:
            self._mp_hands.close()
            self._mp_hands = None
        
        logger.info("[HandMotion] Gestoppt")
    
    async def _detection_loop(self):
        """
        Haupt-Erkennungs-Loop.
        
        Läuft in separatem asyncio Task.
        """
        logger.info("[HandMotion] Detection-Loop gestartet")
        
        while self.is_running and self._capture and self._capture.isOpened():
            # Frame lesen
            ret, frame = self._capture.read()
            if not ret:
                await asyncio.sleep(0.01)
                continue
            
            # Frame horizontal spiegeln (für natürlichere Interaktion)
            frame = cv2.flip(frame, 1)
            
            # BGR zu RGB konvertieren
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # MediaPipe verarbeiten
            results = self._mp_hands.process(rgb_frame)
            
            # Hand erkannt?
            if results.multi_hand_landmarks:
                for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    # Handedness bestimmen
                    handedness = "Right"
                    if results.multi_handedness:
                        handedness = results.multi_handedness[idx].classification[0].label
                    
                    # Landmarks extrahieren
                    landmarks = HandLandmarks.from_mediapipe(hand_landmarks, handedness)
                    
                    # Geste erkennen
                    gesture = self.gesture_recognizer.recognize(landmarks)
                    
                    # Velocity berechnen
                    velocity = {"x": 0, "y": 0, "z": 0}
                    if self._last_hand:
                        prev_pos = self._last_hand.landmarks.get_palm_center()
                        curr_pos = landmarks.get_palm_center()
                        velocity = {
                            "x": curr_pos["x"] - prev_pos["x"],
                            "y": curr_pos["y"] - prev_pos["y"],
                            "z": curr_pos.get("z", 0) - prev_pos.get("z", 0),
                        }
                    
                    detected = DetectedHand(
                        landmarks=landmarks,
                        gesture=gesture,
                        velocity=velocity,
                    )
                    
                    self._last_hand = detected
                    
                    # Callbacks
                    if self.on_gesture_detected:
                        self.on_gesture_detected(detected)
                    
                    if self.on_hand_position_changed:
                        self.on_hand_position_changed(landmarks.get_palm_center())
                    
                    # Visualisierung zeichnen
                    if self.on_frame_processed:
                        self._mp_drawing.draw_landmarks(
                            frame,
                            hand_landmarks,
                            mp.solutions.hands.HAND_CONNECTIONS
                        )
            
            # Frame-Callback für Debug-Visualisierung
            if self.on_frame_processed:
                self.on_frame_processed(frame)
            
            # Frame-Rate Control
            await asyncio.sleep(self._frame_interval)
        
        logger.info("[HandMotion] Detection-Loop beendet")
    
    def process_landmarks(self, landmarks_data: List[Dict[str, float]], 
                         handedness: str = "Right",
                         confidence: float = 1.0) -> Optional[DetectedHand]:
        """
        Verarbeite Hand-Landmarks (für externe Datenquellen).
        
        Args:
            landmarks_data: Liste mit 21 Landmark-Dicts
            handedness: "Left" oder "Right"
            confidence: Erkennungs-Konfidenz
            
        Returns:
            DetectedHand mit Geste, oder None
        """
        if len(landmarks_data) != 21:
            return None
        
        hand_landmarks = HandLandmarks(
            landmarks=landmarks_data,
            handedness=handedness,
            confidence=confidence
        )
        
        gesture = self.gesture_recognizer.recognize(hand_landmarks)
        
        # Velocity berechnen
        velocity = {"x": 0, "y": 0, "z": 0}
        if self._last_hand:
            prev_pos = self._last_hand.landmarks.get_palm_center()
            curr_pos = hand_landmarks.get_palm_center()
            velocity = {
                "x": curr_pos["x"] - prev_pos["x"],
                "y": curr_pos["y"] - prev_pos["y"],
                "z": curr_pos.get("z", 0) - prev_pos.get("z", 0),
            }
        
        detected = DetectedHand(
            landmarks=hand_landmarks,
            gesture=gesture,
            velocity=velocity,
        )
        
        self._last_hand = detected
        
        # Callbacks
        if self.on_gesture_detected:
            self.on_gesture_detected(detected)
        
        if self.on_hand_position_changed:
            self.on_hand_position_changed(hand_landmarks.get_palm_center())
        
        return detected
    
    def simulate_gesture(self, gesture: GestureType, 
                        position: Dict[str, float] = None) -> DetectedHand:
        """
        Simuliere eine Geste (für Tests ohne Webcam).
        
        Args:
            gesture: Zu simulierende Geste
            position: Hand-Position (default: Zentrum)
            
        Returns:
            Simulierte DetectedHand
        """
        pos = position or {"x": 0.5, "y": 0.5, "z": 0.0}
        
        # Erzeuge Fake-Landmarks basierend auf Geste
        fake_landmarks = [pos.copy() for _ in range(21)]
        
        hand = DetectedHand(
            landmarks=HandLandmarks(
                landmarks=fake_landmarks,
                handedness="Right",
                confidence=1.0
            ),
            gesture=gesture,
            velocity={"x": 0, "y": 0, "z": 0},
        )
        
        if self.on_gesture_detected:
            self.on_gesture_detected(hand)
        
        return hand
    
    def get_status(self) -> Dict[str, Any]:
        """Hole aktuellen Status des Detectors."""
        return {
            "is_running": self.is_running,
            "has_opencv": HAS_OPENCV,
            "has_mediapipe": HAS_MEDIAPIPE,
            "camera_open": self._capture is not None and self._capture.isOpened() if self._capture else False,
            "last_gesture": self._last_hand.gesture.value if self._last_hand else "none",
        }


# Globale Instanz
_hand_detector: Optional[HandMotionDetector] = None


def get_hand_detector() -> HandMotionDetector:
    """Hole die globale Hand Motion Detector Instanz."""
    global _hand_detector
    if _hand_detector is None:
        _hand_detector = HandMotionDetector()
    return _hand_detector


__all__ = [
    "GestureType",
    "HandLandmarks",
    "DetectedHand",
    "GestureRecognizer",
    "HandMotionDetector",
    "get_hand_detector",
    "HAS_OPENCV",
    "HAS_MEDIAPIPE",
]