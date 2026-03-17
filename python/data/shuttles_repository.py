"""Shuttles Repository — CRUD operations for requirement shuttle tracking."""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from .database import Database, get_database
from .models import Shuttle, ShuttleStatus, ShuttleStage, ShuttleType
from .repository_utils import generate_id

logger = logging.getLogger(__name__)


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
        logger.debug("create_stage_shuttle: bubble_id=%s stage_type=%s", bubble_id, stage_type)
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
