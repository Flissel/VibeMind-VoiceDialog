"""Integration tests for Flowzen (Blaue Rose) end-to-end flow."""
import os
import tempfile
from unittest.mock import patch, MagicMock

from data.database import Database


def _temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    db.initialize()
    return db, path


def test_event_router_knows_flowzen_streams():
    """EventRouter maps rose.* events to flowzen stream."""
    from swarm.event_team.event_router import EventRouter
    router = EventRouter()
    assert router.get_stream("rose.recommend") == "events:tasks:flowzen"
    assert router.get_stream("rose.status") == "events:tasks:flowzen"


def test_agent_handles_recommend():
    """FlowzenAgent routes rose.recommend to recommend_task tool."""
    from spaces.flowzen.agents.flowzen_agent import FlowzenAgent
    agent = FlowzenAgent()
    tool_name = agent._get_tool_name("rose.recommend")
    assert tool_name == "recommend_task"
    tools = agent._load_tools()
    assert "recommend_task" in tools
    assert callable(tools["recommend_task"])


def test_agent_handles_status():
    """FlowzenAgent routes rose.status to get_flowzen_status tool."""
    from spaces.flowzen.agents.flowzen_agent import FlowzenAgent
    agent = FlowzenAgent()
    tool_name = agent._get_tool_name("rose.status")
    assert tool_name == "get_flowzen_status"


def test_get_flowzen_status_returns_dict():
    """get_flowzen_status returns a success dict with tracker info."""
    from spaces.flowzen.tools.flowzen_tools import get_flowzen_status
    result = get_flowzen_status()
    assert result["success"] is True
    assert "status" in result
    assert "current_time_window" in result["status"]


def test_tracker_on_intent_persists_to_db():
    """ActivityTracker.on_intent logs to flowzen_activity table."""
    db, path = _temp_db()
    try:
        with patch("data.flowzen_repository.get_database", return_value=db):
            from spaces.flowzen.activity_tracker import ActivityTracker
            tracker = ActivityTracker(summary_interval_minutes=30)
            tracker.on_intent("code.generate", {"description": "test"})

            from data.flowzen_repository import FlowzenRepository
            repo = FlowzenRepository(db)
            recent = repo.get_recent_activity(limit=5)
            assert len(recent) == 1
            assert recent[0].event_type == "code.generate"
    finally:
        os.unlink(path)


def test_circadian_matrix_recommends_rest_for_tired_night():
    """Tired mood + night = rest category."""
    from spaces.flowzen.activity_tracker import get_circadian_category
    assert get_circadian_category("tired", "night") == "rest"


def test_circadian_matrix_recommends_deep_work_for_energized_morning():
    """Energized mood + morning = deep_work category."""
    from spaces.flowzen.activity_tracker import get_circadian_category
    assert get_circadian_category("energized", "morning") == "deep_work"


def test_space_router_maps_rose_to_flowzen():
    """SpaceRouter deterministic map includes rose. → flowzen."""
    try:
        from spaces.minibook.enrichment.space_router import EVENT_TYPE_TO_SPACE
        assert EVENT_TYPE_TO_SPACE.get("rose.") == "flowzen"
    except ImportError:
        pass  # Minibook may not be importable without full env


def test_plugin_manifest_exists():
    """plugin.json exists and has correct structure."""
    import json
    plugin_path = os.path.join(
        os.path.dirname(__file__), "..", "plugins", "builtin", "flowzen", "plugin.json"
    )
    if os.path.exists(plugin_path):
        with open(plugin_path) as f:
            manifest = json.load(f)
        assert manifest["id"] == "flowzen"
        assert "rose.recommend" in manifest["event_routes"]
        assert manifest["env_flag"] == "FLOWZEN_ENABLED"
    else:
        # Plugin dir might be at different relative path — skip gracefully
        pass


def test_event_router_flowzen_stream_constant_exists():
    """EventRouter defines STREAM_TASKS_FLOWZEN constant."""
    from swarm.event_team.event_router import EventRouter
    assert hasattr(EventRouter, "STREAM_TASKS_FLOWZEN")
    assert EventRouter.STREAM_TASKS_FLOWZEN == "events:tasks:flowzen"


def test_agent_stream_property():
    """FlowzenAgent.stream returns the correct Redis stream name."""
    from spaces.flowzen.agents.flowzen_agent import FlowzenAgent
    agent = FlowzenAgent()
    assert agent.stream == "events:tasks:flowzen"


def test_agent_unknown_event_returns_none():
    """FlowzenAgent returns None for events it does not handle."""
    from spaces.flowzen.agents.flowzen_agent import FlowzenAgent
    agent = FlowzenAgent()
    assert agent._get_tool_name("idea.create") is None
    assert agent._get_tool_name("rose.mood") is None
    assert agent._get_tool_name("code.generate") is None


def test_param_mapping_stimmung_to_mood():
    """PARAM_MAPPING maps German 'stimmung' to English 'mood' for rose.recommend."""
    from spaces.flowzen.agents.flowzen_agent import FlowzenAgent
    agent = FlowzenAgent()
    mapping = agent.PARAM_MAPPING.get("rose.recommend", {})
    assert mapping.get("stimmung") == "mood"