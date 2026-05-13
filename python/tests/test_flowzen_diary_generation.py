"""Tests for diary entry generation in periodic summary."""
import os, tempfile
from unittest.mock import patch, AsyncMock
from data.supabase_database import Database


def _temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    db.initialize()
    return db, path


def test_diary_prompt_constants_exist():
    from spaces.flowzen.activity_tracker import DIARY_SYSTEM_PROMPT, DIARY_USER_TEMPLATE
    assert "Tagebuch" in DIARY_SYSTEM_PROMPT or "Taschenbuch" in DIARY_SYSTEM_PROMPT
    assert "{mood}" in DIARY_USER_TEMPLATE
    assert "{brain_action}" in DIARY_USER_TEMPLATE


def test_generate_diary_entry_fallback():
    """When LLM fails, a warm fallback text is returned."""
    import asyncio
    from spaces.flowzen.activity_tracker import generate_diary_entry

    with patch("llm_config.get_async_client", side_effect=Exception("no key")):
        text = asyncio.run(generate_diary_entry(
            mood="calm", energy=5, time_window="evening", hour=19,
            category="rest", intent_count=3, activity_summary="idea.create:3",
        ))
        assert len(text) > 20
        assert "3" in text  # references intent count


def test_set_brain_bridge():
    from spaces.flowzen.activity_tracker import ActivityTracker
    tracker = ActivityTracker()
    tracker.set_brain_bridge("mock_bridge")
    assert tracker._brain_bridge == "mock_bridge"
