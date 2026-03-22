# Blaue Rose (Flowzen) — Passive Circadian Intelligence Layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Blaue Rose" background intelligence layer that passively observes all system activity, tracks circadian patterns, and sends inactivity signals to Brain/Tahlamus for cognitive analysis. Visualized as a blue rose under a glass dome (Beauty and the Beast) in the 3D multiverse.

**Architecture:** NOT a regular routed space. The Blaue Rose is a **broadcast listener** that receives copies of all intents, tracks activity patterns (frequency, gaps, time-of-day), and maintains a circadian model. On user inactivity (>X minutes), it sends a signal to Brain/Tahlamus which decides whether to recommend a task, suggest a break, or stay silent. The only direct user trigger is an explicit "Was soll ich machen?" mapped to `rose.recommend`. The rose never proactively asks the user anything.

**Tech Stack:** Python, SQLite (existing `vibemind.db`), Three.js (glass dome rose), BaseBackendAgent pattern, LLM (via `llm_config.py` — GPT 5.4 or configured model) for dynamic neuroscience reasoning

---

## Architecture Overview

```
ALL Intents (idea.create, code.generate, etc.)
     │
     ├── Normal Routing → zustaendiger Space (Ideas, Coding, etc.)
     │
     └── Broadcast Copy → Blaue Rose (ActivityTracker)
              │
              ├── Trackt: Tageszeit, Intent-Frequenz, Pausen, Themen
              ├── Aktualisiert: circadian state (mood × time_window)
              └── Schreibt: flowzen_activity_log (DB)
              │
              Alle 30 Minuten:
              ├── Aggregiert: Intent-Frequenz, Pausen, Themen, Tagesphase
              ├── Baut Situationsbericht (JSON summary)
              └── Sendet EIN Summary an Brain/Tahlamus
                    │
                    Brain entscheidet:
                    ├── "Aufgabe vorschlagen" → Rose gluht, Rachel spricht
                    ├── "Pause empfehlen" → Rose dimmt, Blaetter fallen
                    └── "Nichts tun" → Rose bleibt ruhig (default)

              User fragt EXPLIZIT "Was soll ich machen?"
              └── rose.recommend → Circadian Matrix → Empfehlung
```

**Key principles:**
- **Die Rose fragt NIE den User.** Sie beobachtet und informiert Brain.
- **30-Minuten-Takt:** Rose sammelt alle Beobachtungen und sendet nur alle 30 Min ein Summary an Brain.
- **Brain entscheidet.** Rose liefert nur Daten — Brain entscheidet ob/was passiert.

---

## File Structure

```
python/spaces/flowzen/                     # NEW directory
    __init__.py                            # Re-exports
    config.py                              # FlowzenConfig dataclass
    activity_tracker.py                    # Core: broadcast listener + inactivity detection
    agents/
        __init__.py                        # Re-exports
        flowzen_agent.py                   # Minimal agent (only rose.recommend)
    tools/
        __init__.py                        # Re-exports
        flowzen_tools.py                   # Circadian matrix + recommend_task + status
python/data/models.py                      # MODIFY — add FlowzenCheckin, FlowzenActivity
python/data/database.py                    # MODIFY — migration v18, 2 new tables
python/data/flowzen_repository.py          # NEW — FlowzenRepository (own file per pattern)
python/data/repository.py                  # MODIFY — add re-export for FlowzenRepository
python/data/__init__.py                    # MODIFY — add new models + repository
python/swarm/event_team/event_router.py    # MODIFY — add stream + mappings (only rose.recommend)
python/swarm/backend_agents/__init__.py    # MODIFY — add getter + lazy class
python/swarm/orchestrator/intent_classifier.py  # MODIFY — add MINIMAL section (only rose.recommend)
python/spaces/minibook/enrichment/space_router.py  # MODIFY — add prefix
python/plugins/builtin/flowzen/plugin.json # NEW — plugin manifest
electron-app/renderer/glass_rose.js        # NEW — Three.js glass dome rose renderer
```

---

### Task 1: Database — Models

**Files:**
- Modify: `python/data/models.py` (append after line ~873)

- [ ] **Step 1: Write the failing test**

Create `python/tests/test_flowzen_models.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && python -m pytest tests/test_flowzen_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'FlowzenCheckin'`

- [ ] **Step 3: Implement FlowzenCheckin and FlowzenActivity dataclasses**

Append to `python/data/models.py` after the `ScheduledTask` class (after line ~873):

```python
# --- Flowzen (Blaue Rose) --- Passive Circadian Intelligence Layer --------


@dataclass
class FlowzenCheckin:
    """
    A mood/energy state inferred by the Flowzen activity tracker.

    Unlike active check-ins, these are derived from activity patterns —
    the user is never asked directly.

    Mood values: 'energized', 'focused', 'calm', 'tired', 'anxious'
    Time windows: 'early_morning', 'morning', 'midday', 'afternoon', 'evening', 'night'
    """
    id: str
    mood: str
    energy: int                                            # 1-10 (inferred)
    time_window: str = ""
    hour: int = 0
    source: str = "inferred"                               # 'inferred' or 'explicit'
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mood": self.mood,
            "energy": self.energy,
            "time_window": self.time_window,
            "hour": self.hour,
            "source": self.source,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowzenCheckin":
        def parse_dt(v):
            return datetime.fromisoformat(v) if isinstance(v, str) else v

        return cls(
            id=data["id"],
            mood=data["mood"],
            energy=data.get("energy", 5),
            time_window=data.get("time_window", ""),
            hour=data.get("hour", 0),
            source=data.get("source", "inferred"),
            notes=data.get("notes", ""),
            created_at=parse_dt(data.get("created_at")) or datetime.now(),
        )


@dataclass
class FlowzenActivity:
    """
    A logged intent event observed by the Blaue Rose activity tracker.

    Used to detect inactivity gaps and infer mood from usage patterns.
    """
    id: str
    event_type: str                                        # e.g. "idea.create"
    time_window: str = ""
    hour: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "time_window": self.time_window,
            "hour": self.hour,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowzenActivity":
        def parse_dt(v):
            return datetime.fromisoformat(v) if isinstance(v, str) else v

        return cls(
            id=data["id"],
            event_type=data.get("event_type", ""),
            time_window=data.get("time_window", ""),
            hour=data.get("hour", 0),
            created_at=parse_dt(data.get("created_at")) or datetime.now(),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python && python -m pytest tests/test_flowzen_models.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add python/data/models.py python/tests/test_flowzen_models.py
git commit -m "feat(flowzen): add FlowzenCheckin and FlowzenActivity data models"
```

---

### Task 2: Database — Migration & Repository

**Files:**
- Modify: `python/data/database.py` (line 30: bump version, add migration block)
- Create: `python/data/flowzen_repository.py` (own file, following schedule_repository.py pattern)
- Modify: `python/data/repository.py` (add re-export line)
- Modify: `python/data/__init__.py` (add FlowzenCheckin, FlowzenActivity, FlowzenRepository)

- [ ] **Step 1: Write the failing test**

Create `python/tests/test_flowzen_repository.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && python -m pytest tests/test_flowzen_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'FlowzenRepository'`

- [ ] **Step 3: Add migration v18 to database.py**

In `python/data/database.py`:

1. Change line 30: `SCHEMA_VERSION = 18`
2. Add to `SCHEMA_SQL` string (after existing tables):

```sql
    -- Flowzen: mood/energy state (inferred by activity tracker)
    CREATE TABLE IF NOT EXISTS flowzen_checkins (
        id           TEXT PRIMARY KEY,
        mood         TEXT NOT NULL,
        energy       INTEGER NOT NULL DEFAULT 5,
        time_window  TEXT DEFAULT '',
        hour         INTEGER DEFAULT 0,
        source       TEXT DEFAULT 'inferred',
        notes        TEXT DEFAULT '',
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Flowzen: observed intent activity log
    CREATE TABLE IF NOT EXISTS flowzen_activity (
        id           TEXT PRIMARY KEY,
        event_type   TEXT NOT NULL,
        time_window  TEXT DEFAULT '',
        hour         INTEGER DEFAULT 0,
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_flowzen_checkins_created ON flowzen_checkins(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_flowzen_activity_created ON flowzen_activity(created_at DESC);
```

3. Add migration block in `_migrate()` method (after the `if from_version < 17:` block):

```python
        if from_version < 18:
            logger.info("Migration v18: Flowzen circadian tables")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flowzen_checkins (
                    id           TEXT PRIMARY KEY,
                    mood         TEXT NOT NULL,
                    energy       INTEGER NOT NULL DEFAULT 5,
                    time_window  TEXT DEFAULT '',
                    hour         INTEGER DEFAULT 0,
                    source       TEXT DEFAULT 'inferred',
                    notes        TEXT DEFAULT '',
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flowzen_activity (
                    id           TEXT PRIMARY KEY,
                    event_type   TEXT NOT NULL,
                    time_window  TEXT DEFAULT '',
                    hour         INTEGER DEFAULT 0,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_flowzen_checkins_created ON flowzen_checkins(created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_flowzen_activity_created ON flowzen_activity(created_at DESC)")
```

- [ ] **Step 4: Create FlowzenRepository as own file**

Create `python/data/flowzen_repository.py` (following `schedule_repository.py` pattern — uses `self.db.execute()`, `self.db.fetch_one()`, `self.db.fetch_all()`):

```python
"""Flowzen Repository — CRUD for circadian activity tracking tables."""

import logging
from datetime import datetime
from typing import Optional, List

from .database import Database, get_database
from .models import FlowzenCheckin, FlowzenActivity
from .repository_utils import generate_id

logger = logging.getLogger(__name__)


class FlowzenRepository:
    """Repository for Flowzen activity tracking and circadian state."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    # -- Checkins (inferred mood state) --

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
            "INSERT INTO flowzen_checkins (id, mood, energy, time_window, hour, source, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (checkin.id, checkin.mood, checkin.energy, checkin.time_window,
             checkin.hour, checkin.source, checkin.notes),
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

    # -- Activity log (observed intents) --

    def log_activity(self, event_type: str, hour: int = None) -> FlowzenActivity:
        if hour is None:
            hour = datetime.now().hour

        activity = FlowzenActivity(
            id=generate_id(), event_type=event_type,
            time_window=self._hour_to_window(hour), hour=hour,
        )
        self.db.execute(
            "INSERT INTO flowzen_activity (id, event_type, time_window, hour) VALUES (?, ?, ?, ?)",
            (activity.id, activity.event_type, activity.time_window, activity.hour),
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
```

- [ ] **Step 5: Add re-export to repository.py**

In `python/data/repository.py`, add import line:

```python
from .flowzen_repository import FlowzenRepository
```

And add `"FlowzenRepository"` to the `__all__` list.

- [ ] **Step 6: Update data/__init__.py**

In `python/data/__init__.py`:

Add to imports from `.models`:
```python
    FlowzenCheckin, FlowzenActivity,
```

Add to imports from `.repository`:
```python
    FlowzenRepository,
```

Add to `__all__`:
```python
    "FlowzenCheckin",
    "FlowzenActivity",
    "FlowzenRepository",
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd python && python -m pytest tests/test_flowzen_repository.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 8: Commit**

```bash
git add python/data/database.py python/data/flowzen_repository.py python/data/repository.py python/data/__init__.py python/tests/test_flowzen_repository.py
git commit -m "feat(flowzen): DB migration v18, FlowzenRepository with activity tracking"
```

---

### Task 3: Activity Tracker (Core Brain)

The activity tracker is the heart of the Blaue Rose — it passively receives all intent events, logs them, detects inactivity, and sends signals to Brain/Tahlamus.

**Files:**
- Create: `python/spaces/flowzen/__init__.py`
- Create: `python/spaces/flowzen/config.py`
- Create: `python/spaces/flowzen/activity_tracker.py`

- [ ] **Step 1: Write the failing test**

Create `python/tests/test_flowzen_tracker.py`:

```python
"""Tests for Flowzen ActivityTracker — passive broadcast listener."""
import time
from unittest.mock import patch, MagicMock
import os
import tempfile

from data.database import Database


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
            tracker = ActivityTracker(inactivity_threshold_minutes=5)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && python -m pytest tests/test_flowzen_tracker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'spaces.flowzen'`

- [ ] **Step 3: Create directory structure and config**

`python/spaces/flowzen/__init__.py`:

```python
"""Flowzen (Blaue Rose) — Passive circadian intelligence layer."""
```

`python/spaces/flowzen/config.py`:

```python
"""Flowzen configuration."""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class FlowzenConfig:
    """Configuration for the Blaue Rose activity tracker."""
    enabled: bool = False
    summary_interval_minutes: int = 30   # how often to send summary to Brain
    default_mood: str = "calm"

    @classmethod
    def from_env(cls) -> "FlowzenConfig":
        return cls(
            enabled=os.getenv("FLOWZEN_ENABLED", "false").lower() == "true",
            summary_interval_minutes=int(os.getenv("FLOWZEN_SUMMARY_INTERVAL", "30")),
            default_mood=os.getenv("FLOWZEN_DEFAULT_MOOD", "calm"),
        )


_config: Optional[FlowzenConfig] = None


def get_config() -> FlowzenConfig:
    global _config
    if _config is None:
        _config = FlowzenConfig.from_env()
    return _config
```

- [ ] **Step 4: Implement ActivityTracker**

Create `python/spaces/flowzen/activity_tracker.py`:

```python
"""
Flowzen Activity Tracker — Passive broadcast listener (Blaue Rose).

Receives ALL intents via broadcast, logs activity, detects inactivity,
and sends signals to Brain/Tahlamus. Never asks the user anything.

Usage:
    tracker = get_activity_tracker()
    tracker.on_intent(event_type, payload)  # Called from IntentOrchestrator
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# ===================================================================
# Circadian Matrix (Flowzen Core)
# ===================================================================
# Mood x Time-of-Day -> recommended task category
#
# Based on circadian cortisol curves and prefrontal cortex research:
# - Cortisol peaks 06:00-09:00 -> best for deep analytical work
# - Post-lunch dip 13:00-15:00 -> admin/routine tasks
# - Late afternoon -> creative/divergent thinking
# - Evening -> social/light work, then rest

CIRCADIAN_MATRIX: Dict[str, Dict[str, str]] = {
    "energized": {
        "early_morning": "deep_work",
        "morning": "deep_work",
        "midday": "deep_work",
        "afternoon": "creative",
        "evening": "social",
        "night": "rest",
    },
    "focused": {
        "early_morning": "deep_work",
        "morning": "deep_work",
        "midday": "deep_work",
        "afternoon": "deep_work",
        "evening": "admin",
        "night": "rest",
    },
    "calm": {
        "early_morning": "creative",
        "morning": "creative",
        "midday": "admin",
        "afternoon": "creative",
        "evening": "rest",
        "night": "rest",
    },
    "tired": {
        "early_morning": "rest",
        "morning": "admin",
        "midday": "rest",
        "afternoon": "admin",
        "evening": "rest",
        "night": "rest",
    },
    "anxious": {
        "early_morning": "admin",
        "morning": "admin",
        "midday": "admin",
        "afternoon": "admin",
        "evening": "rest",
        "night": "rest",
    },
}

CATEGORY_DESCRIPTIONS = {
    "deep_work": "Analytische Tiefenarbeit",
    "creative": "Kreatives Denken",
    "admin": "Verwaltung & Organisation",
    "social": "Kommunikation",
    "rest": "Pause empfohlen",
}

# --- LLM Reasoning Generator (replaces static templates) ---

REASONING_SYSTEM_PROMPT = """Du bist ein Neurowissenschafts-Berater im VibeMind System (Blaue Rose).
Deine Aufgabe: Generiere eine kurze (2-3 Saetze), wissenschaftlich fundierte Erklaerung
warum eine bestimmte Aufgabenkategorie JETZT optimal ist.

Beziehe dich auf:
- Zirkadiane Cortisol-Kurven und praefrontale Cortex-Funktion
- Ultradian Rhythms (90-Minuten Zyklen)
- Kognitive Ermuedung und Aufmerksamkeitsressourcen
- Default Mode Network vs Task-Positive Network
- Dopamin- und Serotonin-Regulation

Sprich den User direkt an (du-Form). Sei warm aber praezise.
Keine Floskeln, keine Wiederholungen. Jede Antwort soll einzigartig sein."""

REASONING_USER_TEMPLATE = """Situation:
- Stimmung: {mood}
- Tageszeit: {time_window} ({hour}:00 Uhr)
- Empfohlene Kategorie: {category} ({category_description})
- Aktivitaet letzte 30 Min: {activity_summary}

Generiere eine neurowissenschaftliche Empfehlung (2-3 Saetze, deutsch)."""


async def generate_reasoning(
    mood: str, time_window: str, hour: int, category: str,
    activity_summary: str = "",
) -> str:
    """Generate neuroscience-backed reasoning via LLM (GPT 5.4 or configured model)."""
    try:
        from llm_config import get_model, get_async_client

        client = get_async_client()
        model = get_model("flowzen_reasoning")  # falls in llm_models.yml konfiguriert

        user_msg = REASONING_USER_TEMPLATE.format(
            mood=mood,
            time_window=time_window,
            hour=hour,
            category=category,
            category_description=CATEGORY_DESCRIPTIONS.get(category, category),
            activity_summary=activity_summary or "keine Daten",
        )

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": REASONING_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=200,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.warning(f"Flowzen: LLM reasoning failed: {e}")
        # Minimal fallback — no static templates, just category name
        return f"Empfohlene Kategorie: {CATEGORY_DESCRIPTIONS.get(category, category)}."


def get_time_window(hour: int = None) -> str:
    """Map wall-clock hour to circadian time window."""
    if hour is None:
        hour = datetime.now().hour
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


def get_circadian_category(mood: str, time_window: str) -> str:
    """Look up the recommended task category from the circadian matrix."""
    mood_row = CIRCADIAN_MATRIX.get(mood)
    if not mood_row:
        return "admin"
    return mood_row.get(time_window, "admin")


class ActivityTracker:
    """
    Passive broadcast listener for the Blaue Rose.

    - Receives copies of ALL intents (called from IntentOrchestrator)
    - Logs activity to flowzen_activity table
    - Every 30 minutes: builds a situation summary and sends it to Brain/Tahlamus
    - Brain decides whether to act (suggest task, suggest rest, or do nothing)
    - Never asks the user anything directly
    """

    def __init__(self, summary_interval_minutes: int = 30):
        self._interval = timedelta(minutes=summary_interval_minutes)
        self._last_activity: Optional[datetime] = None
        self._last_summary_sent: Optional[datetime] = None
        self._intent_buffer: list = []  # buffered event_types since last summary
        self._brain_callback: Optional[Callable] = None
        self._electron_sender: Optional[Callable[[dict], None]] = None
        self._lock = threading.Lock()

    def set_brain_callback(self, callback: Callable):
        """Set callback to send periodic summaries to Brain/Tahlamus."""
        self._brain_callback = callback

    def set_electron_sender(self, sender: Callable[[dict], None]):
        """Set Electron IPC sender for 3D rose state updates."""
        self._electron_sender = sender

    def on_intent(self, event_type: str, payload: Dict[str, Any] = None):
        """
        Called for EVERY intent passing through the orchestrator.

        Logs activity, buffers event type for next summary.
        This method must be fast — it runs in the intent hot path.
        """
        now = datetime.now()

        with self._lock:
            self._last_activity = now
            self._intent_buffer.append(event_type)

        # Log to DB (fire-and-forget, don't block intent processing)
        try:
            from data.flowzen_repository import FlowzenRepository
            repo = FlowzenRepository()
            repo.log_activity(event_type=event_type, hour=now.hour)
        except Exception as e:
            logger.debug(f"Flowzen: activity log failed: {e}")

        # Update rose visual state -> active (soft glow)
        self._broadcast_rose_state("active", event_type=event_type)

    def send_periodic_summary(self):
        """
        Called every 30 minutes by a background timer (e.g. threading.Timer or APScheduler).

        Builds a situation summary, generates LLM reasoning, and sends to Brain/Tahlamus.
        Brain decides what to do — Rose never acts on its own.
        """
        import asyncio

        now = datetime.now()

        # Don't send if interval hasn't elapsed
        if self._last_summary_sent:
            elapsed = now - self._last_summary_sent
            if elapsed < self._interval:
                return

        summary = self._build_summary()

        # Generate LLM reasoning for the summary
        try:
            # Pick most likely mood from recent checkins or default
            from data.flowzen_repository import FlowzenRepository
            repo = FlowzenRepository()
            recent = repo.get_recent_checkins(limit=1)
            mood = recent[0].mood if recent else "calm"

            activity_str = ", ".join(
                f"{et}:{count}" for et, count in summary["event_types"].items()
            ) or "keine Aktivitaet"

            reasoning = asyncio.run(generate_reasoning(
                mood=mood,
                time_window=summary["time_window"],
                hour=summary["hour"],
                category=get_circadian_category(mood, summary["time_window"]),
                activity_summary=activity_str,
            ))
            summary["llm_reasoning"] = reasoning
        except Exception as e:
            logger.debug(f"Flowzen: LLM reasoning for summary failed: {e}")

        with self._lock:
            self._last_summary_sent = now
            self._intent_buffer.clear()

        # Send summary to Brain — Brain decides what to do
        if self._brain_callback:
            try:
                self._brain_callback(summary)
                logger.info(
                    f"Flowzen: periodic summary sent to Brain "
                    f"({summary['intent_count']} intents, {summary['time_window']})"
                )
            except Exception as e:
                logger.warning(f"Flowzen: Brain callback failed: {e}")

    def _build_summary(self) -> Dict[str, Any]:
        """Build a situation summary from buffered observations."""
        now = datetime.now()
        time_window = get_time_window(now.hour)

        with self._lock:
            buffer_copy = list(self._intent_buffer)

        # Count event types
        event_counts: Dict[str, int] = {}
        for et in buffer_copy:
            event_counts[et] = event_counts.get(et, 0) + 1

        return {
            "type": "flowzen_periodic_summary",
            "time_window": time_window,
            "hour": now.hour,
            "intent_count": len(buffer_copy),
            "event_types": event_counts,
            "minutes_since_last_activity": self._minutes_since_last_activity(),
            "circadian_matrix": {
                mood: get_circadian_category(mood, time_window)
                for mood in CIRCADIAN_MATRIX
            },
        }

    def on_brain_response(self, decision: Dict[str, Any]):
        """
        Called when Brain/Tahlamus responds to a periodic summary.

        Brain sends: {"action": "suggest_task"|"suggest_rest"|"do_nothing", ...}
        """
        action = decision.get("action", "do_nothing")

        if action == "suggest_task":
            self._broadcast_rose_state("recommending",
                                       category=decision.get("category", ""),
                                       reasoning=decision.get("reasoning", ""))
        elif action == "suggest_rest":
            self._broadcast_rose_state("rest")
        else:
            self._broadcast_rose_state("idle")

    def _minutes_since_last_activity(self) -> int:
        if self._last_activity is None:
            return -1
        return int((datetime.now() - self._last_activity).total_seconds() / 60)

    def _broadcast_rose_state(self, state: str, **extra):
        """Send rose visual state to Electron 3D renderer."""
        if self._electron_sender:
            msg = {"type": "flowzen_rose_state", "state": state, **extra}
            self._electron_sender(msg)

    def get_status(self) -> Dict[str, Any]:
        """Return current tracker status (for rose.status tool)."""
        now = datetime.now()
        time_window = get_time_window(now.hour)

        with self._lock:
            buffered = len(self._intent_buffer)

        return {
            "active": True,
            "current_time_window": time_window,
            "current_hour": now.hour,
            "last_activity": self._last_activity.isoformat() if self._last_activity else None,
            "minutes_since_activity": self._minutes_since_last_activity(),
            "summary_interval_minutes": int(self._interval.total_seconds() / 60),
            "intents_buffered": buffered,
            "last_summary_sent": self._last_summary_sent.isoformat() if self._last_summary_sent else None,
        }


# Singleton
_tracker: Optional[ActivityTracker] = None


def get_activity_tracker() -> ActivityTracker:
    global _tracker
    if _tracker is None:
        from spaces.flowzen.config import get_config
        cfg = get_config()
        _tracker = ActivityTracker(
            summary_interval_minutes=cfg.summary_interval_minutes,
        )
    return _tracker
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd python && python -m pytest tests/test_flowzen_tracker.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 6: Commit**

```bash
git add python/spaces/flowzen/ python/tests/test_flowzen_tracker.py
git commit -m "feat(flowzen): ActivityTracker — passive broadcast listener with Brain signaling"
```

---

### Task 4: Tools & Agent (Minimal — only rose.recommend + rose.status)

**Files:**
- Create: `python/spaces/flowzen/tools/__init__.py`
- Create: `python/spaces/flowzen/tools/flowzen_tools.py`
- Create: `python/spaces/flowzen/agents/__init__.py`
- Create: `python/spaces/flowzen/agents/flowzen_agent.py`

- [ ] **Step 1: Write the failing test**

Create `python/tests/test_flowzen_agent.py`:

```python
"""Tests for FlowzenAgent — minimal agent with only 2 explicit tools."""
from spaces.flowzen.agents.flowzen_agent import FlowzenAgent


def test_event_to_tool_mapping():
    agent = FlowzenAgent()
    assert agent._get_tool_name("rose.recommend") == "recommend_task"
    assert agent._get_tool_name("rose.status") == "get_flowzen_status"


def test_only_two_events():
    """Rose should only handle explicit queries, not be a general router."""
    agent = FlowzenAgent()
    assert agent._get_tool_name("rose.mood") is None  # mood is inferred, not commanded
    assert agent._get_tool_name("rose.history") is None  # removed


def test_tools_load():
    agent = FlowzenAgent()
    tools = agent._load_tools()
    assert "recommend_task" in tools
    assert "get_flowzen_status" in tools
    assert len(tools) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python && python -m pytest tests/test_flowzen_agent.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement tools**

`python/spaces/flowzen/tools/__init__.py`:

```python
"""Flowzen tools."""
from spaces.flowzen.tools.flowzen_tools import recommend_task, get_flowzen_status

__all__ = ["recommend_task", "get_flowzen_status"]
```

`python/spaces/flowzen/tools/flowzen_tools.py`:

```python
"""
Flowzen Tools — Only 2 explicit tools (passive space).

Events:
    rose.recommend  -> recommend_task()   # User asks "Was soll ich machen?"
    rose.status     -> get_flowzen_status()  # "Blaue Rose Status"

All other intelligence is handled passively by ActivityTracker.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

_electron_send_message: Optional[Callable[[dict], None]] = None


def set_electron_sender(sender: Callable[[dict], None]):
    global _electron_send_message
    _electron_send_message = sender


def _broadcast_to_electron(message: dict):
    if _electron_send_message:
        _electron_send_message(message)


def recommend_task(mood: str = "", **kwargs) -> Dict[str, Any]:
    """
    Generate a circadian-aware task recommendation with LLM reasoning.

    Only triggered when user explicitly asks "Was soll ich machen?"
    Uses circadian matrix for category + LLM (GPT 5.4) for reasoning.
    """
    import asyncio
    from data import IdeasRepository
    from data.flowzen_repository import FlowzenRepository
    from spaces.flowzen.activity_tracker import (
        get_circadian_category, get_time_window, get_activity_tracker,
        CATEGORY_DESCRIPTIONS, generate_reasoning,
    )

    repo = FlowzenRepository()
    ideas_repo = IdeasRepository()
    now = datetime.now()
    hour = now.hour
    time_window = get_time_window(hour)

    # Mood: use last inferred checkin, or default
    if not mood:
        recent = repo.get_recent_checkins(limit=1)
        if recent:
            mood = recent[0].mood
        else:
            from spaces.flowzen.config import get_config
            mood = get_config().default_mood

    category = get_circadian_category(mood, time_window)

    # Build activity summary from tracker buffer
    tracker = get_activity_tracker()
    status = tracker.get_status()
    activity_summary = f"{status['intents_buffered']} Intents in letzten 30 Min"

    # Generate LLM reasoning (async -> sync bridge)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                reasoning = pool.submit(
                    asyncio.run,
                    generate_reasoning(mood, time_window, hour, category, activity_summary)
                ).result(timeout=10)
        else:
            reasoning = asyncio.run(
                generate_reasoning(mood, time_window, hour, category, activity_summary)
            )
    except Exception as e:
        logger.warning(f"Flowzen: reasoning generation failed: {e}")
        reasoning = f"Empfohlene Kategorie: {CATEGORY_DESCRIPTIONS.get(category, category)}."

    # Find a matching idea
    all_ideas = ideas_repo.get_all()
    idea = _pick_best_idea(all_ideas, category)

    if idea:
        title = idea.get("title", "")
        hint = f"{reasoning} Ich empfehle dir: '{title}'."
    elif category == "rest":
        title = ""
        hint = reasoning
    else:
        title = ""
        hint = f"{reasoning} Moechtest du eine neue Aufgabe erstellen?"

    _broadcast_to_electron({
        "type": "flowzen_rose_state", "state": "recommending",
        "category": category, "idea_title": title,
    })

    return {
        "success": True,
        "message": f"Flowzen: {category} recommended ({mood}/{time_window})",
        "response_hint": hint,
        "recommendation": {
            "category": category,
            "mood": mood,
            "time_window": time_window,
            "reasoning": reasoning,
            "idea_title": title,
            "idea_id": idea.get("id", "") if idea else "",
        },
    }


def _pick_best_idea(ideas: list, category: str) -> Optional[Dict[str, Any]]:
    """Pick highest-scored child idea. Future: use Brain cognitive signal."""
    if not ideas:
        return None
    candidates = [i for i in ideas if i.get("parent_id")]
    if not candidates:
        candidates = ideas
    candidates.sort(key=lambda i: i.get("score", 0), reverse=True)
    return candidates[0] if candidates else None


def get_flowzen_status(**kwargs) -> Dict[str, Any]:
    """Get Blaue Rose status — tracker state + circadian info."""
    from spaces.flowzen.activity_tracker import get_activity_tracker

    tracker = get_activity_tracker()
    status = tracker.get_status()

    return {
        "success": True,
        "message": "Flowzen status OK",
        "response_hint": (
            f"Blaue Rose aktiv. Tageszeit: {status['current_time_window']} "
            f"({status['current_hour']}:00). "
            f"Letzte Aktivitaet vor {status['minutes_since_activity']} Minuten."
        ),
        "status": status,
    }
```

- [ ] **Step 4: Implement agent**

`python/spaces/flowzen/agents/__init__.py`:

```python
"""Flowzen agents."""
from spaces.flowzen.agents.flowzen_agent import FlowzenAgent, get_flowzen_agent

__all__ = ["FlowzenAgent", "get_flowzen_agent"]
```

`python/spaces/flowzen/agents/flowzen_agent.py`:

```python
"""
Flowzen Backend Agent (Blaue Rose) — Minimal agent.

Only handles 2 explicit events:
- rose.recommend: User asks "Was soll ich machen?"
- rose.status: "Blaue Rose Status"

All other intelligence runs passively via ActivityTracker.
"""

import logging
from typing import Dict, Callable, Optional

from swarm.backend_agents.base_agent import BaseBackendAgent

logger = logging.getLogger(__name__)


class FlowzenAgent(BaseBackendAgent):
    """Minimal backend agent for explicit Blaue Rose queries."""

    EVENT_TO_TOOL: Dict[str, str] = {
        "rose.recommend": "recommend_task",
        "rose.status":    "get_flowzen_status",
    }

    PARAM_MAPPING: Dict[str, Dict[str, str]] = {
        "rose.recommend": {
            "stimmung": "mood",
        },
    }

    @property
    def name(self) -> str:
        return "FlowzenAgent"

    @property
    def stream(self) -> str:
        return "events:tasks:flowzen"

    def _load_tools(self) -> Dict[str, Callable]:
        tools = {}
        try:
            from spaces.flowzen.tools.flowzen_tools import (
                recommend_task,
                get_flowzen_status,
            )
            tools.update({
                "recommend_task": recommend_task,
                "get_flowzen_status": get_flowzen_status,
            })
            logger.info(f"{self.name}: Loaded {len(tools)} tools")
        except ImportError as e:
            logger.warning(f"{self.name}: Could not load tools: {e}")
        return tools

    def _get_tool_name(self, event_type: str) -> Optional[str]:
        return self.EVENT_TO_TOOL.get(event_type)


_flowzen_agent: Optional[FlowzenAgent] = None


def get_flowzen_agent() -> FlowzenAgent:
    global _flowzen_agent
    if _flowzen_agent is None:
        _flowzen_agent = FlowzenAgent()
    return _flowzen_agent


__all__ = ["FlowzenAgent", "get_flowzen_agent"]
```

- [ ] **Step 5: Run tests**

Run: `cd python && python -m pytest tests/test_flowzen_agent.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 6: Commit**

```bash
git add python/spaces/flowzen/tools/ python/spaces/flowzen/agents/
git commit -m "feat(flowzen): minimal agent with 2 tools (recommend + status)"
```

---

### Task 5: Routing Registration (Minimal — only 2 events)

**Files:**
- Modify: `python/swarm/event_team/event_router.py`
- Modify: `python/swarm/backend_agents/__init__.py`
- Modify: `python/swarm/orchestrator/intent_classifier.py`
- Modify: `python/spaces/minibook/enrichment/space_router.py`
- Create: `python/plugins/builtin/flowzen/plugin.json`

**NOTE:** No entry in `collaboration_tools.py` SPACE_AGENT_REGISTRY — Rose is not a collaboration participant. It observes silently.

- [ ] **Step 1: Add stream constant and mappings to event_router.py**

After line 45 (`STREAM_TASKS_AGENTFARM`), add:

```python
    STREAM_TASKS_FLOWZEN = "events:tasks:flowzen"
```

In `STREAM_MAPPING`, after the video block (after line 211), add:

```python
        # Flowzen (Blaue Rose) — only explicit user queries
        "rose.recommend": STREAM_TASKS_FLOWZEN,
        "rose.status": STREAM_TASKS_FLOWZEN,
```

In `get_category()` (line 288-325), add before the `else` branch:

```python
        elif stream == self.STREAM_TASKS_FLOWZEN:
            return "flowzen"
```

In `all_streams()` (line 328-345), add:

```python
            cls.STREAM_TASKS_FLOWZEN,
```

- [ ] **Step 2: Add getter to backend_agents/__init__.py**

After `get_agentfarm_agent` (after line 138), add:

```python
def get_flowzen_agent():
    """Get FlowzenAgent singleton (lazy import)."""
    agent = get_agent("flowzen")
    if agent:
        return agent
    from spaces.flowzen.agents.flowzen_agent import get_flowzen_agent as _get
    return _get()
```

In `__getattr__`, before `raise AttributeError`:

```python
    elif name == "FlowzenAgent":
        from spaces.flowzen.agents.flowzen_agent import FlowzenAgent
        return FlowzenAgent
```

In `__all__`, add `"FlowzenAgent"` and `"get_flowzen_agent"`.

- [ ] **Step 3: Add MINIMAL section to intent_classifier.py**

After the AgentFarm section (after line ~451), add:

```
### 10. BLAUE ROSE (Aufgaben-Empfehlung)
NUR fuer explizite Empfehlungs-Anfragen. Die Blaue Rose beobachtet passiv — der User muss aktiv fragen.

**Schluesselwoerter:** was soll ich, empfiehl, vorschlag, blaue rose, flowzen

**Event-Types:**
- rose.recommend: Aufgabe basierend auf Tageszeit empfehlen (NUR wenn User EXPLIZIT fragt!)
  → "Was soll ich jetzt machen?", "Empfiehl mir eine Aufgabe"
  → "Was passt gerade am besten?", "Blaue Rose"
  → "Gib mir einen Vorschlag", "Was waere jetzt sinnvoll?"
  → payload: {"mood": "..."} (optional)
- rose.status: Blaue Rose Status
  → "Blaue Rose Status", "Flowzen Status"

### WICHTIGE UNTERSCHEIDUNG - BLAUE ROSE vs ANDERE
- rose.recommend: User fragt EXPLIZIT nach Empfehlung → "Was soll ich machen?"
- schedule.list: Zeigt geplante Termine → "Was steht an?" (NICHT rose!)
- idea.list: Zeigt vorhandene Ideen → "Zeig meine Ideen" (NICHT rose!)
- conversation.greeting: Begruessung → "Hallo" (NICHT rose!)
- conversation.help: Hilfe → "Was kannst du?" (NICHT rose!)
NUR wenn der User eine EMPFEHLUNG oder VORSCHLAG will → rose.recommend
```

- [ ] **Step 4: Add prefix to space_router.py**

In `EVENT_TYPE_TO_SPACE` dict (after line 53):

```python
    "rose.": "flowzen",
```

- [ ] **Step 5: Create plugin manifest**

Create `python/plugins/builtin/flowzen/plugin.json`:

```json
{
  "id": "flowzen",
  "version": "1.0.0",
  "name": "Flowzen (Blaue Rose)",
  "description": "Passive circadian intelligence — observes activity, signals Brain on inactivity",
  "author": "VibeMind Team",
  "category": "productivity",
  "changelog": "Initial release — passive activity tracker with Beauty-and-the-Beast rose UI",

  "agent_module": "spaces.flowzen.agents.flowzen_agent",
  "agent_class": "FlowzenAgent",
  "agent_factory": "get_flowzen_agent",

  "stream": "events:tasks:flowzen",
  "event_routes": {
    "rose.recommend": "events:tasks:flowzen",
    "rose.status": "events:tasks:flowzen"
  },

  "classifier_hints": {
    "keywords_de": ["empfehlung", "vorschlag", "blaue rose", "flowzen", "was soll ich"],
    "keywords_en": ["recommendation", "suggest", "blue rose", "what should I do"],
    "example_utterances": [
      {"text": "Was soll ich jetzt machen?", "event_type": "rose.recommend"},
      {"text": "Blaue Rose Status", "event_type": "rose.status"}
    ]
  },

  "builtin": true,
  "env_flag": "FLOWZEN_ENABLED",
  "dependencies": []
}
```

- [ ] **Step 6: Verify routing**

Run: `cd python && python -c "from swarm.event_team.event_router import EventRouter; er = EventRouter(); print(er.get_stream('rose.recommend'))"`
Expected: `events:tasks:flowzen`

- [ ] **Step 7: Commit**

```bash
git add python/swarm/event_team/event_router.py \
        python/swarm/backend_agents/__init__.py \
        python/swarm/orchestrator/intent_classifier.py \
        python/spaces/minibook/enrichment/space_router.py \
        python/plugins/builtin/flowzen/plugin.json
git commit -m "feat(flowzen): register Blaue Rose in routing (2 events only)"
```

---

### Task 6: Wire ActivityTracker into IntentOrchestrator

The tracker needs to receive ALL intents. This is a one-line hook in the orchestrator.

**Files:**
- Modify: `python/swarm/orchestrator/intent_orchestrator.py`

- [ ] **Step 1: Find the intent processing point**

Read `python/swarm/orchestrator/intent_orchestrator.py` and find where intents are dispatched after classification. Look for the method that calls the event router or tool executor.

- [ ] **Step 2: Add broadcast hook**

At the point where `event_type` and `payload` are known (after classification, before routing), add:

```python
        # Broadcast to Blaue Rose activity tracker (passive, fire-and-forget)
        try:
            from spaces.flowzen.activity_tracker import get_activity_tracker
            get_activity_tracker().on_intent(event_type, payload)
        except Exception:
            pass  # Never block intent processing for tracking
```

- [ ] **Step 3: Verify tracker receives events**

Run: `cd python && python -c "
from spaces.flowzen.activity_tracker import get_activity_tracker
t = get_activity_tracker()
t.on_intent('idea.create', {'title': 'Test'})
print(t.get_status())
"`
Expected: Shows `minutes_since_activity: 0`

- [ ] **Step 4: Commit**

```bash
git add python/swarm/orchestrator/intent_orchestrator.py
git commit -m "feat(flowzen): wire ActivityTracker into IntentOrchestrator broadcast"
```

---

### Task 7: Integration Test

**Files:**
- Create: `python/tests/test_flowzen_integration.py`

- [ ] **Step 1: Write integration test**

```python
"""Integration test: Flowzen passive intelligence layer."""
import os
import tempfile
from unittest.mock import patch, MagicMock

from data.database import Database
from spaces.flowzen.activity_tracker import (
    ActivityTracker, get_circadian_category, get_time_window, CIRCADIAN_MATRIX,
)
from spaces.flowzen.agents.flowzen_agent import FlowzenAgent


def _temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    db.initialize()
    return db, path


def test_passive_observation_cycle():
    """Tracker receives intents, buffers them, status reflects activity."""
    db, path = _temp_db()
    try:
        with patch("data.flowzen_repository.get_database", return_value=db):
            tracker = ActivityTracker(summary_interval_minutes=30)

            # No activity yet
            status = tracker.get_status()
            assert status["intents_buffered"] == 0

            # After intents, buffer fills
            tracker.on_intent("idea.create", {"title": "Test"})
            tracker.on_intent("code.generate", {})
            status = tracker.get_status()
            assert status["intents_buffered"] == 2
            assert status["minutes_since_activity"] == 0
    finally:
        os.unlink(path)


def test_periodic_summary_signals_brain():
    """Every 30 min, tracker sends aggregated summary to Brain."""
    db, path = _temp_db()
    try:
        with patch("data.flowzen_repository.get_database", return_value=db):
            brain_mock = MagicMock()
            # interval=0 so summary fires immediately
            tracker = ActivityTracker(summary_interval_minutes=0)
            tracker.set_brain_callback(brain_mock)

            tracker.on_intent("idea.create", {})
            tracker.on_intent("idea.create", {})
            tracker.on_intent("code.generate", {})

            tracker.send_periodic_summary()

            brain_mock.assert_called_once()
            summary = brain_mock.call_args[0][0]
            assert summary["type"] == "flowzen_periodic_summary"
            assert summary["intent_count"] == 3
            assert summary["event_types"]["idea.create"] == 2
            assert "circadian_matrix" in summary
    finally:
        os.unlink(path)


def test_brain_response_updates_rose_state():
    """Brain response should update rose visual state."""
    electron_mock = MagicMock()
    tracker = ActivityTracker()
    tracker.set_electron_sender(electron_mock)

    tracker.on_brain_response({"action": "suggest_rest"})
    electron_mock.assert_called_with({"type": "flowzen_rose_state", "state": "rest"})


def test_agent_has_only_two_tools():
    """FlowzenAgent should only expose recommend + status."""
    agent = FlowzenAgent()
    tools = agent._load_tools()
    assert set(tools.keys()) == {"recommend_task", "get_flowzen_status"}


def test_circadian_consistency():
    """Matrix should always return valid categories."""
    valid_cats = {"deep_work", "creative", "admin", "social", "rest"}
    for hour in range(24):
        window = get_time_window(hour)
        for mood in CIRCADIAN_MATRIX:
            cat = get_circadian_category(mood, window)
            assert cat in valid_cats, f"Invalid '{cat}' for {mood}/{window}"
```

- [ ] **Step 2: Run all Flowzen tests**

Run: `cd python && python -m pytest tests/test_flowzen_*.py -v`
Expected: PASS (all ~15 tests)

- [ ] **Step 3: Commit**

```bash
git add python/tests/test_flowzen_integration.py
git commit -m "test(flowzen): integration tests for passive intelligence layer"
```

---

### Task 8: Configuration & .env

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add env variables**

Add after the SCHEDULE section:

```bash
# Flowzen (Blaue Rose) — Passive circadian intelligence
FLOWZEN_ENABLED=false
FLOWZEN_SUMMARY_INTERVAL=30     # Minutes between Brain summaries
FLOWZEN_DEFAULT_MOOD=calm
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "feat(flowzen): add FLOWZEN_ENABLED to .env.example"
```

---

## Summary

| Task | Files | Tests | What it does |
| ---- | ----- | ----- | ------------ |
| 1 | models.py | 4 | FlowzenCheckin + FlowzenActivity dataclasses |
| 2 | database.py, flowzen_repository.py, repository.py, __init__.py | 4 | Migration v18, FlowzenRepository CRUD |
| 3 | activity_tracker.py, config.py | 4 | Core: passive broadcast listener + Brain signaling |
| 4 | flowzen_tools.py, flowzen_agent.py | 3 | Minimal agent: only recommend + status |
| 5 | 5 routing files + plugin.json | 1 verify | Register in routing (2 events only) |
| 6 | intent_orchestrator.py | 1 verify | Wire tracker into broadcast |
| 7 | test_flowzen_integration.py | 5 | End-to-end passive cycle tests |
| 8 | .env.example | — | Configuration |

**Total: ~22 tests, 8 commits, 15 files touched/created**

### Future Extensions (not in scope)

- **Three.js Glass Rose** — `electron-app/renderer/glass_rose.js` with petal animation, glow states, particle effects
- **Brain/Tahlamus cognitive response** — Brain receives inactivity signal, returns recommendation decision
- **Mood inference engine** — derive mood from intent frequency, gaps, and time patterns
- **Acceptance tracking** — personalize matrix based on which recommendations user follows
