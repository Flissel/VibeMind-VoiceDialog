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
from typing import Any, Dict
from .config import is_publishing_enabled, is_space_enabled, is_mongo_enabled

logger = logging.getLogger(__name__)

# Singleton instances
_ideas_publisher = None
_swe_design_publisher = None
_arch_team_publisher = None
_coding_publisher = None
_doc_publisher = None
_openfang_publisher = None
_n8n_publisher = None
_blue_rose_publisher = None
_mirofish_publisher = None


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


def get_doc_publisher():
    """Get the Doc → filesystem publisher (singleton).

    Writes project documentation as Markdown files to ~/.rowboat/docs/.
    """
    global _doc_publisher
    if _doc_publisher is None:
        if not is_publishing_enabled():
            return _NoOpPublisher()
        from .doc_publisher import DocPublisher
        _doc_publisher = DocPublisher()
    return _doc_publisher


def get_openfang_publisher():
    """Get the OpenFang → filesystem publisher (singleton).

    Reads agent definitions from ~/.openfang/agents/ and publishes
    metadata to ~/.rowboat/vibemind/openfang/.
    """
    global _openfang_publisher
    if _openfang_publisher is None:
        if not is_space_enabled("openfang"):
            return _NoOpPublisher()
        from .openfang_publisher import OpenFangPublisher
        _openfang_publisher = OpenFangPublisher()
    return _openfang_publisher


def get_n8n_publisher():
    """Get the n8n → filesystem publisher (singleton).

    Fetches workflows from the n8n REST API and publishes metadata
    to ~/.rowboat/vibemind/n8n/.
    """
    global _n8n_publisher
    if _n8n_publisher is None:
        if not is_space_enabled("n8n"):
            return _NoOpPublisher()
        from .n8n_publisher import N8nPublisher
        _n8n_publisher = N8nPublisher()
    return _n8n_publisher


def get_blue_rose_publisher():
    """Get the Blue Rose (Flowzen) → filesystem publisher (singleton).

    Reads diary / check-ins from FlowzenRepository and publishes
    metadata to ~/.rowboat/vibemind/blue-rose/.
    """
    global _blue_rose_publisher
    if _blue_rose_publisher is None:
        if not is_space_enabled("blue-rose"):
            return _NoOpPublisher()
        from .blue_rose_publisher import BlueRosePublisher
        _blue_rose_publisher = BlueRosePublisher()
    return _blue_rose_publisher


def get_mirofish_publisher():
    """Get the MiroFish → filesystem publisher (singleton).

    Reads project + status from the MiroFish HTTP API and publishes
    metadata to ~/.rowboat/vibemind/mirofish/.
    """
    global _mirofish_publisher
    if _mirofish_publisher is None:
        if not is_space_enabled("mirofish"):
            return _NoOpPublisher()
        from .mirofish_publisher import MiroFishPublisher
        _mirofish_publisher = MiroFishPublisher()
    return _mirofish_publisher


def sync_all_spaces() -> Dict[str, Any]:
    """Mirror every space's source into its ~/.rowboat/vibemind/ folder.

    Each publisher's mirror() clears its space folder and republishes from
    the live source, so the workspace reflects the current state (removed
    objects drop out). Fire-and-forget: a per-space failure is logged and
    does not abort the others.

    Returns a dict {space: result} for diagnostics.
    """
    results: Dict[str, Any] = {}

    if not is_publishing_enabled():
        logger.debug("[Publishing] sync_all_spaces skipped — publishing disabled")
        return results

    mirrors = [
        ("openfang", get_openfang_publisher),
        ("n8n", get_n8n_publisher),
        ("blue-rose", get_blue_rose_publisher),
        ("mirofish", get_mirofish_publisher),
    ]
    for space, getter in mirrors:
        try:
            publisher = getter()
            mirror = getattr(publisher, "mirror", None)
            if callable(mirror):
                results[space] = mirror()
            else:
                results[space] = "no-op"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[Publishing] sync '{space}' failed: {e}")
            results[space] = f"error: {e}"

    # Reverse-cleanup: purge Rowboat MongoDB sources with no matching live
    # bubble (the missing half of the Supabase->Rowboat sync). Hard-delete,
    # guarded: empty-DB-abort + max_delete cap live inside cleanup_orphaned_sources.
    # Kill-switch: VIBEMIND_ROWBOAT_AUTOCLEAN=0 disables the auto path entirely.
    import os as _os
    if _os.getenv("VIBEMIND_ROWBOAT_AUTOCLEAN", "1") not in ("0", "false", "False"):
        try:
            from data import IdeasRepository
            from .rowboat_mongo_publisher import RowboatMongoPublisher
            live_titles = {
                b.title for b in IdeasRepository().list_top_level(limit=10000)
                if getattr(b, "title", None)
            }
            # Ebene 1: RAG-MongoDB-Sources
            rep = RowboatMongoPublisher().cleanup_orphaned_sources(
                live_titles, dry_run=False, max_delete=200
            )
            results["rowboat-cleanup"] = rep
            if rep.get("aborted"):
                logger.warning("[Publishing] rowboat-cleanup aborted: %s", rep["aborted"])
            else:
                logger.info("[Publishing] rowboat-cleanup deleted %s orphaned sources",
                            rep.get("deleted"))
            # Ebene 2: Filesystem-Vault knowledge/Projects/'VibeMind - *'
            from .ideas_publisher import IdeasPublisher
            frep = IdeasPublisher().cleanup_orphaned_project_dirs(
                live_titles, dry_run=False, max_delete=200
            )
            results["rowboat-cleanup-vault"] = frep
            if frep.get("aborted"):
                logger.warning("[Publishing] rowboat-cleanup-vault aborted: %s", frep["aborted"])
            else:
                logger.info("[Publishing] rowboat-cleanup-vault deleted %s orphaned dirs",
                            frep.get("deleted"))
        except Exception as e:  # noqa: BLE001 — cleanup must not break startup sync
            logger.warning(f"[Publishing] rowboat-cleanup failed: {e}")
            results["rowboat-cleanup"] = f"error: {e}"

    logger.info(f"[Publishing] sync_all_spaces: {results}")
    return results


class _NoOpPublisher:
    """Stub publisher when publishing is disabled."""
    def __getattr__(self, name):
        return lambda *a, **kw: None


# Ensure the per-space workspace folders exist on import.
# Fire-and-forget: a filesystem error must never break the import.
try:
    from .base_publisher import BasePublisher as _BasePublisher
    _BasePublisher.ensure_space_dirs()
except Exception as _e:  # noqa: BLE001
    logger.debug(f"[Publishing] ensure_space_dirs skipped: {_e}")
