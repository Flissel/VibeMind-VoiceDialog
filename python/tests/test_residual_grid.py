"""Tests for ResidualGrid — 5x5 local correction grid."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import json
import pytest

from spaces.desktop.eyeterm.cursor.residual_grid import ResidualGrid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_grid(**kwargs) -> ResidualGrid:
    """Create a standard 1920x1080 / 5x5 grid with optional overrides."""
    defaults = dict(screen_w=1920, screen_h=1080, grid_cols=5, grid_rows=5, min_samples=3)
    defaults.update(kwargs)
    return ResidualGrid(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestResidualGridInitialState:

    def test_grid_initial_correction_is_zero(self):
        """Before any updates, interpolation returns (0, 0) everywhere."""
        grid = _make_grid()
        for x in [100, 500, 960, 1500, 1900]:
            for y in [100, 300, 540, 800, 1000]:
                dx, dy = grid.interpolate(x, y)
                assert dx == 0.0 and dy == 0.0, (
                    f"Expected (0, 0) at ({x}, {y}), got ({dx}, {dy})"
                )


class TestResidualGridUpdate:

    def test_grid_update_single_cell(self):
        """After >= 3 updates in the same region the correction direction is correct."""
        grid = _make_grid()

        # Cell (0, 0) covers x=[0, 384), y=[0, 216)
        # Simulate: predicted at (192, 108) but actual click at (242, 158) → residual (+50, +50)
        predicted_x, predicted_y = 192.0, 108.0
        click_x, click_y = 242.0, 158.0

        for _ in range(5):
            grid.update(predicted_x, predicted_y, click_x, click_y, alpha=0.3)

        # The correction at the cell centre should be positive in both axes
        dx, dy = grid.interpolate(predicted_x, predicted_y)
        assert dx > 0, f"Expected positive dx correction, got {dx}"
        assert dy > 0, f"Expected positive dy correction, got {dy}"

    def test_grid_ema_blends_toward_new_value(self):
        """EMA blend: starting from 0, after 1 update dx equals raw residual (first sample direct assign)."""
        grid = _make_grid(min_samples=1)

        grid.update(192.0, 108.0, 292.0, 108.0, alpha=0.5)
        # First update: direct assign — correction should equal raw residual 100
        dx, dy = grid.interpolate(192.0, 108.0)
        assert math.isclose(dx, 100.0, abs_tol=1.0), f"Expected ~100.0, got {dx}"

        # Second update: EMA blend
        grid.update(192.0, 108.0, 292.0, 108.0, alpha=0.5)
        dx2, dy2 = grid.interpolate(192.0, 108.0)
        # After blend: 0.5 * 100 + 0.5 * 100 = 100 (stable because same residual)
        assert math.isclose(dx2, 100.0, abs_tol=2.0), f"Expected ~100.0 after EMA, got {dx2}"


class TestResidualGridMinSamples:

    def test_grid_min_samples_below_threshold_returns_zero(self):
        """Cells with fewer than min_samples updates do not contribute to interpolation."""
        grid = _make_grid(min_samples=3)

        # Only 2 updates in the top-left cell
        for _ in range(2):
            grid.update(192.0, 108.0, 292.0, 108.0, alpha=0.3)

        dx, dy = grid.interpolate(192.0, 108.0)
        assert dx == 0.0 and dy == 0.0, (
            f"Expected (0, 0) below min_samples, got ({dx}, {dy})"
        )

    def test_grid_min_samples_at_threshold_contributes(self):
        """Exactly min_samples updates makes the cell active."""
        grid = _make_grid(min_samples=3)

        for _ in range(3):
            grid.update(192.0, 108.0, 292.0, 108.0, alpha=0.3)

        dx, dy = grid.interpolate(192.0, 108.0)
        assert dx > 0.0, f"Expected positive dx after reaching min_samples, got {dx}"


class TestResidualGridCap:

    def test_grid_correction_cap_limits_huge_residual(self):
        """A very large residual is capped at half the cell size."""
        grid = _make_grid()
        # cell_w = 1920/5 = 384, cap_x = 192
        # cell_h = 1080/5 = 216, cap_y = 108

        # Push an absurdly large residual
        grid.update(192.0, 108.0, 5000.0, 5000.0, alpha=1.0)
        grid.update(192.0, 108.0, 5000.0, 5000.0, alpha=1.0)
        grid.update(192.0, 108.0, 5000.0, 5000.0, alpha=1.0)

        dx, dy = grid.interpolate(192.0, 108.0)
        assert abs(dx) <= grid.cap_x + 1e-9, f"dx {dx} exceeds cap {grid.cap_x}"
        assert abs(dy) <= grid.cap_y + 1e-9, f"dy {dy} exceeds cap {grid.cap_y}"

    def test_grid_correction_cap_negative_direction(self):
        """Cap applies symmetrically in the negative direction."""
        grid = _make_grid()

        grid.update(192.0, 108.0, -5000.0, -5000.0, alpha=1.0)
        grid.update(192.0, 108.0, -5000.0, -5000.0, alpha=1.0)
        grid.update(192.0, 108.0, -5000.0, -5000.0, alpha=1.0)

        dx, dy = grid.interpolate(192.0, 108.0)
        assert dx >= -grid.cap_x - 1e-9, f"dx {dx} below negative cap {-grid.cap_x}"
        assert dy >= -grid.cap_y - 1e-9, f"dy {dy} below negative cap {-grid.cap_y}"


class TestResidualGridReset:

    def test_grid_reset_clears_all_corrections(self):
        """reset() removes all accumulated data; interpolation returns (0, 0)."""
        grid = _make_grid()

        # Populate several cells
        for px, py in [(192, 108), (576, 324), (960, 540), (1344, 756), (1728, 972)]:
            for _ in range(5):
                grid.update(float(px), float(py), px + 50.0, py + 50.0, alpha=0.3)

        # Verify at least one cell is active
        dx, dy = grid.interpolate(192.0, 108.0)
        assert dx != 0.0 or dy != 0.0, "Expected non-zero correction before reset"

        grid.reset()

        for px, py in [(192, 108), (576, 324), (960, 540)]:
            dx, dy = grid.interpolate(float(px), float(py))
            assert dx == 0.0 and dy == 0.0, (
                f"Expected (0, 0) after reset at ({px}, {py}), got ({dx}, {dy})"
            )

    def test_grid_reset_allows_fresh_learning(self):
        """After reset, the grid can learn a completely different correction."""
        grid = _make_grid()

        for _ in range(5):
            grid.update(192.0, 108.0, 292.0, 158.0, alpha=0.3)

        grid.reset()

        # Now train in opposite direction
        for _ in range(5):
            grid.update(192.0, 108.0, 92.0, 58.0, alpha=0.3)

        dx, dy = grid.interpolate(192.0, 108.0)
        assert dx < 0.0, f"Expected negative dx after reset + new training, got {dx}"
        assert dy < 0.0, f"Expected negative dy after reset + new training, got {dy}"


class TestResidualGridPersistence:

    def test_grid_persistence_roundtrip(self):
        """to_dict / from_dict preserves all cell data exactly."""
        grid = _make_grid()

        updates = [
            (192.0,  108.0,  242.0,  158.0),
            (576.0,  324.0,  626.0,  374.0),
            (960.0,  540.0,  910.0,  490.0),
            (1344.0, 756.0, 1394.0,  806.0),
            (1728.0, 972.0, 1778.0, 1022.0),
        ]
        for px, py, cx, cy in updates:
            for _ in range(5):
                grid.update(px, py, cx, cy, alpha=0.3)

        d = grid.to_dict()

        # Verify it is JSON-serialisable
        serialised = json.dumps(d)
        d2 = json.loads(serialised)

        restored = ResidualGrid.from_dict(d2)

        # Cell data must match
        assert len(restored._cells) == len(grid._cells)
        for i, (orig, rest) in enumerate(zip(grid._cells, restored._cells)):
            assert math.isclose(orig.dx, rest.dx, abs_tol=1e-9), (
                f"Cell {i}: dx mismatch {orig.dx} vs {rest.dx}"
            )
            assert math.isclose(orig.dy, rest.dy, abs_tol=1e-9), (
                f"Cell {i}: dy mismatch {orig.dy} vs {rest.dy}"
            )
            assert orig.count == rest.count, (
                f"Cell {i}: count mismatch {orig.count} vs {rest.count}"
            )

    def test_grid_persistence_interpolation_identical(self):
        """Interpolation output is identical before and after serialisation round-trip."""
        grid = _make_grid()

        for _ in range(5):
            grid.update(960.0, 540.0, 1010.0, 590.0, alpha=0.3)

        probe_points = [(800, 400), (960, 540), (1100, 650)]
        before = [grid.interpolate(float(x), float(y)) for x, y in probe_points]

        restored = ResidualGrid.from_dict(grid.to_dict())
        after = [restored.interpolate(float(x), float(y)) for x, y in probe_points]

        for i, ((dx1, dy1), (dx2, dy2)) in enumerate(zip(before, after)):
            assert math.isclose(dx1, dx2, abs_tol=1e-9), (
                f"Point {probe_points[i]}: dx mismatch {dx1} vs {dx2}"
            )
            assert math.isclose(dy1, dy2, abs_tol=1e-9), (
                f"Point {probe_points[i]}: dy mismatch {dy1} vs {dy2}"
            )
