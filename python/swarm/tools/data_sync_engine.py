"""
Data Sync Engine for PostgreSQL Synchronization

Handles the actual synchronization of Ideaspace data to PostgreSQL.
Runs asynchronously in the background without blocking user interactions.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

# Check if asyncpg is available (optional dependency for PostgreSQL sync)
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logger.info("asyncpg not installed - PostgreSQL sync disabled")


class DataSyncEngine:
    """
    Engine for synchronizing Ideaspace data to PostgreSQL.

    Handles connections, schema management, and data synchronization.
    All operations are asynchronous to avoid blocking user interactions.
    """

    def __init__(self):
        self._connection_string = None
        self._pool = None
        self._initialized = False

    async def _ensure_initialized(self):
        """Ensure PostgreSQL connection and schema are ready."""
        if self._initialized:
            return

        # Skip if asyncpg is not available
        if not ASYNCPG_AVAILABLE:
            logger.debug("PostgreSQL sync skipped - asyncpg not installed")
            return

        try:
            # Get PostgreSQL connection from environment
            import os
            host = os.getenv('POSTGRES_HOST', 'localhost')
            port = os.getenv('POSTGRES_PORT', '5432')
            database = os.getenv('POSTGRES_DB', 'vibemind')
            user = os.getenv('POSTGRES_USER', 'vibemind')
            password = os.getenv('POSTGRES_PASSWORD', '')

            if not password:
                logger.warning("POSTGRES_PASSWORD not set, using empty password")

            self._connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"

            # Create connection pool (asyncpg already imported at module level)
            self._pool = await asyncpg.create_pool(
                self._connection_string,
                min_size=1,
                max_size=10,
                command_timeout=60
            )

            # Ensure schema exists
            await self._ensure_schema()

            self._initialized = True
            logger.info("Data sync engine initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize data sync engine: {e}")
            raise

    async def _ensure_schema(self):
        """Create necessary tables if they don't exist."""
        schema_sql = """
        -- Ideaspace data schema for PostgreSQL

        CREATE TABLE IF NOT EXISTS bubbles (
            id UUID PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            color TEXT,
            position_x REAL,
            position_y REAL,
            position_z REAL,
            radius REAL DEFAULT 1.0,
            space_type TEXT DEFAULT 'ideas',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            is_deleted BOOLEAN DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS ideas (
            id UUID PRIMARY KEY,
            bubble_id UUID REFERENCES bubbles(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            content TEXT,
            idea_type TEXT DEFAULT 'note',
            position_x REAL,
            position_y REAL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            is_deleted BOOLEAN DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS edges (
            id UUID PRIMARY KEY,
            bubble_id UUID REFERENCES bubbles(id) ON DELETE CASCADE,
            source_id UUID NOT NULL,
            target_id UUID NOT NULL,
            edge_type TEXT DEFAULT 'related',
            weight REAL DEFAULT 1.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            is_deleted BOOLEAN DEFAULT FALSE,
            UNIQUE(bubble_id, source_id, target_id, edge_type)
        );

        CREATE TABLE IF NOT EXISTS metadata (
            id UUID PRIMARY KEY,
            entity_type TEXT NOT NULL, -- 'bubble', 'idea', 'edge'
            entity_id UUID NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(entity_type, entity_id, key)
        );

        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_bubbles_space_type ON bubbles(space_type) WHERE NOT is_deleted;
        CREATE INDEX IF NOT EXISTS idx_bubbles_updated ON bubbles(updated_at DESC) WHERE NOT is_deleted;
        CREATE INDEX IF NOT EXISTS idx_ideas_bubble ON ideas(bubble_id) WHERE NOT is_deleted;
        CREATE INDEX IF NOT EXISTS idx_ideas_updated ON ideas(updated_at DESC) WHERE NOT is_deleted;
        CREATE INDEX IF NOT EXISTS idx_edges_bubble ON edges(bubble_id) WHERE NOT is_deleted;
        CREATE INDEX IF NOT EXISTS idx_metadata_entity ON metadata(entity_type, entity_id);

        -- Full-text search setup
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
        CREATE INDEX IF NOT EXISTS idx_ideas_search ON ideas USING gin(to_tsvector('english', title || ' ' || coalesce(content, '')))
            WHERE NOT is_deleted;
        """

        async with self._pool.acquire() as conn:
            await conn.execute(schema_sql)
            logger.info("Database schema ensured")

    async def sync_bubble_async(self, bubble_id: str):
        """
        Synchronize a complete bubble to PostgreSQL.

        Args:
            bubble_id: The bubble ID to sync
        """
        try:
            await self._ensure_initialized()

            # Skip if PostgreSQL not available
            if not self._pool:
                return

            # Get bubble data from the main system
            from tools.bubble_tools import get_bubble as _get_bubble
            bubble_data = _get_bubble({"bubble_id": bubble_id})

            if not bubble_data:
                logger.warning(f"Bubble {bubble_id} not found, skipping sync")
                return

            async with self._pool.acquire() as conn:
                # Upsert bubble data
                await conn.execute("""
                    INSERT INTO bubbles (id, title, description, color, position_x, position_y, position_z,
                                       radius, space_type, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        color = EXCLUDED.color,
                        position_x = EXCLUDED.position_x,
                        position_y = EXCLUDED.position_y,
                        position_z = EXCLUDED.position_z,
                        radius = EXCLUDED.radius,
                        space_type = EXCLUDED.space_type,
                        updated_at = NOW(),
                        is_deleted = FALSE
                """,
                bubble_data.get('id'),
                bubble_data.get('title'),
                bubble_data.get('description'),
                bubble_data.get('color'),
                bubble_data.get('position', {}).get('x'),
                bubble_data.get('position', {}).get('y'),
                bubble_data.get('position', {}).get('z'),
                bubble_data.get('radius', 1.0),
                bubble_data.get('space_type', 'ideas')
                )

            logger.info(f"Synced bubble {bubble_id} to PostgreSQL")

        except Exception as e:
            logger.error(f"Failed to sync bubble {bubble_id}: {e}")

    async def sync_idea_async(self, idea_id: str, bubble_id: str):
        """
        Synchronize a single idea to PostgreSQL.

        Args:
            idea_id: The idea ID to sync
            bubble_id: The bubble containing the idea
        """
        try:
            await self._ensure_initialized()

            # Skip if PostgreSQL not available
            if not self._pool:
                return

            # Get idea data from the main system
            from tools.idea_tools import get_idea as _get_idea
            idea_data = _get_idea({"idea_id": idea_id})

            if not idea_data:
                logger.warning(f"Idea {idea_id} not found, skipping sync")
                return

            async with self._pool.acquire() as conn:
                # Upsert idea data
                await conn.execute("""
                    INSERT INTO ideas (id, bubble_id, title, content, idea_type,
                                     position_x, position_y, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        bubble_id = EXCLUDED.bubble_id,
                        title = EXCLUDED.title,
                        content = EXCLUDED.content,
                        idea_type = EXCLUDED.idea_type,
                        position_x = EXCLUDED.position_x,
                        position_y = EXCLUDED.position_y,
                        updated_at = NOW(),
                        is_deleted = FALSE
                """,
                idea_data.get('id'),
                bubble_id,
                idea_data.get('title'),
                idea_data.get('content'),
                idea_data.get('type', 'note'),
                idea_data.get('position', {}).get('x'),
                idea_data.get('position', {}).get('y')
                )

            logger.info(f"Synced idea {idea_id} to PostgreSQL")

        except Exception as e:
            logger.error(f"Failed to sync idea {idea_id}: {e}")

    async def sync_edge_async(self, edge_id: str, bubble_id: str):
        """
        Synchronize a single edge to PostgreSQL.

        Args:
            edge_id: The edge ID to sync
            bubble_id: The bubble containing the edge
        """
        try:
            await self._ensure_initialized()

            # Skip if PostgreSQL not available
            if not self._pool:
                return

            # Get edge data from the main system
            from tools.idea_tools import get_edge as _get_edge
            edge_data = _get_edge({"edge_id": edge_id})

            if not edge_data:
                logger.warning(f"Edge {edge_id} not found, skipping sync")
                return

            async with self._pool.acquire() as conn:
                # Upsert edge data
                await conn.execute("""
                    INSERT INTO edges (id, bubble_id, source_id, target_id, edge_type, weight, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        bubble_id = EXCLUDED.bubble_id,
                        source_id = EXCLUDED.source_id,
                        target_id = EXCLUDED.target_id,
                        edge_type = EXCLUDED.edge_type,
                        weight = EXCLUDED.weight,
                        updated_at = NOW(),
                        is_deleted = FALSE
                """,
                edge_data.get('id'),
                bubble_id,
                edge_data.get('source_id'),
                edge_data.get('target_id'),
                edge_data.get('type', 'related'),
                edge_data.get('weight', 1.0)
                )

            logger.info(f"Synced edge {edge_id} to PostgreSQL")

        except Exception as e:
            logger.error(f"Failed to sync edge {edge_id}: {e}")

    async def cleanup_deleted_async(self):
        """
        Clean up items marked as deleted in the main system.
        This maintains referential integrity in PostgreSQL.
        """
        try:
            await self._ensure_initialized()

            # This would need to be implemented based on how deletions are tracked
            # in the main system. For now, just log that cleanup ran.
            logger.info("Cleanup completed (placeholder implementation)")

        except Exception as e:
            logger.error(f"Failed to cleanup deleted items: {e}")

    async def rebuild_search_index_async(self):
        """
        Rebuild the full-text search index.
        PostgreSQL handles this automatically with the gin index we created.
        """
        try:
            await self._ensure_initialized()

            async with self._pool.acquire() as conn:
                # Reindex the search index
                await conn.execute("REINDEX INDEX idx_ideas_search")
                logger.info("Search index rebuilt")

        except Exception as e:
            logger.error(f"Failed to rebuild search index: {e}")

    async def close(self):
        """Close the database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("Data sync engine closed")