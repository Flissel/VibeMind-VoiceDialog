"""
ReasoningEvent - Data structures for tracking execution reasoning.

Captures reasoning at each layer of multi-step execution:
- Intent classification
- Dependency ordering
- Tool execution
- Result formatting
"""

import uuid
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class ReasoningEvent:
    """
    A single reasoning event for execution tracking.

    Used to capture what the system is doing and why during
    intent processing, dependency resolution, and tool execution.
    """
    event_id: str                           # Unique ID for this event
    job_id: str                             # Parent job ID
    session_id: Optional[str] = None        # User session ID
    timestamp: float = field(default_factory=time.time)

    # Classification
    level: str = "tool"                     # "intent" | "dependency" | "tool" | "result"
    phase: str = "started"                  # "started" | "reasoning" | "completed" | "error"

    # Content
    title: str = ""                         # Brief title for UI/logs
    reasoning: str = ""                     # Detailed explanation
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Progress tracking (for multi-step)
    step_index: Optional[int] = None        # Current step (1-based)
    total_steps: Optional[int] = None       # Total number of steps
    confidence: Optional[float] = None      # Confidence score (0-1)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for Redis/IPC transport and JSONL logging."""
        return {
            "event_id": self.event_id,
            "job_id": self.job_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "level": self.level,
            "phase": self.phase,
            "title": self.title,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
            "step_index": self.step_index,
            "total_steps": self.total_steps,
            "confidence": self.confidence,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReasoningEvent":
        """Deserialize from dict."""
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            job_id=data.get("job_id", ""),
            session_id=data.get("session_id"),
            timestamp=data.get("timestamp", time.time()),
            level=data.get("level", "tool"),
            phase=data.get("phase", "started"),
            title=data.get("title", ""),
            reasoning=data.get("reasoning", ""),
            metadata=data.get("metadata", {}),
            step_index=data.get("step_index"),
            total_steps=data.get("total_steps"),
            confidence=data.get("confidence"),
        )


@dataclass
class ReasoningContext:
    """
    Accumulates reasoning throughout a job execution.

    Tracks all reasoning events for a single job and provides
    summarization for logging and voice responses.
    """
    job_id: str
    session_id: Optional[str] = None
    user_input: str = ""
    start_time: float = field(default_factory=time.time)

    events: List[ReasoningEvent] = field(default_factory=list)

    # Summary fields (populated after execution)
    classification_summary: Optional[str] = None
    dependency_summary: Optional[str] = None
    execution_summary: Optional[str] = None

    def add_event(self, event: ReasoningEvent):
        """Add a reasoning event to this context."""
        self.events.append(event)

    def get_by_level(self, level: str) -> List[ReasoningEvent]:
        """Get all events of a specific level."""
        return [e for e in self.events if e.level == level]

    def get_tool_events(self) -> List[ReasoningEvent]:
        """Get all tool-level events."""
        return self.get_by_level("tool")

    def get_duration_ms(self) -> float:
        """Get total duration in milliseconds."""
        if not self.events:
            return 0
        return (time.time() - self.start_time) * 1000

    def get_voice_summary(self) -> str:
        """
        Generate a natural summary for voice output.

        Example: "Ich habe zuerst die Bubble 'Marketing' erstellt,
        dann drei Ideen hinzugefuegt und sie automatisch verlinkt."
        """
        tool_events = [e for e in self.events if e.level == "tool" and e.phase == "completed"]

        if not tool_events:
            return ""

        summaries = []
        for event in tool_events:
            tool_name = event.metadata.get("tool_name", "")
            action = self._get_german_action(tool_name, event.metadata)
            if action:
                summaries.append(action)

        if len(summaries) == 1:
            return summaries[0]
        elif len(summaries) == 2:
            return f"{summaries[0]} und {summaries[1]}"
        else:
            return ", ".join(summaries[:-1]) + f" und {summaries[-1]}"

    def _get_german_action(self, tool_name: str, metadata: Dict) -> str:
        """Map tool name to German action description."""
        action_map = {
            "bubble.create": "Bubble erstellt",
            "bubble.enter": "Bubble betreten",
            "bubble.list": "Bubbles aufgelistet",
            "idea.create": "Idee hinzugefuegt",
            "idea.list": "Ideen aufgelistet",
            "idea.connect": "Ideen verlinkt",
            "idea.auto_link": "Ideen automatisch verlinkt",
            "code.generate": "Code generiert",
            "desktop.type_text": "Text eingegeben",
        }
        return action_map.get(tool_name, f"{tool_name} ausgefuehrt")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dict."""
        return {
            "job_id": self.job_id,
            "session_id": self.session_id,
            "user_input": self.user_input,
            "start_time": self.start_time,
            "duration_ms": self.get_duration_ms(),
            "event_count": len(self.events),
            "events": [e.to_dict() for e in self.events],
            "classification_summary": self.classification_summary,
            "dependency_summary": self.dependency_summary,
            "execution_summary": self.execution_summary,
        }


__all__ = ["ReasoningEvent", "ReasoningContext"]
