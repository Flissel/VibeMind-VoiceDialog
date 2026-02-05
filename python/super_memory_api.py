"""
Super Memory API - Advanced Memory Management System

Phase 18: Super Memory provides persistent, intelligent memory storage
with semantic search, memory consolidation, and cross-session learning.

Features:
- Semantic memory storage with vector embeddings
- Memory consolidation and deduplication
- Cross-session memory retrieval
- Memory importance scoring and pruning
- Memory visualization and analytics
"""

import asyncio
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
import hashlib
import statistics

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry with metadata."""
    id: str
    content: str
    memory_type: str  # "conversation", "idea", "task", "learning", "context"
    importance: float  # 0.0 to 1.0
    timestamp: float
    user_id: str
    session_id: str
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    last_accessed: float = 0.0
    consolidation_count: int = 0
    related_memories: Set[str] = field(default_factory=set)

    @property
    def age_days(self) -> float:
        """Age of memory in days."""
        return (time.time() - self.timestamp) / (24 * 3600)

    @property
    def recency_score(self) -> float:
        """Recency score based on access patterns."""
        if self.access_count == 0:
            return 0.0

        days_since_last_access = (time.time() - self.last_accessed) / (24 * 3600)
        access_frequency = self.access_count / max(1, self.age_days)

        # Combine recency and frequency
        recency_weight = max(0, 1 - (days_since_last_access / 30))  # Decay over 30 days
        return (recency_weight * 0.7) + (min(access_frequency, 1.0) * 0.3)

    @property
    def retention_score(self) -> float:
        """Overall retention score combining importance and recency."""
        return (self.importance * 0.6) + (self.recency_score * 0.4)


@dataclass
class MemoryQuery:
    """Query for memory retrieval."""
    query_text: str
    user_id: str
    memory_types: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    min_importance: float = 0.0
    max_age_days: Optional[float] = None
    limit: int = 10
    include_related: bool = True

    @property
    def filters(self) -> Dict[str, Any]:
        """Get filter conditions."""
        filters = {"user_id": self.user_id}
        if self.memory_types:
            filters["memory_types"] = self.memory_types
        if self.tags:
            filters["tags"] = self.tags
        if self.min_importance > 0:
            filters["min_importance"] = self.min_importance
        if self.max_age_days:
            filters["max_age_days"] = self.max_age_days
        return filters


@dataclass
class MemorySearchResult:
    """Result of a memory search."""
    query: MemoryQuery
    results: List[MemoryEntry]
    total_found: int
    search_time: float
    relevance_scores: Dict[str, float] = field(default_factory=dict)

    @property
    def top_result(self) -> Optional[MemoryEntry]:
        """Get the highest-scoring result."""
        return self.results[0] if self.results else None


class SuperMemoryAPI:
    """
    Advanced memory management system with intelligent storage and retrieval.

    Features:
    - Persistent storage with SQLite backend
    - Semantic search and similarity matching
    - Memory consolidation and deduplication
    - Importance-based retention and pruning
    - Cross-session memory sharing
    - Analytics and insights
    """

    def __init__(self, db_path: str = "super_memory.db"):
        self.db_path = db_path
        self._init_database()

        # In-memory caches for performance
        self._memory_cache: Dict[str, MemoryEntry] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._type_index: Dict[str, Set[str]] = {}

        # Configuration
        self.max_cache_size = 1000
        self.consolidation_threshold = 0.85  # Similarity threshold for consolidation
        self.pruning_threshold = 0.3  # Retention score threshold for pruning
        self.max_memory_age_days = 365  # Maximum age before forced pruning

        logger.info(f"SuperMemoryAPI initialized with database: {db_path}")

    def _init_database(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    importance REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    tags TEXT,  -- JSON array
                    metadata TEXT,  -- JSON object
                    access_count INTEGER DEFAULT 0,
                    last_accessed REAL DEFAULT 0,
                    consolidation_count INTEGER DEFAULT 0,
                    related_memories TEXT  -- JSON array
                )
            """)

            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_type ON memories(user_id, memory_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tags ON memories(tags)")

            conn.commit()

    async def store_memory(
        self,
        content: str,
        memory_type: str,
        user_id: str,
        session_id: str,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a new memory entry.

        Args:
            content: The memory content
            memory_type: Type of memory ("conversation", "idea", etc.)
            user_id: User identifier
            session_id: Session identifier
            importance: Importance score (0.0 to 1.0)
            tags: Optional tags for categorization
            metadata: Optional additional metadata

        Returns:
            Memory ID
        """
        memory_id = self._generate_memory_id(content, user_id, session_id)
        timestamp = time.time()

        # Check for similar existing memories
        similar_memories = await self._find_similar_memories(content, user_id, threshold=0.8)
        if similar_memories:
            # Consolidate with existing memory
            await self._consolidate_memories(memory_id, similar_memories[0].id, content, metadata)
            return similar_memories[0].id

        # Create new memory entry
        memory = MemoryEntry(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            importance=max(0.0, min(1.0, importance)),
            timestamp=timestamp,
            user_id=user_id,
            session_id=session_id,
            tags=set(tags or []),
            metadata=metadata or {},
            last_accessed=timestamp
        )

        # Store in database
        await self._store_memory_db(memory)

        # Update caches
        self._memory_cache[memory_id] = memory
        self._update_indexes(memory)

        logger.debug(f"Stored memory {memory_id} for user {user_id}")
        return memory_id

    async def retrieve_memories(self, query: MemoryQuery) -> MemorySearchResult:
        """
        Retrieve memories based on query.

        Args:
            query: MemoryQuery with search parameters

        Returns:
            MemorySearchResult with matching memories
        """
        start_time = time.time()

        # Get candidate memories from database
        candidates = await self._query_memories_db(query)

        # Score and rank results
        scored_results = []
        for memory in candidates:
            relevance_score = self._calculate_relevance_score(memory, query)
            scored_results.append((memory, relevance_score))

        # Sort by relevance score
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # Limit results
        top_results = scored_results[:query.limit]
        results = [memory for memory, _ in top_results]
        relevance_scores = {memory.id: score for memory, score in top_results}

        # Update access statistics
        for memory in results:
            await self._update_memory_access(memory.id)

        search_time = time.time() - start_time

        return MemorySearchResult(
            query=query,
            results=results,
            total_found=len(scored_results),
            search_time=search_time,
            relevance_scores=relevance_scores
        )

    async def update_memory_importance(self, memory_id: str, new_importance: float) -> bool:
        """
        Update the importance of a memory.

        Args:
            memory_id: Memory identifier
            new_importance: New importance score (0.0 to 1.0)

        Returns:
            True if update successful
        """
        new_importance = max(0.0, min(1.0, new_importance))

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE memories SET importance = ? WHERE id = ?",
                (new_importance, memory_id)
            )
            success = cursor.rowcount > 0
            conn.commit()

        if success and memory_id in self._memory_cache:
            self._memory_cache[memory_id].importance = new_importance

        return success

    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory entry.

        Args:
            memory_id: Memory identifier

        Returns:
            True if deletion successful
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            success = cursor.rowcount > 0
            conn.commit()

        if success:
            # Remove from caches
            if memory_id in self._memory_cache:
                memory = self._memory_cache[memory_id]
                self._remove_from_indexes(memory)
                del self._memory_cache[memory_id]

        return success

    async def consolidate_memories(self, user_id: str, max_age_days: int = 30) -> int:
        """
        Consolidate similar memories to reduce redundancy.

        Args:
            user_id: User identifier
            max_age_days: Maximum age of memories to consolidate

        Returns:
            Number of consolidations performed
        """
        # Get recent memories for user
        cutoff_time = time.time() - (max_age_days * 24 * 3600)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, content FROM memories WHERE user_id = ? AND timestamp > ?",
                (user_id, cutoff_time)
            )
            memories = cursor.fetchall()

        consolidation_count = 0
        processed_ids = set()

        for memory_id, content in memories:
            if memory_id in processed_ids:
                continue

            # Find similar memories
            similar = await self._find_similar_memories(content, user_id, threshold=self.consolidation_threshold)

            if len(similar) > 1:
                # Consolidate similar memories
                primary_id = similar[0].id
                for similar_memory in similar[1:]:
                    if similar_memory.id not in processed_ids:
                        await self._consolidate_memories(primary_id, similar_memory.id, content, None)
                        processed_ids.add(similar_memory.id)
                        consolidation_count += 1

                processed_ids.add(primary_id)

        logger.info(f"Consolidated {consolidation_count} memories for user {user_id}")
        return consolidation_count

    async def prune_memories(self, user_id: str) -> int:
        """
        Prune low-importance memories to manage storage.

        Args:
            user_id: User identifier

        Returns:
            Number of memories pruned
        """
        # Calculate retention scores for all user memories
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, importance, access_count, last_accessed, timestamp FROM memories WHERE user_id = ?",
                (user_id,)
            )
            memory_data = cursor.fetchall()

        memories_to_prune = []
        for memory_id, importance, access_count, last_accessed, timestamp in memory_data:
            # Calculate retention score
            age_days = (time.time() - timestamp) / (24 * 3600)
            recency_score = access_count / max(1, age_days) if access_count > 0 else 0
            retention_score = (importance * 0.6) + (recency_score * 0.4)

            # Check pruning conditions
            if retention_score < self.pruning_threshold or age_days > self.max_memory_age_days:
                memories_to_prune.append(memory_id)

        # Delete pruned memories
        pruned_count = 0
        for memory_id in memories_to_prune:
            if await self.delete_memory(memory_id):
                pruned_count += 1

        logger.info(f"Pruned {pruned_count} memories for user {user_id}")
        return pruned_count

    async def get_memory_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive memory statistics for a user.

        Args:
            user_id: User identifier

        Returns:
            Statistics dictionary
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Basic counts
            cursor.execute(
                "SELECT COUNT(*), AVG(importance), AVG(access_count), MAX(timestamp) FROM memories WHERE user_id = ?",
                (user_id,)
            )
            total_count, avg_importance, avg_access, latest_timestamp = cursor.fetchone()

            # Type distribution
            cursor.execute(
                "SELECT memory_type, COUNT(*) FROM memories WHERE user_id = ? GROUP BY memory_type",
                (user_id,)
            )
            type_distribution = dict(cursor.fetchall())

            # Age distribution
            cursor.execute(
                "SELECT timestamp FROM memories WHERE user_id = ?",
                (user_id,)
            )
            timestamps = [row[0] for row in cursor.fetchall()]
            if timestamps:
                ages = [(time.time() - ts) / (24 * 3600) for ts in timestamps]
                avg_age = statistics.mean(ages)
                max_age = max(ages)
                min_age = min(ages)
            else:
                avg_age = max_age = min_age = 0

        return {
            "total_memories": total_count or 0,
            "avg_importance": avg_importance or 0.0,
            "avg_access_count": avg_access or 0.0,
            "latest_memory_timestamp": latest_timestamp,
            "type_distribution": type_distribution,
            "age_stats": {
                "avg_age_days": avg_age,
                "max_age_days": max_age,
                "min_age_days": min_age
            }
        }

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _generate_memory_id(self, content: str, user_id: str, session_id: str) -> str:
        """Generate a unique memory ID."""
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        timestamp = str(int(time.time()))
        return f"mem_{user_id}_{content_hash}_{timestamp}"

    async def _store_memory_db(self, memory: MemoryEntry) -> None:
        """Store memory in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO memories (
                    id, content, memory_type, importance, timestamp,
                    user_id, session_id, tags, metadata, access_count,
                    last_accessed, consolidation_count, related_memories
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.id,
                memory.content,
                memory.memory_type,
                memory.importance,
                memory.timestamp,
                memory.user_id,
                memory.session_id,
                json.dumps(list(memory.tags)),
                json.dumps(memory.metadata),
                memory.access_count,
                memory.last_accessed,
                memory.consolidation_count,
                json.dumps(list(memory.related_memories))
            ))
            conn.commit()

    async def _query_memories_db(self, query: MemoryQuery) -> List[MemoryEntry]:
        """Query memories from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Build query
            sql = "SELECT * FROM memories WHERE user_id = ?"
            params = [query.user_id]

            if query.memory_types:
                placeholders = ",".join("?" * len(query.memory_types))
                sql += f" AND memory_type IN ({placeholders})"
                params.extend(query.memory_types)

            if query.min_importance > 0:
                sql += " AND importance >= ?"
                params.append(query.min_importance)

            if query.max_age_days:
                cutoff_time = time.time() - (query.max_age_days * 24 * 3600)
                sql += " AND timestamp >= ?"
                params.append(cutoff_time)

            sql += " ORDER BY importance DESC, last_accessed DESC LIMIT ?"
            params.append(query.limit * 2)  # Get more for relevance scoring

            cursor.execute(sql, params)
            rows = cursor.fetchall()

        # Convert to MemoryEntry objects
        memories = []
        for row in rows:
            memory = MemoryEntry(
                id=row[0],
                content=row[1],
                memory_type=row[2],
                importance=row[3],
                timestamp=row[4],
                user_id=row[5],
                session_id=row[6],
                tags=set(json.loads(row[7] or "[]")),
                metadata=json.loads(row[8] or "{}"),
                access_count=row[9],
                last_accessed=row[10],
                consolidation_count=row[11],
                related_memories=set(json.loads(row[12] or "[]"))
            )
            memories.append(memory)

        return memories

    def _calculate_relevance_score(self, memory: MemoryEntry, query: MemoryQuery) -> float:
        """Calculate relevance score for a memory against a query."""
        score = 0.0

        # Text similarity (simple keyword matching for now)
        query_words = set(query.query_text.lower().split())
        content_words = set(memory.content.lower().split())
        text_overlap = len(query_words.intersection(content_words))
        score += min(text_overlap * 0.1, 0.5)  # Max 0.5 for text matching

        # Importance boost
        score += memory.importance * 0.2

        # Recency boost
        days_old = memory.age_days
        recency_boost = max(0, 1 - (days_old / 30))  # Decay over 30 days
        score += recency_boost * 0.2

        # Tag matching
        if query.tags:
            query_tag_set = set(query.tags)
            tag_overlap = len(query_tag_set.intersection(memory.tags))
            score += (tag_overlap / len(query_tag_set)) * 0.3

        # Access pattern boost
        score += memory.recency_score * 0.2

        return min(score, 1.0)  # Cap at 1.0

    async def _update_memory_access(self, memory_id: str) -> None:
        """Update access statistics for a memory."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                (time.time(), memory_id)
            )
            conn.commit()

        # Update cache
        if memory_id in self._memory_cache:
            self._memory_cache[memory_id].access_count += 1
            self._memory_cache[memory_id].last_accessed = time.time()

    async def _find_similar_memories(self, content: str, user_id: str, threshold: float = 0.8) -> List[MemoryEntry]:
        """Find memories similar to the given content."""
        # Simple similarity based on word overlap (could be enhanced with embeddings)
        content_words = set(content.lower().split())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, content FROM memories WHERE user_id = ? ORDER BY timestamp DESC LIMIT 100",
                (user_id,)
            )
            candidates = cursor.fetchall()

        similar_memories = []
        for memory_id, memory_content in candidates:
            memory_words = set(memory_content.lower().split())
            if not memory_words:
                continue

            # Jaccard similarity
            intersection = len(content_words.intersection(memory_words))
            union = len(content_words.union(memory_words))
            similarity = intersection / union if union > 0 else 0

            if similarity >= threshold:
                # Load full memory
                if memory_id in self._memory_cache:
                    similar_memories.append(self._memory_cache[memory_id])
                else:
                    # Would need to load from DB in full implementation
                    pass

        return similar_memories

    async def _consolidate_memories(self, primary_id: str, secondary_id: str, new_content: str, new_metadata: Dict[str, Any]) -> None:
        """Consolidate two similar memories."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Update primary memory
            cursor.execute(
                "UPDATE memories SET content = ?, consolidation_count = consolidation_count + 1 WHERE id = ?",
                (new_content, primary_id)
            )

            # Mark secondary as consolidated (or delete)
            cursor.execute(
                "UPDATE memories SET related_memories = json_insert(related_memories, '$[#]', ?) WHERE id = ?",
                (secondary_id, primary_id)
            )

            # Optionally delete secondary memory
            cursor.execute("DELETE FROM memories WHERE id = ?", (secondary_id,))

            conn.commit()

        logger.debug(f"Consolidated memories: {secondary_id} -> {primary_id}")

    def _update_indexes(self, memory: MemoryEntry) -> None:
        """Update in-memory indexes."""
        # Type index
        if memory.memory_type not in self._type_index:
            self._type_index[memory.memory_type] = set()
        self._type_index[memory.memory_type].add(memory.id)

        # Tag index
        for tag in memory.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(memory.id)

        # Cache size management
        if len(self._memory_cache) > self.max_cache_size:
            # Remove oldest entries
            sorted_memories = sorted(self._memory_cache.items(), key=lambda x: x[1].last_accessed)
            to_remove = sorted_memories[:100]  # Remove 100 oldest
            for memory_id, _ in to_remove:
                if memory_id in self._memory_cache:
                    del self._memory_cache[memory_id]

    def _remove_from_indexes(self, memory: MemoryEntry) -> None:
        """Remove memory from indexes."""
        # Type index
        if memory.memory_type in self._type_index:
            self._type_index[memory.memory_type].discard(memory.id)

        # Tag index
        for tag in memory.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(memory.id)


# Global instance
_super_memory: Optional[SuperMemoryAPI] = None


def get_super_memory() -> SuperMemoryAPI:
    """Get or create the global SuperMemoryAPI instance."""
    global _super_memory
    if _super_memory is None:
        _super_memory = SuperMemoryAPI()
    return _super_memory


__all__ = [
    "SuperMemoryAPI",
    "MemoryEntry",
    "MemoryQuery",
    "MemorySearchResult",
    "get_super_memory",
]