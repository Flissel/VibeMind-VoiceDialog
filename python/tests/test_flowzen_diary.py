"""Tests for Flowzen diary entries."""
import os, tempfile
from data.supabase_database import Database
from data.flowzen_repository import FlowzenRepository


def _temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    db.initialize()
    return db, path


def test_create_diary_entry():
    db, path = _temp_db()
    try:
        repo = FlowzenRepository(db)
        entry = repo.create_diary_entry(
            entry_text="Du warst heute kreativ unterwegs...",
            mood="focused", energy=7, time_window="afternoon",
            hour=15, intent_count=5, category="creative",
            brain_action="suggest_task", brain_reasoning="Gute Phase",
        )
        assert entry.id
        assert entry.entry_text == "Du warst heute kreativ unterwegs..."
        assert entry.mood == "focused"
        assert entry.source == "periodic"
    finally:
        os.unlink(path)


def test_get_recent_diary_entries():
    import time
    db, path = _temp_db()
    try:
        repo = FlowzenRepository(db)
        repo.create_diary_entry(entry_text="Eintrag 1", mood="calm", hour=10)
        time.sleep(0.01)
        repo.create_diary_entry(entry_text="Eintrag 2", mood="tired", hour=14)
        time.sleep(0.01)
        repo.create_diary_entry(entry_text="Eintrag 3", mood="energized", hour=16)
        entries = repo.get_recent_diary_entries(limit=2)
        assert len(entries) == 2
        assert entries[0].entry_text == "Eintrag 3"  # newest first
    finally:
        os.unlink(path)


def test_diary_entry_to_dict():
    from data.models import FlowzenDiaryEntry
    entry = FlowzenDiaryEntry(id="d-001", entry_text="Test", mood="calm")
    d = entry.to_dict()
    assert d["id"] == "d-001"
    assert d["entry_text"] == "Test"
    assert d["source"] == "periodic"


def test_diary_entry_from_dict():
    from data.models import FlowzenDiaryEntry
    raw = {"id": "d-002", "entry_text": "Warm text", "mood": "focused",
           "energy": 8, "intent_count": 3, "source": "manual",
           "created_at": "2026-03-22T17:00:00"}
    entry = FlowzenDiaryEntry.from_dict(raw)
    assert entry.mood == "focused"
    assert entry.source == "manual"
    assert entry.intent_count == 3
