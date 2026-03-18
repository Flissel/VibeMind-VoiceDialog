"""
SpaceAgent Models — Data structures for space-specific tool orchestration.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import uuid


@dataclass
class SpaceAgentContext:
    """Context passed to a SpaceAgent for tool execution."""
    user_input: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    current_bubble: Optional[str] = None          # Bubble name
    current_bubble_id: Optional[str] = None       # Bubble UUID
    idea_count: int = 0


@dataclass
class SpaceToolCall:
    """A single tool call made by the SpaceAgent."""
    name: str
    arguments: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class SpaceToolResult:
    """Result of executing a single tool."""
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None


@dataclass
class SpaceAgentResult:
    """Complete result of SpaceAgent execution."""
    tool_calls: List[SpaceToolCall] = field(default_factory=list)
    results: List[SpaceToolResult] = field(default_factory=list)
    summary: str = ""
    total_latency_ms: float = 0.0
    turns: int = 0
    error: Optional[str] = None
