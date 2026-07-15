"""VOICE_BRAIN_MULTIHOP_TIMEOUT_S — der Miss-Timeout der Phase-2-Bridge ist
env-tunbar.

Warum: bei einem MISS (keine Cap / kein Plan) wartet der Voice-Turn diesen
Timeout, bevor er auf den alten schnellen Pfad durchfällt. Der Default (6s)
ist für eine gesprochene Interaktion spürbar; er muss ohne Code-Änderung
runterdrehbar sein.
"""
from swarm.routing.brain_multihop_bridge import BrainMultihopBridge


def test_default_timeout_is_six(monkeypatch):
    monkeypatch.delenv("VOICE_BRAIN_MULTIHOP_TIMEOUT_S", raising=False)
    assert BrainMultihopBridge()._request_timeout == 6.0


def test_env_overrides_timeout(monkeypatch):
    monkeypatch.setenv("VOICE_BRAIN_MULTIHOP_TIMEOUT_S", "2.5")
    assert BrainMultihopBridge()._request_timeout == 2.5


def test_bad_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("VOICE_BRAIN_MULTIHOP_TIMEOUT_S", "garbage")
    assert BrainMultihopBridge()._request_timeout == 6.0


def test_explicit_arg_is_the_fallback_when_env_unset(monkeypatch):
    monkeypatch.delenv("VOICE_BRAIN_MULTIHOP_TIMEOUT_S", raising=False)
    assert BrainMultihopBridge(request_timeout_s=3.0)._request_timeout == 3.0
