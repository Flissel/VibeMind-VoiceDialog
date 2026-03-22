"""Flowzen Repository — CRUD for circadian activity tracking tables."""

import logging
from datetime import datetime
from typing import Optional, List

from .database import Database, get_database
from .models import FlowzenCheckin, FlowzenActivity, FlowzenDiaryEntry
from .repository_utils import generate_id

logger = logging.getLogger(__name__)


class FlowzenRepository:
    """Repository for Flowzen activity tracking and circadian state."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    def create_checkin(self, mood: str, energy: int, hour: int = None,
                       source: str = "inferred", notes: str = "") -> FlowzenCheckin:
        if hour is None:
            hour = datetime.now().hour

        checkin = FlowzenCheckin(
            id=generate_id(), mood=mood, energy=energy,
            time_window=self._hour_to_window(hour), hour=hour,
            source=source, notes=notes,
        )
        self.db.execute(
            "INSERT INTO flowzen_checkins (id, mood, energy, time_window, hour, source, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (checkin.id, checkin.mood, checkin.energy, checkin.time_window,
             checkin.hour, checkin.source, checkin.notes,
             checkin.created_at.isoformat()),
        )
        return checkin

    def get_checkin(self, checkin_id: str) -> Optional[FlowzenCheckin]:
        row = self.db.fetch_one("SELECT * FROM flowzen_checkins WHERE id = ?", (checkin_id,))
        return FlowzenCheckin.from_dict(dict(row)) if row else None

    def get_recent_checkins(self, limit: int = 10) -> List[FlowzenCheckin]:
        rows = self.db.fetch_all(
            "SELECT * FROM flowzen_checkins ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [FlowzenCheckin.from_dict(dict(r)) for r in rows]

    def log_activity(self, event_type: str, hour: int = None) -> FlowzenActivity:
        if hour is None:
            hour = datetime.now().hour

        activity = FlowzenActivity(
            id=generate_id(), event_type=event_type,
            time_window=self._hour_to_window(hour), hour=hour,
        )
        self.db.execute(
            "INSERT INTO flowzen_activity (id, event_type, time_window, hour, created_at) VALUES (?, ?, ?, ?, ?)",
            (activity.id, activity.event_type, activity.time_window, activity.hour,
             activity.created_at.isoformat()),
        )
        return activity

    def get_recent_activity(self, limit: int = 20) -> List[FlowzenActivity]:
        rows = self.db.fetch_all(
            "SELECT * FROM flowzen_activity ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [FlowzenActivity.from_dict(dict(r)) for r in rows]

    def get_last_activity_time(self) -> Optional[datetime]:
        row = self.db.fetch_one(
            "SELECT created_at FROM flowzen_activity ORDER BY created_at DESC LIMIT 1"
        )
        if row:
            val = row["created_at"]
            return datetime.fromisoformat(val) if isinstance(val, str) else val
        return None

    def create_diary_entry(self, entry_text: str, mood: str = "calm", energy: int = 5,
                           time_window: str = "", hour: int = 0, intent_count: int = 0,
                           category: str = "", brain_action: str = "", brain_reasoning: str = "",
                           raw_data: str = "{}", source: str = "periodic") -> FlowzenDiaryEntry:
        entry = FlowzenDiaryEntry(
            id=generate_id(), entry_text=entry_text, mood=mood, energy=energy,
            time_window=time_window, hour=hour, intent_count=intent_count,
            category=category, brain_action=brain_action, brain_reasoning=brain_reasoning,
            raw_data=raw_data, source=source,
        )
        self.db.execute(
            """INSERT INTO flowzen_diary
               (id, entry_text, mood, energy, time_window, hour, intent_count,
                category, brain_action, brain_reasoning, raw_data, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry.id, entry.entry_text, entry.mood, entry.energy,
             entry.time_window, entry.hour, entry.intent_count,
             entry.category, entry.brain_action, entry.brain_reasoning,
             entry.raw_data, entry.source, entry.created_at.isoformat()),
        )
        return entry

    def get_recent_diary_entries(self, limit: int = 10) -> list:
        rows = self.db.fetch_all(
            "SELECT * FROM flowzen_diary ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [FlowzenDiaryEntry.from_dict(dict(r)) for r in rows]

    @staticmethod
    def _hour_to_window(hour: int) -> str:
        if 5 <= hour < 8:
            return "early_morning"
        elif 8 <= hour < 12:
            return "morning"
        elif 12 <= hour < 14:
            return "midday"
        elif 14 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"
