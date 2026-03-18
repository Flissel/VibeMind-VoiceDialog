"""Tests for eyeTerm gaze smoother and focus router."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spaces.desktop.eyeterm.vision.gaze import GazeSmoother, FocusRouter


class TestGazeSmoother:

    def test_first_sample_passes_through(self):
        s = GazeSmoother(alpha=0.3)
        result = s.smooth((0.5, 0.5))
        assert result == (0.5, 0.5)

    def test_smoothing_moves_toward_new_value(self):
        s = GazeSmoother()
        s.smooth((0.0, 0.0))
        x, y = s.smooth((1.0, 1.0))
        # One-Euro filter: output moves toward new value but is damped
        assert 0.0 < x < 1.0, "should move toward 1.0 but not reach it"
        assert 0.0 < y < 1.0

    def test_converges_to_steady_value(self):
        s = GazeSmoother()
        for _ in range(50):
            x, y = s.smooth((0.7, 0.3))
        assert abs(x - 0.7) < 0.01
        assert abs(y - 0.3) < 0.01

    def test_reset_clears_state(self):
        s = GazeSmoother()
        s.smooth((0.9, 0.9))
        s.reset()
        result = s.smooth((0.1, 0.1))
        assert result == (0.1, 0.1)

    def test_low_min_cutoff_smooths_more(self):
        # Lower min_cutoff = heavier smoothing at rest
        smooth = GazeSmoother(min_cutoff=0.5)
        responsive = GazeSmoother(min_cutoff=5.0)
        smooth.smooth((0.0, 0.0))
        responsive.smooth((0.0, 0.0))
        sx, _ = smooth.smooth((1.0, 1.0))
        rx, _ = responsive.smooth((1.0, 1.0))
        assert sx < rx, "lower cutoff should produce less movement"

    def test_high_beta_tracks_fast_movement(self):
        # Higher beta = faster tracking during saccades
        s = GazeSmoother(beta=1.0)
        s.smooth((0.0, 0.0))
        x, _ = s.smooth((1.0, 1.0))
        # With very high beta, should track closely
        assert x > 0.5, "high beta should track fast changes closely"


class TestFocusRouter:
    """Test pane-level focus routing with dwell gating."""

    def test_four_panes_top_left(self):
        r = FocusRouter(num_panes=4, dwell_ms=100)
        # Top-left quadrant
        result = r.update(100, 100, 0)
        assert result is None  # No dwell yet
        result = r.update(100, 100, 150)  # 150ms > 100ms dwell
        assert result == 0

    def test_four_panes_top_right(self):
        r = FocusRouter(num_panes=4, dwell_ms=100, screen_width=1920, screen_height=1080)
        r.update(1500, 200, 0)
        result = r.update(1500, 200, 150)
        assert result == 1

    def test_four_panes_bottom_left(self):
        r = FocusRouter(num_panes=4, dwell_ms=100, screen_width=1920, screen_height=1080)
        r.update(200, 800, 0)
        result = r.update(200, 800, 150)
        assert result == 2

    def test_four_panes_bottom_right(self):
        r = FocusRouter(num_panes=4, dwell_ms=100, screen_width=1920, screen_height=1080)
        r.update(1500, 800, 0)
        result = r.update(1500, 800, 150)
        assert result == 3

    def test_two_panes_left_right(self):
        r = FocusRouter(num_panes=2, dwell_ms=100, screen_width=1920, screen_height=1080)
        r.update(200, 500, 0)
        result = r.update(200, 500, 150)
        assert result == 0

        # Reset for right side
        r2 = FocusRouter(num_panes=2, dwell_ms=100, screen_width=1920, screen_height=1080)
        r2.update(1500, 500, 0)
        result = r2.update(1500, 500, 150)
        assert result == 1

    def test_dwell_not_met(self):
        r = FocusRouter(num_panes=4, dwell_ms=300)
        r.update(100, 100, 0)
        result = r.update(100, 100, 200)  # only 200ms < 300ms dwell
        assert result is None

    def test_gaze_change_resets_dwell(self):
        r = FocusRouter(num_panes=4, dwell_ms=100, screen_width=1920, screen_height=1080)
        # Look top-left
        r.update(100, 100, 0)
        # Jump to top-right before dwell
        r.update(1500, 100, 50)
        # Stay at top-right
        result = r.update(1500, 100, 200)  # 150ms from pane change
        assert result == 1

    def test_single_pane_always_returns_zero(self):
        r = FocusRouter(num_panes=1, dwell_ms=100)
        r.update(500, 500, 0)
        result = r.update(500, 500, 150)
        assert result == 0
