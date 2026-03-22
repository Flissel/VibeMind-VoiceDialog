"""
Flowzen Activity Tracker — Passive broadcast listener (Blaue Rose).

Receives ALL intents via broadcast, logs activity, and every 30 minutes
sends a situation summary with LLM-generated neuroscience reasoning to Brain/Tahlamus.
Never asks the user anything.

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

# --- LLM Reasoning Generator ---

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


# --- Diary Entry Generator ---

DIARY_SYSTEM_PROMPT = """Du bist die Blaue Rose — das stille, warme Tagebuch im VibeMind System.
Deine Aufgabe: Schreibe einen kurzen, persoenlichen Tagebucheintrag (max 150 Woerter)
im Stil eines handgeschriebenen Taschenbuches.

Regeln:
- Sprich den User warm und direkt an (du-Form)
- Beschreibe was er/sie in den letzten 30 Minuten getan hat
- Deute vorsichtig die Stimmung/Energie an (nie klinisch, immer menschlich)
- Erwaehne die Empfehlung die gegeben wurde (falls vorhanden)
- Beende mit einem ermutigenden oder nachdenklichen Satz
- Schreibe auf Deutsch
- Kein Markdown, keine Aufzaehlungen — fliessender Text wie handgeschrieben
- Jeder Eintrag soll einzigartig sein, keine Wiederholungen
- Wenn keine Aktivitaet war, schreibe trotzdem etwas Warmes ueber die Stille"""

DIARY_USER_TEMPLATE = """Zeitpunkt: {time_window} ({hour}:00 Uhr)
Stimmung: {mood} (Energie: {energy}/10)
Aktivitaet letzte 30 Min: {activity_summary}
Anzahl Intents: {intent_count}
Empfohlene Kategorie: {category} ({category_description})
Brain-Entscheidung: {brain_action} — {brain_reasoning}

Schreibe einen warmen Tagebucheintrag (max 150 Woerter, deutsch, fliessender Text)."""


async def generate_diary_entry(
    mood: str, energy: int, time_window: str, hour: int,
    category: str, intent_count: int, activity_summary: str,
    brain_action: str = "", brain_reasoning: str = "",
) -> str:
    """Generate a warm diary entry via LLM."""
    try:
        from llm_config import get_model, get_async_client

        client = get_async_client("flowzen_reasoning")
        model = get_model("flowzen_reasoning")

        user_msg = DIARY_USER_TEMPLATE.format(
            mood=mood, energy=energy,
            time_window=time_window, hour=hour,
            activity_summary=activity_summary or "keine Aktivitaet",
            intent_count=intent_count,
            category=category,
            category_description=CATEGORY_DESCRIPTIONS.get(category, category),
            brain_action=brain_action or "do_nothing",
            brain_reasoning=brain_reasoning or "Alles ruhig",
        )

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": DIARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_completion_tokens=300,
            temperature=0.8,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.warning(f"Flowzen: diary generation failed: {e}")
        # Warm fallback text
        desc = CATEGORY_DESCRIPTIONS.get(category, "")
        if intent_count > 0:
            return f"Die letzten dreissig Minuten waren bewegt — {intent_count} Aktionen, {desc.lower()} stand im Fokus. Die Rose beobachtet still."
        else:
            return "Eine ruhige halbe Stunde. Manchmal braucht es genau das — Stille, in der Gedanken reifen koennen."


async def generate_reasoning(
    mood: str, time_window: str, hour: int, category: str,
    activity_summary: str = "",
) -> str:
    """Generate neuroscience-backed reasoning via LLM."""
    try:
        from llm_config import get_model, get_async_client

        client = get_async_client("flowzen_reasoning")
        model = get_model("flowzen_reasoning")

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
            max_completion_tokens=200,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.warning(f"Flowzen: LLM reasoning failed: {e}")
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
    - Every 30 minutes: builds situation summary + LLM reasoning, sends to Brain
    - Never asks the user anything directly
    """

    def __init__(self, summary_interval_minutes: int = 30):
        self._interval = timedelta(minutes=summary_interval_minutes)
        self._last_activity: Optional[datetime] = None
        self._last_summary_sent: Optional[datetime] = None
        self._intent_buffer: list = []
        self._brain_callback: Optional[Callable] = None
        self._electron_sender: Optional[Callable[[dict], None]] = None
        self._brain_bridge = None
        self._lock = threading.Lock()

    def set_brain_callback(self, callback: Callable):
        """Set callback to send periodic summaries to Brain/Tahlamus."""
        self._brain_callback = callback

    def set_electron_sender(self, sender: Callable[[dict], None]):
        """Set Electron IPC sender for 3D rose state updates."""
        self._electron_sender = sender

    def set_brain_bridge(self, bridge):
        """Set direct reference to BrainBridge for async diary generation."""
        self._brain_bridge = bridge

    def on_intent(self, event_type: str, payload: Dict[str, Any] = None):
        """
        Called for EVERY intent passing through the orchestrator.
        Must be fast — runs in the intent hot path.
        """
        now = datetime.now()

        with self._lock:
            self._last_activity = now
            self._intent_buffer.append(event_type)

        # Log to DB (fire-and-forget)
        try:
            from data.flowzen_repository import FlowzenRepository
            repo = FlowzenRepository()
            repo.log_activity(event_type=event_type, hour=now.hour)
        except Exception as e:
            logger.debug(f"Flowzen: activity log failed: {e}")

        self._broadcast_rose_state("active", event_type=event_type)

    def send_periodic_summary(self):
        """
        Called every 30 minutes by a background timer.
        Builds summary, generates LLM reasoning, sends to Brain.
        """
        import asyncio

        now = datetime.now()

        if self._last_summary_sent:
            elapsed = now - self._last_summary_sent
            if elapsed < self._interval:
                return

        summary = self._build_summary()

        # Generate LLM reasoning
        try:
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

        if self._brain_callback:
            try:
                self._brain_callback(summary)
                logger.info(
                    f"Flowzen: periodic summary sent to Brain "
                    f"({summary['intent_count']} intents, {summary['time_window']})"
                )
            except Exception as e:
                logger.warning(f"Flowzen: Brain callback failed: {e}")

    async def send_periodic_summary_async(self):
        """
        Async version of send_periodic_summary.
        Builds summary, gets Brain decision, generates diary entry, persists.
        """
        import json as json_module
        now = datetime.now()

        if self._last_summary_sent:
            elapsed = now - self._last_summary_sent
            if elapsed < self._interval:
                return

        summary = self._build_summary()

        # Determine mood from recent checkins
        try:
            from data.flowzen_repository import FlowzenRepository
            repo = FlowzenRepository()
            recent = repo.get_recent_checkins(limit=1)
            mood = recent[0].mood if recent else "calm"
            energy = recent[0].energy if recent else 5
        except Exception:
            mood = "calm"
            energy = 5

        time_window = summary["time_window"]
        hour = summary["hour"]
        category = get_circadian_category(mood, time_window)

        activity_str = ", ".join(
            f"{et}:{count}" for et, count in summary["event_types"].items()
        ) or "keine Aktivitaet"

        # 1. Generate LLM reasoning (existing)
        reasoning = await generate_reasoning(
            mood=mood, time_window=time_window, hour=hour,
            category=category, activity_summary=activity_str,
        )
        summary["llm_reasoning"] = reasoning

        # 2. Get Brain decision
        decision = {"action": "do_nothing", "reasoning": ""}
        if self._brain_bridge:
            try:
                decision = await self._brain_bridge.process_summary(summary)
            except Exception as e:
                logger.debug(f"Flowzen: brain decision failed: {e}")

        # 3. Generate warm diary entry
        try:
            diary_text = await generate_diary_entry(
                mood=mood, energy=energy, time_window=time_window, hour=hour,
                category=category, intent_count=summary["intent_count"],
                activity_summary=activity_str,
                brain_action=decision.get("action", ""),
                brain_reasoning=decision.get("reasoning", ""),
            )

            from data.flowzen_repository import FlowzenRepository
            repo = FlowzenRepository()
            entry = repo.create_diary_entry(
                entry_text=diary_text, mood=mood, energy=energy,
                time_window=time_window, hour=hour,
                intent_count=summary["intent_count"], category=category,
                brain_action=decision.get("action", ""),
                brain_reasoning=decision.get("reasoning", ""),
                raw_data=json_module.dumps(summary, ensure_ascii=False),
                source="periodic",
            )

            # Broadcast new diary entry to Electron
            self._broadcast_rose_state("diary_new", diary_entry=entry.to_dict())
            logger.info(f"Flowzen: diary entry created ({mood}/{time_window}, {summary['intent_count']} intents)")
        except Exception as e:
            logger.warning(f"Flowzen: diary entry creation failed: {e}")

        # 4. Handle Brain response (rose state animation)
        if decision.get("action") != "do_nothing":
            self.on_brain_response(decision)

        with self._lock:
            self._last_summary_sent = now
            self._intent_buffer.clear()

    def _build_summary(self) -> Dict[str, Any]:
        """Build situation summary from buffered observations."""
        now = datetime.now()
        time_window = get_time_window(now.hour)

        with self._lock:
            buffer_copy = list(self._intent_buffer)

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
        """Called when Brain responds to a periodic summary."""
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
        """Return current tracker status."""
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
