"""Tests for Flowzen repository CRUD."""
import os
import tempfile
from data.database import Database
from data.repository import FlowzenRepository, generate_id


def _setup_db():
    """Create a temp database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    db.initialize()
    return db, path


def test_create_and_get_checkin():
    db, path = _setup_db()
    try:
        repo = FlowzenRepository(db)
        checkin = repo.create_checkin(mood="focused", energy=7, hour=10)
        assert checkin.id
        assert checkin.mood == "focused"

        fetched = repo.get_checkin(checkin.id)
        assert fetched is not None
        assert fetched.mood == "focused"
    finally:
        os.unlink(path)


def test_recent_checkins():
    db, path = _setup_db()
    try:
        repo = FlowzenRepository(db)
        repo.create_checkin(mood="tired", energy=3, hour=20)
        repo.create_checkin(mood="energized", energy=9, hour=8)
        recent = repo.get_recent_checkins(limit=5)
        assert len(recent) == 2
        assert recent[0].mood == "energized"
    finally:
        os.unlink(path)


def test_log_and_query_activity():
    db, path = _setup_db()
    try:
        repo = FlowzenRepository(db)
        repo.log_activity(event_type="idea.create", hour=10)
        repo.log_activity(event_type="code.generate", hour=10)
        recent = repo.get_recent_activity(limit=5)
        assert len(recent) == 2
        assert recent[0].event_type == "code.generate"
    finally:
        os.unlink(path)


def test_last_activity_timestamp():
    db, path = _setup_db()
    try:
        repo = FlowzenRepository(db)
        assert repo.get_last_activity_time() is None
        repo.log_activity(event_type="idea.list", hour=14)
        ts = repo.get_last_activity_time()
        assert ts is not None
    finally:
        os.unlink(path)
