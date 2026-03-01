"""
VibeMind → Rowboat Publishing Module

Publishes space metadata to Rowboat's knowledge graph (~/.rowboat/).
Each space has a publisher that writes JSON manifests and
Rowboat-native markdown notes.

Usage:
    from publishing import get_ideas_publisher
    get_ideas_publisher().publish_bubble(bubble_id="abc123")

All publishing is fire-and-forget. Import errors or missing
~/.rowboat/ gracefully degrade to no-ops.
"""

from .config import is_publishing_enabled, is_space_enabled

# Singleton instances
_ideas_publisher = None
_swe_design_publisher = None
_arch_team_publisher = None
_coding_publisher = None


def get_ideas_publisher():
    """Get the Ideas → Rowboat publisher (singleton)."""
    global _ideas_publisher
    if _ideas_publisher is None:
        if not is_space_enabled("ideas"):
            return _NoOpPublisher()
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
