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
    Each idea can have its own ElevenLabs agent for voice interaction.
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

    # ElevenLabs agent ID for this bubble/idea (for multi-agent architecture)
    agent_id: Optional[str] = None

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
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Idea":
        """Create Idea from database row"""
        tags = json.loads(data.get("tags", "[]")) if isinstance(data.get("tags"), str) else data.get("tags", [])
        metadata = json.loads(data.get("metadata", "{}")) if isinstance(data.get("metadata"), str) else data.get("metadata", {})

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
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasNode":
        """Create CanvasNode from database row"""
        metadata = json.loads(data.get("metadata", "{}")) if isinstance(data.get("metadata"), str) else data.get("metadata", {})

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
