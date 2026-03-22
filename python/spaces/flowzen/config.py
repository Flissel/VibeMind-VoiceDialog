"""Flowzen configuration."""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class FlowzenConfig:
    """Configuration for the Blaue Rose activity tracker."""
    enabled: bool = False
    summary_interval_minutes: int = 30
    default_mood: str = "calm"

    @classmethod
    def from_env(cls) -> "FlowzenConfig":
        return cls(
            enabled=os.getenv("FLOWZEN_ENABLED", "false").lower() == "true",
            summary_interval_minutes=int(os.getenv("FLOWZEN_SUMMARY_INTERVAL", "30")),
            default_mood=os.getenv("FLOWZEN_DEFAULT_MOOD", "calm"),
        )


_config: Optional[FlowzenConfig] = None


def get_config() -> FlowzenConfig:
    global _config
    if _config is None:
        _config = FlowzenConfig.from_env()
    return _config
