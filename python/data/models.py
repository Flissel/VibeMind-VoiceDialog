"""
Vibemind Data Models

Dataclasses for Ideas, Projects, and Canvas elements.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import json

# Generation status enum values
class GenerationStatus:
    """Status values for code generation projects."""
    PENDING = "pending"
    GENERATING = "generating"
    CONVERGING = "converging"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"
    PREVIEWING = "previewing"


@dataclass
class Idea:
    """
    An idea captured from voice or text input.

    Ideas can be scored and promoted to projects.
    Each idea can have its own agent for voice interaction.
    """
    id: str
    title: str
    description: str = ""
    source: str = "voice"  # "voice" or "text"
    created_at: datetime = field(default_factory=datetime.now)
    score: float = 0.0  # Composite score 0-100
    status: str = "raw"  # "raw", "scored", "promoted", "archived"
    promoted_to_project_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Scoring dimensions (0-10 each)
    feasibility: float = 0.0
    impact: float = 0.0
    novelty: float = 0.0
    urgency: float = 0.0

    # Agent ID for this bubble/idea (for multi-agent architecture)
    agent_id: Optional[str] = None

    # Parent bubble ID for nested bubble hierarchy
    parent_id: Optional[str] = None

    # Embedding for semantic search
    embedding_vector: Optional[List[float]] = None
    embedding_hash: Optional[str] = None

    def calculate_score(self) -> float:
        """Calculate composite score from dimensions (0-100)"""
        if all(d == 0 for d in [self.feasibility, self.impact, self.novelty, self.urgency]):
            return 0.0
        # Weighted average, then scale to 0-100
        weights = {"feasibility": 0.25, "impact": 0.35, "novelty": 0.2, "urgency": 0.2}
        weighted_sum = (
            self.feasibility * weights["feasibility"] +
            self.impact * weights["impact"] +
            self.novelty * weights["novelty"] +
            self.urgency * weights["urgency"]
        )
        return weighted_sum * 10  # Scale from 0-10 to 0-100

    def is_ready_for_promotion(self, threshold: float = 70.0) -> bool:
        """Check if idea score meets promotion threshold"""
        return self.score >= threshold

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "score": self.score,
            "status": self.status,
            "promoted_to_project_id": self.promoted_to_project_id,
            "tags": json.dumps(self.tags),
            "metadata": json.dumps({
                **self.metadata,
                "feasibility": self.feasibility,
                "impact": self.impact,
                "novelty": self.novelty,
                "urgency": self.urgency,
            }),
            "agent_id": self.agent_id,
            "parent_id": self.parent_id,
            "embedding_vector": json.dumps(self.embedding_vector) if self.embedding_vector else None,
            "embedding_hash": self.embedding_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Idea":
        """Create Idea from database row"""
        raw_tags = data.get("tags")
        tags = json.loads(raw_tags) if isinstance(raw_tags, str) else (raw_tags or [])
        raw_meta = data.get("metadata")
        metadata = json.loads(raw_meta) if isinstance(raw_meta, str) else (raw_meta or {})

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            source=data.get("source", "voice"),
            created_at=created_at,
            score=data.get("score", 0.0),
            status=data.get("status", "raw"),
            promoted_to_project_id=data.get("promoted_to_project_id"),
            tags=tags,
            metadata=metadata,
            feasibility=metadata.get("feasibility", 0.0),
            impact=metadata.get("impact", 0.0),
            novelty=metadata.get("novelty", 0.0),
            urgency=metadata.get("urgency", 0.0),
            agent_id=data.get("agent_id"),
            parent_id=data.get("parent_id"),
            embedding_vector=json.loads(data["embedding_vector"]) if data.get("embedding_vector") else None,
            embedding_hash=data.get("embedding_hash"),
        )


@dataclass
class Project:
    """
    A project created from a promoted idea or directly.

    Projects track progress and can be linked back to source ideas.
    Extended with code generation fields for Hybrid Run integration.
    """
    id: str
    name: str
    description: str = ""
    status: str = "active"  # "active", "paused", "completed", "archived"
    created_at: datetime = field(default_factory=datetime.now)
    from_idea_id: Optional[str] = None
    progress: float = 0.0  # 0-100 percentage
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Code Generation Fields (Hybrid Run Integration)
    project_path: Optional[str] = None  # Path to generated project files
    generation_status: str = "pending"  # See GenerationStatus class
    vnc_port: Optional[int] = None  # Port for VNC preview
    job_id: Optional[str] = None  # Hybrid Run job identifier
    requirements_json: Optional[str] = None  # JSON requirements for generation
    convergence_progress: float = 0.0  # 0-100 Society of Mind convergence
    preview_url: Optional[str] = None  # noVNC preview URL
    tech_stack: Optional[str] = None  # e.g., "react", "vue", "python-flask"
    error_message: Optional[str] = None  # Last error if failed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "from_idea_id": self.from_idea_id,
            "progress": self.progress,
            "metadata": json.dumps(self.metadata),
            # Code Generation Fields
            "project_path": self.project_path,
            "generation_status": self.generation_status,
            "vnc_port": self.vnc_port,
            "job_id": self.job_id,
            "requirements_json": self.requirements_json,
            "convergence_progress": self.convergence_progress,
            "preview_url": self.preview_url,
            "tech_stack": self.tech_stack,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        """Create Project from database row"""
        metadata = json.loads(data.get("metadata", "{}")) if isinstance(data.get("metadata"), str) else data.get("metadata", {})
        if metadata is None:
            metadata = {}

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            status=data.get("status", "active"),
            created_at=created_at,
            from_idea_id=data.get("from_idea_id"),
            progress=data.get("progress", 0.0),
            metadata=metadata,
            # Code Generation Fields
            project_path=data.get("project_path"),
            generation_status=data.get("generation_status", "pending"),
            vnc_port=data.get("vnc_port"),
            job_id=data.get("job_id"),
            requirements_json=data.get("requirements_json"),
            convergence_progress=data.get("convergence_progress", 0.0),
            preview_url=data.get("preview_url"),
            tech_stack=data.get("tech_stack"),
            error_message=data.get("error_message"),
        )


@dataclass
class CanvasNode:
    """
    A node on the visual canvas.

    Can represent ideas, projects, or custom content.
    """
    id: str
    node_type: str  # "idea", "project", "note", "image", "link"
    title: str = ""
    content: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 200.0
    height: float = 100.0
    linked_idea_id: Optional[str] = None
    linked_project_id: Optional[str] = None
    summary: Optional[str] = None  # AI-generated summary of the node content
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Structured formatting fields (for LLM-generated structured content)
    format_schema: Optional[Dict[str, Any]] = None  # JSON Schema defining allowed structure
    content_json: Optional[Dict[str, Any]] = None   # Structured JSON content (alternative to plain text)
    previous_content_json: Optional[Dict[str, Any]] = None  # Previous content_json for revert
    last_formatted: Optional[datetime] = None       # When content was last structured by LLM

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "node_type": self.node_type,
            "title": self.title,
            "content": self.content,
            "x": self.x,
            "y": self.y,
            "linked_idea_id": self.linked_idea_id,
            "linked_project_id": self.linked_project_id,
            "summary": self.summary,
            "metadata": json.dumps({
                **self.metadata,
                "width": self.width,
                "height": self.height,
            }),
            # Structured formatting fields
            "format_schema": json.dumps(self.format_schema) if self.format_schema else None,
            "content_json": json.dumps(self.content_json) if self.content_json else None,
            "previous_content_json": json.dumps(self.previous_content_json) if self.previous_content_json else None,
            "last_formatted": self.last_formatted.isoformat() if self.last_formatted else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasNode":
        """Create CanvasNode from database row"""
        metadata = json.loads(data.get("metadata", "{}")) if isinstance(data.get("metadata"), str) else data.get("metadata", {})
        if metadata is None:
            metadata = {}

        # Parse structured formatting fields
        format_schema = json.loads(data.get("format_schema", "{}")) if isinstance(data.get("format_schema"), str) and data.get("format_schema") else None
        content_json = json.loads(data.get("content_json", "{}")) if isinstance(data.get("content_json"), str) and data.get("content_json") else None
        previous_content_json = json.loads(data.get("previous_content_json", "{}")) if isinstance(data.get("previous_content_json"), str) and data.get("previous_content_json") else None

        last_formatted = data.get("last_formatted")
        if isinstance(last_formatted, str):
            last_formatted = datetime.fromisoformat(last_formatted)

        return cls(
            id=data["id"],
            node_type=data["node_type"],
            title=data.get("title", ""),
            content=data.get("content", ""),
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            width=metadata.get("width", 200.0),
            height=metadata.get("height", 100.0),
            linked_idea_id=data.get("linked_idea_id"),
            linked_project_id=data.get("linked_project_id"),
            summary=data.get("summary"),
            metadata=metadata,
            # Structured formatting fields
            format_schema=format_schema,
            content_json=content_json,
            previous_content_json=previous_content_json,
            last_formatted=last_formatted,
        )


@dataclass
class CanvasEdge:
    """
    An edge connecting two canvas nodes.
    """
    id: str
    from_node_id: str
    to_node_id: str
    edge_type: str = "default"  # "default", "dependency", "reference", "flow"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "edge_type": self.edge_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasEdge":
        """Create CanvasEdge from database row"""
        return cls(
            id=data["id"],
            from_node_id=data["from_node_id"],
            to_node_id=data["to_node_id"],
            edge_type=data.get("edge_type", "default"),
        )


@dataclass
class ConversationMessage:
    """
    A single message in a conversation history.

    Persists each voice dialog message for supermemory.
    """
    id: str
    session_id: str
    speaker: str  # "user" or "agent"
    text: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "speaker": self.speaker,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMessage":
        """Create ConversationMessage from database row"""
        metadata = json.loads(data.get("metadata", "{}")) if isinstance(data.get("metadata"), str) else data.get("metadata", {})
        if metadata is None:
            metadata = {}

        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        return cls(
            id=data["id"],
            session_id=data["session_id"],
            speaker=data["speaker"],
            text=data["text"],
            timestamp=timestamp,
            metadata=metadata,
        )


@dataclass
class ConversationSession:
    """
    A conversation session grouping multiple messages.

    Tracks conversation lifecycle and can store LLM-generated summaries.
    """
    id: str
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    summary: Optional[str] = None
    agent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "summary": self.summary,
            "agent_id": self.agent_id,
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSession":
        """Create ConversationSession from database row"""
        metadata = json.loads(data.get("metadata", "{}")) if isinstance(data.get("metadata"), str) else data.get("metadata", {})
        if metadata is None:
            metadata = {}

        started_at = data.get("started_at")
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)
        elif started_at is None:
            started_at = datetime.now()

        ended_at = data.get("ended_at")
        if isinstance(ended_at, str):
            ended_at = datetime.fromisoformat(ended_at)

        return cls(
            id=data["id"],
            started_at=started_at,
            ended_at=ended_at,
            summary=data.get("summary"),
            agent_id=data.get("agent_id"),
            metadata=metadata,
        )


# Shuttle status enum values
class ShuttleStatus:
    """Status values for requirement shuttles."""
    LAUNCHING = "launching"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    NEEDS_WORK = "needs_work"


# DNA Pipeline stages (from req-orchestrator)
class ShuttleStage:
    """The 5 DNA pipeline stages from req-orchestrator."""
    MINING = "mining"              # Stage 1: Extract requirements from documents
    REQUIREMENTS = "requirements"  # Stage 2: Store/manage requirements
    VALIDATION = "validation"      # Stage 3: 9-criteria quality scoring
    KNOWLEDGE_GRAPH = "knowledge_graph"  # Stage 4: Build entity relationships
    TECHSTACK = "techstack"        # Stage 5: Generate tech recommendations
    COMPLETE = "complete"          # Done - all stages passed


# Map stages to progress (0.0 - 1.0) for shuttle positioning on curve
STAGE_PROGRESS = {
    ShuttleStage.MINING: 0.2,
    ShuttleStage.REQUIREMENTS: 0.4,
    ShuttleStage.VALIDATION: 0.6,
    ShuttleStage.KNOWLEDGE_GRAPH: 0.8,
    ShuttleStage.TECHSTACK: 1.0,
    ShuttleStage.COMPLETE: 1.0,
}


# Shuttle type for multi-shuttle per checkpoint architecture
class ShuttleType:
    """Shuttle types for stage-specific shuttles."""
    FULL = "full"  # Legacy: single shuttle travels through all stages
    MINING = "mining"  # Stage-specific: parked at Mining checkpoint
    VALIDATION = "validation"  # Stage-specific: parked at Validation checkpoint
    KNOWLEDGE_GRAPH = "knowledge_graph"  # Stage-specific: parked at Knowledge Graph checkpoint
    TECHSTACK = "techstack"  # Stage-specific: parked at TechStack checkpoint


@dataclass
class Shuttle:
    """
    A requirement shuttle tracking evaluation progress.

    Shuttles represent requirements being evaluated by req-orchestrator.
    Score determines position on the journey from Ideas to Projects space.
    Current stage tracks progress through the 5 DNA pipeline stages.
    Links to a project_id which is created immediately when shuttle launches.

    Multi-Shuttle Architecture (Phase 13):
    - stage_type='full': Legacy single shuttle that travels through all stages
    - stage_type='mining'/'validation'/'knowledge_graph'/'techstack': Stage-specific
      shuttles that stay parked at their checkpoint, containing only that stage's data
    """
    id: str
    shuttle_id: str  # Visual ID (e.g., "shuttle-e-ticketing-1701234567")
    bubble_id: str
    bubble_name: str
    score: float = 0.0  # Overall evaluation score (0.0-1.0)
    passed_count: int = 0
    failed_count: int = 0
    total_count: int = 0
    status: str = ShuttleStatus.LAUNCHING
    current_stage: str = ShuttleStage.MINING  # Current DNA pipeline stage
    project_id: Optional[str] = None  # Links to project created at shuttle launch
    stage_type: str = ShuttleType.FULL  # 'full', 'mining', 'validation', 'knowledge_graph', 'techstack'
    stage_data: Dict[str, Any] = field(default_factory=dict)  # Stage-specific data only
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    requirement_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "shuttle_id": self.shuttle_id,
            "bubble_id": self.bubble_id,
            "bubble_name": self.bubble_name,
            "score": self.score,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "total_count": self.total_count,
            "status": self.status,
            "current_stage": self.current_stage,
            "project_id": self.project_id,
            "stage_type": self.stage_type,
            "stage_data": json.dumps(self.stage_data),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "requirement_results": json.dumps(self.requirement_results),
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Shuttle":
        """Create Shuttle from database row"""
        requirement_results = json.loads(data.get("requirement_results", "{}")) if isinstance(data.get("requirement_results"), str) else data.get("requirement_results", {})
        metadata = json.loads(data.get("metadata", "{}")) if isinstance(data.get("metadata"), str) else data.get("metadata", {})
        if metadata is None:
            metadata = {}
        stage_data = json.loads(data.get("stage_data", "{}")) if isinstance(data.get("stage_data"), str) else data.get("stage_data", {})

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        completed_at = data.get("completed_at")
        if isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at)

        return cls(
            id=data["id"],
            shuttle_id=data["shuttle_id"],
            bubble_id=data["bubble_id"],
            bubble_name=data["bubble_name"],
            score=data.get("score", 0.0),
            passed_count=data.get("passed_count", 0),
            failed_count=data.get("failed_count", 0),
            total_count=data.get("total_count", 0),
            status=data.get("status", ShuttleStatus.LAUNCHING),
            current_stage=data.get("current_stage", ShuttleStage.MINING),
            project_id=data.get("project_id"),
            stage_type=data.get("stage_type", ShuttleType.FULL),
            stage_data=stage_data,
            created_at=created_at,
            completed_at=completed_at,
            requirement_results=requirement_results,
            metadata=metadata,
        )


# Task status enum values
class TaskStatus:
    """Status values for persistent tasks."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """
    A persistent task tracked across conversation sessions.

    Used by Rachel to remember ongoing tasks and their status.
    Tasks are created for complex operations and tracked until completion.
    """
    id: str
    title: str
    user_id: str = "default"
    session_id: Optional[str] = None
    description: str = ""
    status: str = TaskStatus.PENDING

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Execution context
    intent_type: Optional[str] = None  # original event_type (idea.move, code.generate, etc.)
    payload: Dict[str, Any] = field(default_factory=dict)  # original parameters
    job_id: Optional[str] = None  # last job_id for this task
    progress: int = 0  # 0-100
    stage: str = ""  # current stage description

    # Results
    result: Optional[str] = None
    error: Optional[str] = None

    # Priority and tags
    priority: int = 2  # 1=low, 2=medium, 3=high
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "title": self.title,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "intent_type": self.intent_type,
            "payload": json.dumps(self.payload),
            "job_id": self.job_id,
            "progress": self.progress,
            "stage": self.stage,
            "result": self.result,
            "error": self.error,
            "priority": self.priority,
            "tags": json.dumps(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create Task from database row"""
        payload = json.loads(data.get("payload", "{}")) if isinstance(data.get("payload"), str) else data.get("payload", {})
        tags = json.loads(data.get("tags", "[]")) if isinstance(data.get("tags"), str) else data.get("tags", [])

        def parse_datetime(value):
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            return value

        return cls(
            id=data["id"],
            title=data["title"],
            user_id=data.get("user_id", "default"),
            session_id=data.get("session_id"),
            description=data.get("description", ""),
            status=data.get("status", TaskStatus.PENDING),
            created_at=parse_datetime(data.get("created_at")) or datetime.now(),
            started_at=parse_datetime(data.get("started_at")),
            completed_at=parse_datetime(data.get("completed_at")),
            updated_at=parse_datetime(data.get("updated_at")),
            intent_type=data.get("intent_type"),
            payload=payload,
            job_id=data.get("job_id"),
            progress=data.get("progress", 0),
            stage=data.get("stage", ""),
            result=data.get("result"),
            error=data.get("error"),
            priority=data.get("priority", 2),
            tags=tags,
        )


# Mermaid diagram type enum values
class MermaidDiagramType:
    """Mermaid diagram types."""
    FLOWCHART = "flowchart"
    SEQUENCE = "sequenceDiagram"
    CLASS = "classDiagram"
    STATE = "stateDiagram"
    ER = "erDiagram"
    GANTT = "gantt"
    PIE = "pie"
    JOURNEY = "journey"
    MINDMAP = "mindmap"
    TIMELINE = "timeline"
    REQUIREMENT = "requirementDiagram"
    GITGRAPH = "gitgraph"
    C4 = "C4Context"


@dataclass
class MermaidDiagram:
    """
    A mermaid diagram generated from requirements or ideas.

    Supports various diagram types: flowchart, sequence, class, state, ER, gantt, etc.
    Links back to source ideas/requirements for traceability.
    """
    id: str
    title: str
    diagram_type: str = MermaidDiagramType.FLOWCHART
    content: str = ""
    source_idea_id: Optional[str] = None
    source_shuttle_id: Optional[str] = None
    source_requirement_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "title": self.title,
            "diagram_type": self.diagram_type,
            "content": self.content,
            "source_idea_id": self.source_idea_id,
            "source_shuttle_id": self.source_shuttle_id,
            "source_requirement_ids": json.dumps(self.source_requirement_ids),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "version": self.version,
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MermaidDiagram":
        """Create MermaidDiagram from database row."""
        requirement_ids = json.loads(data.get("source_requirement_ids", "[]")) \
            if isinstance(data.get("source_requirement_ids"), str) \
            else data.get("source_requirement_ids", [])
        metadata = json.loads(data.get("metadata", "{}")) \
            if isinstance(data.get("metadata"), str) \
            else data.get("metadata", {})

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            id=data["id"],
            title=data["title"],
            diagram_type=data.get("diagram_type", MermaidDiagramType.FLOWCHART),
            content=data.get("content", ""),
            source_idea_id=data.get("source_idea_id"),
            source_shuttle_id=data.get("source_shuttle_id"),
            source_requirement_ids=requirement_ids,
            created_at=created_at,
            updated_at=updated_at,
            version=data.get("version", 1),
            metadata=metadata,
        )

    def to_markdown(self) -> str:
        """Return the diagram wrapped in markdown code block."""
        return f"```mermaid\n{self.content}\n```"


# Schedule status enum values
class ScheduleStatus:
    """Status values for scheduled tasks."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class TriggerType:
    """Trigger types for scheduled tasks."""
    DATE = "date"          # One-shot at specific datetime
    CRON = "cron"          # Recurring cron expression
    INTERVAL = "interval"  # Recurring interval


class ExecutionMode:
    """Execution modes for scheduled tasks."""
    SIMPLE = "simple"    # APScheduler → IntentOrchestrator.process_intent_sync()
    COMPLEX = "complex"  # APScheduler → Minibook start_collaboration()


@dataclass
class ScheduledTask:
    """
    A scheduled task managed by APScheduler.

    Persisted in SQLite so tasks survive restarts.
    APScheduler reloads active tasks from DB on startup.

    Execution modes:
      - simple: Direct execution via IntentOrchestrator (reminders, single-space tasks)
      - complex: Multi-space execution via Minibook collaboration
    """
    id: str
    title: str
    action_text: str                                        # Natural language intent to execute
    trigger_type: str = TriggerType.DATE                    # date, cron, interval
    trigger_config: Dict[str, Any] = field(default_factory=dict)  # APScheduler trigger kwargs
    execution_mode: str = ExecutionMode.SIMPLE               # simple or complex
    timezone: str = "Europe/Berlin"
    status: str = ScheduleStatus.ACTIVE
    description: str = ""
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    run_count: int = 0
    max_runs: Optional[int] = None                          # None = unlimited for recurring
    last_result: Optional[str] = None
    last_error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)  # original_user_text, parsed_time_expr

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "action_text": self.action_text,
            "execution_mode": self.execution_mode,
            "trigger_type": self.trigger_type,
            "trigger_config": json.dumps(self.trigger_config),
            "timezone": self.timezone,
            "status": self.status,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "run_count": self.run_count,
            "max_runs": self.max_runs,
            "last_result": self.last_result,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": json.dumps(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledTask":
        """Create ScheduledTask from database row."""
        trigger_config = json.loads(data.get("trigger_config", "{}")) \
            if isinstance(data.get("trigger_config"), str) else data.get("trigger_config", {})
        metadata = json.loads(data.get("metadata", "{}")) \
            if isinstance(data.get("metadata"), str) else data.get("metadata", {})

        def parse_dt(value):
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            return value

        return cls(
            id=data["id"],
            title=data["title"],
            action_text=data.get("action_text", ""),
            trigger_type=data.get("trigger_type", TriggerType.DATE),
            trigger_config=trigger_config,
            execution_mode=data.get("execution_mode", ExecutionMode.SIMPLE),
            timezone=data.get("timezone", "Europe/Berlin"),
            status=data.get("status", ScheduleStatus.ACTIVE),
            description=data.get("description", ""),
            next_run_at=parse_dt(data.get("next_run_at")),
            last_run_at=parse_dt(data.get("last_run_at")),
            run_count=data.get("run_count", 0),
            max_runs=data.get("max_runs"),
            last_result=data.get("last_result"),
            last_error=data.get("last_error"),
            created_at=parse_dt(data.get("created_at")) or datetime.now(),
            updated_at=parse_dt(data.get("updated_at")),
            metadata=metadata,
        )


# --- Flowzen (Blaue Rose) --- Passive Circadian Intelligence Layer --------


@dataclass
class FlowzenCheckin:
    """
    A mood/energy state inferred by the Flowzen activity tracker.

    Mood values: 'energized', 'focused', 'calm', 'tired', 'anxious'
    Time windows: 'early_morning', 'morning', 'midday', 'afternoon', 'evening', 'night'
    """
    id: str
    mood: str
    energy: int                                            # 1-10 (inferred)
    time_window: str = ""
    hour: int = 0
    source: str = "inferred"                               # 'inferred' or 'explicit'
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mood": self.mood,
            "energy": self.energy,
            "time_window": self.time_window,
            "hour": self.hour,
            "source": self.source,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowzenCheckin":
        def parse_dt(v):
            return datetime.fromisoformat(v) if isinstance(v, str) else v

        return cls(
            id=data["id"],
            mood=data["mood"],
            energy=data.get("energy", 5),
            time_window=data.get("time_window", ""),
            hour=data.get("hour", 0),
            source=data.get("source", "inferred"),
            notes=data.get("notes", ""),
            created_at=parse_dt(data.get("created_at")) or datetime.now(),
        )


@dataclass
class FlowzenActivity:
    """
    A logged intent event observed by the Blaue Rose activity tracker.

    Used to detect inactivity gaps and infer mood from usage patterns.
    """
    id: str
    event_type: str                                        # e.g. "idea.create"
    time_window: str = ""
    hour: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "time_window": self.time_window,
            "hour": self.hour,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowzenActivity":
        def parse_dt(v):
            return datetime.fromisoformat(v) if isinstance(v, str) else v

        return cls(
            id=data["id"],
            event_type=data.get("event_type", ""),
            time_window=data.get("time_window", ""),
            hour=data.get("hour", 0),
            created_at=parse_dt(data.get("created_at")) or datetime.now(),
        )


@dataclass
class FlowzenDiaryEntry:
    """A warm, personal diary entry generated every 30 minutes by the Blaue Rose."""
    id: str
    entry_text: str
    mood: str = "calm"
    energy: int = 5
    time_window: str = ""
    hour: int = 0
    intent_count: int = 0
    category: str = ""
    brain_action: str = ""
    brain_reasoning: str = ""
    raw_data: str = "{}"           # JSON string of full summary
    source: str = "periodic"       # "periodic" or "manual"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "entry_text": self.entry_text,
            "mood": self.mood, "energy": self.energy,
            "time_window": self.time_window, "hour": self.hour,
            "intent_count": self.intent_count, "category": self.category,
            "brain_action": self.brain_action, "brain_reasoning": self.brain_reasoning,
            "raw_data": self.raw_data, "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowzenDiaryEntry":
        def parse_dt(v):
            return datetime.fromisoformat(v) if isinstance(v, str) else v
        return cls(
            id=data["id"], entry_text=data.get("entry_text", ""),
            mood=data.get("mood", "calm"), energy=data.get("energy", 5),
            time_window=data.get("time_window", ""), hour=data.get("hour", 0),
            intent_count=data.get("intent_count", 0), category=data.get("category", ""),
            brain_action=data.get("brain_action", ""), brain_reasoning=data.get("brain_reasoning", ""),
            raw_data=data.get("raw_data", "{}"), source=data.get("source", "periodic"),
            created_at=parse_dt(data.get("created_at")) or datetime.now(),
        )
