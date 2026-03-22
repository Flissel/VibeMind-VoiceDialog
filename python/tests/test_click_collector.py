"""Tests for ClickCollector — data model, filtering logic, thread-safe prediction.

The actual Windows WH_MOUSE_LL hook cannot be exercised in a test environment,
so all tests operate on the pure-Python logic only.
"""

import math
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spaces.desktop.eyeterm.cursor.click_collector import ClickCollector, ClickSample


# ---------------------------------------------------------------------------
# ClickSample dataclass
# ---------------------------------------------------------------------------


class TestClickSampleResiduual:
    """Verify ClickSample.residual_px uses math.hypot correctly."""

    def test_click_sample_residual_zero(self):
        """Perfect prediction → residual is 0."""
        s = ClickSample(
            timestamp=1.0, click_x=100, click_y=200, predicted_x=100, predicted_y=200
        )
        assert s.residual_px == 0.0

    def test_click_sample_residual_horizontal(self):
        """Pure horizontal offset."""
        s = ClickSample(
            timestamp=1.0, click_x=103, click_y=200, predicted_x=100, predicted_y=200
        )
        assert s.residual_px == pytest_approx(3.0)

    def test_click_sample_residual_vertical(self):
        """Pure vertical offset."""
        s = ClickSample(
            timestamp=1.0, click_x=100, click_y=204, predicted_x=100, predicted_y=200
        )
        assert s.residual_px == pytest_approx(4.0)

    def test_click_sample_residual_diagonal(self):
        """3-4-5 right triangle → residual = 5."""
        s = ClickSample(
            timestamp=1.0, click_x=103, click_y=204, predicted_x=100, predicted_y=200
        )
        assert abs(s.residual_px - 5.0) < 1e-9

    def test_click_sample_residual_general(self):
        """General case matches math.hypot reference."""
        dx, dy = 7, 24  # 7-24-25 triple
        s = ClickSample(
            timestamp=1.0,
            click_x=107,
            click_y=224,
            predicted_x=100,
            predicted_y=200,
        )
        expected = math.hypot(dx, dy)
        assert abs(s.residual_px - expected) < 1e-9


# ---------------------------------------------------------------------------
# Atomic prediction tuple
# ---------------------------------------------------------------------------


class TestPredictionTupleAtomic:
    """update_prediction stores a new tuple that can be read back immediately."""

    def test_prediction_tuple_atomic(self):
        col = ClickCollector()
        col.update_prediction(320, 240, True)
        x, y, valid, ts = col._prediction
        assert x == 320
        assert y == 240
        assert valid is True
        assert ts > 0.0

    def test_default_prediction_invalid(self):
        """Freshly created collector should have an invalid prediction."""
        col = ClickCollector()
        _x, _y, valid, _ts = col._prediction
        assert valid is False

    def test_prediction_overwrite(self):
        col = ClickCollector()
        col.update_prediction(10, 20, True)
        col.update_prediction(999, 888, False)
        x, y, valid, _ts = col._prediction
        assert x == 999
        assert y == 888
        assert valid is False


# ---------------------------------------------------------------------------
# _should_accept filtering logic
# ---------------------------------------------------------------------------


class TestShouldAcceptClickValid:
    """A click with a fresh, valid prediction within max_residual is accepted."""

    def test_should_accept_click_valid(self):
        col = ClickCollector(max_age=1.0, max_residual=200.0)
        col.update_prediction(100, 100, True)
        # Click very close to prediction
        assert col._should_accept(105, 105) is True

    def test_should_accept_click_at_exact_prediction(self):
        col = ClickCollector(max_age=1.0, max_residual=200.0)
        col.update_prediction(500, 300, True)
        assert col._should_accept(500, 300) is True

    def test_should_accept_click_within_residual_boundary(self):
        """Click exactly at max_residual should be accepted (boundary inclusive)."""
        col = ClickCollector(max_age=1.0, max_residual=100.0)
        col.update_prediction(0, 0, True)
        # residual = 100.0 exactly (100, 0 → hypot(100,0)=100)
        assert col._should_accept(100, 0) is True


class TestShouldRejectNoFace:
    """Clicks are rejected when the prediction is marked invalid (face not detected)."""

    def test_should_reject_no_face(self):
        col = ClickCollector(max_age=1.0, max_residual=500.0)
        col.update_prediction(100, 100, False)
        assert col._should_accept(100, 100) is False

    def test_should_reject_default_state(self):
        """Before any update_prediction call, valid=False → reject all clicks."""
        col = ClickCollector()
        assert col._should_accept(500, 400) is False


class TestShouldRejectStale:
    """Clicks are rejected when the prediction is older than max_age."""

    def test_should_reject_stale(self):
        col = ClickCollector(max_age=0.05, max_residual=500.0)
        col.update_prediction(100, 100, True)
        # Sleep longer than max_age
        time.sleep(0.1)
        assert col._should_accept(100, 100) is False

    def test_should_accept_fresh(self):
        """A prediction set just now should pass the age check."""
        col = ClickCollector(max_age=2.0, max_residual=500.0)
        col.update_prediction(200, 200, True)
        assert col._should_accept(200, 200) is True

    def test_stale_prediction_rejections_independent_of_residual(self):
        """Even a perfect-residual click is rejected if prediction is stale."""
        col = ClickCollector(max_age=0.05, max_residual=1000.0)
        col.update_prediction(300, 300, True)
        time.sleep(0.1)
        assert col._should_accept(300, 300) is False


class TestShouldRejectHugeResiduual:
    """Clicks far from the prediction are rejected as outliers."""

    def test_should_reject_huge_residual(self):
        col = ClickCollector(max_age=2.0, max_residual=50.0)
        col.update_prediction(100, 100, True)
        # Click 200 px away → residual = 200 > max_residual 50
        assert col._should_accept(300, 100) is False

    def test_boundary_just_over_max_residual(self):
        """Click one pixel beyond max_residual should be rejected."""
        col = ClickCollector(max_age=2.0, max_residual=100.0)
        col.update_prediction(0, 0, True)
        # residual = hypot(101, 0) = 101 > 100
        assert col._should_accept(101, 0) is False

    def test_boundary_just_within_max_residual(self):
        col = ClickCollector(max_age=2.0, max_residual=100.0)
        col.update_prediction(0, 0, True)
        # residual = hypot(99, 0) = 99 < 100
        assert col._should_accept(99, 0) is True


# ---------------------------------------------------------------------------
# get_recent
# ---------------------------------------------------------------------------


class TestGetRecent:
    """get_recent returns the last n ClickSamples in chronological order."""

    def _add_samples(self, col: ClickCollector, count: int) -> None:
        """Inject synthetic samples directly into the deque."""
        for i in range(count):
            sample = ClickSample(
                timestamp=float(i),
                click_x=i,
                click_y=i,
                predicted_x=i,
                predicted_y=i,
            )
            col._samples.append(sample)

    def test_get_recent(self):
        col = ClickCollector()
        self._add_samples(col, 10)
        result = col.get_recent(3)
        assert len(result) == 3
        # Should be the last 3: indices 7, 8, 9
        assert result[0].click_x == 7
        assert result[1].click_x == 8
        assert result[2].click_x == 9

    def test_get_recent_all_when_fewer_than_n(self):
        col = ClickCollector()
        self._add_samples(col, 5)
        result = col.get_recent(20)
        assert len(result) == 5

    def test_get_recent_empty(self):
        col = ClickCollector()
        result = col.get_recent(5)
        assert result == []

    def test_get_recent_returns_list(self):
        col = ClickCollector()
        self._add_samples(col, 3)
        result = col.get_recent(10)
        assert isinstance(result, list)

    def test_get_recent_chronological_order(self):
        """Samples are returned oldest-first (chronological)."""
        col = ClickCollector()
        self._add_samples(col, 5)
        result = col.get_recent(5)
        timestamps = [s.timestamp for s in result]
        assert timestamps == sorted(timestamps)

    def test_get_recent_respects_maxlen_ringbuffer(self):
        """When collector wraps around its ring buffer, oldest entries are dropped."""
        col = ClickCollector(maxlen=5)
        self._add_samples(col, 10)  # 10 samples into a maxlen-5 deque
        all_samples = col.get_recent(100)
        assert len(all_samples) == 5
        # Should contain click_x 5..9 (newest 5)
        assert all_samples[0].click_x == 5
        assert all_samples[-1].click_x == 9


# ---------------------------------------------------------------------------
# _record_click integration (no Windows hook needed)
# ---------------------------------------------------------------------------


class TestRecordClick:
    """_record_click appends samples only when _should_accept returns True."""

    def test_record_click_appends_on_valid_prediction(self):
        col = ClickCollector(max_age=2.0, max_residual=500.0)
        col.update_prediction(100, 100, True)
        col._record_click(110, 110)
        assert len(col._samples) == 1
        s = col._samples[0]
        assert s.click_x == 110
        assert s.click_y == 110
        assert s.predicted_x == 100
        assert s.predicted_y == 100

    def test_record_click_skips_on_invalid_face(self):
        col = ClickCollector(max_age=2.0, max_residual=500.0)
        col.update_prediction(100, 100, False)
        col._record_click(110, 110)
        assert len(col._samples) == 0

    def test_record_click_skips_huge_residual(self):
        col = ClickCollector(max_age=2.0, max_residual=10.0)
        col.update_prediction(0, 0, True)
        col._record_click(500, 500)
        assert len(col._samples) == 0

    def test_record_click_multiple_accumulates(self):
        col = ClickCollector(max_age=2.0, max_residual=500.0)
        col.update_prediction(200, 200, True)
        for i in range(5):
            col._record_click(200 + i, 200 + i)
        assert len(col._samples) == 5


# ---------------------------------------------------------------------------
# Pytest compatibility helpers
# ---------------------------------------------------------------------------


def pytest_approx(value, rel=1e-6, abs=1e-9):  # noqa: A002
    """Thin wrapper so tests run without importing pytest at module level."""
    import pytest  # noqa: PLC0415
    return pytest.approx(value, rel=rel, abs=abs)
