"""Tests for PolynomialMapper — quadratic gaze-to-screen coordinate mapping."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

from spaces.desktop.eyeterm.vision.polynomial_mapper import PolynomialMapper


# ---------------------------------------------------------------------------
# Helper: build 9-point grid gaze/screen pairs for a linear mapping.
# ---------------------------------------------------------------------------

def _linear_grid(screen_w: int = 1920, screen_h: int = 1080):
    """Return (gaze_points, screen_targets) for a perfect linear mapping."""
    gaze_xs = [0.1, 0.5, 0.9]
    gaze_ys = [0.1, 0.5, 0.9]
    gaze_points = []
    screen_targets = []
    for gy in gaze_ys:
        for gx in gaze_xs:
            gaze_points.append((gx, gy))
            screen_targets.append((gx * screen_w, gy * screen_h))
    return gaze_points, screen_targets


# ---------------------------------------------------------------------------
# Feature vector
# ---------------------------------------------------------------------------

class TestFeatureVector:

    def test_feature_vector_shape(self):
        fv = PolynomialMapper.feature_vector(0.5, 0.3)
        assert fv.shape == (6,), f"Expected shape (6,), got {fv.shape}"

    def test_feature_vector_values(self):
        gx, gy = 0.4, 0.6
        fv = PolynomialMapper.feature_vector(gx, gy)
        expected = np.array(
            [gx ** 2, gy ** 2, gx * gy, gx, gy, 1.0],
            dtype=np.float64,
        )
        np.testing.assert_allclose(fv, expected, rtol=1e-12)


# ---------------------------------------------------------------------------
# Fit and predict — linear ground truth
# ---------------------------------------------------------------------------

class TestFitAndPredictIdentity:

    def test_fit_and_predict_identity(self):
        """9-point grid with a perfect linear mapping should predict exactly."""
        screen_w, screen_h = 1920, 1080
        gaze_points, screen_targets = _linear_grid(screen_w, screen_h)

        mapper = PolynomialMapper()
        mapper.fit(gaze_points, screen_targets, ridge_lambda=1e-6)

        # Test a corner and the centre.
        for gx, gy in [(0.1, 0.1), (0.5, 0.5), (0.9, 0.9), (0.3, 0.7)]:
            px, py = mapper.predict(gx, gy)
            assert abs(px - gx * screen_w) < 2.0, (
                f"screen_x error too large: got {px:.2f}, expected {gx * screen_w:.2f}"
            )
            assert abs(py - gy * screen_h) < 2.0, (
                f"screen_y error too large: got {py:.2f}, expected {gy * screen_h:.2f}"
            )


# ---------------------------------------------------------------------------
# Fit and predict — nonlinear (quadratic) ground truth
# ---------------------------------------------------------------------------

class TestFitNonlinear:

    def test_fit_nonlinear(self):
        """Quadratic ground truth should be recovered by the polynomial mapper."""
        # screen_x = 500 * gx^2 + 1000 * gx + 100
        # screen_y = 300 * gy^2 + 700 * gy + 50
        def true_x(gx, gy):
            return 500 * gx ** 2 + 1000 * gx + 100

        def true_y(gx, gy):
            return 300 * gy ** 2 + 700 * gy + 50

        gaze_xs = [0.0, 0.25, 0.5, 0.75, 1.0]
        gaze_ys = [0.0, 0.25, 0.5, 0.75, 1.0]
        gaze_points = []
        screen_targets = []
        for gy in gaze_ys:
            for gx in gaze_xs:
                gaze_points.append((gx, gy))
                screen_targets.append((true_x(gx, gy), true_y(gx, gy)))

        mapper = PolynomialMapper()
        mapper.fit(gaze_points, screen_targets, ridge_lambda=1e-9)

        # Verify type
        assert mapper.mapper_type == "polynomial"
        assert mapper.matrix is not None
        assert mapper.matrix.shape == (2, 6)

        # Test at an unseen point
        gx_test, gy_test = 0.4, 0.6
        px, py = mapper.predict(gx_test, gy_test)
        assert abs(px - true_x(gx_test, gy_test)) < 5.0, (
            f"Nonlinear screen_x error: got {px:.2f}"
        )
        assert abs(py - true_y(gx_test, gy_test)) < 5.0, (
            f"Nonlinear screen_y error: got {py:.2f}"
        )


# ---------------------------------------------------------------------------
# Predict with legacy affine (2, 3) matrix
# ---------------------------------------------------------------------------

class TestPredictAffineLegacy:

    def test_predict_affine_legacy(self):
        """A (2, 3) affine matrix should produce correct linear predictions."""
        # Hand-crafted affine: screen_x = 1920*gx + 0*gy + 0
        #                      screen_y = 0*gx + 1080*gy + 0
        affine = np.array(
            [[1920.0, 0.0, 0.0],
             [0.0, 1080.0, 0.0]],
            dtype=np.float64,
        )
        mapper = PolynomialMapper()
        mapper.matrix = affine
        mapper.mapper_type = "affine"

        px, py = mapper.predict(0.5, 0.25)
        assert abs(px - 960.0) < 1e-6
        assert abs(py - 270.0) < 1e-6


# ---------------------------------------------------------------------------
# Ridge prevents huge coefficients when gaze range is narrow
# ---------------------------------------------------------------------------

class TestRidgePreventsHugeCoefficients:

    def test_ridge_prevents_huge_coefficients(self):
        """With a very narrow gaze cluster, ridge should keep coefficients finite."""
        # All gaze points clumped near (0.5, 0.5) — very low variance.
        rng = np.random.default_rng(42)
        eps = 1e-4  # tiny spread

        gaze_points = [
            (0.5 + rng.uniform(-eps, eps), 0.5 + rng.uniform(-eps, eps))
            for _ in range(12)
        ]
        screen_targets = [
            (gx * 1920, gy * 1080)
            for gx, gy in gaze_points
        ]

        mapper = PolynomialMapper()
        mapper.fit(gaze_points, screen_targets, ridge_lambda=0.01)

        # Whatever the type, coefficients must not be astronomically large.
        max_coeff = float(np.max(np.abs(mapper.matrix)))
        assert max_coeff < 1e9, (
            f"Coefficients are too large: max abs = {max_coeff:.2e}"
        )

        # predict must return a finite value
        px, py = mapper.predict(0.5, 0.5)
        assert np.isfinite(px), "screen_x is not finite"
        assert np.isfinite(py), "screen_y is not finite"


# ---------------------------------------------------------------------------
# Save / load round-trip
# ---------------------------------------------------------------------------

class TestSaveLoadRoundtrip:

    def test_save_load_roundtrip(self):
        """Saving and loading a polynomial mapper must preserve coefficients."""
        gaze_points, screen_targets = _linear_grid()

        mapper = PolynomialMapper()
        mapper.fit(gaze_points, screen_targets, ridge_lambda=1e-6)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            mapper.save(tmp_path)

            loaded = PolynomialMapper.load(tmp_path)

            assert loaded.mapper_type == mapper.mapper_type
            assert loaded.matrix is not None
            np.testing.assert_allclose(loaded.matrix, mapper.matrix, rtol=1e-10)

            # Predictions should match
            for gx, gy in [(0.1, 0.9), (0.5, 0.5), (0.8, 0.2)]:
                px_orig, py_orig = mapper.predict(gx, gy)
                px_load, py_load = loaded.predict(gx, gy)
                assert abs(px_orig - px_load) < 1e-6
                assert abs(py_orig - py_load) < 1e-6

            # JSON must contain "type" field
            raw = json.loads(open(tmp_path, encoding="utf-8").read())
            assert "type" in raw
            assert raw["type"] in ("polynomial", "affine")
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Load legacy affine file (no "type" field)
# ---------------------------------------------------------------------------

class TestLoadAffineLegacyFile:

    def test_load_affine_legacy_file(self):
        """Loading a (2, 3) affine JSON file without a 'type' key must work."""
        affine_matrix = [
            [1920.0, 0.0, 0.0],
            [0.0, 1080.0, 0.0],
        ]
        # Legacy file: only has "matrix", no "type"
        legacy_data = {"matrix": affine_matrix}

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(legacy_data, f)
            tmp_path = f.name

        try:
            loaded = PolynomialMapper.load(tmp_path)

            assert loaded.matrix is not None
            assert loaded.matrix.shape == (2, 3)
            assert loaded.mapper_type == "affine"

            # Should predict correctly with the affine matrix
            px, py = loaded.predict(0.5, 0.5)
            assert abs(px - 960.0) < 1e-6
            assert abs(py - 540.0) < 1e-6
        finally:
            os.unlink(tmp_path)
