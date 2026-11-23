"""Der Kontext der App (offene Bubble, sichtbare Karten) geht unveraendert ans Gehirn.

Der Chat neben dem Canvas schickt mit jedem Satz mit, was auf dem Schirm ist. Das Feld
wird bis zur Anfrage an ``/api/multihop/execute`` durchgereicht und steht dort als
``context`` neben ``intent``. Ohne Kontext bleibt der Koerper wie zuvor.
"""
import asyncio

from swarm.routing import brain_multihop_bridge as bridge_module
from swarm.routing.brain_multihop_bridge import BrainMultihopBridge

UI_CONTEXT = {
    "space": "ideas",
    "bubble": {"id": "7", "title": "Marketing"},
    "cards": [{"id": "n1", "title": "Zielgruppe", "format": "note", "score": None}],
    "selection": [],
    "new_id": "8f6db1b5-b5a7-415d-8e43-b5926e23a984",
}

ANSWER = {"ok": True, "plan_id": "p1", "executed": {}, "state": {}, "final_text": "done"}


class _FakeResponse:
    status = 200

    async def json(self):
        return ANSWER

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    posted = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, url, json=None):
        _FakeSession.posted.append((url, json))
        return _FakeResponse()


def _post(monkeypatch, *args):
    _FakeSession.posted = []
    monkeypatch.setattr(bridge_module.aiohttp, "ClientSession", _FakeSession)
    asyncio.run(BrainMultihopBridge()._post_multihop(*args))
    return _FakeSession.posted[0]


def test_context_goes_into_the_body_unchanged(monkeypatch):
    url, body = _post(monkeypatch, "verbinde Zielgruppe mit Kanaele", UI_CONTEXT)

    assert url.endswith("/api/multihop/execute")
    assert body == {"intent": "verbinde Zielgruppe mit Kanaele", "context": UI_CONTEXT}


def test_the_mark_typed_reaches_the_brain_only_when_the_app_set_it(monkeypatch):
    # The main process of the app sets eingabe "getippt" for a sentence typed into a chat field
    # (electron-app/chat-input.js); Python passes it on as it is and adds nothing of its own.
    typed = {"space": "ideas", "eingabe": "getippt"}
    assert _post(monkeypatch, "oeffne den Rechner", typed)[1]["context"]["eingabe"] == "getippt"
    assert "eingabe" not in _post(monkeypatch, "oeffne den Rechner", {"space": "ideas"})[1]["context"]
    assert "context" not in _post(monkeypatch, "oeffne den Rechner")[1]


def test_without_context_the_body_is_as_before(monkeypatch):
    assert _post(monkeypatch, "zeig meine Bubbles")[1] == {"intent": "zeig meine Bubbles"}
    assert _post(monkeypatch, "zeig meine Bubbles", {})[1] == {"intent": "zeig meine Bubbles"}


def test_execute_hands_the_context_to_the_request():
    bridge = BrainMultihopBridge()
    calls = []

    async def _fake_post(text, ui_context=None):
        calls.append((text, ui_context))
        return ANSWER

    bridge._post_multihop = _fake_post

    async def _main():
        await bridge.execute("notiere: API Design", ui_context=UI_CONTEXT)
        await bridge.execute("ohne Kontext")
        await asyncio.sleep(0)

    asyncio.run(_main())

    assert calls == [("notiere: API Design", UI_CONTEXT), ("ohne Kontext", None)]


def _execute(answer):
    bridge = BrainMultihopBridge()

    async def _fake_post(text, ui_context=None):
        return answer

    async def _no_reward(plan_id, success):
        return None

    bridge._post_multihop = _fake_post
    bridge._reward_multihop = _no_reward

    async def _main():
        result = await bridge.execute("notiere: API Design")
        await asyncio.sleep(0)
        return result

    return asyncio.run(_main())


def test_a_refused_tool_keeps_the_sentence_of_the_brain():
    result = _execute({
        "ok": False, "plan_id": "p2", "state": {},
        "executed": {"s1": {"ok": False, "error": "supabase_http_error"}},
        "final_text": "Das Werkzeug hat eine Angabe abgelehnt: Bubble unbekannt.",
    })

    assert result is not None, "the sentence must not be dropped"
    assert result.event_type == "brain.multihop.failed"
    assert result.response_hint == "Das Werkzeug hat eine Angabe abgelehnt: Bubble unbekannt."
    assert result.error is None, "with error set the orchestrator would fall through and lose it again"


def test_a_question_back_reaches_the_user():
    result = _execute({
        "ok": False, "rueckfrage": True, "plan_id": "p3", "executed": {}, "state": {},
        "final_text": "Welche Bubble meinst du?",
    })

    assert result.event_type == "brain.multihop.question"
    assert result.response_hint == "Welche Bubble meinst du?"


def test_nothing_found_still_falls_through():
    assert _execute({"ok": False, "error": "planner returned no plan"}) is None
    assert _execute({"ok": False, "final_text": "", "executed": {}}) is None
    # a sentence without anything executed and without a question is not the Brain's verdict
    assert _execute({"ok": False, "final_text": "irgendein Text", "executed": {}}) is None


def test_a_plan_that_ran_is_reported_as_before():
    result = _execute(ANSWER)

    assert result.event_type == "brain.multihop"
    assert result.response_hint == "done"
