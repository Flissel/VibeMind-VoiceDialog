"""Tests for Flowzen ActivityTracker — passive broadcast listener."""
import time
from unittest.mock import patch, MagicMock
import os
import tempfile

from data.supabase_database import Database


def _temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    db.initialize()
    return db, path


def test_on_intent_logs_activity():
    db, path = _temp_db()
    try:
        with patch("data.flowzen_repository.get_database", return_value=db):
            from spaces.flowzen.activity_tracker import ActivityTracker
            tracker = ActivityTracker(summary_interval_minutes=5)
            tracker.on_intent("idea.create", {"title": "Test"})

            from data.flowzen_repository import FlowzenRepository
            repo = FlowzenRepository(db)
            recent = repo.get_recent_activity(limit=5)
            assert len(recent) == 1
            assert recent[0].event_type == "idea.create"
    finally:
        os.unlink(path)


def test_build_summary_empty():
    """Summary with no activity should reflect zero intents."""
    from spaces.flowzen.activity_tracker import ActivityTracker
    tracker = ActivityTracker(summary_interval_minutes=30)
    summary = tracker._build_summary()
    assert summary["intent_count"] == 0
    assert summary["minutes_since_last_activity"] == -1


def test_build_summary_after_activity():
    """Summary should aggregate logged intents."""
    db, path = _temp_db()
    try:
        with patch("data.flowzen_repository.get_database", return_value=db):
            from spaces.flowzen.activity_tracker import ActivityTracker
            tracker = ActivityTracker(summary_interval_minutes=30)
            tracker.on_intent("idea.create", {})
            tracker.on_intent("idea.create", {})
            tracker.on_intent("code.generate", {})
            summary = tracker._build_summary()
            assert summary["intent_count"] == 3
            assert "idea.create" in summary["event_types"]
            assert summary["minutes_since_last_activity"] == 0
    finally:
        os.unlink(path)


def test_circadian_matrix_completeness():
    from spaces.flowzen.activity_tracker import CIRCADIAN_MATRIX
    moods = ["energized", "focused", "calm", "tired", "anxious"]
    windows = ["early_morning", "morning", "midday", "afternoon", "evening", "night"]
    for mood in moods:
        for window in windows:
            assert mood in CIRCADIAN_MATRIX, f"Missing mood: {mood}"
            assert window in CIRCADIAN_MATRIX[mood], f"Missing {window} for {mood}"
