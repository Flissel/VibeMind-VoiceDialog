"""Tests for TeamRunner -- async Autogen 0.4 team executor."""
import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


class TestTeamRunner(unittest.TestCase):
    """Test TeamRunner singleton and run lifecycle."""

    def setUp(self):
        from spaces.autogen.runner.team_runner import TeamRunner
        TeamRunner._instance = None
        self.runner = TeamRunner.get_instance()

    def test_singleton(self):
        from spaces.autogen.runner.team_runner import TeamRunner
        runner2 = TeamRunner.get_instance()
        self.assertIs(self.runner, runner2)

    def test_get_status_empty(self):
        status = self.runner.get_status()
        self.assertEqual(status, {})

    def test_cancel_nonexistent_run(self):
        result = self.runner.cancel_run("nonexistent-id")
        self.assertFalse(result)

    def test_prune_completed_under_limit(self):
        from spaces.autogen.runner.team_runner import RunState
        state = RunState(
            run_id="r1", team_id="t1", task="test",
            status="completed", completed_at=datetime.now(),
        )
        self.runner._active_runs["r1"] = state
        self.runner._prune_completed()
        self.assertIn("r1", self.runner._active_runs)


class TestTeamRunnerAsync(unittest.IsolatedAsyncioTestCase):
    """Test async run execution."""

    async def asyncSetUp(self):
        from spaces.autogen.runner.team_runner import TeamRunner
        TeamRunner._instance = None
        self.runner = TeamRunner.get_instance()

    @patch("spaces.autogen.runner.team_runner._broadcast_to_electron")
    @patch("spaces.autogen.runner.team_runner.TeamRunner._build_team")
    async def test_start_run_returns_run_id(self, mock_build, mock_broadcast):
        mock_team = AsyncMock()
        mock_team.run_stream = AsyncMock(return_value=AsyncMock(__aiter__=lambda s: s, __anext__=AsyncMock(side_effect=StopAsyncIteration)))
        mock_build.return_value = mock_team

        run_id = await self.runner.start_run(
            team_id="team-1",
            team_config={"agents": [], "model": "gpt-4o"},
            task="Build a REST API",
        )
        self.assertIsInstance(run_id, str)
        self.assertIn(run_id, self.runner._active_runs)
        await asyncio.sleep(0.1)

    @patch("spaces.autogen.runner.team_runner._broadcast_to_electron")
    async def test_cancel_running_run(self, mock_broadcast):
        from spaces.autogen.runner.team_runner import RunState

        cancel_token = MagicMock()
        state = RunState(
            run_id="r1", team_id="t1", task="test",
            status="running", cancel_token=cancel_token,
        )
        self.runner._active_runs["r1"] = state

        result = self.runner.cancel_run("r1")
        self.assertTrue(result)
        cancel_token.cancel.assert_called_once()


if __name__ == "__main__":
    unittest.main()
