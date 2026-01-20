"""
Data Event Handler for Automatic Synchronization

Handles events from the main system and triggers automatic PostgreSQL synchronization.
This ensures data stays current without user interaction.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


class DataEventHandler:
    """
    Handles data change events and triggers synchronization.

    Listens for events from the main Ideaspace system and automatically
    syncs changes to PostgreSQL in the background.
    """

    def __init__(self):
        self._initialized = False
        self._sync_engine = None

    async def initialize(self):
        """Initialize the event handler."""
        if self._initialized:
            return

        try:
            from swarm.tools.data_sync_engine import DataSyncEngine
            self._sync_engine = DataSyncEngine()
            await self._sync_engine._ensure_initialized()
            self._initialized = True
            logger.info("Data event handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize data event handler: {e}")
            raise

    async def handle_bubble_created(self, bubble_data: Dict[str, Any]):
        """
        Handle bubble creation event.

        Args:
            bubble_data: The created bubble data
        """
        try:
            await self.initialize()
            bubble_id = bubble_data.get('id')
            if bubble_id:
                await self._sync_engine.sync_bubble_async(str(bubble_id))
                logger.info(f"Auto-synced created bubble {bubble_id}")
        except Exception as e:
            logger.error(f"Failed to sync created bubble: {e}")

    async def handle_bubble_updated(self, bubble_data: Dict[str, Any]):
        """
        Handle bubble update event.

        Args:
            bubble_data: The updated bubble data
        """
        try:
            await self.initialize()
            bubble_id = bubble_data.get('id')
            if bubble_id:
                await self._sync_engine.sync_bubble_async(str(bubble_id))
                logger.info(f"Auto-synced updated bubble {bubble_id}")
        except Exception as e:
            logger.error(f"Failed to sync updated bubble: {e}")

    async def handle_idea_created(self, idea_data: Dict[str, Any]):
        """
        Handle idea creation event.

        Args:
            idea_data: The created idea data
        """
        try:
            await self.initialize()
            idea_id = idea_data.get('id')
            bubble_id = idea_data.get('bubble_id')
            if idea_id and bubble_id:
                await self._sync_engine.sync_idea_async(str(idea_id), str(bubble_id))
                logger.info(f"Auto-synced created idea {idea_id}")
        except Exception as e:
            logger.error(f"Failed to sync created idea: {e}")

    async def handle_idea_updated(self, idea_data: Dict[str, Any]):
        """
        Handle idea update event.

        Args:
            idea_data: The updated idea data
        """
        try:
            await self.initialize()
            idea_id = idea_data.get('id')
            bubble_id = idea_data.get('bubble_id')
            if idea_id and bubble_id:
                await self._sync_engine.sync_idea_async(str(idea_id), str(bubble_id))
                logger.info(f"Auto-synced updated idea {idea_id}")
        except Exception as e:
            logger.error(f"Failed to sync updated idea: {e}")

    async def handle_edge_created(self, edge_data: Dict[str, Any]):
        """
        Handle edge creation event.

        Args:
            edge_data: The created edge data
        """
        try:
            await self.initialize()
            edge_id = edge_data.get('id')
            bubble_id = edge_data.get('bubble_id')
            if edge_id and bubble_id:
                await self._sync_engine.sync_edge_async(str(edge_id), str(bubble_id))
                logger.info(f"Auto-synced created edge {edge_id}")
        except Exception as e:
            logger.error(f"Failed to sync created edge: {e}")

    async def handle_edge_deleted(self, edge_data: Dict[str, Any]):
        """
        Handle edge deletion event.

        Args:
            edge_data: The deleted edge data
        """
        try:
            await self.initialize()
            edge_id = edge_data.get('id')
            bubble_id = edge_data.get('bubble_id')
            if edge_id and bubble_id:
                # For deletions, we mark as deleted in PostgreSQL
                # The actual deletion logic would need to be implemented in the sync engine
                logger.info(f"Auto-handled deleted edge {edge_id}")
        except Exception as e:
            logger.error(f"Failed to handle deleted edge: {e}")

    async def handle_bubble_deleted(self, bubble_data: Dict[str, Any]):
        """
        Handle bubble deletion event.

        Args:
            bubble_data: The deleted bubble data
        """
        try:
            await self.initialize()
            bubble_id = bubble_data.get('id')
            if bubble_id:
                # Mark bubble as deleted in PostgreSQL
                # The actual deletion logic would need to be implemented in the sync engine
                logger.info(f"Auto-handled deleted bubble {bubble_id}")
        except Exception as e:
            logger.error(f"Failed to handle deleted bubble: {e}")

    async def handle_periodic_cleanup(self):
        """
        Handle periodic cleanup tasks.

        Called by a scheduler to perform maintenance tasks.
        """
        try:
            await self.initialize()
            await self._sync_engine.cleanup_deleted_async()
            await self._sync_engine.rebuild_search_index_async()
            logger.info("Completed periodic data cleanup")
        except Exception as e:
            logger.error(f"Failed periodic cleanup: {e}")


# Global event handler instance
_event_handler = None

async def get_event_handler() -> DataEventHandler:
    """Get the global event handler instance."""
    global _event_handler
    if _event_handler is None:
        _event_handler = DataEventHandler()
        await _event_handler.initialize()
    return _event_handler

# Convenience functions for easy integration
async def on_bubble_created(bubble_data: Dict[str, Any]):
    """Event handler for bubble creation."""
    handler = await get_event_handler()
    await handler.handle_bubble_created(bubble_data)

async def on_bubble_updated(bubble_data: Dict[str, Any]):
    """Event handler for bubble updates."""
    handler = await get_event_handler()
    await handler.handle_bubble_updated(bubble_data)

async def on_idea_created(idea_data: Dict[str, Any]):
    """Event handler for idea creation."""
    handler = await get_event_handler()
    await handler.handle_idea_created(idea_data)

async def on_idea_updated(idea_data: Dict[str, Any]):
    """Event handler for idea updates."""
    handler = await get_event_handler()
    await handler.handle_idea_updated(idea_data)

async def on_edge_created(edge_data: Dict[str, Any]):
    """Event handler for edge creation."""
    handler = await get_event_handler()
    await handler.handle_edge_created(edge_data)

async def on_edge_deleted(edge_data: Dict[str, Any]):
    """Event handler for edge deletion."""
    handler = await get_event_handler()
    await handler.handle_edge_deleted(edge_data)

async def on_bubble_deleted(bubble_data: Dict[str, Any]):
    """Event handler for bubble deletion."""
    handler = await get_event_handler()
    await handler.handle_bubble_deleted(bubble_data)

async def periodic_cleanup():
    """Periodic cleanup function."""
    handler = await get_event_handler()
    await handler.handle_periodic_cleanup()


__all__ = [
    "DataEventHandler",
    "get_event_handler",
    "on_bubble_created",
    "on_bubble_updated",
    "on_idea_created",
    "on_idea_updated",
    "on_edge_created",
    "on_edge_deleted",
    "on_bubble_deleted",
    "periodic_cleanup",
]