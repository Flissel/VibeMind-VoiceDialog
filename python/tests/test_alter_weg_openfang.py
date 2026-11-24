"""The old path of the app (classifier after the Brain) over OpenFang and the subscription.

Since 2026-11-23 06:05 every call of the old path to OpenRouter failed with 401 "User not found."
(25 sentences, 4 calls each). The default is now OpenFang: POST <OpenFang>/v1/chat/completions with
model "openfang:<agent>", the answer in the OpenAI form (choices[0].message.content), as the Brain
calls its planner. The real OpenAI client runs here against a stand-in transport.
"""
import asyncio
import json

import httpx
import openai
import pytest

import llm_config
from swarm.orchestrator import yaml_classifier as yc

KEY = "test-openfang-key"


def _completion(content, model="openfang:voice-einordnung"):
    """An answer of /v1/chat/completions in the OpenAI form."""
    return {
        "id": "chatcmpl-0001", "object": "chat.completion", "created": 1795500000, "model": model,
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.fixture
def wire(monkeypatch):
    """Every OpenAI client of llm_config talks to `answer` instead of the network; requests recorded."""
    requests = []
    answer = {"status": 200, "body": _completion('{"event_type": "idea.list", "payload": {}}')}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(answer["status"], json=answer["body"])

    real = openai.OpenAI
    monkeypatch.setattr(openai, "OpenAI",
                        lambda **kw: real(**kw, http_client=httpx.Client(transport=httpx.MockTransport(handler))))
    monkeypatch.setattr(yc, "BACKOFF_BASE", 0)
    monkeypatch.delenv(llm_config.ALTER_WEG_ENV, raising=False)
    monkeypatch.setenv("OPENFANG_API_KEY", KEY)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.delenv("LLM_MODEL_CLASSIFIER_OPENFANG", raising=False)
    return requests, answer


def _classify(text):
    return asyncio.run(yc.YamlClassifier().classify(text))


def test_the_switch_chooses_openfang_by_default_and_openrouter_on_request(monkeypatch):
    monkeypatch.delenv(llm_config.ALTER_WEG_ENV, raising=False)
    assert llm_config.classifier_role() == "classifier_openfang"
    assert llm_config.get_provider("classifier_openfang") == "openfang"
    assert llm_config.get_model("classifier_openfang") == "openfang:voice-einordnung"
    monkeypatch.setenv(llm_config.ALTER_WEG_ENV, "openrouter")
    assert llm_config.classifier_role() == "classifier"
    assert llm_config.get_provider("classifier") == "openrouter", "the old way stays, not deleted"


def test_a_sentence_goes_to_openfang_once_and_its_answer_is_read(wire):
    requests, answer = wire
    answer["body"] = _completion('```json\n{"event_type": "idea.list", "payload": {}}\n```')

    result = _classify("Zeige meine Ideen")

    assert result["event_type"] == "idea.list"
    assert len(requests) == 1
    sent = requests[0]
    assert str(sent.url) == "http://localhost:4200/v1/chat/completions"
    assert sent.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(sent.content)
    assert body["model"] == "openfang:voice-einordnung"
    assert "openrouter" not in str(sent.url)


def test_a_refusal_of_openfang_is_one_call_then_not_understood(wire):
    requests, answer = wire
    answer["status"], answer["body"] = 401, {"error": {"message": "unauthorized"}}

    result = _classify("Zeige meine Ideen")

    assert result["event_type"] == "conversation.unknown"
    assert len(requests) == 1, "no retries on OpenFang (they were for openrouter/free)"


def test_without_the_openfang_key_nothing_is_sent_and_never_openrouter(wire, monkeypatch):
    requests, _ = wire
    monkeypatch.delenv("OPENFANG_API_KEY", raising=False)
    monkeypatch.setattr(llm_config, "_openfang_key", lambda: None)

    with pytest.raises(ValueError):
        llm_config.get_client("classifier_openfang")
    result = _classify("Zeige meine Ideen")

    assert result["event_type"] == "conversation.unknown"
    assert requests == [], "no call at all, also not to OpenRouter"


def test_a_greeting_needs_no_model(wire):
    requests, _ = wire
    for text in ("hi", "Hallo!", "guten Morgen", "Hey Rachel"):
        result = _classify(text)
        assert result["event_type"] == "conversation.greeting", text
        assert result["response_hint"] == "Hallo! Wie kann ich dir helfen?"
    assert requests == []
    # a sentence that only starts with a greeting goes on to the model
    assert _classify("Hallo, zeige meine Ideen")["event_type"] == "idea.list"
    assert len(requests) == 1


def test_switched_back_to_openrouter_it_runs_as_before(wire, monkeypatch):
    requests, answer = wire
    monkeypatch.setenv(llm_config.ALTER_WEG_ENV, "openrouter")
    answer["status"], answer["body"] = 401, {"error": {"message": "User not found.", "code": 401}}

    result = _classify("Zeige meine Ideen")

    assert result["event_type"] == "conversation.unknown"
    assert len(requests) == yc.MAX_RETRIES == 3
    assert all(r.url.host == "openrouter.ai" for r in requests)
    assert json.loads(requests[0].content)["model"] == "openrouter/free"


def test_the_large_classifier_uses_the_same_switch(wire, monkeypatch):
    from swarm.orchestrator.intent_classifier import IntentClassifier
    assert IntentClassifier()._model == "openfang:voice-einordnung"
    monkeypatch.setenv(llm_config.ALTER_WEG_ENV, "openrouter")
    assert IntentClassifier()._model == "openrouter/free"
