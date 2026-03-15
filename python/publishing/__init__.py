"""
VibeMind → Rowboat Publishing Module

Publishes space metadata to Rowboat's knowledge base.

Two backends:
1. MongoDB (preferred) — writes directly into Rowboat's DB so the
   rag-worker automatically chunks, embeds, and indexes content.
2. Filesystem (fallback) — writes to ~/.rowboat/ for Graph Builder.

The MongoDB publisher includes a schema semaphore that validates
compatibility on every write. If the schema changes, it disables
itself and falls back to filesystem publishing automatically.

Usage:
    from publishing import get_ideas_publisher
    get_ideas_publisher().publish_bubble(bubble_id="abc123")

All publishing is fire-and-forget. Import errors or missing
dependencies gracefully degrade to no-ops.
"""

import logging
from .config import is_publishing_enabled, is_space_enabled, is_mongo_enabled

logger = logging.getLogger(__name__)

# Singleton instances
_ideas_publisher = None
_swe_design_publisher = None
_arch_team_publisher = None
_coding_publisher = None


def _try_create_mongo_publisher():
    """Try to create a MongoDB publisher. Returns None on failure."""
    if not is_mongo_enabled():
        return None
    try:
        from .rowboat_mongo_publisher import RowboatMongoPublisher
        pub = RowboatMongoPublisher()
        if pub.is_available:
            logger.info("[Publishing] Using MongoDB publisher (direct DB)")
            return pub
        logger.warning("[Publishing] MongoDB schema check failed, using filesystem")
        return None
    except Exception as e:
        logger.warning(f"[Publishing] MongoDB publisher unavailable: {e}")
        return None


def get_ideas_publisher():
    """Get the Ideas → Rowboat publisher (singleton).

    Priority: MongoDB → Filesystem → NoOp
    """
    global _ideas_publisher
    if _ideas_publisher is None:
        if not is_space_enabled("ideas"):
            return _NoOpPublisher()
        # Try MongoDB first
        mongo = _try_create_mongo_publisher()
        if mongo:
            _ideas_publisher = mongo
        else:
            from .ideas_publisher import IdeasPublisher
            _ideas_publisher = IdeasPublisher()
    return _ideas_publisher


def get_swe_design_publisher():
    """Get the SWE Design → Rowboat publisher (singleton)."""
    global _swe_design_publisher
    if _swe_design_publisher is None:
        if not is_space_enabled("swe_design"):
            return _NoOpPublisher()
        from .swe_design_publisher import SweDesignPublisher
        _swe_design_publisher = SweDesignPublisher()
    return _swe_design_publisher


def get_arch_team_publisher():
    """Get the Arch-Team → Rowboat publisher (singleton)."""
    global _arch_team_publisher
    if _arch_team_publisher is None:
        if not is_space_enabled("arch_team"):
            return _NoOpPublisher()
        from .arch_team_publisher import ArchTeamPublisher
        _arch_team_publisher = ArchTeamPublisher()
    return _arch_team_publisher


def get_coding_publisher():
    """Get the Coding Engine → Rowboat publisher (singleton)."""
    global _coding_publisher
    if _coding_publisher is None:
        if not is_space_enabled("coding"):
            return _NoOpPublisher()
        from .coding_publisher import CodingPublisher
        _coding_publisher = CodingPublisher()
    return _coding_publisher


class _NoOpPublisher:
    """Stub publisher when publishing is disabled."""
    def __getattr__(self, name):
        return lambda *a, **kw: None
