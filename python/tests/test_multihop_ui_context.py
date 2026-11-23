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

    def post(self, url, json=None, headers=None):
        _FakeSession.posted.append((url, json))
        _FakeSession.headers.append(headers)
        return _FakeResponse()


def _post(monkeypatch, *args):
    _FakeSession.posted = []
    _FakeSession.headers = []
    monkeypatch.setattr(bridge_module.aiohttp, "ClientSession", _FakeSession)
    asyncio.run(BrainMultihopBridge()._post_multihop(*args))
    return _FakeSession.posted[0]


def test_context_goes_into_the_body_unchanged(monkeypatch):
    url, body = _post(monkeypatch, "verbinde Zielgruppe mit Kanaele", UI_CONTEXT)

    assert url.endswith("/api/multihop/execute")
    assert body == {"intent": "verbinde Zielgruppe mit Kanaele", "context": UI_CONTEXT}


KEY = "k" * 32
# Computed with eingabe_zeichen() of the Brain (vibemind-os a60cafc7,
# brain/the_brain/core/desktop_tagesrest.py) for KEY, this sentence and this time.
TEMPLATE_SIGNATURE = "1763900000.44a19a1c2893fd048a9f38df56c0ebe5b32c45bf839ad9b5be2ee0e29c02229b"


def test_the_signature_matches_the_template_of_the_brain():
    assert bridge_module.eingabe_zeichen(KEY, "Öffne den Rechner", 1763900000) == TEMPLATE_SIGNATURE


def test_a_typed_sentence_is_signed_for_exactly_its_text_and_time():
    context, headers = bridge_module.typed_request(
        "  Öffne den Rechner \n", {"space": "desktop", "eingabe": "getippt"},
        environ={"VIBEMIND_EINGABE_SCHLUESSEL": KEY}, now=1763900000.7,
    )
    assert context == {"space": "desktop", "eingabe": "getippt"}
    assert headers == {"X-Vibemind-Eingabe": TEMPLATE_SIGNATURE}


def test_without_the_key_neither_field_nor_header_go():
    for env in ({}, {"VIBEMIND_EINGABE_SCHLUESSEL": "zu-kurz"}):
        context, headers = bridge_module.typed_request(
            "Öffne den Rechner", {"space": "desktop", "eingabe": "getippt"}, environ=env, now=1763900000,
        )
        assert context == {"space": "desktop"}
        assert headers == {}
    context, headers = bridge_module.typed_request(
        "Öffne den Rechner", {"eingabe": "getippt"}, environ={}, now=1763900000,
    )
    assert (context, headers) == (None, {})


def test_automatic_sentences_get_no_signature():
    env = {"VIBEMIND_EINGABE_SCHLUESSEL": KEY}
    # no context (voice, eyeTerm, MCP), a context without the mark, a mark with another value
    assert bridge_module.typed_request("Öffne den Rechner", None, environ=env) == (None, {})
    assert bridge_module.typed_request("Öffne den Rechner", {"space": "ideas"}, environ=env) == ({"space": "ideas"}, {})
    assert bridge_module.typed_request("x", {"space": "ideas", "eingabe": "stimme"}, environ=env) == ({"space": "ideas"}, {})
    given = {"space": "ideas", "eingabe": "getippt"}
    bridge_module.typed_request("x", given, environ={})
    assert given == {"space": "ideas", "eingabe": "getippt"}, "the context of the caller is not changed"


def test_the_request_carries_the_header_only_for_a_typed_sentence(monkeypatch):
    monkeypatch.setenv("VIBEMIND_EINGABE_SCHLUESSEL", KEY)
    body = _post(monkeypatch, "Öffne den Rechner", {"space": "desktop", "eingabe": "getippt"})[1]
    assert body["context"]["eingabe"] == "getippt"
    header = _FakeSession.headers[0]["X-Vibemind-Eingabe"]
    zeit = int(header.split(".")[0])
    assert header == bridge_module.eingabe_zeichen(KEY, "Öffne den Rechner", zeit)

    body = _post(monkeypatch, "Öffne den Rechner", {"space": "desktop"})[1]
    assert "eingabe" not in body["context"] and _FakeSession.headers[0] is None
    assert "context" not in _post(monkeypatch, "Öffne den Rechner")[1] and _FakeSession.headers[0] is None

    monkeypatch.delenv("VIBEMIND_EINGABE_SCHLUESSEL")
    body = _post(monkeypatch, "Öffne den Rechner", {"space": "desktop", "eingabe": "getippt"})[1]
    assert "eingabe" not in body["context"] and _FakeSession.headers[0] is None


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


def test_not_understood_is_a_question_back_with_the_german_sentence_only():
    result = _execute({
        "ok": False, "verstanden": False, "plan_id": "p5", "executed": {}, "state": {},
        "final_text": "Das habe ich nicht verstanden. Sag zum Beispiel: Halt fest: Preise prüfen.",
        "fehler": "NoCapabilityMatch: score 0.12 < 0.35",
    })

    assert result.event_type == "brain.multihop.question"
    assert result.response_hint.startswith("Das habe ich nicht verstanden.")
    assert "NoCapabilityMatch" not in result.response_hint, "the raw original is never passed on"


def test_a_hint_reaches_the_user_as_a_hint_not_a_failure():
    result = _execute({
        "ok": False, "hinweis": True, "plan_id": "p6", "executed": {}, "state": {},
        "final_text": "Die Tabelle hat keine Spalten; sag, welche es geben soll.",
    })

    assert result.event_type == "brain.multihop.hint"
    assert result.response_hint.startswith("Die Tabelle hat keine Spalten")


def test_nothing_found_still_falls_through():
    assert _execute({"ok": False, "error": "planner returned no plan"}) is None
    assert _execute({"ok": False, "final_text": "", "executed": {}}) is None
    # a sentence without anything executed and without a question is not the Brain's verdict
    assert _execute({"ok": False, "final_text": "irgendein Text", "executed": {}}) is None


def test_a_plan_that_ran_is_reported_as_before():
    result = _execute(ANSWER)

    assert result.event_type == "brain.multihop"
    assert result.response_hint == "done"
