"""
ZeroClaw Integration - Research Space Backend

Manages ZeroClaw as a subprocess and provides an async HTTP client
for communicating with its gateway.
"""

from .process_manager import ZeroClawProcessManager, get_zeroclaw_manager
from .client import ZeroClawClient, get_zeroclaw_client

__all__ = [
    "ZeroClawProcessManager",
    "get_zeroclaw_manager",
    "ZeroClawClient",
    "get_zeroclaw_client",
]
