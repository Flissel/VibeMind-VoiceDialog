"""
LLM Metrics for Agent Simulation.

Tracks token usage, estimated costs, and confidence scores from LLM API calls.
"""

import re
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# Token prices (as of 2025) - per million tokens
TOKEN_PRICES = {
    # OpenRouter / Anthropic models
    "anthropic/claude-3.5-haiku": {"input": 0.80, "output": 4.00},
    "anthropic/claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "anthropic/claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "anthropic/claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    # Fallback for unknown models
    "default": {"input": 1.00, "output": 5.00},
}


@dataclass
class LLMMetrics:
    """Metrics from a single LLM API call."""
    model: str                      # Model identifier
    input_tokens: int = 0           # Prompt tokens
    output_tokens: int = 0          # Completion tokens
    total_tokens: int = 0           # Total tokens
    estimated_cost_usd: float = 0.0 # Estimated cost in USD
    confidence: float = 0.0         # Extracted confidence score (0-1.0)
    latency_ms: float = 0.0         # API call duration in milliseconds


@dataclass
class AggregatedLLMMetrics:
    """Aggregated LLM metrics across multiple calls."""
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_confidence: float = 0.0
    avg_latency_ms: float = 0.0
    by_model: Dict[str, Dict] = field(default_factory=dict)


def _get_price(model: str) -> Dict[str, float]:
    """Get token prices for a model."""
    # Try exact match first
    if model in TOKEN_PRICES:
        return TOKEN_PRICES[model]

    # Try partial match
    model_lower = model.lower()
    for key, prices in TOKEN_PRICES.items():
        if key != "default" and key.lower() in model_lower:
            return prices

    return TOKEN_PRICES["default"]


def _extract_confidence(content: str) -> float:
    """
    Extract confidence score from LLM response content.

    Looks for patterns like:
    - "confidence": 0.95
    - confidence: 0.85
    - Confidence: 90%
    """
    if not content:
        return 0.0

    # Pattern 1: JSON-style "confidence": 0.95
    match = re.search(r'"?confidence"?\s*[:\s]+\s*([\d.]+)', content, re.IGNORECASE)
    if match:
        try:
            value = float(match.group(1))
            # If > 1, assume percentage
            return value / 100.0 if value > 1 else value
        except ValueError:
            pass

    # Pattern 2: Percentage format 95%
    match = re.search(r'confidence[:\s]+(\d+)\s*%', content, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1)) / 100.0
        except ValueError:
            pass

    # Default: assume moderate confidence if no explicit value
    return 0.5


def extract_llm_metrics(
    response: dict,
    model: str,
    latency_ms: float,
    content: str = None
) -> LLMMetrics:
    """
    Extract LLM metrics from API response.

    Args:
        response: API response dictionary (OpenRouter/OpenAI format)
        model: Model identifier string
        latency_ms: Request latency in milliseconds
        content: Optional response content for confidence extraction

    Returns:
        LLMMetrics with extracted values
    """
    # Extract token usage
    usage = response.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    total_tokens = input_tokens + output_tokens

    # Calculate cost
    prices = _get_price(model)
    cost = (
        (input_tokens * prices["input"] / 1_000_000) +
        (output_tokens * prices["output"] / 1_000_000)
    )

    # Extract confidence from content if provided
    if content is None:
        # Try to get content from response
        choices = response.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")

    confidence = _extract_confidence(content or "")

    return LLMMetrics(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=cost,
        confidence=confidence,
        latency_ms=latency_ms
    )


class LLMMetricsCollector:
    """Collects and aggregates LLM metrics across multiple calls."""

    def __init__(self):
        self._metrics: List[LLMMetrics] = []

    def record(self, metrics: LLMMetrics):
        """Record a single LLM call's metrics."""
        self._metrics.append(metrics)

    def record_from_response(
        self,
        response: dict,
        model: str,
        latency_ms: float,
        content: str = None
    ):
        """Record metrics directly from API response."""
        metrics = extract_llm_metrics(response, model, latency_ms, content)
        self.record(metrics)

    def reset(self):
        """Clear all recorded metrics."""
        self._metrics = []

    @property
    def all_metrics(self) -> List[LLMMetrics]:
        """Get all recorded metrics."""
        return self._metrics.copy()

    def summarize(self) -> AggregatedLLMMetrics:
        """Generate aggregated metrics summary."""
        if not self._metrics:
            return AggregatedLLMMetrics()

        # Calculate totals
        total_input = sum(m.input_tokens for m in self._metrics)
        total_output = sum(m.output_tokens for m in self._metrics)
        total_tokens = sum(m.total_tokens for m in self._metrics)
        total_cost = sum(m.estimated_cost_usd for m in self._metrics)

        # Calculate averages
        confidences = [m.confidence for m in self._metrics if m.confidence > 0]
        avg_confidence = statistics.mean(confidences) if confidences else 0.0

        latencies = [m.latency_ms for m in self._metrics]
        avg_latency = statistics.mean(latencies) if latencies else 0.0

        # Group by model
        by_model = {}
        for m in self._metrics:
            if m.model not in by_model:
                by_model[m.model] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "avg_latency_ms": 0.0,
                    "latencies": []
                }
            by_model[m.model]["calls"] += 1
            by_model[m.model]["input_tokens"] += m.input_tokens
            by_model[m.model]["output_tokens"] += m.output_tokens
            by_model[m.model]["total_tokens"] += m.total_tokens
            by_model[m.model]["cost_usd"] += m.estimated_cost_usd
            by_model[m.model]["latencies"].append(m.latency_ms)

        # Calculate per-model average latency
        for model_stats in by_model.values():
            if model_stats["latencies"]:
                model_stats["avg_latency_ms"] = statistics.mean(model_stats["latencies"])
            del model_stats["latencies"]  # Remove temp list

        return AggregatedLLMMetrics(
            total_calls=len(self._metrics),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
            avg_confidence=avg_confidence,
            avg_latency_ms=avg_latency,
            by_model=by_model
        )


__all__ = [
    "LLMMetrics",
    "AggregatedLLMMetrics",
    "LLMMetricsCollector",
    "extract_llm_metrics",
    "TOKEN_PRICES",
]
