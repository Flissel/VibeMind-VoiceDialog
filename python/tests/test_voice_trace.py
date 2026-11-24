"""Ein gesprochener Satz bekommt seine eigene Satz-Kennung (trace_id), wie die Chatfelder der App.

Routing (24.11.): Das Gehirn haengt die Kennung an jedes Ereignis des Laufs und an seine Antwort.
Ohne Kennung liess sich die Spur eines gesprochenen Satzes nicht von der eines anderen trennen.
Die Kennung geht im ui_context mit; die Bruecke legt sie neben ``intent`` und laesst keinen leeren
Kontext stehen (test_multihop_ui_context.py).
"""
import asyncio

from ipc import voice_manager
from swarm.routing import brain_multihop_bridge as bridge_module
from swarm.routing.brain_multihop_bridge import TRACE_ID, BrainMultihopBridge, trace_of


def test_each_spoken_sentence_has_its_own_valid_trace():
    first = voice_manager.voice_context().metadata["ui_context"]
    second = voice_manager.voice_context().metadata["ui_context"]

    assert set(first) == {"trace_id"}, "nothing on screen is claimed, only the trace"
    assert TRACE_ID.match(first["trace_id"]) and first["trace_id"].startswith("sprache-")
    assert first["trace_id"] != second["trace_id"]
    trace, rest = trace_of(first)
    assert trace == first["trace_id"] and rest is None


class _Answer:
    status = 200

    async def json(self):
        return {"ok": True, "plan_id": "p1", "executed": {}, "state": {}, "final_text": "erledigt"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Session:
    posted = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, url, json=None, **kwargs):
        _Session.posted.append(json)
        return _Answer()


def test_the_voice_trace_reaches_the_brain_beside_the_intent(monkeypatch):
    _Session.posted = []
    monkeypatch.setattr(bridge_module.aiohttp, "ClientSession", _Session)
    ui_context = voice_manager.voice_context().metadata["ui_context"]

    asyncio.run(BrainMultihopBridge()._post_multihop("Welche Bubbles gibt es?", ui_context))

    assert _Session.posted == [{"intent": "Welche Bubbles gibt es?", "trace_id": ui_context["trace_id"]}]


def test_the_voice_dispatch_passes_the_context_to_the_orchestrator(monkeypatch):
    seen = {}

    class _Orchestrator:
        async def process_intent(self, text, context=None):
            seen["text"] = text
            seen["ui_context"] = (context.metadata or {}).get("ui_context")
            return "ok"

    import swarm.orchestrator as orchestrator_module
    monkeypatch.setattr(orchestrator_module, "get_orchestrator", lambda: _Orchestrator())
    manager = voice_manager.VoiceManager.__new__(voice_manager.VoiceManager)

    assert manager._run_orchestrator_blocking("Welche Bubbles gibt es?") == "ok"
    assert seen["text"] == "Welche Bubbles gibt es?"
    assert seen["ui_context"]["trace_id"].startswith("sprache-")
