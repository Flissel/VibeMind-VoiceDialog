"""K8: Die Rueckfrage "bauen?" des Coding-Wegs gibt nur ihre frage_id an den Hauptprozess der App weiter.

Das Gehirn antwortet auf "Bau mir ..." mit rueckfrage true, weg "coding" und frage_id (32 Hex-Zeichen).
Die Bruecke legt die id als coding_frage in tool_result; die Antwort an den Chat traegt sie, der
Hauptprozess behaelt sie und signiert "Ja, bauen" selbst (electron-app/coding-bauen.js).
Erfundene ids.
"""
import asyncio

from swarm.routing.brain_multihop_bridge import BrainMultihopBridge, coding_question_of

FRAGE = "0123456789abcdef0123456789abcdef"


def _execute(answer):
    bridge = BrainMultihopBridge()

    async def _fake_post(text, ui_context=None):
        return answer

    async def _no_reward(plan_id, success):
        return None

    bridge._post_multihop = _fake_post
    bridge._reward_multihop = _no_reward

    async def _main():
        result = await bridge.execute("Bau mir eine kleine App")
        await asyncio.sleep(0)
        return result

    return asyncio.run(_main())


def test_only_a_coding_question_with_a_clean_id_counts():
    assert coding_question_of({"rueckfrage": True, "weg": "coding", "frage_id": FRAGE}) == FRAGE
    assert coding_question_of({"rueckfrage": False, "weg": "coding", "frage_id": FRAGE}) is None
    assert coding_question_of({"rueckfrage": True, "weg": "lesen", "frage_id": FRAGE}) is None
    assert coding_question_of({"rueckfrage": True, "weg": "coding", "frage_id": FRAGE.upper()}) is None
    assert coding_question_of({"rueckfrage": True, "weg": "coding", "frage_id": "../x"}) is None
    assert coding_question_of(None) is None


def test_the_question_carries_its_id_in_the_tool_result():
    result = _execute({"ok": False, "rueckfrage": True, "weg": "coding", "frage_id": FRAGE,
                       "final_text": "Soll ich das bauen? Sag „Ja, bauen“.", "executed": {}, "state": {}})
    assert result.event_type == "brain.multihop.question"
    assert result.response_hint.startswith("Soll ich das bauen?")
    assert result.tool_result == {"coding_frage": FRAGE}


def test_another_question_carries_none():
    result = _execute({"ok": False, "rueckfrage": True, "weg": "lesen", "frage_id": FRAGE,
                       "final_text": "Welche Karte meinst du?", "executed": {}, "state": {}})
    assert result.tool_result is None
