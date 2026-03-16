# eyeTerm Pixel-Precise Gaze Control Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace affine gaze-to-screen mapping with polynomial + click-learning pipeline that achieves +-5-10px cursor accuracy.

**Architecture:** Quadratic polynomial mapper for non-linear gaze-to-screen mapping, Windows mouse hook for click ground-truth collection, 5x5 residual grid for local correction, and accuracy gate that only enables cursor when 75% of predictions are within tolerance.

**Tech Stack:** Python 3.12, numpy, ctypes (Windows API), mediapipe, existing eyeTerm framework

**Spec:** `docs/superpowers/specs/2026-03-15-eyeterm-precision-gaze-design.md`

---

## File Structure

| File | Action | Responsibility |
| ---- | ------ | -------------- |
| `python/spaces/desktop/eyeterm/vision/polynomial_mapper.py` | CREATE | Quadratic polynomial gaze-to-screen mapping, ridge regression fit, persistence |
| `python/spaces/desktop/eyeterm/cursor/click_collector.py` | CREATE | Windows WH_MOUSE_LL hook with message pump, ring buffer, thread-safe prediction sharing |
| `python/spaces/desktop/eyeterm/cursor/residual_grid.py` | CREATE | 5x5 correction grid with EMA update, bilinear interpolation, persistence |
| `python/spaces/desktop/eyeterm/cursor/accuracy_gate.py` | CREATE | Three-phase manager (learning/ready/degraded), resolution-independent thresholds |
| `python/spaces/desktop/eyeterm/cursor/__init__.py` | MODIFY | Add lazy imports for new modules |
| `python/spaces/desktop/eyeterm/vision/calibrate.py` | MODIFY | Use PolynomialMapper instead of raw affine lstsq |
| `python/spaces/desktop/eyeterm/headless.py` | MODIFY | Wire new pipeline, start/stop click collector, accuracy gate, CSV |
| `python/spaces/desktop/eyeterm/config.py` | MODIFY | New config params + env vars |
| `python/tests/test_polynomial_mapper.py` | CREATE | Unit tests for polynomial fit, predict, persistence, affine fallback |
| `python/tests/test_residual_grid.py` | CREATE | Unit tests for grid update, interpolation, cap, persistence |
| `python/tests/test_accuracy_gate.py` | CREATE | Unit tests for phase transitions, resolution scaling |
| `python/tests/test_click_collector.py` | CREATE | Unit tests for filtering, buffer, thread-safe prediction |

---

## Chunk 1: PolynomialMapper

### Task 1: PolynomialMapper — tests + implementation

**Files:**
- Create: `python/tests/test_polynomial_mapper.py`
- Create: `python/spaces/desktop/eyeterm/vision/polynomial_mapper.py`

- [ ] **Step 1: Write failing tests**

```python
# python/tests/test_polynomial_mapper.py
import numpy as np
import json
import tempfile
from pathlib import Path

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_feature_vector_shape():
    from spaces.desktop.eyeterm.vision.polynomial_mapper import PolynomialMapper
    fv = PolynomialMapper.feature_vector(0.5, 0.5)
    assert fv.shape == (6,)
    assert fv[5] == 1.0  # bias term


def test_feature_vector_values():
    from spaces.desktop.eyeterm.vision.polynomial_mapper import PolynomialMapper
    fv = PolynomialMapper.feature_vector(0.3, 0.7)
    expected = [0.09, 0.49, 0.21, 0.3, 0.7, 1.0]
    np.testing.assert_allclose(fv, expected, atol=1e-10)


def test_fit_and_predict_identity():
    """9 calibration points should produce a mapping close to ground truth."""
    from spaces.desktop.eyeterm.vision.polynomial_mapper import PolynomialMapper
    pm = PolynomialMapper()
    # Simulate: gaze (0..1) maps linearly to screen (0..1920, 0..1080)
    gaze_pts = [
        (0.1, 0.1), (0.5, 0.1), (0.9, 0.1),
        (0.1, 0.5), (0.5, 0.5), (0.9, 0.5),
        (0.1, 0.9), (0.5, 0.9), (0.9, 0.9),
    ]
    screen_pts = [(g[0] * 1920, g[1] * 1080) for g in gaze_pts]
    pm.fit(gaze_pts, screen_pts)
    # Predict center
    px, py = pm.predict(0.5, 0.5)
    assert abs(px - 960) < 5
    assert abs(py - 540) < 5


def test_fit_nonlinear():
    """Polynomial should fit a quadratic mapping better than affine."""
    from spaces.desktop.eyeterm.vision.polynomial_mapper import PolynomialMapper
    pm = PolynomialMapper()
    # Quadratic ground truth: screen_x = 1920 * gx^2
    gaze_pts = [(g/10, 0.5) for g in range(1, 10)]
    screen_pts = [(1920 * (g[0] ** 2), 540) for g in gaze_pts]
    pm.fit(gaze_pts, screen_pts)
    px, _ = pm.predict(0.7, 0.5)
    expected = 1920 * 0.49  # 0.7^2 = 0.49
    assert abs(px - expected) < 20


def test_predict_affine_legacy():
    """PolynomialMapper should handle legacy (2,3) affine matrices."""
    from spaces.desktop.eyeterm.vision.polynomial_mapper import PolynomialMapper
    # Simple affine: screen = 1920*gx, 1080*gy
    coeff = np.array([[1920.0, 0.0, 0.0], [0.0, 1080.0, 0.0]])
    pm = PolynomialMapper(coefficients=coeff)
    px, py = pm.predict(0.5, 0.5)
    assert abs(px - 960) < 1
    assert abs(py - 540) < 1


def test_ridge_prevents_huge_coefficients():
    """Ridge regression should prevent extreme coefficients from narrow gaze range."""
    from spaces.desktop.eyeterm.vision.polynomial_mapper import PolynomialMapper
    pm = PolynomialMapper()
    # Very narrow gaze range (0.55-0.65) — this is what causes affine amplification
    gaze_pts = [
        (0.55, 0.45), (0.60, 0.45), (0.65, 0.45),
        (0.55, 0.50), (0.60, 0.50), (0.65, 0.50),
        (0.55, 0.55), (0.60, 0.55), (0.65, 0.55),
    ]
    screen_pts = [
        (192, 108), (960, 108), (1728, 108),
        (192, 540), (960, 540), (1728, 540),
        (192, 972), (960, 972), (1728, 972),
    ]
    coeff = pm.fit(gaze_pts, screen_pts)
    # Coefficients should not exceed reasonable bounds
    assert np.all(np.abs(coeff) < 1e6), f"Coefficients too large: {coeff}"


def test_save_load_roundtrip():
    """Save and load should produce identical mapper."""
    from spaces.desktop.eyeterm.vision.polynomial_mapper import PolynomialMapper
    pm = PolynomialMapper()
    gaze_pts = [(0.3, 0.3), (0.5, 0.3), (0.7, 0.3),
                (0.3, 0.5), (0.5, 0.5), (0.7, 0.5),
                (0.3, 0.7), (0.5, 0.7), (0.7, 0.7)]
    screen_pts = [(g[0]*1920, g[1]*1080) for g in gaze_pts]
    pm.fit(gaze_pts, screen_pts)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        path = Path(f.name)
    try:
        pm.save(path)
        pm2 = PolynomialMapper.load(path)
        px1, py1 = pm.predict(0.5, 0.5)
        px2, py2 = pm2.predict(0.5, 0.5)
        assert abs(px1 - px2) < 0.01
        assert abs(py1 - py2) < 0.01
    finally:
        path.unlink(missing_ok=True)


def test_load_affine_legacy_file():
    """Loading a legacy (2,3) affine file should work."""
    from spaces.desktop.eyeterm.vision.polynomial_mapper import PolynomialMapper
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump({"matrix": [[1920, 0, 0], [0, 1080, 0]]}, f)
        path = Path(f.name)
    try:
        pm = PolynomialMapper.load(path)
        px, py = pm.predict(0.5, 0.5)
        assert abs(px - 960) < 1
        assert abs(py - 540) < 1
    finally:
        path.unlink(missing_ok=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python && python -m pytest tests/test_polynomial_mapper.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement PolynomialMapper**

```python
# python/spaces/desktop/eyeterm/vision/polynomial_mapper.py
"""Quadratic polynomial gaze-to-screen mapping with ridge regression."""

import json
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger("eyeterm.polynomial")


class PolynomialMapper:
    """Map gaze ratios to screen coordinates via quadratic polynomial.

    Supports both polynomial (2x6) and legacy affine (2x3) matrices.
    Uses ridge regression to prevent extreme coefficients when the
    gaze input range is narrow.
    """

    def __init__(self, coefficients: Optional[np.ndarray] = None) -> None:
        self._coeff = coefficients  # shape (2, 6) or (2, 3) or None

    @property
    def coefficients(self) -> Optional[np.ndarray]:
        return self._coeff

    @property
    def is_polynomial(self) -> bool:
        return self._coeff is not None and self._coeff.shape == (2, 6)

    @staticmethod
    def feature_vector(gx: float, gy: float) -> np.ndarray:
        """Build quadratic feature vector [gx^2, gy^2, gx*gy, gx, gy, 1]."""
        return np.array([gx * gx, gy * gy, gx * gy, gx, gy, 1.0])

    def predict(self, gx: float, gy: float) -> Tuple[float, float]:
        """Map gaze coordinates to screen pixel coordinates."""
        if self._coeff is None:
            raise RuntimeError("No calibration loaded")
        if self._coeff.shape == (2, 6):
            fv = self.feature_vector(gx, gy)
        else:  # (2, 3) affine legacy
            fv = np.array([gx, gy, 1.0])
        mapped = self._coeff @ fv
        return (float(mapped[0]), float(mapped[1]))

    def fit(
        self,
        gaze_points: List[Tuple[float, float]],
        screen_targets: List[Tuple[float, float]],
        ridge_lambda: float = 0.01,
    ) -> np.ndarray:
        """Least-squares polynomial fit with ridge regularization.

        Falls back to affine if the polynomial system is ill-conditioned.
        """
        n = len(gaze_points)
        A = np.array([self.feature_vector(g[0], g[1]) for g in gaze_points])
        B = np.array(screen_targets, dtype=np.float64)

        # Ridge regression: (A^T A + lambda*I) x = A^T B
        AtA = A.T @ A + ridge_lambda * np.eye(A.shape[1])
        AtB = A.T @ B

        cond = np.linalg.cond(AtA)
        if cond > 1e6:
            logger.warning(
                "Polynomial fit ill-conditioned (cond=%.1e), falling back to affine",
                cond,
            )
            return self._fit_affine_fallback(gaze_points, screen_targets)

        solution = np.linalg.solve(AtA, AtB)
        self._coeff = solution.T.copy()  # (2, 6)
        return self._coeff

    def _fit_affine_fallback(
        self,
        gaze_points: List[Tuple[float, float]],
        screen_targets: List[Tuple[float, float]],
    ) -> np.ndarray:
        """Simple affine fit as fallback."""
        n = len(gaze_points)
        A = np.zeros((n, 3), dtype=np.float64)
        B = np.array(screen_targets, dtype=np.float64)
        for i, (gx, gy) in enumerate(gaze_points):
            A[i] = [gx, gy, 1.0]
        solution, _, _, _ = np.linalg.lstsq(A, B, rcond=None)
        self._coeff = solution.T.copy()  # (2, 3)
        return self._coeff

    def save(self, path: Path) -> None:
        """Save calibration to JSON with type marker."""
        if self._coeff is None:
            raise RuntimeError("No calibration to save")
        data = {
            "type": "polynomial" if self._coeff.shape == (2, 6) else "affine",
            "matrix": self._coeff.tolist(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "PolynomialMapper":
        """Load calibration from JSON, auto-detecting polynomial vs affine."""
        raw = json.loads(path.read_text(encoding="utf-8"))
        m = np.array(raw["matrix"], dtype=np.float64)
        if m.shape not in ((2, 3), (2, 6)):
            raise ValueError(f"Unexpected matrix shape {m.shape}")
        return cls(coefficients=m)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python && python -m pytest tests/test_polynomial_mapper.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add python/spaces/desktop/eyeterm/vision/polynomial_mapper.py python/tests/test_polynomial_mapper.py
git commit -m "feat(eyeterm): add PolynomialMapper with ridge regression and affine fallback"
```

---

## Chunk 2: ResidualGrid

### Task 2: ResidualGrid — tests + implementation

**Files:**
- Create: `python/tests/test_residual_grid.py`
- Create: `python/spaces/desktop/eyeterm/cursor/residual_grid.py`

- [ ] **Step 1: Write failing tests**

```python
# python/tests/test_residual_grid.py
import numpy as np
import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_grid_initial_correction_is_zero():
    from spaces.desktop.eyeterm.cursor.residual_grid import ResidualGrid
    grid = ResidualGrid(1920, 1080, grid_size=5)
    dx, dy = grid.interpolate(960, 540)
    assert dx == 0.0 and dy == 0.0


def test_grid_update_single_cell():
    from spaces.desktop.eyeterm.cursor.residual_grid import ResidualGrid
    grid = ResidualGrid(1920, 1080, grid_size=5)
    # Click at center, predicted at center, actual 50px to the right
    for _ in range(3):  # need 3 clicks to activate cell
        grid.update(960, 540, 1010, 540)
    dx, dy = grid.interpolate(960, 540)
    assert dx > 0  # correction should push right
    assert abs(dy) < 1  # no vertical correction


def test_grid_min_samples():
    """Cell must have >= 3 clicks to be active."""
    from spaces.desktop.eyeterm.cursor.residual_grid import ResidualGrid
    grid = ResidualGrid(1920, 1080, grid_size=5)
    grid.update(960, 540, 1010, 540)  # only 1 click
    dx, dy = grid.interpolate(960, 540)
    assert dx == 0.0  # not active yet


def test_grid_correction_cap():
    """Corrections should be capped at half cell size."""
    from spaces.desktop.eyeterm.cursor.residual_grid import ResidualGrid
    grid = ResidualGrid(1920, 1080, grid_size=5)
    # Huge residual that would exceed cap
    for _ in range(5):
        grid.update(960, 540, 1800, 540)  # 840px residual
    dx, dy = grid.interpolate(960, 540)
    max_correction = (1920 / 5) / 2  # 192px
    assert abs(dx) <= max_correction + 1


def test_grid_reset():
    from spaces.desktop.eyeterm.cursor.residual_grid import ResidualGrid
    grid = ResidualGrid(1920, 1080, grid_size=5)
    for _ in range(5):
        grid.update(960, 540, 1010, 540)
    grid.reset()
    dx, dy = grid.interpolate(960, 540)
    assert dx == 0.0 and dy == 0.0


def test_grid_persistence_roundtrip():
    from spaces.desktop.eyeterm.cursor.residual_grid import ResidualGrid
    grid = ResidualGrid(1920, 1080, grid_size=5)
    for _ in range(5):
        grid.update(960, 540, 1010, 540)
    data = grid.to_dict()
    grid2 = ResidualGrid.from_dict(data)
    dx1, dy1 = grid.interpolate(960, 540)
    dx2, dy2 = grid2.interpolate(960, 540)
    assert abs(dx1 - dx2) < 0.01
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python && python -m pytest tests/test_residual_grid.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement ResidualGrid**

```python
# python/spaces/desktop/eyeterm/cursor/residual_grid.py
"""Local correction grid for polynomial mapper residuals."""

import logging
from typing import Dict, Tuple

import numpy as np

logger = logging.getLogger("eyeterm.residual_grid")


class ResidualGrid:
    """5x5 correction grid with EMA update and bilinear interpolation.

    Each cell stores a correction vector (dx, dy) representing the
    average error of the polynomial mapper in that screen region.
    Corrections are applied via bilinear interpolation between the
    4 nearest cell centers to prevent jumps at cell boundaries.
    """

    def __init__(self, screen_w: int, screen_h: int, grid_size: int = 5) -> None:
        self._sw = screen_w
        self._sh = screen_h
        self._gs = grid_size
        self._cell_w = screen_w / grid_size
        self._cell_h = screen_h / grid_size
        self._max_correction = min(self._cell_w, self._cell_h) / 2
        self._dx = np.zeros((grid_size, grid_size), dtype=np.float64)
        self._dy = np.zeros((grid_size, grid_size), dtype=np.float64)
        self._count = np.zeros((grid_size, grid_size), dtype=np.int32)

    def _cell(self, screen_x: float, screen_y: float) -> Tuple[int, int]:
        """Convert screen coordinates to grid cell indices."""
        col = int(np.clip(screen_x / self._cell_w, 0, self._gs - 1))
        row = int(np.clip(screen_y / self._cell_h, 0, self._gs - 1))
        return (row, col)

    def update(
        self,
        predicted_x: float,
        predicted_y: float,
        click_x: float,
        click_y: float,
        alpha: float = 0.3,
    ) -> None:
        """Update the correction for the cell containing the predicted position."""
        row, col = self._cell(predicted_x, predicted_y)
        rx = click_x - predicted_x
        ry = click_y - predicted_y
        if self._count[row, col] == 0:
            self._dx[row, col] = rx
            self._dy[row, col] = ry
        else:
            self._dx[row, col] = alpha * rx + (1 - alpha) * self._dx[row, col]
            self._dy[row, col] = alpha * ry + (1 - alpha) * self._dy[row, col]
        self._count[row, col] += 1

    def interpolate(self, screen_x: float, screen_y: float) -> Tuple[float, float]:
        """Bilinear interpolation of correction vectors at a screen position.

        Only uses cells with >= 3 samples. Caps corrections at half cell size.
        """
        # Fractional cell position (relative to cell centers)
        fx = screen_x / self._cell_w - 0.5
        fy = screen_y / self._cell_h - 0.5
        x0 = int(np.clip(np.floor(fx), 0, self._gs - 2))
        y0 = int(np.clip(np.floor(fy), 0, self._gs - 2))
        x1 = x0 + 1
        y1 = y0 + 1
        wx = np.clip(fx - x0, 0, 1)
        wy = np.clip(fy - y0, 0, 1)

        dx_total = 0.0
        dy_total = 0.0
        w_total = 0.0

        for (r, c, w) in [
            (y0, x0, (1 - wx) * (1 - wy)),
            (y0, x1, wx * (1 - wy)),
            (y1, x0, (1 - wx) * wy),
            (y1, x1, wx * wy),
        ]:
            r = np.clip(r, 0, self._gs - 1)
            c = np.clip(c, 0, self._gs - 1)
            if self._count[r, c] >= 3:
                dx_total += w * self._dx[r, c]
                dy_total += w * self._dy[r, c]
                w_total += w

        if w_total < 1e-6:
            return (0.0, 0.0)

        dx = dx_total / w_total
        dy = dy_total / w_total

        # Cap corrections
        dx = np.clip(dx, -self._max_correction, self._max_correction)
        dy = np.clip(dy, -self._max_correction, self._max_correction)

        return (float(dx), float(dy))

    def reset(self) -> None:
        """Clear all corrections (on drift detection)."""
        self._dx[:] = 0
        self._dy[:] = 0
        self._count[:] = 0

    def to_dict(self) -> Dict:
        """Serialize for JSON persistence."""
        return {
            "screen_w": self._sw,
            "screen_h": self._sh,
            "grid_size": self._gs,
            "dx": self._dx.tolist(),
            "dy": self._dy.tolist(),
            "count": self._count.tolist(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ResidualGrid":
        """Deserialize from JSON."""
        grid = cls(data["screen_w"], data["screen_h"], data["grid_size"])
        grid._dx = np.array(data["dx"], dtype=np.float64)
        grid._dy = np.array(data["dy"], dtype=np.float64)
        grid._count = np.array(data["count"], dtype=np.int32)
        return grid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python && python -m pytest tests/test_residual_grid.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add python/spaces/desktop/eyeterm/cursor/residual_grid.py python/tests/test_residual_grid.py
git commit -m "feat(eyeterm): add ResidualGrid with bilinear interpolation and correction cap"
```

---

## Chunk 3: AccuracyGate

### Task 3: AccuracyGate — tests + implementation

**Files:**
- Create: `python/tests/test_accuracy_gate.py`
- Create: `python/spaces/desktop/eyeterm/cursor/accuracy_gate.py`

- [ ] **Step 1: Write failing tests**

```python
# python/tests/test_accuracy_gate.py
import math
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_sample(residual_px):
    """Create a minimal ClickSample-like object."""
    class S:
        pass
    s = S()
    s.residual_px = residual_px
    return s


def test_initial_phase_is_learning():
    from spaces.desktop.eyeterm.cursor.accuracy_gate import AccuracyGate
    gate = AccuracyGate(1920, 1080)
    assert gate.phase == "learning"
    assert gate.cursor_enabled is False


def test_not_enough_clicks_stays_learning():
    from spaces.desktop.eyeterm.cursor.accuracy_gate import AccuracyGate
    gate = AccuracyGate(1920, 1080, min_clicks=20)
    clicks = [_make_sample(50) for _ in range(5)]  # only 5
    gate.update(clicks)
    assert gate.phase == "learning"


def test_high_accuracy_transitions_to_ready():
    from spaces.desktop.eyeterm.cursor.accuracy_gate import AccuracyGate
    gate = AccuracyGate(1920, 1080, min_clicks=10)
    clicks = [_make_sample(50) for _ in range(10)]  # all accurate
    gate.update(clicks)
    assert gate.phase == "ready"
    assert gate.cursor_enabled is True


def test_low_accuracy_transitions_to_degraded():
    from spaces.desktop.eyeterm.cursor.accuracy_gate import AccuracyGate
    gate = AccuracyGate(1920, 1080, min_clicks=10)
    # First get to ready
    gate.update([_make_sample(50) for _ in range(10)])
    assert gate.phase == "ready"
    # Then accuracy drops
    gate.update([_make_sample(500) for _ in range(10)])
    assert gate.phase == "degraded"
    assert gate.cursor_enabled is False


def test_resolution_independent_radius():
    """Radius should scale with screen diagonal."""
    from spaces.desktop.eyeterm.cursor.accuracy_gate import AccuracyGate
    gate_1080 = AccuracyGate(1920, 1080)
    gate_4k = AccuracyGate(3840, 2160)
    # 4K radius should be ~2x 1080p radius
    ratio = gate_4k._radius / gate_1080._radius
    assert 1.8 < ratio < 2.2


def test_degraded_can_recover_to_ready():
    from spaces.desktop.eyeterm.cursor.accuracy_gate import AccuracyGate
    gate = AccuracyGate(1920, 1080, min_clicks=10)
    gate.update([_make_sample(50) for _ in range(10)])  # -> ready
    gate.update([_make_sample(500) for _ in range(10)])  # -> degraded
    gate.update([_make_sample(50) for _ in range(10)])  # -> ready again
    assert gate.phase == "ready"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python && python -m pytest tests/test_accuracy_gate.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement AccuracyGate**

```python
# python/spaces/desktop/eyeterm/cursor/accuracy_gate.py
"""Accuracy-based cursor activation gate."""

import logging
import math
from typing import List

logger = logging.getLogger("eyeterm.accuracy_gate")


class AccuracyGate:
    """Three-phase cursor manager: learning -> ready -> degraded.

    Cursor is only enabled in the 'ready' phase. Uses resolution-independent
    thresholds (fraction of screen diagonal).
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        threshold_on: float = 0.75,
        threshold_off: float = 0.50,
        accuracy_radius_frac: float = 0.05,
        drift_threshold_frac: float = 0.07,
        min_clicks: int = 20,
    ) -> None:
        self._phase = "learning"
        self._threshold_on = threshold_on
        self._threshold_off = threshold_off
        self._min_clicks = min_clicks

        diag = math.hypot(screen_w, screen_h)
        self._radius = accuracy_radius_frac * diag
        self._drift_threshold = drift_threshold_frac * diag

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def cursor_enabled(self) -> bool:
        return self._phase == "ready"

    def update(self, recent_clicks: List) -> str:
        """Evaluate accuracy from recent clicks and transition phase.

        Each click must have a .residual_px attribute.
        """
        if len(recent_clicks) < self._min_clicks:
            return self._phase

        accuracy = self._compute_accuracy(recent_clicks)
        mean_residual = sum(c.residual_px for c in recent_clicks) / len(recent_clicks)

        old_phase = self._phase

        if self._phase == "learning" and accuracy >= self._threshold_on:
            self._phase = "ready"
        elif self._phase == "ready" and accuracy < self._threshold_off:
            self._phase = "degraded"
        elif self._phase == "degraded" and accuracy >= self._threshold_on:
            self._phase = "ready"

        if self._phase != old_phase:
            logger.info(
                "AccuracyGate: %s -> %s (accuracy=%.0f%%, mean_residual=%.0fpx)",
                old_phase, self._phase, accuracy * 100, mean_residual,
            )

        return self._phase

    def _compute_accuracy(self, clicks: List) -> float:
        """Fraction of clicks with residual below radius threshold."""
        if not clicks:
            return 0.0
        accurate = sum(1 for c in clicks if c.residual_px < self._radius)
        return accurate / len(clicks)

    def check_drift(self, recent_clicks: List) -> bool:
        """Return True if drift is detected (sudden large residual spike)."""
        if len(recent_clicks) < 10:
            return False
        mean_r = sum(c.residual_px for c in recent_clicks[-10:]) / 10
        return mean_r > self._drift_threshold
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python && python -m pytest tests/test_accuracy_gate.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add python/spaces/desktop/eyeterm/cursor/accuracy_gate.py python/tests/test_accuracy_gate.py
git commit -m "feat(eyeterm): add AccuracyGate with resolution-independent thresholds"
```

---

## Chunk 4: ClickCollector

### Task 4: ClickCollector — tests + implementation

**Files:**
- Create: `python/tests/test_click_collector.py`
- Create: `python/spaces/desktop/eyeterm/cursor/click_collector.py`

- [ ] **Step 1: Write failing tests**

Note: We cannot test the actual Windows hook in unit tests. Tests focus on the data model, filtering logic, and thread-safe prediction.

```python
# python/tests/test_click_collector.py
import math
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_click_sample_residual():
    from spaces.desktop.eyeterm.cursor.click_collector import ClickSample
    s = ClickSample(
        timestamp=time.time(),
        click_x=100, click_y=200,
        predicted_x=130, predicted_y=240,
    )
    assert abs(s.residual_px - 50.0) < 1  # hypot(30, 40) = 50


def test_prediction_tuple_atomic():
    """Prediction should be a single tuple for atomic read/write."""
    from spaces.desktop.eyeterm.cursor.click_collector import ClickCollector
    cc = ClickCollector(buffer_size=10)
    cc.update_prediction(100, 200, True)
    pred = cc._prediction
    assert pred == (100, 200, True, pred[3])  # timestamp is dynamic


def test_should_accept_click_valid():
    from spaces.desktop.eyeterm.cursor.click_collector import ClickCollector
    cc = ClickCollector(buffer_size=10, max_residual_px=500, max_age_ms=200)
    cc.update_prediction(100, 200, True)
    # Simulate a click right after prediction
    assert cc._should_accept(130, 240) is True


def test_should_reject_no_face():
    from spaces.desktop.eyeterm.cursor.click_collector import ClickCollector
    cc = ClickCollector(buffer_size=10)
    cc.update_prediction(100, 200, False)  # no face
    assert cc._should_accept(130, 240) is False


def test_should_reject_stale():
    from spaces.desktop.eyeterm.cursor.click_collector import ClickCollector
    cc = ClickCollector(buffer_size=10, max_age_ms=50)
    cc._prediction = (100, 200, True, time.time() - 1.0)  # 1s old
    assert cc._should_accept(130, 240) is False


def test_should_reject_huge_residual():
    from spaces.desktop.eyeterm.cursor.click_collector import ClickCollector
    cc = ClickCollector(buffer_size=10, max_residual_px=100)
    cc.update_prediction(100, 200, True)
    assert cc._should_accept(900, 900) is False  # way too far


def test_get_recent():
    from spaces.desktop.eyeterm.cursor.click_collector import ClickCollector, ClickSample
    cc = ClickCollector(buffer_size=5)
    for i in range(10):
        cc._buffer.append(ClickSample(time.time(), i, i, i, i))
    recent = cc.get_recent(3)
    assert len(recent) == 3
    assert recent[-1].click_x == 9  # most recent
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python && python -m pytest tests/test_click_collector.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement ClickCollector**

```python
# python/spaces/desktop/eyeterm/cursor/click_collector.py
"""System-wide mouse click collector for implicit gaze calibration.

Uses Windows WH_MOUSE_LL hook with a proper message pump thread.
Thread safety: prediction is shared as a single immutable tuple
(atomic assignment in CPython due to GIL).
"""

import ctypes
import ctypes.wintypes
import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger("eyeterm.click_collector")


@dataclass
class ClickSample:
    """One recorded click with predicted gaze position."""

    timestamp: float
    click_x: int
    click_y: int
    predicted_x: int
    predicted_y: int
    residual_px: float = field(init=False)

    def __post_init__(self):
        self.residual_px = math.hypot(
            self.click_x - self.predicted_x,
            self.click_y - self.predicted_y,
        )


class ClickCollector:
    """Collect mouse clicks with gaze predictions for implicit calibration.

    The hook thread runs a Windows message pump (required for WH_MOUSE_LL).
    Prediction data is shared via atomic tuple assignment.
    """

    WH_MOUSE_LL = 14
    WM_LBUTTONDOWN = 0x0201
    WM_QUIT = 0x0012

    def __init__(
        self,
        buffer_size: int = 500,
        max_residual_px: int = 500,
        max_age_ms: int = 200,
    ) -> None:
        self._buffer: deque[ClickSample] = deque(maxlen=buffer_size)
        self._max_residual = max_residual_px
        self._max_age = max_age_ms / 1000.0
        # Thread-safe prediction: single tuple, atomic assignment
        self._prediction: Tuple[int, int, bool, float] = (0, 0, False, 0.0)
        self._hook = None
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None

    def update_prediction(self, x: int, y: int, valid: bool) -> None:
        """Called each frame from _tick(). Atomic tuple assignment."""
        self._prediction = (x, y, valid, time.time())

    def _should_accept(self, click_x: int, click_y: int) -> bool:
        """Check if a click should be recorded (filter logic)."""
        px, py, valid, t = self._prediction
        if not valid:
            return False
        if time.time() - t > self._max_age:
            return False
        residual = math.hypot(click_x - px, click_y - py)
        if residual > self._max_residual:
            return False
        return True

    def _record_click(self, click_x: int, click_y: int) -> None:
        """Record a click if it passes filters. Called from hook callback."""
        if not self._should_accept(click_x, click_y):
            return
        px, py, _, _ = self._prediction
        self._buffer.append(ClickSample(
            timestamp=time.time(),
            click_x=click_x,
            click_y=click_y,
            predicted_x=px,
            predicted_y=py,
        ))

    def start(self) -> None:
        """Start the hook thread with message pump."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_hook,
            daemon=True,
            name="click-collector",
        )
        self._thread.start()
        logger.info("ClickCollector started")

    def _run_hook(self) -> None:
        """Hook thread: install WH_MOUSE_LL and run message pump."""
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            self._thread_id = kernel32.GetCurrentThreadId()

            # Define callback type
            HOOKPROC = ctypes.WINFUNCTYPE(
                ctypes.c_long,
                ctypes.c_int,
                ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_long),
            )

            def hook_proc(nCode, wParam, lParam):
                if nCode >= 0 and wParam == self.WM_LBUTTONDOWN:
                    click_x = lParam[0]
                    click_y = lParam[1]
                    self._record_click(click_x, click_y)
                return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

            self._hook_func = HOOKPROC(hook_proc)  # prevent GC
            self._hook = user32.SetWindowsHookExW(
                self.WH_MOUSE_LL, self._hook_func, None, 0,
            )

            if not self._hook:
                logger.error("SetWindowsHookExW failed")
                return

            # Message pump — required for WH_MOUSE_LL callbacks
            msg = ctypes.wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        except Exception as e:
            logger.error("ClickCollector hook thread error: %s", e)
        finally:
            if self._hook:
                try:
                    ctypes.windll.user32.UnhookWindowsHookEx(self._hook)
                except Exception:
                    pass
            logger.info("ClickCollector hook thread exited")

    def stop(self) -> None:
        """Post WM_QUIT to break the message pump, then join."""
        if self._thread_id:
            try:
                ctypes.windll.user32.PostThreadMessageW(
                    self._thread_id, self.WM_QUIT, 0, 0,
                )
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None
        self._thread_id = None
        logger.info("ClickCollector stopped")

    def get_recent(self, n: int = 20) -> List[ClickSample]:
        """Return the most recent n click samples."""
        items = list(self._buffer)
        return items[-n:] if len(items) > n else items
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python && python -m pytest tests/test_click_collector.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add python/spaces/desktop/eyeterm/cursor/click_collector.py python/tests/test_click_collector.py
git commit -m "feat(eyeterm): add ClickCollector with WH_MOUSE_LL hook and message pump"
```

---

## Chunk 5: Config + Calibrate + Headless Integration

### Task 5: Update config with new params

**Files:**
- Modify: `python/spaces/desktop/eyeterm/config.py`

- [ ] **Step 1: Add new config fields to CursorConfig**

Add after existing `dwell_lock_frames` field in `CursorConfig`:

```python
    # AccuracyGate
    accuracy_threshold: float = 0.75
    accuracy_off_threshold: float = 0.50
    accuracy_radius_frac: float = 0.05   # fraction of screen diagonal
    drift_threshold_frac: float = 0.07
    accuracy_min_clicks: int = 20
    # ResidualGrid
    grid_size: int = 5
    # ClickCollector
    click_buffer_size: int = 500
    click_max_age_ms: int = 200
    click_max_residual_frac: float = 0.25  # fraction of screen diagonal
    # Polynomial
    poly_ridge_lambda: float = 0.01
```

- [ ] **Step 2: Add env var reading in `from_env()`**

```python
        # Accuracy gate
        accuracy_threshold = float(os.environ.get("EYETERM_ACCURACY_THRESHOLD", "0.75"))
        accuracy_off = float(os.environ.get("EYETERM_ACCURACY_OFF", "0.50"))
        accuracy_radius_frac = float(os.environ.get("EYETERM_ACCURACY_RADIUS_FRAC", "0.05"))
        drift_frac = float(os.environ.get("EYETERM_DRIFT_THRESHOLD_FRAC", "0.07"))
        accuracy_min_clicks = int(os.environ.get("EYETERM_ACCURACY_MIN_CLICKS", "20"))
        grid_size = int(os.environ.get("EYETERM_GRID_SIZE", "5"))
        click_buffer = int(os.environ.get("EYETERM_CLICK_BUFFER", "500"))
        click_age = int(os.environ.get("EYETERM_CLICK_MAX_AGE", "200"))
        click_residual_frac = float(os.environ.get("EYETERM_CLICK_MAX_RESIDUAL_FRAC", "0.25"))
        poly_ridge = float(os.environ.get("EYETERM_POLY_RIDGE_LAMBDA", "0.01"))
```

Wire into `CursorConfig(...)` constructor.

- [ ] **Step 3: Commit**

```bash
git add python/spaces/desktop/eyeterm/config.py
git commit -m "feat(eyeterm): add config params for accuracy gate, grid, click collector"
```

### Task 6: Update calibrate.py to use PolynomialMapper

**Files:**
- Modify: `python/spaces/desktop/eyeterm/vision/calibrate.py`

- [ ] **Step 1: Replace affine `_fit_affine()` with PolynomialMapper.fit()**

In `HeadlessCalibrationManager._do_fitting()`:

```python
def _do_fitting(self) -> None:
    try:
        from .polynomial_mapper import PolynomialMapper
        pm = PolynomialMapper()
        gaze_pts = [c[0] for c in self._collected]
        screen_pts = [c[1] for c in self._collected]
        new_matrix = pm.fit(gaze_pts, screen_pts, ridge_lambda=self._ridge_lambda)
        # ... rest of merge logic stays the same
```

- [ ] **Step 2: Update persistence to use PolynomialMapper.save/load**

Replace `save_calibration()` and `load_calibration()` to delegate to `PolynomialMapper`.

- [ ] **Step 3: Commit**

```bash
git add python/spaces/desktop/eyeterm/vision/calibrate.py
git commit -m "refactor(eyeterm): use PolynomialMapper in calibration fitting"
```

### Task 7: Wire everything into headless.py

**Files:**
- Modify: `python/spaces/desktop/eyeterm/headless.py`
- Modify: `python/spaces/desktop/eyeterm/cursor/__init__.py`

- [ ] **Step 1: Update `__init__.py` with lazy imports**

```python
# python/spaces/desktop/eyeterm/cursor/__init__.py
def __getattr__(name):
    if name == "CursorDriver":
        from .cursor_driver import CursorDriver
        return CursorDriver
    if name == "ClickCollector":
        from .click_collector import ClickCollector
        return ClickCollector
    if name == "ResidualGrid":
        from .residual_grid import ResidualGrid
        return ResidualGrid
    if name == "AccuracyGate":
        from .accuracy_gate import AccuracyGate
        return AccuracyGate
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 2: Add new components to `_init_components()`**

After screen mapper setup, add:

```python
# --- ResidualGrid ---
from .cursor.residual_grid import ResidualGrid
self._residual_grid = ResidualGrid(sw, sh, grid_size=self._config.cursor.grid_size)

# --- AccuracyGate ---
from .cursor.accuracy_gate import AccuracyGate
self._accuracy_gate = AccuracyGate(
    sw, sh,
    threshold_on=self._config.cursor.accuracy_threshold,
    threshold_off=self._config.cursor.accuracy_off_threshold,
    accuracy_radius_frac=self._config.cursor.accuracy_radius_frac,
    drift_threshold_frac=self._config.cursor.drift_threshold_frac,
    min_clicks=self._config.cursor.accuracy_min_clicks,
)

# --- ClickCollector ---
from .cursor.click_collector import ClickCollector
diag = math.hypot(sw, sh)
self._click_collector = ClickCollector(
    buffer_size=self._config.cursor.click_buffer_size,
    max_residual_px=int(self._config.cursor.click_max_residual_frac * diag),
    max_age_ms=self._config.cursor.click_max_age_ms,
)
self._click_collector.start()
```

- [ ] **Step 3: Update `_tick()` pipeline**

After screen mapping, add grid correction and accuracy gating:

```python
# Apply residual grid correction
if self._residual_grid:
    dx, dy = self._residual_grid.interpolate(screen_x, screen_y)
    screen_x = int(screen_x + dx)
    screen_y = int(screen_y + dy)

# Update click collector with current prediction
if self._click_collector:
    self._click_collector.update_prediction(screen_x, screen_y, True)

# Process new clicks: update grid + check accuracy
if self._click_collector:
    for sample in self._click_collector.get_recent(5):
        self._residual_grid.update(
            sample.predicted_x, sample.predicted_y,
            sample.click_x, sample.click_y,
        )

# Accuracy gate controls cursor
if self._accuracy_gate:
    recent = self._click_collector.get_recent(20) if self._click_collector else []
    self._accuracy_gate.update(recent)
    if not self._accuracy_gate.cursor_enabled:
        cursor_moved = False  # don't move cursor in learning/degraded phase
    # Drift detection
    if self._accuracy_gate.check_drift(recent) and self._residual_grid:
        self._residual_grid.reset()
        self._log("Drift detected — grid reset")
```

- [ ] **Step 4: Update `_cleanup()` to stop ClickCollector**

```python
if hasattr(self, '_click_collector') and self._click_collector:
    self._click_collector.stop()
```

- [ ] **Step 5: Add click-learning CSV**

Open a separate CSV file `logs/eyeterm_click_learning.csv` in `_init_components()`. Flush new click samples from the main tick loop periodically (every 30 frames).

- [ ] **Step 6: Commit**

```bash
git add python/spaces/desktop/eyeterm/cursor/__init__.py python/spaces/desktop/eyeterm/headless.py
git commit -m "feat(eyeterm): wire polynomial mapper, residual grid, accuracy gate, click collector into pipeline"
```

---

## Chunk 6: End-to-End Verification

### Task 8: Integration test

**Files:**
- Create: `python/tests/test_eyeterm_precision_e2e.py`

- [ ] **Step 1: Write integration test**

```python
# python/tests/test_eyeterm_precision_e2e.py
"""Integration test: full pipeline without camera/hooks."""
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_polynomial_to_grid_to_accuracy():
    """Full pipeline: fit polynomial, simulate clicks, verify accuracy gate activation."""
    from spaces.desktop.eyeterm.vision.polynomial_mapper import PolynomialMapper
    from spaces.desktop.eyeterm.cursor.residual_grid import ResidualGrid
    from spaces.desktop.eyeterm.cursor.accuracy_gate import AccuracyGate
    from spaces.desktop.eyeterm.cursor.click_collector import ClickSample

    # 1. Fit polynomial
    pm = PolynomialMapper()
    gaze_pts = [
        (0.1, 0.1), (0.5, 0.1), (0.9, 0.1),
        (0.1, 0.5), (0.5, 0.5), (0.9, 0.5),
        (0.1, 0.9), (0.5, 0.9), (0.9, 0.9),
    ]
    screen_pts = [(g[0] * 1920, g[1] * 1080) for g in gaze_pts]
    pm.fit(gaze_pts, screen_pts)

    # 2. Predict and verify reasonable accuracy
    px, py = pm.predict(0.5, 0.5)
    assert abs(px - 960) < 10
    assert abs(py - 540) < 10

    # 3. Simulate clicks and grid learning
    grid = ResidualGrid(1920, 1080, grid_size=5)
    gate = AccuracyGate(1920, 1080, min_clicks=10)

    assert gate.phase == "learning"

    # Simulate 20 clicks with small residuals
    clicks = []
    for i in range(20):
        gx, gy = 0.3 + i * 0.02, 0.4 + i * 0.01
        pred_x, pred_y = pm.predict(gx, gy)
        # Actual click is close to prediction (user looking where they click)
        click_x = int(pred_x + np.random.normal(0, 30))
        click_y = int(pred_y + np.random.normal(0, 30))
        grid.update(pred_x, pred_y, click_x, click_y)
        clicks.append(ClickSample(
            timestamp=0, click_x=click_x, click_y=click_y,
            predicted_x=int(pred_x), predicted_y=int(pred_y),
        ))

    gate.update(clicks[-20:])
    # With 30px noise vs ~110px radius, most clicks should be "accurate"
    assert gate.phase == "ready", f"Expected ready, got {gate.phase}"
```

- [ ] **Step 2: Run integration test**

Run: `cd python && python -m pytest tests/test_eyeterm_precision_e2e.py -v`
Expected: PASS

- [ ] **Step 3: Run all eyeterm tests**

Run: `cd python && python -m pytest tests/test_polynomial_mapper.py tests/test_residual_grid.py tests/test_accuracy_gate.py tests/test_click_collector.py tests/test_eyeterm_precision_e2e.py -v`
Expected: All tests PASS

- [ ] **Step 4: Final commit**

```bash
git add python/tests/test_eyeterm_precision_e2e.py
git commit -m "test(eyeterm): add integration test for precision gaze pipeline"
```
