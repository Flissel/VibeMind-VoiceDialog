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
    assert result.tool_result == {"pending": True, "status": "angenommen", "targets": [CARD]}


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
    asyncio.run(handlers.handle_chat_text_input({"type": "chat_text_input", "text": "recherchiere zu Karte 1"}))
    assert sent == [{"type": "chat_response", "success": True, "message": "Die Recherche laeuft.",
                     "event_type": "brain.multihop", "pending": True, "status": "angenommen", "targets": [CARD]}]
