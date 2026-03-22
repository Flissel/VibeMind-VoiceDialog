"""Integration test: full precision pipeline without camera/hooks."""

import sys
import os

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPolynomialToGridToAccuracy:
    """Full pipeline: fit polynomial, simulate clicks, verify accuracy gate."""

    def test_full_pipeline(self):
        from spaces.desktop.eyeterm.vision.polynomial_mapper import PolynomialMapper
        from spaces.desktop.eyeterm.cursor.residual_grid import ResidualGrid
        from spaces.desktop.eyeterm.cursor.accuracy_gate import AccuracyGate
        from spaces.desktop.eyeterm.cursor.click_collector import ClickSample

        # 1. Fit polynomial from 9 calibration points
        pm = PolynomialMapper()
        gaze_pts = [
            (0.1, 0.1), (0.5, 0.1), (0.9, 0.1),
            (0.1, 0.5), (0.5, 0.5), (0.9, 0.5),
            (0.1, 0.9), (0.5, 0.9), (0.9, 0.9),
        ]
        screen_pts = [(g[0] * 1920, g[1] * 1080) for g in gaze_pts]
        pm.fit(gaze_pts, screen_pts)

        # 2. Verify polynomial predicts center correctly
        px, py = pm.predict(0.5, 0.5)
        assert abs(px - 960) < 30  # polynomial with ridge has ~27px error
        assert abs(py - 540) < 30

        # 3. Setup grid and gate
        grid = ResidualGrid(1920, 1080, grid_cols=5, grid_rows=5)
        gate = AccuracyGate(1920, 1080, min_clicks=10)
        assert gate.phase == "learning"

        # 4. Simulate 20 clicks with small residuals
        np.random.seed(42)
        clicks = []
        for i in range(20):
            gx = 0.3 + i * 0.02
            gy = 0.4 + i * 0.01
            pred_x, pred_y = pm.predict(gx, gy)
            click_x = int(pred_x + np.random.normal(0, 30))
            click_y = int(pred_y + np.random.normal(0, 30))
            grid.update(pred_x, pred_y, click_x, click_y)
            clicks.append(ClickSample(
                timestamp=0,
                click_x=click_x,
                click_y=click_y,
                predicted_x=int(pred_x),
                predicted_y=int(pred_y),
            ))

        # 5. Gate should transition to ready (30px noise vs ~110px radius)
        gate.update(clicks[-20:])
        assert gate.phase == "ready", f"Expected ready, got {gate.phase}"
        assert gate.cursor_enabled is True

    def test_drift_detection_degrades(self):
        from spaces.desktop.eyeterm.cursor.accuracy_gate import AccuracyGate
        from spaces.desktop.eyeterm.cursor.click_collector import ClickSample

        gate = AccuracyGate(1920, 1080, min_clicks=10)

        # First reach ready with good clicks
        good_clicks = [
            ClickSample(0, 500, 500, 510, 505) for _ in range(15)
        ]
        gate.update(good_clicks)
        assert gate.phase == "ready"

        # Then simulate drift with huge residuals
        bad_clicks = [
            ClickSample(0, 500, 500, 1500, 1000) for _ in range(15)
        ]
        gate.update(bad_clicks)
        assert gate.phase == "degraded"
        assert gate.cursor_enabled is False

    def test_grid_improves_prediction(self):
        """Grid corrections should reduce residuals over time."""
        from spaces.desktop.eyeterm.cursor.residual_grid import ResidualGrid

        grid = ResidualGrid(1920, 1080, grid_cols=5, grid_rows=5)

        # Simulate consistent 50px error at center
        for _ in range(10):
            grid.update(960, 540, 1010, 540)  # predicted=960, actual=1010

        # Grid should now suggest a correction toward +50px
        dx, dy = grid.interpolate(960, 540)
        assert dx > 30  # should be close to 50
        assert abs(dy) < 5
