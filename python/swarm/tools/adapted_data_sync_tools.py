"""
Adapted Data Sync Tools for AutoGen Swarm

Tools for automatic synchronization of Ideaspace data to PostgreSQL.
These run silently in the background without user interaction.
"""

import logging
from typing import Optional, Dict, Any
import sys
from pathlib import Path
import asyncio

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


def sync_bubble_to_postgres(bubble_id: str) -> str:
    """
    Sync a complete bubble and all its contents to PostgreSQL.

    This runs automatically when a bubble is created or modified.
    No user interaction required.

    Args:
        bubble_id: The bubble ID to sync

    Returns:
        Status message (for logging only, not shown to user)
    """
    try:
        from swarm.tools.data_sync_engine import DataSyncEngine
        sync_engine = DataSyncEngine()

        # Run sync asynchronously but don't wait for completion
        asyncio.create_task(sync_engine.sync_bubble_async(bubble_id))

        logger.info(f"Started background sync for bubble {bubble_id}")
        return f"Background sync initiated for bubble {bubble_id}"

    except Exception as e:
        logger.error(f"Failed to start bubble sync for {bubble_id}: {e}")
        return f"Sync failed: {str(e)}"


def sync_idea_to_postgres(idea_id: str, bubble_id: str) -> str:
    """
    Sync a single idea/node to PostgreSQL.

    Called automatically when ideas are created, updated, or deleted.

    Args:
        idea_id: The idea/node ID to sync
        bubble_id: The bubble containing the idea

    Returns:
        Status message (for logging only)
    """
    try:
        from swarm.tools.data_sync_engine import DataSyncEngine
        sync_engine = DataSyncEngine()

        # Run sync asynchronously
        asyncio.create_task(sync_engine.sync_idea_async(idea_id, bubble_id))

        logger.info(f"Started background sync for idea {idea_id} in bubble {bubble_id}")
        return f"Background sync initiated for idea {idea_id}"

    except Exception as e:
        logger.error(f"Failed to start idea sync for {idea_id}: {e}")
        return f"Sync failed: {str(e)}"


def sync_edge_to_postgres(edge_id: str, bubble_id: str) -> str:
    """
    Sync a single edge/connection to PostgreSQL.

    Called automatically when edges are created or deleted.

    Args:
        edge_id: The edge ID to sync
        bubble_id: The bubble containing the edge

    Returns:
        Status message (for logging only)
    """
    try:
        from swarm.tools.data_sync_engine import DataSyncEngine
        sync_engine = DataSyncEngine()

        # Run sync asynchronously
        asyncio.create_task(sync_engine.sync_edge_async(edge_id, bubble_id))

        logger.info(f"Started background sync for edge {edge_id} in bubble {bubble_id}")
        return f"Background sync initiated for edge {edge_id}"

    except Exception as e:
        logger.error(f"Failed to start edge sync for {edge_id}: {e}")
        return f"Sync failed: {str(e)}"


def cleanup_deleted_items() -> str:
    """
    Clean up items marked as deleted in PostgreSQL.

    Runs periodically to maintain data consistency.

    Returns:
        Status message (for logging only)
    """
    try:
        from swarm.tools.data_sync_engine import DataSyncEngine
        sync_engine = DataSyncEngine()

        # Run cleanup asynchronously
        asyncio.create_task(sync_engine.cleanup_deleted_async())

        logger.info("Started background cleanup of deleted items")
        return "Background cleanup initiated"

    except Exception as e:
        logger.error(f"Failed to start cleanup: {e}")
        return f"Cleanup failed: {str(e)}"


def rebuild_search_index() -> str:
    """
    Rebuild the full-text search index in PostgreSQL.

    Called after bulk operations or periodically.

    Returns:
        Status message (for logging only)
    """
    try:
        from swarm.tools.data_sync_engine import DataSyncEngine
        sync_engine = DataSyncEngine()

        # Run index rebuild asynchronously
        asyncio.create_task(sync_engine.rebuild_search_index_async())

        logger.info("Started background search index rebuild")
        return "Background index rebuild initiated"

    except Exception as e:
        logger.error(f"Failed to start index rebuild: {e}")
        return f"Index rebuild failed: {str(e)}"


# Collect all sync tools for export
DATA_SYNC_TOOLS = [
    sync_bubble_to_postgres,
    sync_idea_to_postgres,
    sync_edge_to_postgres,
    cleanup_deleted_items,
    rebuild_search_index,
]


__all__ = [
    "sync_bubble_to_postgres",
    "sync_idea_to_postgres",
    "sync_edge_to_postgres",
    "cleanup_deleted_items",
    "rebuild_search_index",
    "DATA_SYNC_TOOLS",
]