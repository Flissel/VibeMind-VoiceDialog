"""
Vibemind Repository Layer

CRUD operations for Ideas, Projects, and Canvas elements.
"""

import uuid
import unicodedata
from datetime import datetime
from typing import Optional, List, Dict, Any

from .database import Database, get_database
from .models import Idea, Project, CanvasNode, CanvasEdge, ConversationMessage, ConversationSession, GenerationStatus, Shuttle, ShuttleStatus, ShuttleStage, ShuttleType, MermaidDiagram, MermaidDiagramType


def generate_id() -> str:
    """Generate a unique ID for new entities"""
    return str(uuid.uuid4())[:8]


def normalize_text(text: str) -> str:
    """
    Remove accents and normalize text for fuzzy matching.

    Handles speech recognition artifacts like "evaluiären" vs "evaluieren"
    by decomposing unicode and removing combining marks (accents).
    """
    # NFD: decompose ä → a + ¨ (combining diaeresis)
    text = unicodedata.normalize('NFD', text)
    # Remove combining marks (accents, umlauts decomposed parts)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.lower()


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
        Accent-insensitive fuzzy title search.

        Handles speech recognition artifacts where accents may be added/removed.
        E.g., "swarm team evaluiären" will match "swarm team evaluieren".
        Also handles compound word variations:
        E.g., "Testkontext" will match "Test Kontext" (space vs no-space).

        Args:
            title: Title to search for (may contain accent artifacts)
            parent_id: If provided, only search within this parent (None = top-level spaces)

        Returns:
            Matching Idea or None
        """
        normalized_query = normalize_text(title)
        # Also create spaceless version for compound word matching
        spaceless_query = normalized_query.replace(" ", "")

        # Fetch candidates based on parent_id
        if parent_id is None:
            # Search top-level spaces (bubbles)
            rows = self.db.fetch_all("SELECT * FROM ideas WHERE parent_id IS NULL")
        else:
            # Search within a specific parent
            rows = self.db.fetch_all(
                "SELECT * FROM ideas WHERE parent_id = ?",
                (parent_id,)
            )

        # Fuzzy match in Python (accent-insensitive)
        for row in rows:
            row_title = row['title'] if row['title'] else ''
            normalized_title = normalize_text(row_title)
            spaceless_title = normalized_title.replace(" ", "")

            # Match if query is substring of title (with or without spaces)
            if normalized_query in normalized_title:
                return Idea.from_dict(dict(row))
            # Also match spaceless versions (handles "Testkontext" vs "Test Kontext")
            if spaceless_query in spaceless_title or spaceless_title in spaceless_query:
                return Idea.from_dict(dict(row))

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


class ProjectsRepository:
    """Repository for Project CRUD operations with code generation support"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    def create(
        self,
        name: str,
        description: str = "",
        from_idea_id: Optional[str] = None,
        status: str = "active",
        metadata: Dict[str, Any] = None,
        # Code Generation Fields
        project_path: Optional[str] = None,
        generation_status: str = GenerationStatus.PENDING,
        tech_stack: Optional[str] = None,
        requirements_json: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Project:
        """
        Create a new project.

        Args:
            name: Project name
            description: Project description
            from_idea_id: ID of source idea (if promoted)
            status: Project status (active, paused, completed, archived, shuttling)
            metadata: Additional metadata
            project_path: Path to generated code (optional)
            generation_status: Code generation status (default: pending)
            tech_stack: Technology stack (e.g., "react", "vue")
            requirements_json: JSON requirements for code generation
            job_id: Hybrid Run job identifier

        Returns:
            Created Project object
        """
        project = Project(
            id=generate_id(),
            name=name,
            description=description,
            status=status,
            created_at=datetime.now(),
            from_idea_id=from_idea_id,
            metadata=metadata or {},
            project_path=project_path,
            generation_status=generation_status,
            tech_stack=tech_stack,
            requirements_json=requirements_json,
            job_id=job_id,
        )

        data = project.to_dict()
        self.db.execute(
            """
            INSERT INTO projects (
                id, name, description, status, created_at, from_idea_id, progress, metadata,
                project_path, generation_status, vnc_port, job_id, requirements_json,
                convergence_progress, preview_url, tech_stack, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["name"],
                data["description"],
                data["status"],
                data["created_at"],
                data["from_idea_id"],
                data["progress"],
                data["metadata"],
                data["project_path"],
                data["generation_status"],
                data["vnc_port"],
                data["job_id"],
                data["requirements_json"],
                data["convergence_progress"],
                data["preview_url"],
                data["tech_stack"],
                data["error_message"],
            ),
        )

        return project

    def get(self, project_id: str) -> Optional[Project]:
        """Get project by ID"""
        row = self.db.fetch_one("SELECT * FROM projects WHERE id = ?", (project_id,))
        return Project.from_dict(dict(row)) if row else None

    def get_by_name(self, name: str) -> Optional[Project]:
        """Get project by name (case-insensitive partial match)"""
        row = self.db.fetch_one(
            "SELECT * FROM projects WHERE LOWER(name) LIKE LOWER(?) LIMIT 1",
            (f"%{name}%",)
        )
        return Project.from_dict(dict(row)) if row else None

    def get_by_job_id(self, job_id: str) -> Optional[Project]:
        """Get project by Hybrid Run job ID"""
        row = self.db.fetch_one(
            "SELECT * FROM projects WHERE job_id = ?",
            (job_id,)
        )
        return Project.from_dict(dict(row)) if row else None

    def list(
        self,
        status: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> List[Project]:
        """
        List projects with optional filtering.

        Args:
            status: Filter by status (active, paused, completed, archived)
            limit: Maximum number of results
            offset: Skip first N results
            order_by: SQL ORDER BY clause

        Returns:
            List of matching Projects
        """
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM projects WHERE {where_clause} ORDER BY {order_by} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.db.fetch_all(sql, tuple(params))
        return [Project.from_dict(dict(row)) for row in rows]

    def list_by_generation_status(
        self,
        generation_status: str,
        limit: int = 20,
    ) -> List[Project]:
        """
        List projects by their code generation status.

        Args:
            generation_status: Filter by generation_status (pending, generating, etc.)
            limit: Maximum number of results

        Returns:
            List of matching Projects
        """
        rows = self.db.fetch_all(
            "SELECT * FROM projects WHERE generation_status = ? ORDER BY created_at DESC LIMIT ?",
            (generation_status, limit)
        )
        return [Project.from_dict(dict(row)) for row in rows]

    def list_with_active_preview(self, limit: int = 10) -> List[Project]:
        """List projects that have an active VNC preview."""
        rows = self.db.fetch_all(
            """SELECT * FROM projects 
               WHERE vnc_port IS NOT NULL 
               AND generation_status = ? 
               ORDER BY created_at DESC LIMIT ?""",
            (GenerationStatus.PREVIEWING, limit)
        )
        return [Project.from_dict(dict(row)) for row in rows]

    def update(self, project: Project) -> Project:
        """Update an existing project (all fields)"""
        data = project.to_dict()
        self.db.execute(
            """
            UPDATE projects SET
                name = ?,
                description = ?,
                status = ?,
                progress = ?,
                metadata = ?,
                project_path = ?,
                generation_status = ?,
                vnc_port = ?,
                job_id = ?,
                requirements_json = ?,
                convergence_progress = ?,
                preview_url = ?,
                tech_stack = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                data["name"],
                data["description"],
                data["status"],
                data["progress"],
                data["metadata"],
                data["project_path"],
                data["generation_status"],
                data["vnc_port"],
                data["job_id"],
                data["requirements_json"],
                data["convergence_progress"],
                data["preview_url"],
                data["tech_stack"],
                data["error_message"],
                data["id"],
            ),
        )

        return project

    def update_generation_status(
        self,
        project_id: str,
        generation_status: str,
        convergence_progress: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Update only the code generation status fields.
        
        Args:
            project_id: Project ID
            generation_status: New generation status
            convergence_progress: Optional convergence progress (0-100)
            error_message: Optional error message (for failed status)
            
        Returns:
            True if updated, False if project not found
        """
        project = self.get(project_id)
        if not project:
            return False
        
        project.generation_status = generation_status
        if convergence_progress is not None:
            project.convergence_progress = convergence_progress
        if error_message is not None:
            project.error_message = error_message
        
        self.update(project)
        return True

    def set_preview_url(
        self,
        project_id: str,
        vnc_port: int,
        preview_url: str,
    ) -> bool:
        """
        Set the VNC preview URL for a project.
        
        Args:
            project_id: Project ID
            vnc_port: VNC port number
            preview_url: Full noVNC URL
            
        Returns:
            True if updated, False if project not found
        """
        project = self.get(project_id)
        if not project:
            return False
        
        project.vnc_port = vnc_port
        project.preview_url = preview_url
        project.generation_status = GenerationStatus.PREVIEWING
        
        self.update(project)
        return True

    def allocate_vnc_port(self, base_port: int = 6080) -> int:
        """
        Find the next available VNC port.
        
        Args:
            base_port: Starting port number (default: 6080)
            
        Returns:
            Next available port number
        """
        # Get all currently used ports
        rows = self.db.fetch_all(
            "SELECT vnc_port FROM projects WHERE vnc_port IS NOT NULL"
        )
        used_ports = {row[0] for row in rows}
        
        # Find next available
        port = base_port
        while port in used_ports:
            port += 1
        
        return port

    def clear_vnc_port(self, project_id: str) -> bool:
        """Clear VNC port when preview is stopped."""
        project = self.get(project_id)
        if not project:
            return False
        
        project.vnc_port = None
        project.preview_url = None
        if project.generation_status == GenerationStatus.PREVIEWING:
            project.generation_status = GenerationStatus.COMPLETED
        
        self.update(project)
        return True

    def delete(self, project_id: str) -> bool:
        """Delete a project by ID"""
        self.db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return True

    def count(self, status: Optional[str] = None) -> int:
        """Count projects, optionally filtered by status"""
        if status:
            row = self.db.fetch_one("SELECT COUNT(*) FROM projects WHERE status = ?", (status,))
        else:
            row = self.db.fetch_one("SELECT COUNT(*) FROM projects")
        return row[0] if row else 0

    def count_by_generation_status(self, generation_status: str) -> int:
        """Count projects by generation status"""
        row = self.db.fetch_one(
            "SELECT COUNT(*) FROM projects WHERE generation_status = ?",
            (generation_status,)
        )
        return row[0] if row else 0

    def list_by_idea(self, idea_id: str) -> List[Project]:
        """
        List projects created from a specific idea.

        Args:
            idea_id: ID of the source idea

        Returns:
            List of Projects linked to this idea
        """
        rows = self.db.fetch_all(
            "SELECT * FROM projects WHERE from_idea_id = ?",
            (idea_id,)
        )
        return [Project.from_dict(dict(row)) for row in rows]


class CanvasRepository:
    """Repository for Canvas node and edge operations"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    # Node operations

    def create_node(
        self,
        node_type: str,
        title: str = "",
        content: str = "",
        x: float = 0.0,
        y: float = 0.0,
        linked_idea_id: Optional[str] = None,
        linked_project_id: Optional[str] = None,
        summary: Optional[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> CanvasNode:
        """Create a new canvas node"""
        node = CanvasNode(
            id=generate_id(),
            node_type=node_type,
            title=title,
            content=content,
            x=x,
            y=y,
            linked_idea_id=linked_idea_id,
            linked_project_id=linked_project_id,
            summary=summary,
            metadata=metadata or {},
        )

        data = node.to_dict()
        self.db.execute(
            """
            INSERT INTO canvas_nodes (id, node_type, title, content, x, y, linked_idea_id, linked_project_id, summary, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["node_type"],
                data["title"],
                data["content"],
                data["x"],
                data["y"],
                data["linked_idea_id"],
                data["linked_project_id"],
                data["summary"],
                data["metadata"],
            ),
        )

        return node

    def get_node(self, node_id: str) -> Optional[CanvasNode]:
        """Get canvas node by ID"""
        row = self.db.fetch_one("SELECT * FROM canvas_nodes WHERE id = ?", (node_id,))
        return CanvasNode.from_dict(dict(row)) if row else None

    def list_nodes(
        self,
        node_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[CanvasNode]:
        """List canvas nodes, optionally filtered by type"""
        if node_type:
            rows = self.db.fetch_all(
                "SELECT * FROM canvas_nodes WHERE node_type = ? LIMIT ?",
                (node_type, limit)
            )
        else:
            rows = self.db.fetch_all("SELECT * FROM canvas_nodes LIMIT ?", (limit,))

        return [CanvasNode.from_dict(dict(row)) for row in rows]

    def update_node(self, node: CanvasNode) -> CanvasNode:
        """Update an existing canvas node"""
        data = node.to_dict()
        self.db.execute(
            """
            UPDATE canvas_nodes SET
                node_type = ?,
                title = ?,
                content = ?,
                x = ?,
                y = ?,
                linked_idea_id = ?,
                linked_project_id = ?,
                summary = ?,
                metadata = ?
            WHERE id = ?
            """,
            (
                data["node_type"],
                data["title"],
                data["content"],
                data["x"],
                data["y"],
                data["linked_idea_id"],
                data["linked_project_id"],
                data["summary"],
                data["metadata"],
                data["id"],
            ),
        )

        return node

    def delete_node(self, node_id: str) -> bool:
        """Delete a canvas node and its connected edges"""
        self.db.execute("DELETE FROM canvas_edges WHERE from_node_id = ? OR to_node_id = ?", (node_id, node_id))
        self.db.execute("DELETE FROM canvas_nodes WHERE id = ?", (node_id,))
        return True

    # Edge operations

    def create_edge(
        self,
        from_node_id: str,
        to_node_id: str,
        edge_type: str = "default",
    ) -> CanvasEdge:
        """Create a new canvas edge"""
        edge = CanvasEdge(
            id=generate_id(),
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            edge_type=edge_type,
        )

        self.db.execute(
            """
            INSERT INTO canvas_edges (id, from_node_id, to_node_id, edge_type)
            VALUES (?, ?, ?, ?)
            """,
            (edge.id, edge.from_node_id, edge.to_node_id, edge.edge_type),
        )

        return edge

    def get_edges_for_node(self, node_id: str) -> List[CanvasEdge]:
        """Get all edges connected to a node"""
        rows = self.db.fetch_all(
            "SELECT * FROM canvas_edges WHERE from_node_id = ? OR to_node_id = ?",
            (node_id, node_id)
        )
        return [CanvasEdge.from_dict(dict(row)) for row in rows]

    def list_edges(self, limit: int = 100) -> List[CanvasEdge]:
        """List all canvas edges"""
        rows = self.db.fetch_all("SELECT * FROM canvas_edges LIMIT ?", (limit,))
        return [CanvasEdge.from_dict(dict(row)) for row in rows]

    def delete_edge(self, edge_id: str) -> bool:
        """Delete a canvas edge"""
        self.db.execute("DELETE FROM canvas_edges WHERE id = ?", (edge_id,))
        return True

    # ==============================================================================
    # GRAPH TRAVERSAL FOR WHITE PAPER GENERATION
    # ==============================================================================
    
    def traverse_linked_nodes(
        self,
        start_node_id: str,
        max_depth: int = 10,
        idea_id: Optional[str] = None
    ) -> Dict[int, List[CanvasNode]]:
        """
        Traverse the graph from a starting node using BFS.
        Returns nodes grouped by their distance from the start node.
        
        Args:
            start_node_id: The ID of the node to start traversal from
            max_depth: Maximum traversal depth (default: 10)
            idea_id: Optional - limit traversal to nodes within this idea/bubble
            
        Returns:
            Dict mapping distance (0, 1, 2, ...) to list of nodes at that distance
            Example: {0: [start_node], 1: [direct_neighbors], 2: [neighbors_of_neighbors]}
        """
        from collections import deque
        
        # Get all nodes and edges
        if idea_id:
            all_nodes = [n for n in self.list_nodes(limit=1000) if n.linked_idea_id == idea_id]
        else:
            all_nodes = self.list_nodes(limit=1000)
        
        all_edges = self.list_edges(limit=5000)
        
        # Build node lookup
        node_by_id = {n.id: n for n in all_nodes}
        
        # Build adjacency list from edges
        adjacency: Dict[str, List[str]] = {n.id: [] for n in all_nodes}
        for edge in all_edges:
            if edge.from_node_id in adjacency and edge.to_node_id in adjacency:
                adjacency[edge.from_node_id].append(edge.to_node_id)
                adjacency[edge.to_node_id].append(edge.from_node_id)  # Bidirectional
        
        # BFS traversal
        result: Dict[int, List[CanvasNode]] = {}
        visited: set = set()
        queue = deque([(start_node_id, 0)])  # (node_id, distance)
        
        while queue:
            node_id, distance = queue.popleft()
            
            if node_id in visited or distance > max_depth:
                continue
            
            visited.add(node_id)
            
            # Add node to result at this distance
            if node_id in node_by_id:
                if distance not in result:
                    result[distance] = []
                result[distance].append(node_by_id[node_id])
                
                # Queue neighbors
                for neighbor_id in adjacency.get(node_id, []):
                    if neighbor_id not in visited:
                        queue.append((neighbor_id, distance + 1))
        
        return result
    
    def get_node_by_title(
        self,
        title: str,
        idea_id: Optional[str] = None
    ) -> Optional[CanvasNode]:
        """
        Find a node by its title (case-insensitive partial match).
        
        Args:
            title: Title to search for
            idea_id: Optional - limit search to nodes within this idea/bubble
            
        Returns:
            The matching node or None
        """
        title_lower = title.lower()
        
        if idea_id:
            nodes = [n for n in self.list_nodes(limit=1000) if n.linked_idea_id == idea_id]
        else:
            nodes = self.list_nodes(limit=1000)
        
        # Exact match first
        for node in nodes:
            if (node.title or "").lower() == title_lower:
                return node
        
        # Partial match
        for node in nodes:
            if title_lower in (node.title or "").lower():
                return node
        
        return None


class ConversationRepository:
    """Repository for conversation history CRUD operations"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    # Session operations

    def create_session(
        self,
        agent_id: Optional[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> ConversationSession:
        """Start a new conversation session"""
        session = ConversationSession(
            id=generate_id(),
            started_at=datetime.now(),
            agent_id=agent_id,
            metadata=metadata or {},
        )

        data = session.to_dict()
        self.db.execute(
            """
            INSERT INTO conversation_sessions (id, started_at, ended_at, summary, agent_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["started_at"],
                data["ended_at"],
                data["summary"],
                data["agent_id"],
                data["metadata"],
            ),
        )

        return session

    def end_session(
        self,
        session_id: str,
        summary: Optional[str] = None,
    ) -> Optional[ConversationSession]:
        """End a conversation session"""
        session = self.get_session(session_id)
        if not session:
            return None

        session.ended_at = datetime.now()
        session.summary = summary

        self.db.execute(
            """
            UPDATE conversation_sessions SET ended_at = ?, summary = ?
            WHERE id = ?
            """,
            (session.ended_at.isoformat(), session.summary, session_id),
        )

        return session

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get session by ID"""
        row = self.db.fetch_one("SELECT * FROM conversation_sessions WHERE id = ?", (session_id,))
        return ConversationSession.from_dict(dict(row)) if row else None

    def list_sessions(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> List[ConversationSession]:
        """List recent conversation sessions"""
        rows = self.db.fetch_all(
            "SELECT * FROM conversation_sessions ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [ConversationSession.from_dict(dict(row)) for row in rows]

    # Message operations

    def add_message(
        self,
        session_id: str,
        speaker: str,
        text: str,
        metadata: Dict[str, Any] = None,
    ) -> ConversationMessage:
        """Add a message to conversation history"""
        message = ConversationMessage(
            id=generate_id(),
            session_id=session_id,
            speaker=speaker,
            text=text,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )

        data = message.to_dict()
        self.db.execute(
            """
            INSERT INTO conversation_history (id, session_id, speaker, text, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["session_id"],
                data["speaker"],
                data["text"],
                data["timestamp"],
                data["metadata"],
            ),
        )

        return message

    def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[ConversationMessage]:
        """Get all messages for a session"""
        rows = self.db.fetch_all(
            "SELECT * FROM conversation_history WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
            (session_id, limit)
        )
        return [ConversationMessage.from_dict(dict(row)) for row in rows]

    def get_recent_messages(
        self,
        limit: int = 50,
    ) -> List[ConversationMessage]:
        """Get most recent messages across all sessions"""
        rows = self.db.fetch_all(
            "SELECT * FROM conversation_history ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return [ConversationMessage.from_dict(dict(row)) for row in rows]

    def search_messages(
        self,
        query: str,
        limit: int = 20,
    ) -> List[ConversationMessage]:
        """Search messages by text content"""
        rows = self.db.fetch_all(
            "SELECT * FROM conversation_history WHERE text LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (f"%{query}%", limit)
        )
        return [ConversationMessage.from_dict(dict(row)) for row in rows]

    def count_messages(self, session_id: Optional[str] = None) -> int:
        """Count messages, optionally filtered by session"""
        if session_id:
            row = self.db.fetch_one(
                "SELECT COUNT(*) FROM conversation_history WHERE session_id = ?",
                (session_id,)
            )
        else:
            row = self.db.fetch_one("SELECT COUNT(*) FROM conversation_history")
        return row[0] if row else 0


class ShuttlesRepository:
    """Repository for requirement shuttle tracking operations"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    def create(
        self,
        shuttle_id: str,
        bubble_id: str,
        bubble_name: str,
        total_count: int = 0,
        project_id: Optional[str] = None,
        stage_type: str = ShuttleType.FULL,
        stage_data: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
    ) -> Shuttle:
        """
        Create a new shuttle for tracking requirement evaluation.

        Args:
            shuttle_id: Visual ID (e.g., "shuttle-e-ticketing-1701234567")
            bubble_id: ID of the source bubble/idea
            bubble_name: Name of the source bubble
            total_count: Total number of requirements to evaluate
            project_id: ID of the linked project (created at shuttle launch)
            stage_type: Type of shuttle ('full', 'mining', 'validation', 'knowledge_graph', 'techstack')
            stage_data: Stage-specific data (for stage-specific shuttles)
            metadata: Additional metadata

        Returns:
            Created Shuttle object
        """
        shuttle = Shuttle(
            id=generate_id(),
            shuttle_id=shuttle_id,
            bubble_id=bubble_id,
            bubble_name=bubble_name,
            total_count=total_count,
            project_id=project_id,
            stage_type=stage_type,
            stage_data=stage_data or {},
            status=ShuttleStatus.LAUNCHING,
            created_at=datetime.now(),
            metadata=metadata or {},
        )

        data = shuttle.to_dict()
        self.db.execute(
            """
            INSERT INTO shuttles (
                id, shuttle_id, bubble_id, bubble_name, score, passed_count, failed_count,
                total_count, status, current_stage, project_id, stage_type, stage_data,
                created_at, completed_at, requirement_results, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["shuttle_id"],
                data["bubble_id"],
                data["bubble_name"],
                data["score"],
                data["passed_count"],
                data["failed_count"],
                data["total_count"],
                data["status"],
                data["current_stage"],
                data["project_id"],
                data["stage_type"],
                data["stage_data"],
                data["created_at"],
                data["completed_at"],
                data["requirement_results"],
                data["metadata"],
            ),
        )

        return shuttle

    def get(self, shuttle_db_id: str) -> Optional[Shuttle]:
        """Get shuttle by database ID"""
        row = self.db.fetch_one("SELECT * FROM shuttles WHERE id = ?", (shuttle_db_id,))
        return Shuttle.from_dict(dict(row)) if row else None

    def get_by_shuttle_id(self, shuttle_id: str) -> Optional[Shuttle]:
        """Get shuttle by visual shuttle_id"""
        row = self.db.fetch_one("SELECT * FROM shuttles WHERE shuttle_id = ?", (shuttle_id,))
        return Shuttle.from_dict(dict(row)) if row else None

    def get_by_project_id(self, project_id: str) -> Optional[Shuttle]:
        """Get shuttle by linked project ID"""
        row = self.db.fetch_one("SELECT * FROM shuttles WHERE project_id = ?", (project_id,))
        return Shuttle.from_dict(dict(row)) if row else None

    def list(
        self,
        bubble_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Shuttle]:
        """
        List shuttles with optional filtering.

        Args:
            bubble_id: Filter by source bubble
            status: Filter by status (launching, in_transit, arrived, needs_work)
            limit: Maximum number of results
            offset: Skip first N results

        Returns:
            List of matching Shuttles
        """
        conditions = []
        params = []

        if bubble_id:
            conditions.append("bubble_id = ?")
            params.append(bubble_id)

        if status:
            conditions.append("status = ?")
            params.append(status)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM shuttles WHERE {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.db.fetch_all(sql, tuple(params))
        return [Shuttle.from_dict(dict(row)) for row in rows]

    def list_active(self, limit: int = 50) -> List[Shuttle]:
        """
        List active shuttles (not yet arrived).

        Returns shuttles that are still in progress for UI visualization.
        """
        rows = self.db.fetch_all(
            """
            SELECT * FROM shuttles
            WHERE status != ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (ShuttleStatus.ARRIVED, limit)
        )
        return [Shuttle.from_dict(dict(row)) for row in rows]

    def list_by_bubble(self, bubble_id: str, limit: int = 10) -> List[Shuttle]:
        """Get all shuttles for a specific bubble"""
        return self.list(bubble_id=bubble_id, limit=limit)

    def update(self, shuttle: Shuttle) -> Shuttle:
        """Update an existing shuttle (all fields)"""
        data = shuttle.to_dict()
        self.db.execute(
            """
            UPDATE shuttles SET
                score = ?,
                passed_count = ?,
                failed_count = ?,
                total_count = ?,
                status = ?,
                current_stage = ?,
                project_id = ?,
                stage_type = ?,
                stage_data = ?,
                completed_at = ?,
                requirement_results = ?,
                metadata = ?
            WHERE id = ?
            """,
            (
                data["score"],
                data["passed_count"],
                data["failed_count"],
                data["total_count"],
                data["status"],
                data["current_stage"],
                data["project_id"],
                data["stage_type"],
                data["stage_data"],
                data["completed_at"],
                data["requirement_results"],
                data["metadata"],
                data["id"],
            ),
        )
        return shuttle

    def update_progress(
        self,
        shuttle_db_id: str,
        passed: int,
        failed: int,
        score: float,
    ) -> bool:
        """
        Update shuttle progress during batch evaluation.

        Args:
            shuttle_db_id: Database ID of the shuttle
            passed: Number of passed requirements so far
            failed: Number of failed requirements so far
            score: Current average score

        Returns:
            True if updated, False if shuttle not found
        """
        shuttle = self.get(shuttle_db_id)
        if not shuttle:
            return False

        shuttle.passed_count = passed
        shuttle.failed_count = failed
        shuttle.score = score
        shuttle.status = ShuttleStatus.IN_TRANSIT

        self.update(shuttle)
        return True

    def update_stage(
        self,
        shuttle_db_id: str,
        stage: str,
    ) -> bool:
        """
        Update shuttle's current DNA pipeline stage.

        Args:
            shuttle_db_id: Database ID of the shuttle
            stage: New stage (from ShuttleStage enum)

        Returns:
            True if updated, False if shuttle not found
        """
        shuttle = self.get(shuttle_db_id)
        if not shuttle:
            return False

        shuttle.current_stage = stage
        shuttle.status = ShuttleStatus.IN_TRANSIT

        self.update(shuttle)
        return True

    def complete(
        self,
        shuttle_db_id: str,
        final_score: float,
        passed: int,
        failed: int,
        requirement_results: Dict[str, Any] = None,
    ) -> bool:
        """
        Mark shuttle as complete with final results.

        Args:
            shuttle_db_id: Database ID of the shuttle
            final_score: Final average score (0.0-1.0)
            passed: Total passed requirements
            failed: Total failed requirements
            requirement_results: Detailed per-requirement results

        Returns:
            True if updated, False if shuttle not found
        """
        shuttle = self.get(shuttle_db_id)
        if not shuttle:
            return False

        shuttle.score = final_score
        shuttle.passed_count = passed
        shuttle.failed_count = failed
        shuttle.completed_at = datetime.now()
        shuttle.status = ShuttleStatus.ARRIVED if final_score >= 0.7 else ShuttleStatus.NEEDS_WORK
        shuttle.current_stage = ShuttleStage.COMPLETE if final_score >= 0.7 else ShuttleStage.VALIDATION

        if requirement_results:
            shuttle.requirement_results = requirement_results

        self.update(shuttle)
        return True

    def delete(self, shuttle_db_id: str) -> bool:
        """Delete a shuttle by database ID"""
        self.db.execute("DELETE FROM shuttles WHERE id = ?", (shuttle_db_id,))
        return True

    def count(self, status: Optional[str] = None) -> int:
        """Count shuttles, optionally filtered by status"""
        if status:
            row = self.db.fetch_one("SELECT COUNT(*) FROM shuttles WHERE status = ?", (status,))
        else:
            row = self.db.fetch_one("SELECT COUNT(*) FROM shuttles")
        return row[0] if row else 0

    # ==============================================================================
    # STAGE-SPECIFIC SHUTTLE METHODS (Phase 13: Multi-Shuttle Per Checkpoint)
    # ==============================================================================

    def create_stage_shuttle(
        self,
        bubble_id: str,
        bubble_name: str,
        stage_type: str,
        stage_data: Dict[str, Any],
        project_id: Optional[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> Shuttle:
        """
        Create a stage-specific shuttle (parked at one checkpoint).

        Args:
            bubble_id: ID of the source bubble/idea
            bubble_name: Name of the source bubble
            stage_type: One of 'mining', 'validation', 'knowledge_graph', 'techstack'
            stage_data: Stage-specific data from the API
            project_id: ID of the linked project
            metadata: Additional metadata

        Returns:
            Created Shuttle object with stage_type set
        """
        import time

        # Generate shuttle ID with stage type embedded
        shuttle_id = f"shuttle-{bubble_name[:10].replace(' ', '_')}-{stage_type}-{int(time.time())}"

        # Determine total_count from stage_data if available
        total_count = 0
        if stage_type == ShuttleType.MINING:
            total_count = len(stage_data.get("requirements", []))
        elif stage_type == ShuttleType.VALIDATION:
            total_count = len(stage_data.get("results", []))
        elif stage_type == ShuttleType.KNOWLEDGE_GRAPH:
            total_count = len(stage_data.get("entities", []))
        elif stage_type == ShuttleType.TECHSTACK:
            total_count = len(stage_data.get("templates", [])) or 1

        return self.create(
            shuttle_id=shuttle_id,
            bubble_id=bubble_id,
            bubble_name=bubble_name,
            total_count=total_count,
            project_id=project_id,
            stage_type=stage_type,
            stage_data=stage_data,
            metadata=metadata or {},
        )

    def get_stage_shuttle(
        self,
        bubble_id: str,
        stage_type: str,
    ) -> Optional[Shuttle]:
        """
        Get shuttle for a specific bubble+stage combination.

        Each bubble should have at most one shuttle per stage type.

        Args:
            bubble_id: ID of the source bubble/idea
            stage_type: One of 'mining', 'validation', 'knowledge_graph', 'techstack'

        Returns:
            The matching Shuttle or None
        """
        row = self.db.fetch_one(
            "SELECT * FROM shuttles WHERE bubble_id = ? AND stage_type = ?",
            (bubble_id, stage_type)
        )
        return Shuttle.from_dict(dict(row)) if row else None

    def list_bubble_stage_shuttles(self, bubble_id: str) -> List[Shuttle]:
        """
        Get all 4 stage shuttles for a bubble.

        Excludes 'full' type shuttles (legacy single-shuttle system).

        Args:
            bubble_id: ID of the source bubble/idea

        Returns:
            List of stage-specific Shuttles (up to 4)
        """
        rows = self.db.fetch_all(
            """
            SELECT * FROM shuttles
            WHERE bubble_id = ? AND stage_type != ?
            ORDER BY
                CASE stage_type
                    WHEN 'mining' THEN 1
                    WHEN 'validation' THEN 2
                    WHEN 'knowledge_graph' THEN 3
                    WHEN 'techstack' THEN 4
                    ELSE 5
                END
            """,
            (bubble_id, ShuttleType.FULL)
        )
        return [Shuttle.from_dict(dict(row)) for row in rows]

    def list_by_stage_type(
        self,
        stage_type: str,
        limit: int = 50,
    ) -> List[Shuttle]:
        """
        List all shuttles of a specific stage type.

        Useful for getting all shuttles parked at a specific checkpoint.

        Args:
            stage_type: One of 'mining', 'validation', 'knowledge_graph', 'techstack', 'full'
            limit: Maximum number of results

        Returns:
            List of Shuttles of that stage type
        """
        rows = self.db.fetch_all(
            "SELECT * FROM shuttles WHERE stage_type = ? ORDER BY created_at DESC LIMIT ?",
            (stage_type, limit)
        )
        return [Shuttle.from_dict(dict(row)) for row in rows]

    def delete_bubble_stage_shuttles(self, bubble_id: str) -> int:
        """
        Delete all stage-specific shuttles for a bubble.

        Used when re-running the pipeline or cleaning up.

        Args:
            bubble_id: ID of the source bubble/idea

        Returns:
            Number of shuttles deleted
        """
        with self.db.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM shuttles WHERE bubble_id = ? AND stage_type != ?",
                (bubble_id, ShuttleType.FULL)
            )
            conn.commit()
            return cursor.rowcount

    def update_stage_data(
        self,
        shuttle_db_id: str,
        stage_data: Dict[str, Any],
    ) -> bool:
        """
        Update only the stage_data field for a shuttle.

        Args:
            shuttle_db_id: Database ID of the shuttle
            stage_data: New stage-specific data

        Returns:
            True if updated, False if shuttle not found
        """
        import json

        shuttle = self.get(shuttle_db_id)
        if not shuttle:
            return False

        shuttle.stage_data = stage_data

        # Update only stage_data field
        self.db.execute(
            "UPDATE shuttles SET stage_data = ? WHERE id = ?",
            (json.dumps(stage_data), shuttle_db_id)
        )
        return True


def promote_idea_to_project(idea_id: int, db: Optional[Database] = None) -> Optional[int]:
    """
    Promote an Idea to a Project.
    
    Args:
        idea_id: The ID of the idea to promote
        db: Optional database instance
        
    Returns:
        The new project ID, or None if failed
    """
    if db is None:
        db = get_database()
    
    ideas_repo = IdeasRepository(db)
    projects_repo = ProjectsRepository(db)
    
    # Get the idea
    idea = ideas_repo.get(idea_id)
    if not idea:
        return None
    
    # Create a project from the idea
    project_id = projects_repo.create(
        title=idea.title,
        description=idea.content or "",
        source_idea_id=idea_id
    )

    return project_id


class MermaidDiagramsRepository:
    """Repository for Mermaid Diagram CRUD operations."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    def create(
        self,
        title: str,
        content: str,
        diagram_type: str = MermaidDiagramType.FLOWCHART,
        source_idea_id: Optional[str] = None,
        source_shuttle_id: Optional[str] = None,
        source_requirement_ids: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> MermaidDiagram:
        """
        Create a new mermaid diagram.

        Args:
            title: Diagram title
            content: Mermaid diagram content
            diagram_type: Type of diagram (flowchart, sequenceDiagram, etc.)
            source_idea_id: Optional link to source idea
            source_shuttle_id: Optional link to source shuttle
            source_requirement_ids: Optional list of source requirement IDs
            metadata: Additional metadata

        Returns:
            Created MermaidDiagram object
        """
        import json

        diagram = MermaidDiagram(
            id=generate_id(),
            title=title,
            diagram_type=diagram_type,
            content=content,
            source_idea_id=source_idea_id,
            source_shuttle_id=source_shuttle_id,
            source_requirement_ids=source_requirement_ids or [],
            created_at=datetime.now(),
            metadata=metadata or {},
        )

        data = diagram.to_dict()
        self.db.execute(
            """
            INSERT INTO mermaid_diagrams (
                id, title, diagram_type, content, source_idea_id,
                source_shuttle_id, source_requirement_ids, created_at,
                updated_at, version, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["title"],
                data["diagram_type"],
                data["content"],
                data["source_idea_id"],
                data["source_shuttle_id"],
                data["source_requirement_ids"],
                data["created_at"],
                data["updated_at"],
                data["version"],
                data["metadata"],
            ),
        )

        return diagram

    def get(self, diagram_id: str) -> Optional[MermaidDiagram]:
        """Get diagram by ID."""
        row = self.db.fetch_one("SELECT * FROM mermaid_diagrams WHERE id = ?", (diagram_id,))
        return MermaidDiagram.from_dict(dict(row)) if row else None

    def get_by_title(self, title: str) -> Optional[MermaidDiagram]:
        """Get diagram by title (case-insensitive partial match)."""
        row = self.db.fetch_one(
            "SELECT * FROM mermaid_diagrams WHERE LOWER(title) LIKE LOWER(?) LIMIT 1",
            (f"%{title}%",)
        )
        return MermaidDiagram.from_dict(dict(row)) if row else None

    def list(
        self,
        diagram_type: Optional[str] = None,
        source_idea_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[MermaidDiagram]:
        """
        List diagrams with optional filtering.

        Args:
            diagram_type: Filter by diagram type
            source_idea_id: Filter by source idea
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of MermaidDiagram objects
        """
        conditions = []
        params = []

        if diagram_type:
            conditions.append("diagram_type = ?")
            params.append(diagram_type)

        if source_idea_id:
            conditions.append("source_idea_id = ?")
            params.append(source_idea_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT * FROM mermaid_diagrams
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = self.db.fetch_all(sql, tuple(params))
        return [MermaidDiagram.from_dict(dict(row)) for row in rows]

    def list_by_idea(self, idea_id: str) -> List[MermaidDiagram]:
        """Get all diagrams linked to a specific idea."""
        return self.list(source_idea_id=idea_id)

    def list_by_type(self, diagram_type: str, limit: int = 20) -> List[MermaidDiagram]:
        """Get diagrams of a specific type."""
        return self.list(diagram_type=diagram_type, limit=limit)

    def update(self, diagram: MermaidDiagram) -> MermaidDiagram:
        """
        Update an existing diagram.

        Args:
            diagram: The diagram to update

        Returns:
            Updated MermaidDiagram object
        """
        import json

        diagram.updated_at = datetime.now()
        diagram.version += 1

        data = diagram.to_dict()
        self.db.execute(
            """
            UPDATE mermaid_diagrams SET
                title = ?,
                diagram_type = ?,
                content = ?,
                source_idea_id = ?,
                source_shuttle_id = ?,
                source_requirement_ids = ?,
                updated_at = ?,
                version = ?,
                metadata = ?
            WHERE id = ?
            """,
            (
                data["title"],
                data["diagram_type"],
                data["content"],
                data["source_idea_id"],
                data["source_shuttle_id"],
                data["source_requirement_ids"],
                data["updated_at"],
                data["version"],
                data["metadata"],
                data["id"],
            ),
        )

        return diagram

    def delete(self, diagram_id: str) -> bool:
        """Delete a diagram by ID."""
        self.db.execute("DELETE FROM mermaid_diagrams WHERE id = ?", (diagram_id,))
        return True

    def count(self, diagram_type: Optional[str] = None) -> int:
        """Count diagrams, optionally filtered by type."""
        if diagram_type:
            row = self.db.fetch_one(
                "SELECT COUNT(*) FROM mermaid_diagrams WHERE diagram_type = ?",
                (diagram_type,)
            )
        else:
            row = self.db.fetch_one("SELECT COUNT(*) FROM mermaid_diagrams")
        return row[0] if row else 0

    def search(self, query: str, limit: int = 20) -> List[MermaidDiagram]:
        """
        Search diagrams by title or content.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching MermaidDiagram objects
        """
        rows = self.db.fetch_all(
            """
            SELECT * FROM mermaid_diagrams
            WHERE LOWER(title) LIKE LOWER(?) OR LOWER(content) LIKE LOWER(?)
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (f"%{query}%", f"%{query}%", limit)
        )
        return [MermaidDiagram.from_dict(dict(row)) for row in rows]

    def list_recent(self, limit: int = 10) -> List[MermaidDiagram]:
        """Get most recently created diagrams."""
        rows = self.db.fetch_all(
            "SELECT * FROM mermaid_diagrams ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return [MermaidDiagram.from_dict(dict(row)) for row in rows]
