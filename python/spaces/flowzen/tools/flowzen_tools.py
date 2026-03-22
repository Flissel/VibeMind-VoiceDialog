"""
Flowzen Tools — Only 2 explicit tools (passive space).

Events:
    rose.recommend  -> recommend_task()
    rose.status     -> get_flowzen_status()
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

    # Generate LLM reasoning
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

    # Find a matching idea (top scored from DB)
    top_ideas = ideas_repo.list_top_scored(limit=10)
    idea = _pick_best_idea(top_ideas, category)

    if idea:
        title = getattr(idea, "title", "")
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

    # Create diary entry for this manual recommendation
    try:
        import json as json_module
        from data.flowzen_repository import FlowzenRepository as _FzRepo
        from spaces.flowzen.activity_tracker import generate_diary_entry
        import asyncio as _asyncio

        try:
            _loop = _asyncio.get_event_loop()
            if _loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as _pool:
                    diary_text = _pool.submit(
                        _asyncio.run,
                        generate_diary_entry(
                            mood=mood, energy=5, time_window=time_window, hour=hour,
                            category=category, intent_count=status["intents_buffered"],
                            activity_summary=activity_summary,
                            brain_action="manual_request",
                            brain_reasoning="User fragte explizit nach Empfehlung",
                        )
                    ).result(timeout=15)
            else:
                diary_text = _asyncio.run(generate_diary_entry(
                    mood=mood, energy=5, time_window=time_window, hour=hour,
                    category=category, intent_count=status["intents_buffered"],
                    activity_summary=activity_summary,
                    brain_action="manual_request",
                    brain_reasoning="User fragte explizit nach Empfehlung",
                ))
        except Exception:
            diary_text = None
        if not diary_text:
            diary_text = f"Empfehlung: {CATEGORY_DESCRIPTIONS.get(category, category)}. {reasoning[:80]}"
        _repo = _FzRepo()
        diary_entry = _repo.create_diary_entry(
            entry_text=diary_text, mood=mood, energy=5,
            time_window=time_window, hour=hour,
            intent_count=status["intents_buffered"], category=category,
            brain_action="manual_request", brain_reasoning="User fragte explizit",
            raw_data=json_module.dumps({"recommendation": title, "category": category}),
            source="manual",
        )
    except Exception as e:
        logger.debug(f"Flowzen: diary for recommendation failed: {e}")
        diary_entry = None

    result = {
        "success": True,
        "message": f"Flowzen: {category} recommended ({mood}/{time_window})",
        "response_hint": hint,
        "recommendation": {
            "category": category,
            "mood": mood,
            "time_window": time_window,
            "reasoning": reasoning,
            "idea_title": title,
            "idea_id": getattr(idea, "id", "") if idea else "",
        },
    }
    if diary_entry:
        result["diary_entry"] = diary_entry.to_dict()
    return result


def _pick_best_idea(ideas: list, category: str):
    """Pick highest-scored child idea. Accepts Idea dataclass objects."""
    if not ideas:
        return None
    # Prefer child ideas (inside a bubble)
    candidates = [i for i in ideas if getattr(i, "parent_id", None)]
    if not candidates:
        candidates = ideas
    candidates.sort(key=lambda i: getattr(i, "score", 0), reverse=True)
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
