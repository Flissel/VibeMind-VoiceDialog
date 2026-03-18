"""
Test: SpaceMinibookResponder + SpaceAgent integration.

Verifies that when a SpaceMinibookResponder receives an enriched @mention,
it routes through the SpaceAgent (agentic multi-tool loop) instead of
falling back to the IntentOrchestrator.

Tests:
1. SpaceAgent is called when available (enriched v2 format)
2. Fallback to orchestrator when SpaceAgent is None
3. Fallback to orchestrator when SpaceAgent fails
4. Context passthrough from enriched task to SpaceAgent
5. _load_space_agents() loads IdeasSpaceAgent when USE_SPACE_AGENTS=true
6. create_space_responders() injects SpaceAgents into responders
"""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

# Add project root to path
python_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, python_dir)


# --- Mock SpaceAgentResult ---
@dataclass
class MockSpaceAgentResult:
    tool_calls: list = field(default_factory=list)
    results: list = field(default_factory=list)
    summary: str = ""
    total_latency_ms: float = 0.0
    turns: int = 0
    error: str = ""


class TestSpaceMinibookResponderWithAgent(unittest.TestCase):
    """Test SpaceMinibookResponder routing to SpaceAgent."""

    def setUp(self):
        from spaces.minibook.workers.minibook_workers import SpaceMinibookResponder

        # Create a mock SpaceAgent
        self.mock_agent = MagicMock()
        self.mock_agent.execute = AsyncMock()

        # Create responder with SpaceAgent
        self.responder = SpaceMinibookResponder(
            agent_name="vibemind_ideas",
            space_key="ideas",
            tool_executor=None,
            space_agent=self.mock_agent,
            poll_interval=2.0,
        )

        # Create responder WITHOUT SpaceAgent (for fallback tests)
        self.responder_no_agent = SpaceMinibookResponder(
            agent_name="vibemind_coding",
            space_key="coding",
            tool_executor=MagicMock(return_value="Flat execution result"),
            space_agent=None,
            poll_interval=2.0,
        )

    def _make_enriched_content(
        self,
        event_type: str = "idea.create",
        user_text: str = "Erstelle eine Bubble Marketing",
        space_key: str = "ideas",
        context: Optional[Dict] = None,
    ) -> str:
        """Build Minibook post content in enriched v2 format."""
        task = {
            "space_key": space_key,
            "event_type": event_type,
            "payload": {"user_text": user_text, "title": "Marketing"},
            "context": context or {},
            "priority": "normal",
        }
        enriched = {
            "version": "2",
            "event_type": event_type,
            "tasks": [task],
            "original_text": user_text,
        }
        return f"```enriched\n{json.dumps(enriched, ensure_ascii=False)}\n```\n\nAufgabe: {user_text}"

    # -----------------------------------------------------------------
    # Test 1: SpaceAgent is called when available
    # -----------------------------------------------------------------
    def test_enriched_routes_to_space_agent(self):
        """Enriched v2 mention should route through SpaceAgent, not orchestrator."""
        self.mock_agent.execute.return_value = MockSpaceAgentResult(
            summary="Space Marketing erstellt mit 3 Ideen.",
            turns=2,
            total_latency_ms=850.0,
        )

        content = self._make_enriched_content()
        result = asyncio.get_event_loop().run_until_complete(
            self.responder._handle_mention(content)
        )

        # SpaceAgent should have been called
        self.mock_agent.execute.assert_called_once()
        self.assertEqual(result, "Space Marketing erstellt mit 3 Ideen.")

    # -----------------------------------------------------------------
    # Test 2: Fallback when no SpaceAgent
    # -----------------------------------------------------------------
    def test_no_agent_falls_back_to_executor(self):
        """Without SpaceAgent, should use tool_executor fallback."""
        content = self._make_enriched_content(
            space_key="coding",
            event_type="code.generate",
            user_text="Erstelle eine React App",
        )
        result = asyncio.get_event_loop().run_until_complete(
            self.responder_no_agent._handle_mention(content)
        )

        # tool_executor should have been called (sync via run_in_executor)
        # The content goes through _execute_legacy since coding task
        # won't match enriched parse for space_key="coding"
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    # -----------------------------------------------------------------
    # Test 3: Fallback when SpaceAgent fails
    # -----------------------------------------------------------------
    def test_agent_failure_falls_back(self):
        """When SpaceAgent raises an exception, should fall back to orchestrator."""
        self.mock_agent.execute.side_effect = RuntimeError("LLM timeout")

        content = self._make_enriched_content()

        # Mock the orchestrator fallback to avoid actual orchestrator calls
        with patch.object(
            self.responder, "_execute_via_orchestrator",
            new_callable=AsyncMock,
            return_value="Orchestrator fallback result"
        ):
            result = asyncio.get_event_loop().run_until_complete(
                self.responder._handle_mention(content)
            )

        # Should have fallen back to orchestrator
        self.assertEqual(result, "Orchestrator fallback result")

    # -----------------------------------------------------------------
    # Test 4: Context passthrough
    # -----------------------------------------------------------------
    def test_context_passed_to_space_agent(self):
        """Enriched context fields should be passed to SpaceAgentContext."""
        self.mock_agent.execute.return_value = MockSpaceAgentResult(
            summary="Idee erstellt.",
            turns=1,
            total_latency_ms=500.0,
        )

        context = {
            "conversation_history": [
                {"speaker": "user", "text": "Zeig mir Marketing"},
                {"speaker": "rachel", "text": "Du bist im Space Marketing."},
            ],
            "current_bubble": "Marketing",
            "current_bubble_id": "abc-123",
            "idea_count": 5,
        }

        content = self._make_enriched_content(context=context)
        asyncio.get_event_loop().run_until_complete(
            self.responder._handle_mention(content)
        )

        # Check the SpaceAgentContext that was passed
        call_args = self.mock_agent.execute.call_args
        agent_context = call_args[1].get("context") or call_args[0][1]

        self.assertEqual(agent_context.current_bubble, "Marketing")
        self.assertEqual(agent_context.current_bubble_id, "abc-123")
        self.assertEqual(agent_context.idea_count, 5)
        self.assertEqual(len(agent_context.conversation_history), 2)

    # -----------------------------------------------------------------
    # Test 5: Anti-loop guard
    # -----------------------------------------------------------------
    def test_minibook_event_type_blocked(self):
        """minibook.* event types should be blocked (anti-loop)."""
        content = self._make_enriched_content(
            event_type="minibook.discuss",
            user_text="Starte eine Diskussion",
        )
        result = asyncio.get_event_loop().run_until_complete(
            self.responder._handle_mention(content)
        )

        # SpaceAgent should NOT have been called
        self.mock_agent.execute.assert_not_called()
        self.assertIn("ausserhalb", result)

    # -----------------------------------------------------------------
    # Test 6: SpaceAgent returns empty summary → fallback
    # -----------------------------------------------------------------
    def test_agent_empty_summary_falls_back(self):
        """SpaceAgent returning empty summary should trigger fallback."""
        self.mock_agent.execute.return_value = MockSpaceAgentResult(
            summary="",
            turns=1,
            total_latency_ms=300.0,
        )

        content = self._make_enriched_content()

        with patch.object(
            self.responder, "_execute_via_orchestrator",
            new_callable=AsyncMock,
            return_value="Orchestrator handled it"
        ):
            result = asyncio.get_event_loop().run_until_complete(
                self.responder._handle_mention(content)
            )

        self.assertEqual(result, "Orchestrator handled it")


class TestLoadSpaceAgents(unittest.TestCase):
    """Test _load_space_agents() factory function."""

    def test_disabled_returns_empty(self):
        """USE_SPACE_AGENTS=false should return empty dict."""
        from spaces.minibook.workers.minibook_workers import _load_space_agents

        with patch.dict(os.environ, {"USE_SPACE_AGENTS": "false"}):
            agents = _load_space_agents()
            self.assertEqual(agents, {})

    def test_enabled_loads_ideas_agent(self):
        """USE_SPACE_AGENTS=true should load IdeasSpaceAgent."""
        from spaces.minibook.workers.minibook_workers import _load_space_agents

        mock_agent = MagicMock()
        with patch.dict(os.environ, {"USE_SPACE_AGENTS": "true"}):
            with patch(
                "swarm.space_agents.get_ideas_space_agent",
                return_value=mock_agent,
            ):
                agents = _load_space_agents()
                self.assertIn("ideas", agents)
                self.assertEqual(agents["ideas"], mock_agent)


class TestCreateSpaceResponders(unittest.TestCase):
    """Test create_space_responders() injects SpaceAgents."""

    def test_responders_get_space_agents(self):
        """Responders should have space_agent set when available."""
        from spaces.minibook.workers.minibook_workers import create_space_responders

        mock_agent = MagicMock()
        with patch.dict(os.environ, {"USE_SPACE_AGENTS": "true"}):
            with patch(
                "spaces.minibook.workers.minibook_workers._load_space_agents",
                return_value={"ideas": mock_agent},
            ):
                responders = create_space_responders(poll_interval=99.0)

                # Ideas responder should have the SpaceAgent
                self.assertIn("ideas", responders)
                self.assertEqual(responders["ideas"]._space_agent, mock_agent)

                # Coding responder should NOT have a SpaceAgent
                if "coding" in responders:
                    self.assertIsNone(responders["coding"]._space_agent)


if __name__ == "__main__":
    print("=" * 70)
    print("Test: SpaceMinibookResponder + SpaceAgent Integration")
    print("=" * 70)

    unittest.main(verbosity=2)
