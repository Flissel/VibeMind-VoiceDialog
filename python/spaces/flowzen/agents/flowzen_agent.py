"""
Flowzen Backend Agent (Blaue Rose) — Minimal agent.

Only handles 2 explicit events:
- rose.recommend: User asks "Was soll ich machen?"
- rose.status: "Blaue Rose Status"
"""

import logging
from typing import Dict, Callable, Optional

from swarm.backend_agents.base_agent import BaseBackendAgent

logger = logging.getLogger(__name__)


class FlowzenAgent(BaseBackendAgent):
    """Minimal backend agent for explicit Blaue Rose queries."""

    EVENT_TO_TOOL: Dict[str, str] = {
        "rose.recommend": "recommend_task",
        "rose.status":    "get_flowzen_status",
    }

    PARAM_MAPPING: Dict[str, Dict[str, str]] = {
        "rose.recommend": {
            "stimmung": "mood",
        },
    }

    @property
    def name(self) -> str:
        return "FlowzenAgent"

    @property
    def stream(self) -> str:
        return "events:tasks:flowzen"

    def _load_tools(self) -> Dict[str, Callable]:
        tools = {}
        try:
            from spaces.flowzen.tools.flowzen_tools import (
                recommend_task,
                get_flowzen_status,
            )
            tools.update({
                "recommend_task": recommend_task,
                "get_flowzen_status": get_flowzen_status,
            })
            logger.info(f"{self.name}: Loaded {len(tools)} tools")
        except ImportError as e:
            logger.warning(f"{self.name}: Could not load tools: {e}")
        return tools

    def _get_tool_name(self, event_type: str) -> Optional[str]:
        return self.EVENT_TO_TOOL.get(event_type)


_flowzen_agent: Optional[FlowzenAgent] = None


def get_flowzen_agent() -> FlowzenAgent:
    global _flowzen_agent
    if _flowzen_agent is None:
        _flowzen_agent = FlowzenAgent()
    return _flowzen_agent


__all__ = ["FlowzenAgent", "get_flowzen_agent"]
