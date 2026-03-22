"""Mermaid Repository — CRUD operations for Mermaid diagrams."""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from .database import Database, get_database
from .models import MermaidDiagram, MermaidDiagramType
from .repository_utils import generate_id

logger = logging.getLogger(__name__)


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
