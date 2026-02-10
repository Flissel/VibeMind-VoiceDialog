"""
ProjectSpec - Full project specification generated from bubble/idea transformation.

Contains:
- Source idea reference
- Scoring dimensions (from Idea or computed)
- LLM-extracted requirements (functional, non-functional, user stories)
- Tech stack recommendation with reasoning
- Metadata for tracking
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
import json


@dataclass
class UserStory:
    """User story in As-a/I-want/So-that format."""
    role: str
    action: str
    benefit: str
    priority: str = "medium"  # low, medium, high, critical

    def to_dict(self) -> Dict[str, str]:
        return {
            "role": self.role,
            "action": self.action,
            "benefit": self.benefit,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "UserStory":
        return cls(
            role=data.get("role", "User"),
            action=data.get("action", ""),
            benefit=data.get("benefit", ""),
            priority=data.get("priority", "medium"),
        )

    def __str__(self) -> str:
        return f"Als {self.role} moechte ich {self.action}, damit {self.benefit}"


@dataclass
class ProjectSpec:
    """
    Full project specification generated from bubble/idea transformation.

    This dataclass captures all information needed to create an enriched
    Project from an Idea/Bubble, including LLM-extracted requirements
    and tech stack recommendations.
    """

    # Source reference
    source_idea_id: str
    source_bubble_id: Optional[str] = None

    # Basic info (from Idea)
    title: str = ""
    description: str = ""

    # Scoring dimensions (from Idea or newly computed, 0-10 scale)
    feasibility: float = 0.0
    impact: float = 0.0
    novelty: float = 0.0
    urgency: float = 0.0
    composite_score: float = 0.0  # 0-100 calculated score

    # Requirements (LLM-extracted)
    functional_requirements: List[str] = field(default_factory=list)
    non_functional_requirements: List[str] = field(default_factory=list)
    user_stories: List[UserStory] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)

    # Tech stack recommendation
    recommended_tech_stack: str = "react"  # Default fallback
    tech_stack_reasoning: str = ""
    alternative_stacks: List[str] = field(default_factory=list)

    # Dependencies and integrations
    external_dependencies: List[str] = field(default_factory=list)
    integrations: List[str] = field(default_factory=list)

    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)
    generation_model: str = ""  # Which LLM was used
    confidence_score: float = 0.0  # 0.0-1.0 overall confidence
    transform_mode: str = "full"  # "quick", "full", "shuttle"

    # Shuttle integration (optional)
    shuttle_id: Optional[str] = None
    shuttle_stage_results: Dict[str, Any] = field(default_factory=dict)

    def calculate_composite_score(self) -> float:
        """Calculate composite score from dimensions (0-100)."""
        if all(d == 0.0 for d in [self.feasibility, self.impact, self.novelty, self.urgency]):
            return 0.0

        # Weighted formula: Impact 35%, Feasibility 30%, Novelty 20%, Urgency 15%
        score = (
            self.impact * 3.5 +
            self.feasibility * 3.0 +
            self.novelty * 2.0 +
            self.urgency * 1.5
        )
        return min(100.0, max(0.0, score))

    def requirements_count(self) -> int:
        """Total number of requirements."""
        return (
            len(self.functional_requirements) +
            len(self.non_functional_requirements) +
            len(self.acceptance_criteria)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            # Source
            "source_idea_id": self.source_idea_id,
            "source_bubble_id": self.source_bubble_id,
            # Basic
            "title": self.title,
            "description": self.description,
            # Scoring
            "feasibility": self.feasibility,
            "impact": self.impact,
            "novelty": self.novelty,
            "urgency": self.urgency,
            "composite_score": self.composite_score or self.calculate_composite_score(),
            # Requirements
            "functional_requirements": self.functional_requirements,
            "non_functional_requirements": self.non_functional_requirements,
            "user_stories": [us.to_dict() for us in self.user_stories],
            "acceptance_criteria": self.acceptance_criteria,
            # Tech stack
            "recommended_tech_stack": self.recommended_tech_stack,
            "tech_stack_reasoning": self.tech_stack_reasoning,
            "alternative_stacks": self.alternative_stacks,
            # Dependencies
            "external_dependencies": self.external_dependencies,
            "integrations": self.integrations,
            # Metadata
            "generated_at": self.generated_at.isoformat(),
            "generation_model": self.generation_model,
            "confidence_score": self.confidence_score,
            "transform_mode": self.transform_mode,
            # Shuttle
            "shuttle_id": self.shuttle_id,
            "shuttle_stage_results": self.shuttle_stage_results,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectSpec":
        """Create from dictionary."""
        user_stories = [
            UserStory.from_dict(us) if isinstance(us, dict) else us
            for us in data.get("user_stories", [])
        ]

        generated_at = data.get("generated_at")
        if isinstance(generated_at, str):
            try:
                generated_at = datetime.fromisoformat(generated_at)
            except ValueError:
                generated_at = datetime.now()
        elif generated_at is None:
            generated_at = datetime.now()

        return cls(
            source_idea_id=data.get("source_idea_id", ""),
            source_bubble_id=data.get("source_bubble_id"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            feasibility=data.get("feasibility", 0.0),
            impact=data.get("impact", 0.0),
            novelty=data.get("novelty", 0.0),
            urgency=data.get("urgency", 0.0),
            composite_score=data.get("composite_score", 0.0),
            functional_requirements=data.get("functional_requirements", []),
            non_functional_requirements=data.get("non_functional_requirements", []),
            user_stories=user_stories,
            acceptance_criteria=data.get("acceptance_criteria", []),
            recommended_tech_stack=data.get("recommended_tech_stack", "react"),
            tech_stack_reasoning=data.get("tech_stack_reasoning", ""),
            alternative_stacks=data.get("alternative_stacks", []),
            external_dependencies=data.get("external_dependencies", []),
            integrations=data.get("integrations", []),
            generated_at=generated_at,
            generation_model=data.get("generation_model", ""),
            confidence_score=data.get("confidence_score", 0.0),
            transform_mode=data.get("transform_mode", "full"),
            shuttle_id=data.get("shuttle_id"),
            shuttle_stage_results=data.get("shuttle_stage_results", {}),
        )

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ProjectSpec":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_requirements_json(self) -> str:
        """
        Generate requirements_json for Project model.
        This is the format expected by the CodingEngine.
        """
        return json.dumps({
            "title": self.title,
            "description": self.description,
            "tech_stack": self.recommended_tech_stack,
            "functional_requirements": self.functional_requirements,
            "non_functional_requirements": self.non_functional_requirements,
            "user_stories": [us.to_dict() for us in self.user_stories],
            "acceptance_criteria": self.acceptance_criteria,
            "dependencies": self.external_dependencies,
            "integrations": self.integrations,
        }, indent=2, ensure_ascii=False)

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"# ProjectSpec: {self.title}",
            f"",
            f"**Quelle:** Idea {self.source_idea_id}",
            f"**Tech Stack:** {self.recommended_tech_stack}",
            f"**Score:** {self.composite_score:.1f}/100",
            f"",
            f"## Requirements ({self.requirements_count()} gesamt)",
            f"- Funktional: {len(self.functional_requirements)}",
            f"- Nicht-funktional: {len(self.non_functional_requirements)}",
            f"- User Stories: {len(self.user_stories)}",
            f"- Akzeptanzkriterien: {len(self.acceptance_criteria)}",
        ]

        if self.functional_requirements:
            lines.append(f"")
            lines.append(f"## Funktionale Requirements")
            for req in self.functional_requirements[:5]:
                lines.append(f"- {req}")
            if len(self.functional_requirements) > 5:
                lines.append(f"- ... und {len(self.functional_requirements) - 5} weitere")

        if self.tech_stack_reasoning:
            lines.append(f"")
            lines.append(f"## Tech Stack Begruendung")
            lines.append(self.tech_stack_reasoning)

        return "\n".join(lines)

    def __str__(self) -> str:
        return f"ProjectSpec(title={self.title!r}, reqs={self.requirements_count()}, stack={self.recommended_tech_stack})"


__all__ = ["ProjectSpec", "UserStory"]
