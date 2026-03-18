"""Tests for AgentFarm tool functions."""
import os
import unittest
from unittest.mock import patch, MagicMock


class TestAgentFarmTools(unittest.TestCase):

    @patch("spaces.autogen.tools.agentfarm_tools._broadcast_to_electron")
    def test_create_team_from_config(self, mock_broadcast):
        from spaces.autogen.tools.agentfarm_tools import create_team
        result = create_team(
            template_id=None,
            team_name="TestTeam",
            team_config={
                "agents": [
                    {"name": "planner", "system_message": "You plan."},
                    {"name": "coder", "system_message": "You code."},
                ],
                "team_type": "selector",
                "model": "gpt-4o",
            },
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["agent_count"], 2)
        self.assertIn("team_id", result)

    def test_list_teams_empty(self):
        from spaces.autogen.tools.agentfarm_tools import _team_registry
        _team_registry.clear()
        from spaces.autogen.tools.agentfarm_tools import list_teams
        result = list_teams()
        self.assertTrue(result["success"])
        self.assertEqual(result["team_count"], 0)

    def test_get_farm_status(self):
        from spaces.autogen.tools.agentfarm_tools import get_farm_status
        result = get_farm_status()
        self.assertTrue(result["success"])
        self.assertIn("total_teams", result)

    def test_stop_run_nonexistent(self):
        from spaces.autogen.tools.agentfarm_tools import stop_run
        result = stop_run(run_id="nonexistent")
        self.assertFalse(result["success"])

    def test_get_run_results_nonexistent(self):
        from spaces.autogen.tools.agentfarm_tools import get_run_results
        result = get_run_results(run_id="nonexistent")
        self.assertFalse(result["success"])

    def test_list_templates_no_submodule(self):
        from spaces.autogen.tools.agentfarm_tools import list_templates, _SUBMODULE_PATH
        with patch.object(type(_SUBMODULE_PATH), "is_dir", return_value=False):
            result = list_templates()
            self.assertFalse(result["success"])
            self.assertIn("submodule", result["message"].lower())

    @patch.dict(os.environ, {"MINIBOOK_ENABLED": "false"})
    def test_start_collaboration_minibook_disabled(self):
        from spaces.autogen.tools.agentfarm_tools import start_collaboration
        result = start_collaboration(task="test", goal="test")
        self.assertFalse(result["success"])
        self.assertIn("minibook", result["message"].lower())


if __name__ == "__main__":
    unittest.main()
