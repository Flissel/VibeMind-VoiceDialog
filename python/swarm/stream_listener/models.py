"""
Data structures for the StreamListener system.

Each StreamListener (one per Space) evaluates user input via LLM
and returns a confidence score. The ConfidenceDistribution collects
all scores and determines the winner.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class EvalContext:
    """Context passed to all listeners for evaluation."""
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    current_bubble: Optional[str] = None
    current_bubble_id: Optional[str] = None
    idea_count: int = 0
    user_preferences: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ListenerEvaluation:
    """Result from a single StreamListener's LLM evaluation."""
    space: str                              # "ideas", "coding", "desktop", ...
    confidence: float                       # 0.0–1.0
    event_type: str                         # "bubble.list", "code.generate", ...
    payload: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    mode: str = "execute"                   # "execute" or "direct_answer"
    direct_answer: str = ""                 # Response text when mode=="direct_answer"
    latency_ms: float = 0.0


@dataclass
class ConfidenceDistribution:
    """Aggregated results from all listeners."""
    evaluations: List[ListenerEvaluation]
    winner: Optional[ListenerEvaluation]
    is_ambiguous: bool                      # Top-2 difference < threshold
    total_latency_ms: float = 0.0

    def log_distribution(self) -> str:
        """Format as debug string: 'ideas=0.85 coding=0.05 desktop=0.02 ...'"""
        parts = [f"{e.space}={e.confidence:.2f}" for e in self.evaluations]
        winner_str = f" -> WINNER: {self.winner.space}" if self.winner else " -> NO WINNER"
        ambig_str = " (AMBIGUOUS)" if self.is_ambiguous else ""
        return " ".join(parts) + winner_str + ambig_str


@dataclass
class StreamListenerConfig:
    """Configuration for the StreamListener system."""
    model: str = "openai/gpt-4o-mini"
    timeout_seconds: float = 8.0  # Per-listener LLM timeout (generous for cold starts)
    min_confidence: float = 0.3
    ambiguity_threshold: float = 0.15
    max_context_messages: int = 5
    temperature: float = 0.1
