"""Tests for AccuracyGate — cursor activation based on prediction accuracy."""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spaces.desktop.eyeterm.cursor.accuracy_gate import (
    AccuracyGate,
    PHASE_LEARNING,
    PHASE_READY,
    PHASE_DEGRADED,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sample(residual_px: float):
    """Create a minimal click sample with a residual_px attribute."""
    class S:
        pass
    s = S()
    s.residual_px = residual_px
    return s


def _make_clicks(n: int, residual_px: float):
    """Return a list of n identical click samples."""
    return [_make_sample(residual_px) for _ in range(n)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAccuracyGate:
    """Verify AccuracyGate phase transitions and resolution independence."""

    def _gate_1080p(self, **kwargs) -> AccuracyGate:
        """Standard 1080p gate with default thresholds."""
        return AccuracyGate(screen_w=1920, screen_h=1080, **kwargs)

    def _gate_4k(self, **kwargs) -> AccuracyGate:
        """4K gate with default thresholds."""
        return AccuracyGate(screen_w=3840, screen_h=2160, **kwargs)

    # ------------------------------------------------------------------
    # test_initial_phase_is_learning
    # ------------------------------------------------------------------

    def test_initial_phase_is_learning(self):
        gate = self._gate_1080p()
        assert gate.phase == PHASE_LEARNING
        assert not gate.cursor_enabled

    # ------------------------------------------------------------------
    # test_not_enough_clicks_stays_learning
    # ------------------------------------------------------------------

    def test_not_enough_clicks_stays_learning(self):
        gate = self._gate_1080p(min_clicks=20)
        # Only 5 clicks — even with perfect accuracy should stay learning
        clicks = _make_clicks(5, residual_px=0.0)
        phase = gate.update(clicks)
        assert phase == PHASE_LEARNING
        assert not gate.cursor_enabled

    # ------------------------------------------------------------------
    # test_high_accuracy_transitions_to_ready
    # ------------------------------------------------------------------

    def test_high_accuracy_transitions_to_ready(self):
        gate = self._gate_1080p(
            threshold_on=0.75,
            accuracy_radius_frac=0.05,
            min_clicks=20,
        )
        # All 20 clicks well inside the accuracy radius → accuracy = 1.0
        clicks = _make_clicks(20, residual_px=10.0)
        phase = gate.update(clicks)
        assert phase == PHASE_READY
        assert gate.cursor_enabled

    # ------------------------------------------------------------------
    # test_low_accuracy_transitions_to_degraded
    # ------------------------------------------------------------------

    def test_low_accuracy_transitions_to_degraded(self):
        # Bring gate to ready first
        gate = self._gate_1080p(
            threshold_on=0.75,
            threshold_off=0.50,
            accuracy_radius_frac=0.05,
            min_clicks=20,
        )
        good_clicks = _make_clicks(20, residual_px=10.0)
        gate.update(good_clicks)
        assert gate.phase == PHASE_READY

        # Now simulate accuracy collapse: all clicks far outside radius
        # accuracy_radius at 1080p ≈ 0.05 * hypot(1920, 1080) ≈ 110px
        bad_clicks = _make_clicks(20, residual_px=500.0)
        phase = gate.update(bad_clicks)
        assert phase == PHASE_DEGRADED
        assert not gate.cursor_enabled

    # ------------------------------------------------------------------
    # test_resolution_independent_radius
    # ------------------------------------------------------------------

    def test_resolution_independent_radius(self):
        """4K radius should be approximately 2× the 1080p radius."""
        gate_1080p = self._gate_1080p(accuracy_radius_frac=0.05)
        gate_4k = self._gate_4k(accuracy_radius_frac=0.05)

        diag_1080p = math.hypot(1920, 1080)
        diag_4k = math.hypot(3840, 2160)

        expected_ratio = diag_4k / diag_1080p  # ≈ 2.0

        actual_ratio = gate_4k.accuracy_radius_px / gate_1080p.accuracy_radius_px

        # Should be within 1 % of the expected 2× ratio
        assert abs(actual_ratio - expected_ratio) < 0.01, (
            f"Radius ratio {actual_ratio:.4f} differs from expected {expected_ratio:.4f}"
        )

        # Sanity: 1080p radius is roughly 110 px
        assert 100 < gate_1080p.accuracy_radius_px < 125, (
            f"1080p radius {gate_1080p.accuracy_radius_px:.1f}px out of expected range"
        )

        # Sanity: 4K radius is roughly 220 px
        assert 200 < gate_4k.accuracy_radius_px < 250, (
            f"4K radius {gate_4k.accuracy_radius_px:.1f}px out of expected range"
        )

    # ------------------------------------------------------------------
    # test_degraded_can_recover_to_ready
    # ------------------------------------------------------------------

    def test_degraded_can_recover_to_ready(self):
        gate = self._gate_1080p(
            threshold_on=0.75,
            threshold_off=0.50,
            accuracy_radius_frac=0.05,
            min_clicks=20,
        )

        # 1. Move to ready
        gate.update(_make_clicks(20, residual_px=10.0))
        assert gate.phase == PHASE_READY

        # 2. Degrade
        gate.update(_make_clicks(20, residual_px=500.0))
        assert gate.phase == PHASE_DEGRADED

        # 3. Recover — accurate clicks again
        gate.update(_make_clicks(20, residual_px=10.0))
        assert gate.phase == PHASE_READY
        assert gate.cursor_enabled

    # ------------------------------------------------------------------
    # Additional edge-case tests
    # ------------------------------------------------------------------

    def test_cursor_enabled_only_in_ready(self):
        gate = self._gate_1080p(min_clicks=20)
        # learning
        assert not gate.cursor_enabled
        gate.update(_make_clicks(20, residual_px=10.0))
        # ready
        assert gate.cursor_enabled
        gate.update(_make_clicks(20, residual_px=500.0))
        # degraded
        assert not gate.cursor_enabled

    def test_check_drift_uses_last_10_clicks(self):
        gate = self._gate_1080p(drift_threshold_frac=0.07)
        # drift_threshold at 1080p ≈ 0.07 * hypot(1920,1080) ≈ 154 px
        # First 10 fine, last 10 bad
        fine = _make_clicks(10, residual_px=5.0)
        bad = _make_clicks(10, residual_px=500.0)
        assert gate.check_drift(fine + bad) is True
        assert gate.check_drift(fine) is False

    def test_boundary_exactly_at_threshold_on(self):
        """Exactly 75% accuracy should transition to ready."""
        gate = self._gate_1080p(
            threshold_on=0.75,
            accuracy_radius_frac=0.05,
            min_clicks=20,
        )
        # 15 hits, 5 misses — exactly 75%
        radius = gate.accuracy_radius_px
        hits = _make_clicks(15, residual_px=radius - 1)  # inside
        misses = _make_clicks(5, residual_px=radius + 100)  # outside
        phase = gate.update(hits + misses)
        assert phase == PHASE_READY

    def test_boundary_just_below_threshold_off(self):
        """Just below 50% accuracy from ready should degrade."""
        gate = self._gate_1080p(
            threshold_on=0.75,
            threshold_off=0.50,
            accuracy_radius_frac=0.05,
            min_clicks=20,
        )
        # Reach ready first
        gate.update(_make_clicks(20, residual_px=10.0))
        assert gate.phase == PHASE_READY

        # 9 hits / 20 = 45% — below 50%
        radius = gate.accuracy_radius_px
        hits = _make_clicks(9, residual_px=radius - 1)
        misses = _make_clicks(11, residual_px=radius + 100)
        phase = gate.update(hits + misses)
        assert phase == PHASE_DEGRADED
