"""HybridRouter type definitions."""

from dataclasses import dataclass, field
from typing import List, Optional, Literal


@dataclass
class SpaceBinding:
    """Maps an event_type prefix or keyword pattern to a space + agent."""
    space: str
    agent: str
    stream: str = ""
    pattern: str = ""  # The prefix or keyword pattern that matched


@dataclass
class RouteResult:
    """Result of a routing decision with debugging metadata."""
    space: str
    agent: str
    event_type: str
    matched_by: str          # e.g. "binding.prefix:bubble.*"
    cached: bool = False
    tier: int = 0
    multi_space: Optional["MultiSpaceStrategy"] = None


@dataclass
class ExecutionStep:
    """A single step in a multi-space execution plan."""
    space: str
    depends_on: List[str] = field(default_factory=list)
    context_fields: List[str] = field(default_factory=list)


@dataclass
class MultiSpaceStrategy:
    """Execution strategy for multi-space requests."""
    strategy: Literal["pipeline", "parallel", "mixed"]
    steps: List[ExecutionStep] = field(default_factory=list)


@dataclass
class SessionKey:
    """Identifies a routing session."""
    agent_id: str
    channel: str
    scope: str = "direct"
    peer_id: str = "anonymous"
    thread_id: Optional[str] = None

    @property
    def key(self) -> str:
        base = f"agent:{self.agent_id}:{self.channel}:{self.scope}:{self.peer_id}"
        if self.thread_id:
            return f"{base}:thread:{self.thread_id}"
        return base

    @property
    def main_key(self) -> str:
        return f"agent:{self.agent_id}:main"


@dataclass
class SessionEntry:
    """A session's stored state."""
    session_key: str
    agent_id: str
    channel: str
    canonical_id: Optional[str] = None
    space_state: Optional[dict] = None
    last_route: Optional[RouteResult] = None
    last_active: Optional[str] = None
