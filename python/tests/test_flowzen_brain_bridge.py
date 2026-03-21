"""Tests for Flowzen Brain Bridge."""
import asyncio

import pytest
from unittest.mock import patch, AsyncMock

from spaces.flowzen.brain_bridge import FlowzenBrainBridge


def test_rule_based_fallback_rest_at_night():
    bridge = FlowzenBrainBridge()
    summary = {"time_window": "night", "minutes_since_last_activity": 30, "intent_count": 0}
    result = bridge._rule_based_fallback(summary)
    assert result["action"] == "suggest_rest"


def test_rule_based_fallback_suggest_task_on_idle():
    bridge = FlowzenBrainBridge()
    summary = {"time_window": "morning", "minutes_since_last_activity": 25, "intent_count": 0}
    result = bridge._rule_based_fallback(summary)
    assert result["action"] == "suggest_task"


def test_rule_based_fallback_do_nothing():
    bridge = FlowzenBrainBridge()
    summary = {"time_window": "morning", "minutes_since_last_activity": 5, "intent_count": 3}
    result = bridge._rule_based_fallback(summary)
    assert result["action"] == "do_nothing"


def test_parse_brain_response_high_activity():
    bridge = FlowzenBrainBridge()
    summary = {"intent_count": 15, "minutes_since_last_activity": 2, "time_window": "morning"}
    result = bridge._parse_brain_response({}, summary)
    assert result["action"] == "suggest_rest"


def test_parse_brain_response_evening_idle():
    bridge = FlowzenBrainBridge()
    summary = {"intent_count": 1, "minutes_since_last_activity": 25, "time_window": "evening"}
    result = bridge._parse_brain_response({}, summary)
    assert result["action"] == "suggest_rest"


def test_callback_is_called():
    bridge = FlowzenBrainBridge()
    received = []
    bridge.set_rose_callback(lambda d: received.append(d))

    summary = {"time_window": "morning", "minutes_since_last_activity": 5, "intent_count": 2}

    # Brain not available + LLM will fail -> falls to rule-based
    with patch.object(bridge, '_try_brain', new_callable=AsyncMock, return_value=None):
        with patch.object(bridge, '_local_decision', new_callable=AsyncMock, return_value={"action": "do_nothing", "reasoning": "test"}):
            result = asyncio.run(bridge.process_summary(summary))

    assert len(received) == 1
    assert received[0]["action"] == "do_nothing"
