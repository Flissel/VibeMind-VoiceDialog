"""Ist das Gehirn nicht erreichbar, sagt die Bruecke das selbst.

Gemessen 2026-11-23 waehrend eines Neustarts des Gehirns: Die Verbindung brach ab
("[WinError 64] Der angegebene Netzwerkname ist nicht mehr verfuegbar"), die Bruecke fiel
auf den alten Weg durch, und der antwortete "Ich habe dich nicht ganz verstanden". Jetzt
kommt ein ruhiger Hinweis, solange keine Verbindung besteht; ein Timeout faellt weiter durch.
"""
import asyncio

import aiohttp

from swarm.routing import brain_multihop_bridge as bridge_module
from swarm.routing.brain_multihop_bridge import BrainMultihopBridge, UNREACHABLE_TEXT


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


def test_a_timeout_still_falls_through(monkeypatch):
    bridge, (result,) = _ask(monkeypatch, asyncio.TimeoutError())
    assert result is None
    assert bridge._down == "timeout"
