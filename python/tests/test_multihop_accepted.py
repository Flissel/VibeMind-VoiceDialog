"""Ein angenommener Auftrag des Gehirns ist kein Fehler.

Bei Modell-Funktionen antwortet das Gehirn mit ok true, pending true, status "angenommen":
ein Modell arbeitet noch, das Ergebnis kommt spaeter ueber die Datenbank an der Karte an.
Die Bruecke reicht das als tool_result weiter, die Antwort an den Chat traegt pending,
status und die Karten, an denen gearbeitet wird. Zuvor stand dort "fehlgeschlagen".
"""
import asyncio

from swarm.routing.brain_multihop_bridge import BrainMultihopBridge

CARD = "00000000-0000-4000-8000-000000000001"


def _execute(answer):
    bridge = BrainMultihopBridge()

    async def _fake_post(text, ui_context=None):
        return answer

    async def _no_reward(plan_id, success):
        return None

    bridge._post_multihop = _fake_post
    bridge._reward_multihop = _no_reward

    async def _main():
        result = await bridge.execute("recherchiere zu Karte 1")
        await asyncio.sleep(0)
        return result

    return asyncio.run(_main())


def test_accepted_in_the_answer_itself():
    result = _execute({"ok": True, "pending": True, "status": "angenommen", "plan_id": "p1", "state": {},
                       "executed": {"s1": {"ok": True, "capability": "idea_research"}},
                       "final_text": "Die Recherche laeuft.", "targets": [CARD]})
    assert result.event_type == "brain.multihop"
    assert result.response_hint == "Die Recherche laeuft."
    assert result.tool_result == {"pending": True, "status": "angenommen", "targets": [CARD], "orders": []}


def test_accepted_in_a_hop_result_without_a_sentence():
    result = _execute({"ok": True, "plan_id": "p2", "state": {}, "final_text": "",
                       "executed": {"s1": {"ok": True, "capability": "idea_research",
                                           "result": {"ok": True, "pending": True, "status": "angenommen", "card_id": CARD}}}})
    assert result.event_type == "brain.multihop"
    assert result.response_hint == "Auftrag angenommen"
    assert result.tool_result["targets"] == [CARD]


def test_a_plain_answer_carries_no_receipt():
    result = _execute({"ok": True, "plan_id": "p3", "state": {}, "final_text": "fertig",
                       "executed": {"s1": {"ok": True, "result": {"ok": True}}}})
    assert result.tool_result is None


def test_a_real_failure_stays_a_failure():
    result = _execute({"ok": False, "plan_id": "p4", "state": {}, "final_text": "Werkzeug nicht erreichbar.",
                       "executed": {"s1": {"ok": False, "error": "timeout"},
                                    "s2": {"ok": True, "result": {"pending": True}}}})
    assert result.event_type == "brain.multihop.failed"
    assert result.tool_result is None


def test_the_chat_answer_says_pending_not_failed(monkeypatch):
    import swarm.orchestrator as orchestrator_module
    from ipc.clawport_handlers import ClawPortHandlers
    from swarm.orchestrator.result_formatter import OrchestrationResult

    class _Orchestrator:
        async def process_intent(self, text, context=None):
            return OrchestrationResult(job_id="p1", event_type="brain.multihop", stream="brain",
                                       response_hint="Die Recherche laeuft.",
                                       tool_result={"pending": True, "status": "angenommen", "targets": [CARD]})

    monkeypatch.setattr(orchestrator_module, "get_orchestrator", lambda: _Orchestrator())
    handlers = ClawPortHandlers.__new__(ClawPortHandlers)
    sent = []
    handlers.send_message = sent.append
    asyncio.run(handlers.handle_chat_text_input({"type": "chat_text_input", "text": "recherchiere zu Karte 1",
                                                 "request_id": "r1"}))
    # plan_id: the plan this sentence started; request_id: the app finds the sentence it answers
    assert sent == [{"type": "chat_response", "success": True, "message": "Die Recherche laeuft.",
                     "event_type": "brain.multihop", "plan_id": "p1", "pending": True, "status": "angenommen",
                     "targets": [CARD], "orders": [], "request_id": "r1"}]


ORDER = "00000000-0000-4000-8000-0000000000aa"


def test_the_order_numbers_travel_to_the_app():
    result = _execute({"ok": True, "pending": True, "status": "angenommen", "plan_id": "p5", "state": {},
                       "auftraege": [{"auftrag_id": ORDER, "agent": "brain-ideas", "capability": "idea_explain"}],
                       "executed": {"s1": {"ok": True, "result": {"ok": True, "pending": True, "auftrag_id": ORDER}}},
                       "final_text": "Auftrag angenommen, Nr. 00000000 - die Einschaetzung folgt.", "targets": [CARD]})
    assert result.tool_result["orders"] == [ORDER], "once, from answer and hop"

ORDER_2 = "00000000-0000-4000-8000-0000000000bb"


def test_the_step_that_hands_the_order_over_is_no_failure():
    """Lauf 7: der Schritt, der den Auftrag an ein Modell gibt, sagt ok false, pending true.

    Die Bruecke wertete das als echten Fehler: kein pending, keine Auftragsnummer in der App,
    die App fragte /stand nie und zeigte den Vorschlag nicht.
    """
    result = _execute({"ok": True, "pending": True, "status": "angenommen", "plan_id": "p7", "state": {},
                       "final_text": "Auftrag angenommen, Nr. 00000000 – das Ergebnis kommt, sobald es geprueft ist.",
                       "executed": {"s1": {"ok": False, "pending": True, "invocation_id": ORDER_2,
                                           "result": {"auftrag_id": ORDER_2, "agent": "agent-a", "status": "offen"}}}})
    assert result.tool_result == {"pending": True, "status": "angenommen", "targets": [], "orders": [ORDER_2]}


def test_a_step_that_really_failed_still_is_one():
    result = _execute({"ok": False, "plan_id": "p8", "state": {}, "final_text": "Das hat nicht geklappt.",
                       "executed": {"s1": {"ok": False, "error": "Der Dienst ist gerade nicht erreichbar."}}})
    assert result.tool_result is None


BUBBLE = "00000000-0000-4000-8000-00000000000b"


def test_the_place_of_a_written_result_travels_to_the_app(monkeypatch):
    # The Brain names where a writing call put its result (ziel); the app goes there.
    ziel = {"space": "ideas", "bubble_id": BUBBLE, "node_id": CARD}
    result = _execute({"ok": True, "plan_id": "p9", "state": {}, "final_text": "Notiz festgehalten.",
                       "executed": {}, "ziel": ziel})
    assert result.tool_result == {"ziel": ziel}

    rated = _execute({"ok": True, "plan_id": "p10", "state": {}, "final_text": "Bewertet.",
                      "executed": {}, "ziel": {"space": "ideas", "bubble_id": BUBBLE, "node_id": None}})
    assert rated.tool_result == {"ziel": {"space": "ideas", "bubble_id": BUBBLE, "node_id": None}}

    bad = _execute({"ok": True, "plan_id": "p11", "state": {}, "final_text": "fertig", "executed": {},
                    "ziel": {"space": "ideas", "bubble_id": "../x", "node_id": CARD}})
    assert bad.tool_result is None, "only plain ids pass"

    import swarm.orchestrator as orchestrator_module
    from ipc.clawport_handlers import ClawPortHandlers
    from swarm.orchestrator.result_formatter import OrchestrationResult

    class _Orchestrator:
        async def process_intent(self, text, context=None):
            return OrchestrationResult(job_id="p9", event_type="brain.multihop", stream="brain",
                                       response_hint="Notiz festgehalten.", tool_result={"ziel": ziel})

    monkeypatch.setattr(orchestrator_module, "get_orchestrator", lambda: _Orchestrator())
    handlers = ClawPortHandlers.__new__(ClawPortHandlers)
    sent = []
    handlers.send_message = sent.append
    asyncio.run(handlers.handle_chat_text_input({"type": "chat_text_input", "text": "Halt fest: Karte 1",
                                                 "request_id": "r9"}))
    assert sent[0]["ziel"] == ziel
    assert "pending" not in sent[0]


def test_a_direct_answer_naming_only_a_space_carries_its_ziel_to_the_app(monkeypatch):
    # Befund 24.11.: "Welche Fenster sind offen?" — the Brain answers at once with ziel
    # {"space": "desktop"} (no bubble). The bridge dropped it, so the app never jumped.
    desktop = _execute({"ok": True, "plan_id": "p20", "state": {}, "final_text": "Offen sind zwei Fenster.",
                        "executed": {}, "ziel": {"space": "desktop"}})
    assert desktop.tool_result == {"ziel": {"space": "desktop", "bubble_id": None, "node_id": None}}
    coding = _execute({"ok": True, "plan_id": "p21", "state": {}, "final_text": "Zwei Projekte laufen.",
                       "executed": {}, "ziel": {"space": "coding", "bubble_id": None}})
    assert coding.tool_result == {"ziel": {"space": "coding", "bubble_id": None, "node_id": None}}
    for odd in ({"space": "Desktop!"}, {"space": "desktop", "bubble_id": "../x"}, {"bubble_id": BUBBLE}, "desktop"):
        assert _execute({"ok": True, "plan_id": "p22", "state": {}, "final_text": "fertig", "executed": {},
                         "ziel": odd}).tool_result is None, odd

    # ... and the chat answer the app gets carries it, as the renderer reads it (response.ziel).
    import swarm.orchestrator as orchestrator_module
    from ipc.clawport_handlers import ClawPortHandlers

    class _Orchestrator:
        async def process_intent(self, text, context=None):
            return desktop

    monkeypatch.setattr(orchestrator_module, "get_orchestrator", lambda: _Orchestrator())
    handlers = ClawPortHandlers.__new__(ClawPortHandlers)
    sent = []
    handlers.send_message = sent.append
    asyncio.run(handlers.handle_chat_text_input({"type": "chat_text_input", "text": "Welche Fenster sind offen?",
                                                 "request_id": "r20"}))
    assert sent[0]["type"] == "chat_response"
    assert sent[0]["success"] is True
    assert sent[0]["message"] == "Offen sind zwei Fenster."
    assert sent[0]["ziel"] == {"space": "desktop", "bubble_id": None, "node_id": None}


def test_a_promoted_project_keeps_its_projekt_id_in_the_ziel():
    """After promoting, the Brain names {space: swedesign, projekt_id}: the app opens that project's wizard."""
    from swarm.routing.brain_multihop_bridge import ziel_of

    assert ziel_of({"space": "swedesign", "projekt_id": "p1a2b3c4"}) == {
        "space": "swedesign", "bubble_id": None, "node_id": None, "projekt_id": "p1a2b3c4"}
    assert ziel_of({"space": "swedesign", "projekt_id": 42})["projekt_id"] == "42"
    # an id that is not plain is left out, the place stays
    assert ziel_of({"space": "swedesign", "projekt_id": "../x y"}) == {"space": "swedesign", "bubble_id": None, "node_id": None}
    # without a project nothing changes
    assert "projekt_id" not in ziel_of({"space": "ideas", "bubble_id": CARD, "node_id": None})
    assert ziel_of({"space": "Swe!", "projekt_id": "p1"}) is None
