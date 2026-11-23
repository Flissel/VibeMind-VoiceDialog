"""Ist das Gehirn nicht erreichbar, sagt die Bruecke das selbst.

Gemessen 2026-11-23 waehrend eines Neustarts des Gehirns: Die Verbindung brach ab
("[WinError 64] Der angegebene Netzwerkname ist nicht mehr verfuegbar"), die Bruecke fiel
auf den alten Weg durch, und der antwortete "Ich habe dich nicht ganz verstanden". Jetzt
kommt ein ruhiger Hinweis, solange keine Verbindung besteht. Auch ein Timeout antwortet
ehrlich: Das Gehirn kann gehandelt haben, also kein "geaendert habe ich nichts".
"""
import asyncio

import aiohttp

from swarm.routing import brain_multihop_bridge as bridge_module
from swarm.routing.brain_multihop_bridge import BrainMultihopBridge, TIMEOUT_TEXT, UNREACHABLE_TEXT


class _Refusing:
    """Stand-in for aiohttp.ClientSession whose post fails like the measured restart."""

    def __init__(self, error):
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, *args, **kwargs):
        raise self._error


def _ask(monkeypatch, error, sentences=1):
    monkeypatch.setattr(bridge_module.aiohttp, "ClientSession", lambda *a, **k: _Refusing(error))
    bridge = BrainMultihopBridge()

    async def _main():
        return [await bridge.execute("Gruppiere die Karten") for _ in range(sentences)]

    return bridge, asyncio.run(_main())


def test_no_connection_is_said_plainly_and_calmly(monkeypatch):
    error = aiohttp.ClientOSError(64, "Der angegebene Netzwerkname ist nicht mehr verfügbar")
    bridge, (result,) = _ask(monkeypatch, error)
    assert result is not None, "no fall-through to the old path"
    assert result.response_hint == UNREACHABLE_TEXT
    assert result.event_type == "brain.multihop.hint", "a hint, never a failure"
    assert not result.error
    assert result.tool_result is None
    assert result.job_id.startswith("brain-multihop"), "no plan of the Brain: the answer names no plan id"
    assert "geändert habe ich nichts" in UNREACHABLE_TEXT


def test_the_next_sentence_in_the_backoff_gets_the_same_answer(monkeypatch):
    bridge, results = _ask(monkeypatch, aiohttp.ClientOSError(10061, "Verbindung verweigert"), sentences=2)
    assert [r.response_hint for r in results] == [UNREACHABLE_TEXT, UNREACHABLE_TEXT]
    bridge._re_enable()
    assert bridge._down == "" and bridge._available


def _serve_and_ask(delays, limit):
    """A real local Brain stand-in that answers after `delays[i]` seconds (aiohttp server), and a
    bridge with `limit` as its request timeout. Times are the measured ones scaled 1:100."""
    from aiohttp import web

    async def _main():
        pending = list(delays)

        async def handler(request):
            await asyncio.sleep(pending.pop(0))
            return web.json_response({"ok": True, "plan_id": "p1", "state": {}, "final_text": "Erledigt.",
                                      "executed": {"s1": {"ok": True, "capability": "idea_list"}}})

        app = web.Application()
        app.router.add_post("/api/multihop/execute", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        bridge = BrainMultihopBridge(brain_url=f"http://127.0.0.1:{port}", request_timeout_s=limit)

        async def _no_reward(plan_id, success):
            return None

        bridge._reward_multihop = _no_reward
        try:
            results = [await bridge.execute("Was steht in Karte 1?") for _ in delays]
            await asyncio.sleep(0)
            return bridge, results
        finally:
            await runner.cleanup()

    return asyncio.run(_main())


def test_answers_after_16_and_33_s_arrive_within_a_45_s_limit(monkeypatch):
    monkeypatch.delenv("VOICE_BRAIN_MULTIHOP_TIMEOUT_S", raising=False)
    bridge, results = _serve_and_ask([0.16, 0.33], limit=0.45)
    assert [r.response_hint for r in results] == ["Erledigt.", "Erledigt."]
    assert bridge._available


def test_a_slow_answer_says_so_and_the_next_sentence_is_sent_again(monkeypatch):
    monkeypatch.delenv("VOICE_BRAIN_MULTIHOP_TIMEOUT_S", raising=False)
    bridge, (slow, nxt) = _serve_and_ask([0.60, 0.16], limit=0.45)
    assert slow.response_hint == TIMEOUT_TEXT
    assert slow.event_type == "brain.multihop.hint" and not slow.error
    assert "geändert habe ich nichts" not in TIMEOUT_TEXT, "the Brain may have acted"
    assert bridge._available, "no backoff after a slow answer: the Brain works serially and may still be busy"
    assert nxt.response_hint == "Erledigt.", "the next sentence went to the Brain, not into a pause"


def test_no_connection_in_time_counts_as_unreachable(monkeypatch):
    error = aiohttp.ServerTimeoutError("Connection timeout to host")
    bridge, (result,) = _ask(monkeypatch, error)
    assert result.response_hint == UNREACHABLE_TEXT
    assert bridge._down == "unreachable" and not bridge._available
