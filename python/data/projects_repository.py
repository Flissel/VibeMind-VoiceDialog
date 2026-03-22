"""Projects Repository — CRUD operations for Projects with code generation support."""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from .database import Database, get_database
from .models import Project, GenerationStatus
from .repository_utils import generate_id

logger = logging.getLogger(__name__)


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
        logger.debug("ProjectsRepository.list: status=%s limit=%s", status, limit)
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
        logger.debug("update_generation_status: project_id=%s status=%s", project_id, generation_status)
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
        logger.debug("set_preview_url: project_id=%s vnc_port=%s", project_id, vnc_port)
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
        logger.debug("clear_vnc_port: project_id=%s", project_id)
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

    def sync_from_discovery(self, discovered: Dict[str, Any]) -> Optional[Project]:
        """
        Create a project record from filesystem discovery data (idempotent).

        Checks if a project with the same project_path already exists.
        If not, creates a new record with enrichment metadata stored in
        the metadata JSON field.

        Args:
            discovered: Dict from ProjectDiscoveryService.discover_projects()

        Returns:
            Created Project if new, None if already exists
        """
        logger.debug("sync_from_discovery: path=%s", discovered.get("project_path", ""))
        project_path = discovered.get("project_path", "")
        if not project_path:
            return None

        # Check if already tracked by path
        existing = self.db.fetch_one(
            "SELECT id FROM projects WHERE project_path = ?",
            (project_path,)
        )
        if existing:
            return None

        # Build enrichment metadata (stored in metadata JSON column)
        enrichment = {}
        for key in (
            "total_stages", "stages_completed", "total_cost_usd",
            "total_duration_ms", "total_issues", "issue_counts",
            "issue_categories", "quality_score", "total_artifacts",
            "started_at", "completed_at", "auto_fixed",
            "task_count", "user_story_count", "diagram_count",
            "dir_name",
        ):
            if key in discovered:
                enrichment[key] = discovered[key]

        project = self.create(
            name=discovered.get("name", "Unknown Project"),
            description=discovered.get("description", ""),
            project_path=project_path,
            generation_status=discovered.get("generation_status", "completed"),
            tech_stack=discovered.get("tech_stack"),
            metadata=enrichment,
            status="completed",
        )

        # Also set convergence_progress if available
        if discovered.get("convergence_progress"):
            project.convergence_progress = discovered["convergence_progress"]
            self.update(project)

        return project

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
