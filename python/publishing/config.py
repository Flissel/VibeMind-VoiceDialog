"""
Publishing configuration.

Reads from .env to determine which spaces publish to Rowboat
and whether to use the MongoDB publisher (direct DB writes)
or the filesystem publisher (fallback).
"""

import os


def is_publishing_enabled() -> bool:
    """Check if Rowboat publishing is globally enabled."""
    return os.getenv("ROWBOAT_PUBLISH_ENABLED", "false").lower() in ("true", "1", "yes")


def is_space_enabled(space: str) -> bool:
    """Check if publishing is enabled for a specific space."""
    if not is_publishing_enabled():
        return False
    key = f"ROWBOAT_PUBLISH_{space.upper()}"
    # Default to True if global is enabled and no per-space override
    return os.getenv(key, "true").lower() in ("true", "1", "yes")


def is_mongo_enabled() -> bool:
    """Check if MongoDB publishing is enabled.

    Requires ROWBOAT_PROJECT_ID set. Enabled by default when
    publishing is enabled. Set ROWBOAT_PUBLISH_MONGO=false to
    force filesystem-only publishing.
    """
    if os.getenv("ROWBOAT_PUBLISH_MONGO", "true").lower() not in ("true", "1", "yes"):
        return False
    if not os.getenv("ROWBOAT_PROJECT_ID", ""):
        return False
    return True
