"""Ideas Repository — CRUD operations for Ideas/Bubbles."""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from .database import Database, get_database
from .models import Idea
from .repository_utils import generate_id, normalize_text, _levenshtein

logger = logging.getLogger(__name__)


class IdeasRepository:
    """Repository for Idea CRUD operations"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    def create(
        self,
        title: str,
        description: str = "",
        source: str = "voice",
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> Idea:
        """
        Create a new idea.

        Args:
            title: Brief title for the idea
            description: Detailed description
            source: Origin of idea ("voice" or "text")
            tags: List of tags for categorization
            metadata: Additional metadata

        Returns:
            Created Idea object
        """
        idea = Idea(
            id=generate_id(),
            title=title,
            description=description,
            source=source,
            created_at=datetime.now(),
            tags=tags or [],
            metadata=metadata or {},
        )

        data = idea.to_dict()
        self.db.execute(
            """
            INSERT INTO ideas (id, title, description, source, created_at, score, status, promoted_to_project_id, tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["title"],
                data["description"],
                data["source"],
                data["created_at"],
                data["score"],
                data["status"],
                data["promoted_to_project_id"],
                data["tags"],
                data["metadata"],
            ),
        )

        return idea

    def get(self, idea_id: str) -> Optional[Idea]:
        """Get idea by ID"""
        row = self.db.fetch_one("SELECT * FROM ideas WHERE id = ?", (idea_id,))
        return Idea.from_dict(dict(row)) if row else None

    def get_by_title(self, title: str) -> Optional[Idea]:
        """Get idea by title (case-insensitive partial match)"""
        row = self.db.fetch_one(
            "SELECT * FROM ideas WHERE LOWER(title) LIKE LOWER(?) LIMIT 1",
            (f"%{title}%",)
        )
        return Idea.from_dict(dict(row)) if row else None

    def get_by_title_fuzzy(self, title: str, parent_id: Optional[str] = None) -> Optional[Idea]:
        """
        Semantic fuzzy title search for voice input.

        Matching tiers (first match wins):
        1. Normalized substring (accent-insensitive)
        2. Spaceless match ("Test 2" ↔ "test2", "Testkontext" ↔ "Test Kontext")
        3. Levenshtein distance (edit distance ≤ 2 for short, ≤ 3 for long)

        Args:
            title: Title to search for (may contain ASR artifacts)
            parent_id: If provided, only search within this parent (None = top-level spaces)

        Returns:
            Matching Idea or None
        """
        logger.debug("get_by_title_fuzzy: title=%s parent_id=%s", title, parent_id)
        normalized_query = normalize_text(title)
        spaceless_query = normalized_query.replace(" ", "")

        # Fetch candidates based on parent_id
        if parent_id is None:
            rows = self.db.fetch_all("SELECT * FROM ideas WHERE parent_id IS NULL")
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM ideas WHERE parent_id = ?",
                (parent_id,)
            )

        best_lev_match = None
        best_lev_distance = float('inf')

        for row in rows:
            row_title = row['title'] if row['title'] else ''
            normalized_title = normalize_text(row_title)
            spaceless_title = normalized_title.replace(" ", "")

            # Tier 1: Normalized substring match
            if normalized_query in normalized_title or normalized_title in normalized_query:
                return Idea.from_dict(dict(row))

            # Tier 2: Spaceless match ("Test 2" ↔ "test2")
            if spaceless_query in spaceless_title or spaceless_title in spaceless_query:
                return Idea.from_dict(dict(row))

            # Tier 3: Levenshtein distance (collect best candidate)
            dist = _levenshtein(spaceless_query, spaceless_title)
            if dist < best_lev_distance:
                best_lev_distance = dist
                best_lev_match = row

        # Accept Levenshtein match if close enough
        if best_lev_match is not None:
            max_allowed = 2 if len(normalized_query) <= 8 else 3
            if best_lev_distance <= max_allowed:
                return Idea.from_dict(dict(best_lev_match))

        return None

    def list(
        self,
        filter_by: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> List[Idea]:
        """
        List ideas with optional filtering.

        Args:
            filter_by: Text to search in title/description
            status: Filter by status (raw, scored, promoted, archived)
            limit: Maximum number of results
            offset: Skip first N results
            order_by: SQL ORDER BY clause

        Returns:
            List of matching Ideas
        """
        conditions = []
        params = []

        if filter_by:
            conditions.append("(LOWER(title) LIKE LOWER(?) OR LOWER(description) LIKE LOWER(?))")
            params.extend([f"%{filter_by}%", f"%{filter_by}%"])

        if status:
            conditions.append("status = ?")
            params.append(status)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM ideas WHERE {where_clause} ORDER BY {order_by} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.db.fetch_all(sql, tuple(params))
        return [Idea.from_dict(dict(row)) for row in rows]

    def list_top_scored(self, limit: int = 5) -> List[Idea]:
        """Get top scored ideas"""
        return self.list(limit=limit, order_by="score DESC")

    def update(self, idea: Idea) -> Idea:
        """Update an existing idea"""
        # Recalculate score before saving
        idea.score = idea.calculate_score()
        if idea.score > 0:
            idea.status = "scored"

        data = idea.to_dict()
        self.db.execute(
            """
            UPDATE ideas SET
                title = ?,
                description = ?,
                source = ?,
                score = ?,
                status = ?,
                promoted_to_project_id = ?,
                tags = ?,
                metadata = ?
            WHERE id = ?
            """,
            (
                data["title"],
                data["description"],
                data["source"],
                data["score"],
                data["status"],
                data["promoted_to_project_id"],
                data["tags"],
                data["metadata"],
                data["id"],
            ),
        )

        return idea

    def delete(self, idea_id: str) -> bool:
        """Delete an idea by ID"""
        self.db.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
        return True

    def delete_cascade(self, idea_id: str) -> dict:
        """
        Delete an idea with CASCADE deletion of all related content.

        This handles (in order to respect foreign key constraints):
        1. Delete shuttles referencing this idea (bubble_id)
        2. Find projects created from this idea
        3. Delete shuttles referencing those projects (project_id)
        4. Delete projects created from this idea
        5. Delete canvas_edges connected to nodes in this idea
        6. Delete canvas_nodes linked to this idea
        7. Delete the idea itself

        All operations are done in a single transaction to maintain consistency.

        Args:
            idea_id: ID of the idea to delete

        Returns:
            dict: Statistics about what was deleted
        """
        stats = {
            "shuttles_deleted": 0,
            "projects_deleted": 0,
            "edges_deleted": 0,
            "nodes_deleted": 0,
            "idea_deleted": False
        }

        with self.db.connection() as conn:
            try:
                # Step 1: Delete shuttles where bubble_id = idea_id
                cursor = conn.execute(
                    "DELETE FROM shuttles WHERE bubble_id = ?",
                    (idea_id,)
                )
                stats["shuttles_deleted"] += cursor.rowcount

                # Step 2: Find projects created from this idea
                cursor = conn.execute(
                    "SELECT id FROM projects WHERE from_idea_id = ?",
                    (idea_id,)
                )
                project_ids = [row[0] for row in cursor.fetchall()]

                if project_ids:
                    # Step 3: Delete shuttles referencing these projects
                    placeholders = ','.join('?' * len(project_ids))
                    cursor = conn.execute(
                        f"DELETE FROM shuttles WHERE project_id IN ({placeholders})",
                        project_ids
                    )
                    stats["shuttles_deleted"] += cursor.rowcount

                    # Step 4: Delete the projects
                    cursor = conn.execute(
                        f"DELETE FROM projects WHERE id IN ({placeholders})",
                        project_ids
                    )
                    stats["projects_deleted"] = cursor.rowcount

                # Step 5: Find all node IDs linked to this idea
                cursor = conn.execute(
                    "SELECT id FROM canvas_nodes WHERE linked_idea_id = ?",
                    (idea_id,)
                )
                node_ids = [row[0] for row in cursor.fetchall()]

                if node_ids:
                    # Step 6: Delete edges connected to these nodes
                    placeholders = ','.join('?' * len(node_ids))
                    cursor = conn.execute(
                        f"DELETE FROM canvas_edges WHERE from_node_id IN ({placeholders}) OR to_node_id IN ({placeholders})",
                        node_ids + node_ids
                    )
                    stats["edges_deleted"] = cursor.rowcount

                    # Step 7: Delete the nodes themselves
                    cursor = conn.execute(
                        f"DELETE FROM canvas_nodes WHERE id IN ({placeholders})",
                        node_ids
                    )
                    stats["nodes_deleted"] = cursor.rowcount

                # Step 8: Delete the idea
                cursor = conn.execute(
                    "DELETE FROM ideas WHERE id = ?",
                    (idea_id,)
                )
                stats["idea_deleted"] = cursor.rowcount > 0

                conn.commit()

            except Exception as e:
                conn.rollback()
                raise e

        return stats

    def count(self, status: Optional[str] = None) -> int:
        """Count ideas, optionally filtered by status"""
        if status:
            row = self.db.fetch_one("SELECT COUNT(*) FROM ideas WHERE status = ?", (status,))
        else:
            row = self.db.fetch_one("SELECT COUNT(*) FROM ideas")
        return row[0] if row else 0

    def find_by_metadata_key(self, key: str, value: str) -> Optional[Idea]:
        """
        Find idea by metadata key-value pair.

        Useful for finding ideas by source_file, project_id, etc.

        Args:
            key: Metadata key to search for
            value: Value to match

        Returns:
            The matching Idea or None
        """
        rows = self.db.fetch_all("SELECT * FROM ideas")
        for row in rows:
            idea = Idea.from_dict(dict(row))
            if idea.metadata and idea.metadata.get(key) == value:
                return idea
        return None

    def list_by_source(self, source: str) -> List[Idea]:
        """
        List ideas by source field.

        Args:
            source: Source value to filter by (e.g., "req-orchestrator", "voice")

        Returns:
            List of matching Ideas
        """
        rows = self.db.fetch_all(
            "SELECT * FROM ideas WHERE source = ? ORDER BY created_at DESC",
            (source,)
        )
        return [Idea.from_dict(dict(row)) for row in rows]

    def generate_embeddings_for_all_bubbles(self) -> Dict[str, Any]:
        """
        Generate embeddings for all bubbles in the database.

        This function generates embeddings for all bubbles that don't have embeddings yet,
        or whose content has changed (detected by hash mismatch).

        Args:
            None

        Returns:
            dict: Statistics about the embedding generation process
        """
        import logging
        logger = logging.getLogger(__name__)

        # Lazy import to avoid startup overhead if not used
        try:
            from .embedding_service import get_embedding_service, EmbeddingService
        except ImportError:
            logger.warning("[generate_embeddings_for_all_bubbles] embedding_service not available")
            return {"success": False, "error": "embedding_service not available"}

        embedding_service = get_embedding_service()
        if not embedding_service.is_available:
            logger.debug("[generate_embeddings_for_all_bubbles] Embedding service not available")
            return {"success": False, "error": "Embedding service not available"}

        # Get all bubbles (parent_id IS NULL)
        rows = self.db.fetch_all("SELECT * FROM ideas WHERE parent_id IS NULL")
        bubbles = [Idea.from_dict(dict(row)) for row in rows]

        if not bubbles:
            return {"success": True, "total": 0, "generated": 0, "skipped": 0}

        # Generate embeddings for bubbles that need them
        generated = 0
        skipped = 0
        errors = 0

        for bubble in bubbles:
            # Combine title and description for better semantic representation
            content_for_embedding = f"{bubble.title} {bubble.description}".strip()
            current_hash = EmbeddingService.content_hash(content_for_embedding)

            # Check if embedding needs to be generated
            needs_embedding = (
                bubble.embedding_vector is None or
                bubble.embedding_hash != current_hash
            )

            if needs_embedding:
                try:
                    # Generate embedding
                    embedding_vec = embedding_service.embed(content_for_embedding)

                    if embedding_vec is not None:
                        # Update bubble with embedding
                        self.db.execute(
                            "UPDATE ideas SET embedding_vector = ?, embedding_hash = ? WHERE id = ?",
                            (
                                EmbeddingService.vector_to_json(embedding_vec),
                                current_hash,
                                bubble.id
                            )
                        )
                        generated += 1
                        logger.debug(f"[generate_embeddings_for_all_bubbles] Generated embedding for '{bubble.title}'")
                    else:
                        errors += 1
                        logger.warning(f"[generate_embeddings_for_all_bubbles] Failed to generate embedding for '{bubble.title}'")
                except Exception as e:
                    errors += 1
                    logger.error(f"[generate_embeddings_for_all_bubbles] Error generating embedding for '{bubble.title}': {e}")
            else:
                skipped += 1
                logger.debug(f"[generate_embeddings_for_all_bubbles] Skipped '{bubble.title}' (already has embedding)")

        return {
            "success": True,
            "total": len(bubbles),
            "generated": generated,
            "skipped": skipped,
            "errors": errors
        }

    def search_semantic(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.5,
        parent_id: Optional[str] = None,
    ) -> List[Idea]:
        """
        Semantic search for ideas/bubbles using embeddings.

        Finds conceptually similar bubbles even if keywords don't match exactly.
        E.g., "Testkontext" will find "Test Kontext" with high similarity.

        Args:
            query: Search query (natural language)
            top_k: Maximum number of results
            min_score: Minimum similarity score (0.0 - 1.0)
            parent_id: If provided, only search within this parent (None = top-level spaces)

        Returns:
            List of Ideas sorted by similarity (best match first)
        """
        import logging
        logger = logging.getLogger(__name__)

        # Lazy import to avoid startup overhead if not used
        try:
            from .embedding_service import get_embedding_service, EmbeddingService
        except ImportError:
            logger.warning("[search_semantic] embedding_service not available")
            return []

        embedding_service = get_embedding_service()
        if not embedding_service.is_available:
            logger.debug("[search_semantic] Embedding service not available, falling back")
            return []

        # Generate query embedding
        query_vec = embedding_service.embed(query)
        if query_vec is None:
            logger.debug("[search_semantic] Could not embed query")
            return []

        # Fetch all candidates
        if parent_id is None:
            rows = self.db.fetch_all("SELECT * FROM ideas WHERE parent_id IS NULL")
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM ideas WHERE parent_id = ?",
                (parent_id,)
            )

        # Calculate similarities
        scored_ideas = []
        ideas_to_update = []

        for row in rows:
            idea = Idea.from_dict(dict(row))

            # Get or generate embedding
            idea_vec = idea.embedding_vector
            content_for_embedding = f"{idea.title} {idea.description}".strip()
            current_hash = EmbeddingService.content_hash(content_for_embedding)

            # Regenerate embedding if content changed or doesn't exist
            if idea_vec is None or idea.embedding_hash != current_hash:
                idea_vec = embedding_service.embed(content_for_embedding)
                if idea_vec is not None:
                    idea.embedding_vector = idea_vec
                    idea.embedding_hash = current_hash
                    ideas_to_update.append(idea)

            if idea_vec is not None:
                score = embedding_service.similarity(query_vec, idea_vec)
                if score >= min_score:
                    scored_ideas.append((idea, score))

        # Update embeddings in background (lazy caching)
        for idea in ideas_to_update:
            try:
                self.db.execute(
                    "UPDATE ideas SET embedding_vector = ?, embedding_hash = ? WHERE id = ?",
                    (
                        EmbeddingService.vector_to_json(idea.embedding_vector),
                        idea.embedding_hash,
                        idea.id
                    )
                )
            except Exception as e:
                logger.debug(f"[search_semantic] Failed to cache embedding for {idea.id}: {e}")

        # Sort by similarity (descending) and return top_k
        scored_ideas.sort(key=lambda x: x[1], reverse=True)
        results = [idea for idea, score in scored_ideas[:top_k]]

        logger.debug(f"[search_semantic] Found {len(results)} matches for '{query}'")
        return results


def promote_idea_to_project(idea_id: int, db: Optional[Database] = None) -> Optional[int]:
    """
    Promote an Idea to a Project.

    Args:
        idea_id: The ID of the idea to promote
        db: Optional database instance

    Returns:
        The new project ID, or None if failed
    """
    logger.debug("promote_idea_to_project: idea_id=%s", idea_id)
    if db is None:
        db = get_database()

    ideas_repo = IdeasRepository(db)
    from .projects_repository import ProjectsRepository
    projects_repo = ProjectsRepository(db)

    # Get the idea
    idea = ideas_repo.get(idea_id)
    if not idea:
        return None

    # Create a project from the idea
    project = projects_repo.create(
        name=idea.title,
        description=idea.description or "",
        from_idea_id=idea_id
    )

    return project
