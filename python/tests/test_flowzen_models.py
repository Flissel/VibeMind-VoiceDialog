"""Tests for Flowzen data models."""
from datetime import datetime
from data.models import FlowzenCheckin, FlowzenActivity


def test_checkin_to_dict():
    c = FlowzenCheckin(
        id="chk-001",
        mood="focused",
        energy=7,
        time_window="midday",
        hour=10,
    )
    d = c.to_dict()
    assert d["id"] == "chk-001"
    assert d["mood"] == "focused"
    assert d["energy"] == 7
    assert d["time_window"] == "midday"


def test_checkin_from_dict():
    raw = {
        "id": "chk-002",
        "mood": "tired",
        "energy": 3,
        "time_window": "evening",
        "hour": 19,
        "notes": "long day",
        "created_at": "2026-03-20T14:00:00",
    }
    c = FlowzenCheckin.from_dict(raw)
    assert c.mood == "tired"
    assert c.energy == 3
    assert c.notes == "long day"


def test_activity_to_dict():
    a = FlowzenActivity(
        id="act-001",
        event_type="idea.create",
        time_window="morning",
        hour=9,
    )
    d = a.to_dict()
    assert d["event_type"] == "idea.create"
    assert d["time_window"] == "morning"


def test_activity_from_dict():
    raw = {
        "id": "act-002",
        "event_type": "code.generate",
        "time_window": "afternoon",
        "hour": 15,
        "created_at": "2026-03-20T15:00:00",
    }
    a = FlowzenActivity.from_dict(raw)
    assert a.event_type == "code.generate"
    assert a.hour == 15
