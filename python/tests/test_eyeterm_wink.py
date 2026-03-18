"""Tests for eyeTerm wink detection with synthetic landmark data."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class MockLandmark:
    """Simulates a MediaPipe NormalizedLandmark."""
    def __init__(self, x: float, y: float, z: float = 0.0):
        self.x = x
        self.y = y
        self.z = z


def _make_eye_landmarks(ear_left: float, ear_right: float):
    """Create a synthetic landmark list where left/right eyes have specified EAR values.

    EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)

    With eye width w=0.1, vertical distances |p2-p6|=2v, |p3-p5|=2v:
    EAR = (2v + 2v) / (2 * w) = 4v / 0.2 = 20v
    So v = EAR / 20 = EAR * 0.05
    """
    landmarks = [MockLandmark(0.0, 0.0)] * 478

    # Left eye: p1=33, p2=160, p3=158, p4=133, p5=153, p6=144
    # Set p1 at (0.2, 0.5), p4 at (0.3, 0.5) -> width = 0.1
    left_v = ear_left * 0.05
    landmarks[33] = MockLandmark(0.2, 0.5)    # p1 left corner
    landmarks[133] = MockLandmark(0.3, 0.5)   # p4 right corner
    landmarks[160] = MockLandmark(0.25, 0.5 - left_v)   # p2 upper
    landmarks[144] = MockLandmark(0.25, 0.5 + left_v)   # p6 lower
    landmarks[158] = MockLandmark(0.25, 0.5 - left_v)   # p3 upper
    landmarks[153] = MockLandmark(0.25, 0.5 + left_v)   # p5 lower

    # Right eye: p1=362, p2=385, p3=387, p4=263, p5=373, p6=380
    right_v = ear_right * 0.05
    landmarks[362] = MockLandmark(0.6, 0.5)   # p1
    landmarks[263] = MockLandmark(0.7, 0.5)   # p4
    landmarks[385] = MockLandmark(0.65, 0.5 - right_v)  # p2
    landmarks[380] = MockLandmark(0.65, 0.5 + right_v)  # p6
    landmarks[387] = MockLandmark(0.65, 0.5 - right_v)  # p3
    landmarks[373] = MockLandmark(0.65, 0.5 + right_v)  # p5

    return landmarks


class TestWinkDetector:
    """Tests using synthetic landmark data."""

    def _make_detector(self):
        from spaces.desktop.eyeterm.vision.wink import WinkDetector
        return WinkDetector(ear_threshold=0.21, min_frames=3, cooldown_ms=600)

    def test_both_open_returns_none(self):
        det = self._make_detector()
        lm = _make_eye_landmarks(ear_left=0.30, ear_right=0.30)
        result = det.update(lm, 1000)
        assert result is None

    def test_both_closed_is_blink_ignored(self):
        det = self._make_detector()
        for i in range(5):
            lm = _make_eye_landmarks(ear_left=0.15, ear_right=0.15)
            result = det.update(lm, 1000 + i * 33)
        assert result is None

    def test_left_wink_after_min_frames(self):
        det = self._make_detector()
        # Left closed, right open for 3+ frames
        for i in range(3):
            lm = _make_eye_landmarks(ear_left=0.15, ear_right=0.30)
            result = det.update(lm, 1000 + i * 33)
        assert result == "confirm"

    def test_right_wink_after_min_frames(self):
        det = self._make_detector()
        for i in range(3):
            lm = _make_eye_landmarks(ear_left=0.30, ear_right=0.15)
            result = det.update(lm, 1000 + i * 33)
        assert result == "cancel"

    def test_wink_not_triggered_before_min_frames(self):
        det = self._make_detector()
        # Only 2 frames — should not trigger (min_frames=3)
        for i in range(2):
            lm = _make_eye_landmarks(ear_left=0.15, ear_right=0.30)
            result = det.update(lm, 1000 + i * 33)
        assert result is None

    def test_cooldown_suppresses_rapid_winks(self):
        det = self._make_detector()
        # First wink
        for i in range(3):
            lm = _make_eye_landmarks(ear_left=0.15, ear_right=0.30)
            det.update(lm, 1000 + i * 33)

        # Open eyes briefly
        lm = _make_eye_landmarks(ear_left=0.30, ear_right=0.30)
        det.update(lm, 1200)

        # Try wink again immediately (within 600ms cooldown)
        for i in range(3):
            lm = _make_eye_landmarks(ear_left=0.15, ear_right=0.30)
            result = det.update(lm, 1300 + i * 33)
        # Should be suppressed
        assert result is None

    def test_wink_allowed_after_cooldown(self):
        det = self._make_detector()
        # First wink at t=1000
        for i in range(3):
            lm = _make_eye_landmarks(ear_left=0.15, ear_right=0.30)
            det.update(lm, 1000 + i * 33)

        # Open eyes
        lm = _make_eye_landmarks(ear_left=0.30, ear_right=0.30)
        det.update(lm, 1200)

        # Wink again after cooldown (t=1700, >600ms after first wink at ~1099)
        for i in range(3):
            lm = _make_eye_landmarks(ear_left=0.15, ear_right=0.30)
            result = det.update(lm, 1700 + i * 33)
        assert result == "confirm"


class TestEARComputation:

    def test_ear_open_eye(self):
        from spaces.desktop.eyeterm.vision.wink import WinkDetector
        lm = _make_eye_landmarks(ear_left=0.30, ear_right=0.30)
        left_ear, right_ear = WinkDetector.get_ear_values(lm)
        assert abs(left_ear - 0.30) < 0.02
        assert abs(right_ear - 0.30) < 0.02

    def test_ear_closed_eye(self):
        from spaces.desktop.eyeterm.vision.wink import WinkDetector
        lm = _make_eye_landmarks(ear_left=0.10, ear_right=0.10)
        left_ear, right_ear = WinkDetector.get_ear_values(lm)
        assert left_ear < 0.15
        assert right_ear < 0.15
