"""Tests for FlowzenAgent — minimal agent with only 2 explicit tools."""
from spaces.flowzen.agents.flowzen_agent import FlowzenAgent


def test_event_to_tool_mapping():
    agent = FlowzenAgent()
    assert agent._get_tool_name("rose.recommend") == "recommend_task"
    assert agent._get_tool_name("rose.status") == "get_flowzen_status"


def test_only_two_events():
    """Rose should only handle explicit queries, not be a general router."""
    agent = FlowzenAgent()
    assert agent._get_tool_name("rose.mood") is None
    assert agent._get_tool_name("rose.history") is None


def test_tools_load():
    agent = FlowzenAgent()
    tools = agent._load_tools()
    assert "recommend_task" in tools
    assert "get_flowzen_status" in tools
    assert len(tools) == 2
