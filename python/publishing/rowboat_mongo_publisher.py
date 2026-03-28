"""
Rowboat MongoDB Publisher — writes directly into Rowboat's MongoDB
so the rag-worker automatically chunks, embeds, and indexes content.

Schema-Semaphore: validates the MongoDB schema on every write.
If the schema is incompatible, disables itself and logs a warning.
The caller (publishing/__init__.py) falls back to the filesystem publisher.

Collections used:
  - "sources"     → one doc per bubble (DataSource, type: "text")
  - "source_docs" → one doc per idea  (DataSourceDoc, type: "text")

The rag-worker polls "pending" status every 5s and handles
chunking + embedding + Qdrant upsert automatically.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Expected fields per collection — used by the schema semaphore
_EXPECTED_SOURCE_FIELDS = {
    "projectId", "name", "description", "data", "status",
    "active", "version", "attempts", "createdAt",
}
_EXPECTED_DOC_FIELDS = {
    "sourceId", "projectId", "name", "data", "status",
    "version", "attempts", "createdAt",
}

SCHEMA_VERSION = "1.0"


class SchemaIncompatibleError(Exception):
    """Raised when Rowboat's MongoDB schema doesn't match expectations."""
    pass


class RowboatMongoPublisher:
    """Publishes VibeMind bubbles/ideas directly into Rowboat's MongoDB."""

    def __init__(self):
        from pymongo import MongoClient
        from bson import ObjectId

        conn_str = os.getenv(
            "ROWBOAT_MONGODB_URI",
            os.getenv("MONGODB_CONNECTION_STRING", "mongodb://localhost:37017"),
        )
        db_name = os.getenv("ROWBOAT_MONGODB_DB", "rowboat")
        self._project_id = os.getenv("ROWBOAT_PROJECT_ID", "")

        if not self._project_id:
            raise ValueError(
                "ROWBOAT_PROJECT_ID is required for MongoDB publishing"
            )

        self._client = MongoClient(conn_str, serverSelectionTimeoutMS=5000)
        self._db = self._client[db_name]
        self._sources = self._db["sources"]
        self._docs = self._db["source_docs"]
        self._ObjectId = ObjectId
        self._schema_ok: Optional[bool] = None
        self._disabled = False
        self._on_source_updated_callbacks: List[Callable] = []

        # Desktop action buffer (flushed periodically)
        self._desktop_buffer: Dict[str, List[Dict]] = {}
        self._desktop_buffer_lock = threading.Lock()

        # Agent metrics accumulator (flushed periodically)
        self._agent_metrics: Dict[str, Dict[str, Any]] = {}
        self._agent_metrics_lock = threading.Lock()

        logger.info(
            f"[RowboatMongo] Connected to {conn_str}/{db_name} "
            f"(project: {self._project_id})"
        )

    def close(self):
        """Close MongoDB connection gracefully."""
        if hasattr(self, '_client') and self._client:
            try:
                self._client.close()
                logger.info("[RowboatMongo] Connection closed")
            except Exception as e:
                logger.debug(f"[RowboatMongo] Close error (ignored): {e}")

    # ------------------------------------------------------------------
    # Schema Semaphore
    # ------------------------------------------------------------------

    def _validate_schema(self) -> bool:
        """Check that the MongoDB collections have the expected fields.

        Runs on every write. Caches the result until a failure resets it.
        """
        if self._disabled:
            return False
        if self._schema_ok is True:
            return True

        try:
            # Check sources collection
            sample_source = self._sources.find_one(
                {"projectId": self._project_id}
            )
            if sample_source:
                fields = set(sample_source.keys()) - {"_id"}
                missing = _EXPECTED_SOURCE_FIELDS - fields
                if missing:
                    raise SchemaIncompatibleError(
                        f"sources collection missing fields: {missing}"
                    )

            # Check source_docs collection
            sample_doc = self._docs.find_one(
                {"projectId": self._project_id}
            )
            if sample_doc:
                fields = set(sample_doc.keys()) - {"_id"}
                missing = _EXPECTED_DOC_FIELDS - fields
                if missing:
                    raise SchemaIncompatibleError(
                        f"source_docs collection missing fields: {missing}"
                    )

            # If collections are empty, we trust the schema (first write)
            self._schema_ok = True
            return True

        except SchemaIncompatibleError as e:
            logger.warning(
                f"[RowboatMongo] Schema semaphore FAILED: {e}. "
                "Disabling MongoDB publishing — falling back to filesystem."
            )
            self._disabled = True
            self._schema_ok = False
            return False

        except Exception as e:
            logger.warning(
                f"[RowboatMongo] Schema check error: {e}. "
                "Disabling MongoDB publishing — falling back to filesystem."
            )
            self._disabled = True
            self._schema_ok = False
            return False

    @property
    def is_available(self) -> bool:
        """Whether this publisher is functional (schema OK, DB reachable)."""
        return self._validate_schema()

    # ------------------------------------------------------------------
    # Source (Bubble) management
    # ------------------------------------------------------------------

    def _find_source_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find an existing source by name within our project."""
        return self._sources.find_one({
            "projectId": self._project_id,
            "name": name,
            "status": {"$ne": "deleted"},
        })

    def _create_source(self, name: str, description: str = "") -> str:
        """Create a new DataSource in MongoDB. Returns the source ID.

        Also auto-registers the source in the project's agent ragDataSources
        so it's immediately searchable without manual UI configuration.
        """
        now = datetime.now(timezone.utc).isoformat()
        _id = self._ObjectId()

        doc = {
            "_id": _id,
            "projectId": self._project_id,
            "name": name,
            "description": description,
            "data": {"type": "text"},
            "status": "pending",
            "active": True,
            "version": 1,
            "attempts": 0,
            "createdAt": now,
            "error": None,
            "billingError": None,
            "lastAttemptAt": None,
            "lastUpdatedAt": None,
        }
        self._sources.insert_one(doc)
        source_id = str(_id)
        logger.debug(f"[RowboatMongo] Created source '{name}' ({_id})")

        # Auto-register in agent's ragDataSources
        self._register_source_in_agents(source_id)
        return source_id

    def _register_source_in_agents(self, source_id: str):
        """Add a source ID to all agents' ragDataSources in the project.

        Updates workflow, liveWorkflow, and draftWorkflow so the agent
        can immediately use the new source for RAG searches.
        """
        try:
            projects = self._db["projects"]
            project = projects.find_one({"_id": self._project_id})
            if not project:
                logger.debug("[RowboatMongo] Project not found, skip agent registration")
                return

            updated = False
            for wf_key in ("workflow", "liveWorkflow", "draftWorkflow"):
                wf = project.get(wf_key)
                if not wf or not isinstance(wf, dict):
                    continue
                agents = wf.get("agents", [])
                for agent in agents:
                    rag_sources = agent.get("ragDataSources", [])
                    if source_id not in rag_sources:
                        rag_sources.append(source_id)
                        agent["ragDataSources"] = rag_sources
                        updated = True

            if updated:
                update_fields = {}
                for wf_key in ("workflow", "liveWorkflow", "draftWorkflow"):
                    if wf_key in project:
                        update_fields[wf_key] = project[wf_key]
                projects.update_one(
                    {"_id": self._project_id},
                    {"$set": update_fields},
                )
                logger.debug(
                    f"[RowboatMongo] Registered source {source_id} in agent ragDataSources"
                )
        except Exception as e:
            logger.warning(f"[RowboatMongo] Failed to register source in agents: {e}")

    def _reset_source_to_pending(self, source_id: str):
        """Set an existing source back to pending so rag-worker re-processes."""
        self._sources.update_one(
            {"_id": self._ObjectId(source_id)},
            {"$set": {
                "status": "pending",
                "attempts": 0,
                "lastUpdatedAt": datetime.now(timezone.utc).isoformat(),
                "error": None,
                "billingError": None,
            }},
        )

    def _mark_source_deleted(self, source_id: str):
        """Mark a source as deleted so rag-worker cleans up embeddings."""
        self._sources.update_one(
            {"_id": self._ObjectId(source_id)},
            {"$set": {
                "status": "deleted",
                "lastUpdatedAt": datetime.now(timezone.utc).isoformat(),
            }},
        )

    # ------------------------------------------------------------------
    # Docs (Ideas) management
    # ------------------------------------------------------------------

    def _mark_all_docs_deleted(self, source_id: str):
        """Mark all docs for a source as deleted."""
        self._docs.update_many(
            {"sourceId": source_id, "status": {"$ne": "deleted"}},
            {"$set": {
                "status": "deleted",
                "lastUpdatedAt": datetime.now(timezone.utc).isoformat(),
            }},
        )

    def _insert_docs(self, source_id: str, notes: List[Dict[str, Any]]):
        """Insert text docs for rag-worker to process."""
        if not notes:
            return

        now = datetime.now(timezone.utc).isoformat()
        docs = []
        for note in notes:
            content = self._build_note_text(note)
            docs.append({
                "sourceId": source_id,
                "projectId": self._project_id,
                "name": note.get("title", "Untitled"),
                "version": 1,
                "status": "pending",
                "content": None,
                "createdAt": now,
                "lastUpdatedAt": None,
                "attempts": 0,
                "error": None,
                "data": {
                    "type": "text",
                    "content": content,
                },
            })

        self._docs.insert_many(docs)
        logger.debug(
            f"[RowboatMongo] Inserted {len(docs)} docs for source {source_id}"
        )

    def _build_note_text(self, note: Dict[str, Any]) -> str:
        """Build a rich text representation of an idea for embedding."""
        lines = []
        title = note.get("title", "Untitled")
        lines.append(f"# {title}")
        lines.append("")

        content = note.get("content", "")
        if content:
            lines.append(content)
            lines.append("")

        tags = note.get("tags", [])
        if tags:
            lines.append(f"Tags: {', '.join(tags)}")
            lines.append("")

        node_type = note.get("node_type", "")
        if node_type and node_type not in ("note", "idea"):
            lines.append(f"Type: {node_type}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Public API (matches IdeasPublisher interface)
    # ------------------------------------------------------------------

    def publish_bubble(self, bubble_id: str):
        """Publish a bubble and its ideas to Rowboat's MongoDB.

        Creates/updates a DataSource + DataSourceDocs so the rag-worker
        automatically processes them.
        """
        if not self._validate_schema():
            raise SchemaIncompatibleError("MongoDB schema check failed")

        from data import IdeasRepository, CanvasRepository
        from data.models import Idea

        ideas_repo = IdeasRepository()
        canvas_repo = CanvasRepository()

        bubble = ideas_repo.get(bubble_id)
        if not bubble:
            logger.debug(
                f"[RowboatMongo] Bubble {bubble_id} not found, skipping"
            )
            return

        # Collect notes (same logic as IdeasPublisher)
        notes = []
        seen_titles = set()

        child_rows = ideas_repo.db.fetch_all(
            "SELECT * FROM ideas WHERE parent_id = ?", (bubble_id,)
        )
        for r in child_rows:
            child = Idea.from_dict(dict(r))
            title = child.title or ""
            if title and title not in seen_titles:
                seen_titles.add(title)
                notes.append({
                    "id": child.id,
                    "title": title,
                    "content": child.description or "",
                    "tags": child.tags if child.tags else [],
                    "node_type": "idea",
                })

        all_nodes = canvas_repo.list_nodes(limit=2000)
        bubble_nodes = [n for n in all_nodes if n.linked_idea_id == bubble_id]
        for node in bubble_nodes:
            title = node.title or ""
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            notes.append({
                "id": node.id,
                "title": title,
                "content": node.content or "",
                "tags": [],
                "node_type": node.node_type or "note",
            })

        bubble_title = bubble.title or "Untitled"
        source_name = f"VibeMind - {bubble_title}"
        description = bubble.description or f"Bubble with {len(notes)} ideas"

        # Build an overview doc (always included as first doc)
        overview_lines = [f"# {bubble_title}", ""]
        if bubble.description:
            overview_lines.append(bubble.description)
            overview_lines.append("")
        overview_lines.append(f"Contains {len(notes)} ideas/notes.")
        overview_note = {
            "title": f"{bubble_title} - Overview",
            "content": "\n".join(overview_lines),
            "tags": [],
            "node_type": "overview",
        }
        all_notes = [overview_note] + notes

        # Check if source already exists
        existing = self._find_source_by_name(source_name)
        if existing:
            source_id = str(existing["_id"])
            # Mark old docs as deleted (rag-worker cleans up Qdrant)
            self._mark_all_docs_deleted(source_id)
            # Insert fresh docs
            self._insert_docs(source_id, all_notes)
            # Reset source to pending so rag-worker picks it up
            self._reset_source_to_pending(source_id)
            # Update description
            self._sources.update_one(
                {"_id": existing["_id"]},
                {"$set": {"description": description}},
            )
            logger.info(
                f"[RowboatMongo] Updated '{source_name}' "
                f"({len(all_notes)} docs)"
            )
        else:
            # Create new source + docs
            source_id = self._create_source(source_name, description)
            self._insert_docs(source_id, all_notes)
            logger.info(
                f"[RowboatMongo] Published '{source_name}' "
                f"({len(all_notes)} docs)"
            )

    def remove_bubble(self, title: str):
        """Remove a bubble's data source from MongoDB.

        Marks as deleted so rag-worker removes embeddings from Qdrant.
        """
        if not self._validate_schema():
            raise SchemaIncompatibleError("MongoDB schema check failed")

        source_name = f"VibeMind - {title}"
        existing = self._find_source_by_name(source_name)
        if not existing:
            logger.debug(
                f"[RowboatMongo] Source '{source_name}' not found, skipping"
            )
            return

        source_id = str(existing["_id"])
        self._mark_all_docs_deleted(source_id)
        self._mark_source_deleted(source_id)
        logger.info(f"[RowboatMongo] Marked '{source_name}' as deleted")

    # ------------------------------------------------------------------
    # Shuttle / Project data (Arbeitspaket enrichment)
    # ------------------------------------------------------------------

    def _upsert_doc(self, source_id: str, doc_name: str, content: str):
        """Insert or update a single doc by name within a source.

        Unlike _insert_docs which bulk-inserts, this finds an existing doc
        by name and updates it, or creates a new one. Used for shuttle docs
        that should not be duplicated on re-publish.
        """
        now = datetime.now(timezone.utc).isoformat()
        existing = self._docs.find_one({
            "sourceId": source_id,
            "projectId": self._project_id,
            "name": doc_name,
            "status": {"$ne": "deleted"},
        })

        if existing:
            self._docs.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "data": {"type": "text", "content": content},
                    "status": "pending",
                    "attempts": 0,
                    "lastUpdatedAt": now,
                    "error": None,
                }},
            )
        else:
            self._docs.insert_one({
                "sourceId": source_id,
                "projectId": self._project_id,
                "name": doc_name,
                "version": 1,
                "status": "pending",
                "content": None,
                "createdAt": now,
                "lastUpdatedAt": None,
                "attempts": 0,
                "error": None,
                "data": {"type": "text", "content": content},
            })

    def _build_project_text(self, project, shuttle) -> str:
        """Build markdown text for a project overview doc."""
        lines = [f"# Projekt: {project.name}", ""]

        if project.description:
            lines.append(project.description)
            lines.append("")

        lines.append(f"Status: {project.status}")
        if project.generation_status:
            lines.append(f"Generation: {project.generation_status}")
        if project.tech_stack:
            lines.append(f"Tech Stack: {project.tech_stack}")
        lines.append("")

        if shuttle:
            lines.append(f"Score: {shuttle.score:.1%}")
            lines.append(
                f"Requirements: {shuttle.passed_count}/{shuttle.total_count} passed"
            )
            lines.append(f"Pipeline Stage: {shuttle.current_stage}")
            lines.append("")

        if project.convergence_progress and project.convergence_progress > 0:
            lines.append(f"Convergence: {project.convergence_progress:.0f}%")
            lines.append("")

        return "\n".join(lines)

    def _build_requirements_overview_text(self, shuttle, requirements: list) -> str:
        """Build markdown text for a requirements overview doc."""
        lines = [
            f"# Requirements Overview — {shuttle.bubble_name}",
            "",
            f"Total: {len(requirements)} Requirements",
            f"Passed: {shuttle.passed_count} | Failed: {shuttle.failed_count}",
            f"Score: {shuttle.score:.1%}",
            "",
            "## Requirements",
            "",
        ]

        for req in requirements:
            req_id = req.get("id", "?")
            title = req.get("title", "Untitled")
            status = req.get("status", "pending")
            lines.append(f"- {req_id}: {title} ({status})")

        lines.append("")
        return "\n".join(lines)

    def _build_requirement_text(self, req: dict) -> str:
        """Build markdown text for a single requirement doc."""
        req_id = req.get("id", "REQ-???")
        title = req.get("title", "Untitled")
        lines = [f"# {req_id}: {title}", ""]

        description = req.get("description", "")
        if description:
            lines.append("## Beschreibung")
            lines.append(description)
            lines.append("")

        criteria = req.get("acceptance_criteria", [])
        if criteria:
            lines.append("## Acceptance Criteria")
            for c in criteria:
                lines.append(f"- {c}")
            lines.append("")

        stories = req.get("user_stories", [])
        if stories:
            lines.append("## User Stories")
            for s in stories:
                lines.append(f"- {s}")
            lines.append("")

        priority = req.get("priority", "")
        status = req.get("status", "")
        if priority or status:
            meta = []
            if priority:
                meta.append(f"Priority: {priority}")
            if status:
                meta.append(f"Status: {status}")
            lines.append(" | ".join(meta))
            lines.append("")

        return "\n".join(lines)

    def publish_shuttle_data(self, bubble_id: str):
        """Publish shuttle/project data into the bubble's existing source.

        Adds project overview + requirements as docs to create a complete
        Arbeitspaket (work package) in Rowboat.
        """
        if not self._validate_schema():
            raise SchemaIncompatibleError("MongoDB schema check failed")

        from data import IdeasRepository, ShuttlesRepository, ProjectsRepository

        ideas_repo = IdeasRepository()
        shuttles_repo = ShuttlesRepository()
        projects_repo = ProjectsRepository()

        bubble = ideas_repo.get(bubble_id)
        if not bubble:
            logger.debug(
                f"[RowboatMongo] Shuttle publish: bubble {bubble_id} not found"
            )
            return

        # Find shuttles for this bubble
        shuttles = shuttles_repo.list_by_bubble(bubble_id, limit=10)
        if not shuttles:
            logger.debug(
                f"[RowboatMongo] No shuttles for bubble {bubble_id}, skipping"
            )
            return

        # Use the most recent shuttle
        shuttle = shuttles[0]

        # Find the existing source for this bubble
        source_name = f"VibeMind - {bubble.title}"
        existing = self._find_source_by_name(source_name)
        if not existing:
            logger.debug(
                f"[RowboatMongo] Source '{source_name}' not found. "
                "Publish bubble first."
            )
            return

        source_id = str(existing["_id"])
        docs_added = 0

        # 1. Project overview doc
        if shuttle.project_id:
            project = projects_repo.get(shuttle.project_id)
            if project:
                content = self._build_project_text(project, shuttle)
                self._upsert_doc(
                    source_id,
                    f"[Projekt] {project.name}",
                    content,
                )
                docs_added += 1

        # 2. Requirements from stage_data or requirement_results
        requirements = []
        if shuttle.requirement_results and isinstance(
            shuttle.requirement_results, dict
        ):
            requirements = shuttle.requirement_results.get("requirements", [])
        if not requirements and shuttle.stage_data and isinstance(
            shuttle.stage_data, dict
        ):
            requirements = shuttle.stage_data.get("requirements", [])

        if requirements:
            # Requirements overview
            overview_text = self._build_requirements_overview_text(
                shuttle, requirements
            )
            self._upsert_doc(
                source_id,
                f"[REQ-Overview] {shuttle.bubble_name}",
                overview_text,
            )
            docs_added += 1

            # Individual requirement docs
            for req in requirements:
                req_id = req.get("id", "REQ-???")
                req_title = req.get("title", "Untitled")
                content = self._build_requirement_text(req)
                self._upsert_doc(
                    source_id,
                    f"[{req_id}] {req_title}",
                    content,
                )
                docs_added += 1

        if docs_added > 0:
            # Reset source to pending so rag-worker re-indexes
            self._reset_source_to_pending(source_id)
            logger.info(
                f"[RowboatMongo] Shuttle data published for '{source_name}' "
                f"({docs_added} docs added/updated)"
            )

    # ------------------------------------------------------------------
    # Callback system (for BrainSeeder)
    # ------------------------------------------------------------------

    def on_source_updated(self, callback: Callable):
        """Register a callback for when a source is updated/created.

        Callback signature: callback(source_id: str, source_name: str)
        """
        self._on_source_updated_callbacks.append(callback)

    def _notify_source_updated(self, source_id: str, source_name: str):
        """Fire all registered callbacks after a source update."""
        for cb in self._on_source_updated_callbacks:
            try:
                cb(source_id, source_name)
            except Exception as e:
                logger.debug(f"[RowboatMongo] Callback error: {e}")

    # ------------------------------------------------------------------
    # Supermemory Memories
    # ------------------------------------------------------------------

    def _build_memory_text(self, memory: Dict[str, Any]) -> str:
        """Build markdown text for a Supermemory memory entry."""
        lines = []
        content = memory.get("content", "")
        mem_type = memory.get("type", "general")
        lines.append(f"# Memory ({mem_type})")
        lines.append("")

        if content:
            lines.append(content)
            lines.append("")

        metadata = memory.get("metadata", {})
        if metadata.get("intent_type"):
            lines.append(f"Intent: {metadata['intent_type']}")
        if metadata.get("agent"):
            lines.append(f"Agent: {metadata['agent']}")
        if metadata.get("timestamp"):
            lines.append(f"Time: {metadata['timestamp']}")
        if metadata.get("event_type"):
            lines.append(f"Event: {metadata['event_type']}")
        if metadata.get("duration_ms"):
            lines.append(f"Duration: {metadata['duration_ms']}ms")

        lines.append("")
        return "\n".join(lines)

    def publish_supermemory_snapshot(
        self, container_tag: str, memories: List[Dict[str, Any]]
    ):
        """Publish Supermemory memories to Rowboat MongoDB.

        Each memory becomes a doc within a container-specific source.
        """
        if not self._validate_schema():
            return
        if not memories:
            return

        source_name = f"VibeMind - Memory:{container_tag}"
        description = f"Supermemory {container_tag} ({len(memories)} entries)"

        existing = self._find_source_by_name(source_name)
        if existing:
            source_id = str(existing["_id"])
        else:
            source_id = self._create_source(source_name, description)

        docs_added = 0
        for mem in memories:
            custom_id = mem.get("custom_id") or mem.get("id", f"mem-{docs_added}")
            content = self._build_memory_text(mem)
            self._upsert_doc(source_id, f"[Memory] {custom_id}", content)
            docs_added += 1

        if docs_added > 0:
            self._reset_source_to_pending(source_id)
            self._notify_source_updated(source_id, source_name)
            logger.info(
                f"[RowboatMongo] Published {docs_added} memories "
                f"for '{source_name}'"
            )

    # ------------------------------------------------------------------
    # SWE / Code Generation Projects
    # ------------------------------------------------------------------

    def _build_project_standalone_text(self, project) -> str:
        """Build markdown text for a standalone project doc (no shuttle)."""
        lines = [f"# Projekt: {project.name}", ""]

        if project.description:
            lines.append(project.description)
            lines.append("")

        lines.append(f"Status: {project.status}")
        if project.generation_status:
            lines.append(f"Generation: {project.generation_status}")
        if project.tech_stack:
            lines.append(f"Tech Stack: {project.tech_stack}")
        if project.convergence_progress and project.convergence_progress > 0:
            lines.append(f"Convergence: {project.convergence_progress:.0f}%")
        if project.error_message:
            lines.append(f"Error: {project.error_message}")

        lines.append("")
        return "\n".join(lines)

    def _build_quality_report_text(self, report: Dict[str, Any]) -> str:
        """Build markdown text for a code quality report."""
        lines = ["# Quality Report", ""]

        summary = report.get("summary", {})
        if summary:
            lines.append(f"Total Issues: {summary.get('total_issues', 0)}")
            lines.append(f"Critical: {summary.get('critical', 0)}")
            lines.append(f"High: {summary.get('high', 0)}")
            lines.append(f"Medium: {summary.get('medium', 0)}")
            lines.append(f"Low: {summary.get('low', 0)}")
            lines.append("")

        issues = report.get("issues", [])
        if issues:
            lines.append("## Issues")
            for issue in issues[:20]:  # Cap at 20
                severity = issue.get("severity", "?")
                title = issue.get("title", "Untitled")
                lines.append(f"- [{severity}] {title}")
            lines.append("")

        return "\n".join(lines)

    def publish_project(self, project_id: str):
        """Publish a code generation project to Rowboat MongoDB.

        Creates a standalone source with project overview + quality report.
        """
        if not self._validate_schema():
            return

        from data import ProjectsRepository

        projects_repo = ProjectsRepository()
        project = projects_repo.get(project_id)
        if not project:
            logger.debug(f"[RowboatMongo] Project {project_id} not found")
            return

        source_name = f"VibeMind - Projekt:{project.name}"
        description = (
            f"Code generation project ({project.generation_status or project.status})"
        )

        existing = self._find_source_by_name(source_name)
        if existing:
            source_id = str(existing["_id"])
        else:
            source_id = self._create_source(source_name, description)

        # Project overview doc
        content = self._build_project_standalone_text(project)
        self._upsert_doc(source_id, f"[Projekt] {project.name}", content)

        # Quality report (if exists on filesystem)
        if project.project_path:
            report_path = os.path.join(
                project.project_path, "self_critique_report.json"
            )
            if os.path.isfile(report_path):
                try:
                    with open(report_path, "r", encoding="utf-8") as f:
                        report = json.load(f)
                    report_content = self._build_quality_report_text(report)
                    self._upsert_doc(
                        source_id,
                        f"[Quality] {project.name}",
                        report_content,
                    )
                except Exception as e:
                    logger.debug(f"[RowboatMongo] Quality report read error: {e}")

        # Requirements from metadata
        if project.requirements_json:
            try:
                reqs = (
                    json.loads(project.requirements_json)
                    if isinstance(project.requirements_json, str)
                    else project.requirements_json
                )
                req_list = reqs.get("requirements", [])
                for req in req_list:
                    req_content = self._build_requirement_text(req)
                    req_id = req.get("id", "REQ-???")
                    self._upsert_doc(
                        source_id, f"[{req_id}] {req.get('title', '')}", req_content
                    )
            except Exception as e:
                logger.debug(f"[RowboatMongo] Requirements parse error: {e}")

        self._reset_source_to_pending(source_id)
        self._notify_source_updated(source_id, source_name)
        logger.info(f"[RowboatMongo] Published project '{project.name}'")

    # ------------------------------------------------------------------
    # N8n Workflows
    # ------------------------------------------------------------------

    def _build_workflow_text(self, workflow_data: Dict[str, Any]) -> str:
        """Build markdown text for an n8n workflow."""
        name = workflow_data.get("name", "Unnamed Workflow")
        lines = [f"# Workflow: {name}", ""]

        description = workflow_data.get("description", "")
        if description:
            lines.append(description)
            lines.append("")

        nodes = workflow_data.get("nodes", [])
        if nodes:
            lines.append(f"## Nodes ({len(nodes)})")
            for node in nodes:
                node_name = node.get("name", "?")
                node_type = node.get("type", "?")
                lines.append(f"- {node_name} ({node_type})")
            lines.append("")

        connections = workflow_data.get("connections", [])
        if connections:
            lines.append(f"## Connections ({len(connections)})")
            for conn in connections[:20]:
                src = conn.get("from", "?")
                tgt = conn.get("to", "?")
                conn_type = conn.get("type", "main")
                lines.append(f"- {src} -> {tgt} ({conn_type})")
            lines.append("")

        creds = workflow_data.get("credentials_needed", [])
        if creds:
            lines.append(f"Credentials: {', '.join(creds)}")
            lines.append("")

        return "\n".join(lines)

    def publish_n8n_workflow(
        self, workflow_name: str, workflow_data: Dict[str, Any]
    ):
        """Publish an n8n workflow to Rowboat MongoDB.

        All workflows share a single source, one doc per workflow.
        """
        if not self._validate_schema():
            return

        source_name = "VibeMind - N8n Workflows"
        existing = self._find_source_by_name(source_name)
        if existing:
            source_id = str(existing["_id"])
        else:
            source_id = self._create_source(
                source_name, "N8n workflow definitions"
            )

        content = self._build_workflow_text(workflow_data)
        self._upsert_doc(source_id, f"[Workflow] {workflow_name}", content)

        self._reset_source_to_pending(source_id)
        self._notify_source_updated(source_id, source_name)
        logger.info(f"[RowboatMongo] Published workflow '{workflow_name}'")

    # ------------------------------------------------------------------
    # Desktop Actions
    # ------------------------------------------------------------------

    def _build_action_log_text(self, actions: List[Dict[str, Any]]) -> str:
        """Build markdown text for a batch of desktop actions."""
        lines = [f"# Desktop Actions ({len(actions)} actions)", ""]

        for action in actions:
            action_type = action.get("action_type", "unknown")
            target = action.get("target", "")
            ts = action.get("timestamp", "")
            duration = action.get("duration_seconds", "")

            entry = f"- [{ts}] {action_type}"
            if target:
                entry += f": {target}"
            if duration:
                entry += f" ({duration}s)"
            lines.append(entry)

        lines.append("")
        return "\n".join(lines)

    def buffer_desktop_action(self, session_id: str, action: Dict[str, Any]):
        """Buffer a desktop action for batch publishing.

        Actions are flushed via flush_desktop_buffer() every 30s or 50 actions.
        """
        with self._desktop_buffer_lock:
            if session_id not in self._desktop_buffer:
                self._desktop_buffer[session_id] = []
            self._desktop_buffer[session_id].append(action)

            # Auto-flush at 50 actions
            if len(self._desktop_buffer[session_id]) >= 50:
                actions = self._desktop_buffer.pop(session_id)
                self._publish_desktop_actions(session_id, actions)

    def flush_desktop_buffer(self):
        """Flush all buffered desktop actions to Rowboat."""
        with self._desktop_buffer_lock:
            sessions = dict(self._desktop_buffer)
            self._desktop_buffer.clear()

        for session_id, actions in sessions.items():
            if actions:
                self._publish_desktop_actions(session_id, actions)

    def _publish_desktop_actions(
        self, session_id: str, actions: List[Dict[str, Any]]
    ):
        """Publish a batch of desktop actions to Rowboat MongoDB."""
        if not self._validate_schema():
            return

        source_name = f"VibeMind - Desktop:Session-{session_id}"
        existing = self._find_source_by_name(source_name)
        if existing:
            source_id = str(existing["_id"])
        else:
            source_id = self._create_source(
                source_name, f"Desktop actions ({len(actions)} actions)"
            )

        content = self._build_action_log_text(actions)
        ts = datetime.now(timezone.utc).strftime("%H%M%S")
        self._upsert_doc(
            source_id, f"[Actions] batch-{ts}", content
        )

        self._reset_source_to_pending(source_id)
        self._notify_source_updated(source_id, source_name)
        logger.info(
            f"[RowboatMongo] Published {len(actions)} desktop actions "
            f"for session {session_id}"
        )

    # ------------------------------------------------------------------
    # AgentFarm Metrics
    # ------------------------------------------------------------------

    def _build_agent_metrics_text(
        self, agent_name: str, metrics: Dict[str, Any]
    ) -> str:
        """Build markdown text for agent execution metrics."""
        lines = [f"# Agent: {agent_name}", ""]

        total = metrics.get("total_executions", 0)
        success = metrics.get("success_count", 0)
        error = metrics.get("error_count", 0)
        rate = (success / total * 100) if total > 0 else 0

        lines.append(f"Total Executions: {total}")
        lines.append(f"Success Rate: {rate:.0f}%")
        lines.append(f"Errors: {error}")
        lines.append("")

        tools = metrics.get("tools_used", {})
        if tools:
            lines.append("## Tools Used")
            for tool, count in sorted(
                tools.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"- {tool}: {count}x")
            lines.append("")

        events = metrics.get("event_types", {})
        if events:
            lines.append("## Event Types")
            for evt, count in sorted(
                events.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"- {evt}: {count}x")
            lines.append("")

        avg_ms = metrics.get("avg_duration_ms")
        if avg_ms:
            lines.append(f"Avg Duration: {avg_ms:.0f}ms")
            lines.append("")

        return "\n".join(lines)

    def record_agent_execution(
        self,
        agent_name: str,
        event_type: str,
        tool_name: str,
        success: bool,
        duration_ms: float = 0,
    ):
        """Record an agent tool execution for aggregated publishing.

        Metrics are flushed via flush_agent_metrics() every 5 minutes.
        """
        with self._agent_metrics_lock:
            if agent_name not in self._agent_metrics:
                self._agent_metrics[agent_name] = {
                    "total_executions": 0,
                    "success_count": 0,
                    "error_count": 0,
                    "tools_used": {},
                    "event_types": {},
                    "total_duration_ms": 0,
                }
            m = self._agent_metrics[agent_name]
            m["total_executions"] += 1
            if success:
                m["success_count"] += 1
            else:
                m["error_count"] += 1
            m["tools_used"][tool_name] = m["tools_used"].get(tool_name, 0) + 1
            m["event_types"][event_type] = (
                m["event_types"].get(event_type, 0) + 1
            )
            m["total_duration_ms"] += duration_ms

    def flush_agent_metrics(self):
        """Publish aggregated agent metrics to Rowboat MongoDB."""
        with self._agent_metrics_lock:
            metrics_snapshot = dict(self._agent_metrics)
            self._agent_metrics.clear()

        if not metrics_snapshot or not self._validate_schema():
            return

        source_name = "VibeMind - AgentFarm"
        existing = self._find_source_by_name(source_name)
        if existing:
            source_id = str(existing["_id"])
        else:
            source_id = self._create_source(
                source_name, "Backend agent execution metrics"
            )

        for agent_name, metrics in metrics_snapshot.items():
            total = metrics["total_executions"]
            if total > 0:
                metrics["avg_duration_ms"] = (
                    metrics["total_duration_ms"] / total
                )
            content = self._build_agent_metrics_text(agent_name, metrics)
            self._upsert_doc(
                source_id, f"[Agent] {agent_name}", content
            )

        self._reset_source_to_pending(source_id)
        self._notify_source_updated(source_id, source_name)
        logger.info(
            f"[RowboatMongo] Published metrics for "
            f"{len(metrics_snapshot)} agents"
        )

    # ------------------------------------------------------------------
    # Full sync
    # ------------------------------------------------------------------

    def sync_all(self):
        """Publish all existing bubbles and their shuttle data (startup sync)."""
        if not self._validate_schema():
            raise SchemaIncompatibleError("MongoDB schema check failed")

        from data import IdeasRepository, ShuttlesRepository
        from data.models import Idea

        ideas_repo = IdeasRepository()
        rows = ideas_repo.db.fetch_all(
            "SELECT * FROM ideas WHERE parent_id IS NULL"
        )
        bubbles = [Idea.from_dict(dict(r)) for r in rows]

        published = 0
        shuttle_enriched = 0
        for bubble in bubbles:
            try:
                self.publish_bubble(bubble_id=bubble.id)
                published += 1
            except Exception as e:
                logger.debug(
                    f"[RowboatMongo] sync_all: skip {bubble.title}: {e}"
                )

        # Enrich with shuttle data (arrived shuttles only)
        shuttles_repo = ShuttlesRepository()
        for bubble in bubbles:
            try:
                shuttles = shuttles_repo.list_by_bubble(bubble.id, limit=1)
                if shuttles and shuttles[0].status == "arrived":
                    self.publish_shuttle_data(bubble.id)
                    shuttle_enriched += 1
            except Exception as e:
                logger.debug(
                    f"[RowboatMongo] sync_all shuttle: "
                    f"skip {bubble.title}: {e}"
                )

        # Sync code generation projects
        projects_synced = 0
        try:
            from data import ProjectsRepository
            projects_repo = ProjectsRepository()
            all_projects = projects_repo.list()
            for project in all_projects:
                try:
                    self.publish_project(project.id)
                    projects_synced += 1
                except Exception as e:
                    logger.debug(
                        f"[RowboatMongo] sync_all project: "
                        f"skip {project.name}: {e}"
                    )
        except Exception as e:
            logger.debug(f"[RowboatMongo] sync_all projects: {e}")

        # Sync n8n workflows (if API reachable)
        workflows_synced = 0
        n8n_url = os.getenv("N8N_BASE_URL", "")
        if n8n_url:
            try:
                import httpx
                resp = httpx.get(
                    f"{n8n_url}/api/v1/workflows",
                    headers={"X-N8N-API-KEY": os.getenv("N8N_API_KEY", "")},
                    timeout=10,
                )
                if resp.status_code == 200:
                    workflows = resp.json().get("data", [])
                    for wf in workflows:
                        try:
                            self.publish_n8n_workflow(
                                wf.get("name", "Unnamed"), wf
                            )
                            workflows_synced += 1
                        except Exception as e:
                            logger.debug(
                                f"[RowboatMongo] sync_all n8n: "
                                f"skip {wf.get('name')}: {e}"
                            )
            except Exception as e:
                logger.debug(f"[RowboatMongo] sync_all n8n: {e}")

        logger.info(
            f"[RowboatMongo] Initial sync: "
            f"{published}/{len(bubbles)} bubbles published, "
            f"{shuttle_enriched} enriched with shuttle data, "
            f"{projects_synced} projects, {workflows_synced} n8n workflows"
        )
