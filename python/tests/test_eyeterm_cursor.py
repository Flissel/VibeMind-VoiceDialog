"""Tests for CursorDriver gaze-to-cursor mapping."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
from spaces.desktop.eyeterm.cursor.cursor_driver import CursorDriver


class TestCursorDriver:
    """Test cursor driver safety and movement logic."""

    def test_disabled_by_default(self):
        driver = CursorDriver(enabled=False)
        assert not driver.enabled
        assert not driver.move(500, 500)

    def test_toggle(self):
        driver = CursorDriver(enabled=False)
        result = driver.toggle()
        assert result is True
        assert driver.enabled
        result = driver.toggle()
        assert result is False
        assert not driver.enabled

    def test_enable_disable(self):
        driver = CursorDriver(enabled=False)
        driver.enable()
        assert driver.enabled
        driver.disable()
        assert not driver.enabled

    def test_requires_face_detection(self):
        driver = CursorDriver(enabled=True, require_face=True)
        # Face not detected → no move
        assert not driver.move(500, 500)
        # Face detected → moves
        driver.set_face_detected(True)
        # Would call SetCursorPos on Windows, mock it
        with patch.object(driver, '_user32', create=True) as mock_user32:
            mock_user32.SetCursorPos = MagicMock()
            result = driver.move(500, 500)
            if driver._user32 is not None:
                assert result is True

    def test_face_not_required(self):
        driver = CursorDriver(enabled=True, require_face=False)
        with patch.object(driver, '_user32', create=True) as mock_user32:
            mock_user32.SetCursorPos = MagicMock()
            result = driver.move(500, 500)
            if driver._user32 is not None:
                mock_user32.SetCursorPos.assert_called_once_with(500, 500)

    def test_deadzone_filters_jitter(self):
        driver = CursorDriver(enabled=True, require_face=False, deadzone_px=20)
        with patch.object(driver, '_user32', create=True) as mock_user32:
            mock_user32.SetCursorPos = MagicMock()
            if driver._user32 is None:
                return  # Skip on non-Windows

            # First move always goes through
            driver.move(500, 500)
            mock_user32.SetCursorPos.assert_called_with(500, 500)

            # Small movement within deadzone → ignored
            mock_user32.SetCursorPos.reset_mock()
            result = driver.move(510, 505)
            assert result is False
            mock_user32.SetCursorPos.assert_not_called()

            # Large movement outside deadzone → moves
            result = driver.move(550, 550)
            assert result is True
            mock_user32.SetCursorPos.assert_called_with(550, 550)

    def test_enable_resets_last_position(self):
        driver = CursorDriver(enabled=True, require_face=False, deadzone_px=20)
        with patch.object(driver, '_user32', create=True) as mock_user32:
            mock_user32.SetCursorPos = MagicMock()
            if driver._user32 is None:
                return

            driver.move(500, 500)
            driver.disable()
            driver.enable()
            # After re-enable, last position is reset, so first move goes through
            assert driver._last_x is None
            assert driver._last_y is None
